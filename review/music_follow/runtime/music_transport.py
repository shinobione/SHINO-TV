"""Bounded production media transport. One request exchange, never a retry."""
import http.client,json,secrets,time,threading,hmac
from collections import deque
from datetime import datetime,timezone
from pathlib import Path
from contextlib import contextmanager
from urllib.request import HTTPDigestAuthHandler,HTTPPasswordMgrWithDefaultRealm,Request
from media_music import PATH,STATUS,envelope,tag,verified_ack
from link_display_control import ControlDeadline,unique,hexstr
from shino_b5_get_diagnostic import check_challenge,DiagnosticStop
from shino_digest_coord import digest_exchange,CoordinationBusy
from push_fsless_metrics import validate_host

NOT_SENT_PROVED='NOT_SENT_PROVED'
SEND_OUTCOME_UNKNOWN='SEND_OUTCOME_UNKNOWN'
ACK_VALIDATED='ACK_VALIDATED'
OPCODES={1:'BEGIN',2:'TILE',3:'COMMIT',4:'UPDATE',5:'QUIESCE'}
PHASES=frozenset(('LOCAL_VALIDATION','LEASE','COORDINATOR','GUARD','REQUEST',
 'CONNECT','EMIT','RESPONSE','READ_BODY','FRAMING','ACK','POST_ACK_GUARD','COMPLETE','STOPPED'))
EXCEPTION_CLASSES=frozenset(('Exception','CoordinationBusy','ValueError','TypeError','OSError',
 'TimeoutError','RuntimeError','ConnectionError','ConnectionResetError','ConnectionRefusedError',
 'BrokenPipeError','HTTPException','RemoteDisconnected','IncompleteRead','JSONDecodeError',
 'UnicodeDecodeError','UnicodeEncodeError','PermissionError','FileNotFoundError','FileExistsError',
 'DiagnosticStop','AdmissionHold','HistoryHold','LinkError','SenderError','OverflowError','AssertionError'))
EVENTS=frozenset(('COMMAND','SESSION_ACQUIRED','SESSION_LOST','SESSION_UNAVAILABLE',
 'SESSION_RESTORED','SESSION_STATE','TRACK_CHANGED','GSMTC_EVENT','COLLECTOR_START',
 'COLLECTOR_STOP','COLLECTOR_EXCEPTION','SERVICE_START','SERVICE_STOP','SERVICE_EXCEPTION',
 'MUSIC_STATE','DASHBOARD_DECISION','ADMISSION_START','ADMISSION_READ','ADMISSION_HOLD',
 'SESSIONS_CHANGED','CURRENT_SESSION_CHANGED','MEDIA_PROPERTIES_CHANGED','PLAYBACK_INFO_CHANGED','COLLECTOR_STOP_REQUESTED',
 'POST_ACK_BUDGET_EXHAUSTED'))
STATES=frozenset(('PLAYING','PAUSED','NO_SESSION','STOPPED','CLOSED','UNAVAILABLE','CHANGING',
 'WAITING','ACTIVE','PENDING_ARTWORK','CONFIRMING_END','TRANSITION','IDLE',
 'LOCAL_EXPIRED_NOT_SENT','SOURCE_EXPIRED_NOT_SENT','LOCAL_DEFERRED','LOCAL_HOLD','HOLD'))
TRACE_PHASES=PHASES|frozenset(('CAPTURE','GSMTC_MANAGER','GSMTC_BIND','COLLECTOR_RUNNER','PUMP','START','CLOSE','IDENTITY_DISPLAY','RELEASE','MEDIA_STATUS','READY','CALLBACK'))
DECISIONS=frozenset(('CONFIRMED_NO_SESSION','WAIT_NATIVE_LEASE','NO_RETRY_WAIT_NATIVE_LEASE'))

def trace_event(trace,event,**fields):
 if trace is not None:
  try:trace.event(event,**fields)
  except Exception:pass # Diagnostics never alter admission, commands or metrics.

def exception_class(error):
 # Never persist str(error), custom class names, paths or third-party messages.
 name=type(error).__name__
 return name if name in EXCEPTION_CLASSES else 'Exception'

class MediaSendError(Exception):
 """Transport-owned evidence; posts==0 is never used to infer non-emission."""
 def __init__(self,classification,phase,kind,*,retryable=False):
  self.classification=classification;self.phase=phase;self.exception_class=kind;self.retryable=retryable
  super().__init__(classification+'_'+phase+'_'+kind)

class MusicTrace:
 """Opt-in exclusive new run file, containing only its latest 64 safe events."""
 def __init__(self,path):
  path=Path(path)
  if path.is_symlink():raise ValueError('trace destination rejected')
  self.stream=path.open('x',encoding='utf-8');self.count=0;self.disabled=False;self.lock=threading.Lock();self.rows=deque(maxlen=64)
 def record(self,*,opcode,phase,exception_class,http_status,classification):
  self._record('COMMAND',opcode=opcode,phase=phase,exception_class=exception_class,http_status=http_status,classification=classification)
 def event(self,event,*,phase=None,error=None,from_state=None,to_state=None,decision=None):
  self._record(event,phase=phase,exception_class=exception_class(error) if error is not None else None,
   from_state=from_state,to_state=to_state,decision=decision)
 def _record(self,event,*,opcode=None,phase=None,exception_class=None,http_status=None,classification=None,from_state=None,to_state=None,decision=None):
  with self.lock:
   if self.disabled:return
   row=dict(timestamp=datetime.now(timezone.utc).isoformat(timespec='milliseconds'),
    event=event if event in EVENTS else 'SERVICE_EXCEPTION',
    opcode=OPCODES.get(opcode),phase=phase if phase in TRACE_PHASES else None,
    exception_class=exception_class if exception_class in EXCEPTION_CLASSES else None if exception_class is None else 'Exception',
    http_status=http_status if type(http_status) is int and 100<=http_status<=599 else None,
    classification=classification if classification in (NOT_SENT_PROVED,SEND_OUTCOME_UNKNOWN,ACK_VALIDATED) else None,
    from_state=from_state if from_state in STATES else None,to_state=to_state if to_state in STATES else None,
    decision=decision if decision in DECISIONS else None)
   self.rows.append(row)
   # Only the fresh file exclusively created for THIS run is updated. Old trace,
   # receipt and marker paths are never opened for replacement or truncation.
   try:
    self.stream.seek(0);self.stream.write(''.join(json.dumps(r,separators=(',',':'))+'\n' for r in self.rows))
    self.stream.truncate();self.stream.flush();self.count+=1
   except Exception:self.disabled=True
 def close(self):
  with self.lock:
   self.disabled=True
   try:self.stream.close()
   except Exception:pass

@contextmanager
def production_lease(directory,host):
 from link_identity_admission import read_lease
 from link_installed_control import InstalledEvidence
 # Reuse actual historical reservation validation and both OTA leases. Nothing
 # is removed, rewritten or interpreted as authority for another OTA.
 with read_lease(directory,host,evidence_type=InstalledEvidence) as evidence:
  guard=evidence.command_guard();guard();yield guard;guard()

class Transport:
 def __init__(self,host,user,password,*,identity,lease,connection_factory=http.client.HTTPConnection,coordinator=digest_exchange,trace=None):
  self.host=validate_host(host);self.user=user;self.password=password;self.identity=identity
  if not all(hexstr(identity[k],n) for k,n in [('device',16),('build',64),('boot',32)]):raise ValueError('identity')
  self.lease=lease;self.factory=connection_factory;self.coordinator=coordinator;self.sequence=None;self.failed=False;self.posts=0;self.gets=0
  self.trace=trace;self.last_result=None;self._send_attempt=None
  self.budget_exhausted=False;self.ack_validated_at=None
 def _stage(self,phase,http_status=None):
  if self._send_attempt is not None:
   self._send_attempt['phase']=phase
   if type(http_status) is int and 100<=http_status<=599:self._send_attempt['http_status']=http_status
 def _request(self,method,path,headers,body,deadline):
  self._stage('CONNECT');deadline.check();peer=self.factory(self.host,80,timeout=deadline.timeout())
  try:
   peer.connect();deadline.register(peer.sock)
   if method=='POST':self.posts+=1
   else:self.gets+=1
   self._stage('EMIT')
   peer.request(method,path,body=body,headers={'Host':self.host,'Connection':'close','Accept':'application/json',**headers})
   self._stage('RESPONSE');response=peer.getresponse();self._stage('READ_BODY',response.status)
   raw=response.read(769);deadline.check();self._stage('FRAMING')
   transfer=response.getheader('Transfer-Encoding');lengths=response.headers.get_all('Content-Length',[])
   if len(raw)>768 or transfer not in (None,'chunked') or len(lengths)>1 or transfer and lengths:raise ValueError('response framing')
   return response.status,response.headers,raw
  finally:peer.close()
 def status(self):
  if self.failed:raise ValueError('stopped after ambiguity')
  deadline=ControlDeadline(time.monotonic,threading.Timer,1.5)
  try:
   with self.lease() as guard,self.coordinator(self.host,wait_seconds=0):
    guard();nonce=secrets.token_hex(16);headers={'X-Shino-Nonce':nonce}
    code,head,_=self._request('GET',STATUS,headers,None,deadline)
    if code!=401:raise ValueError('Digest challenge required')
    challenge=check_challenge(head);manager=HTTPPasswordMgrWithDefaultRealm();base='http://'+self.host
    manager.add_password('SHINO-StageA',base,self.user,self.password)
    auth=HTTPDigestAuthHandler(manager).get_authorization(Request(base+STATUS),challenge)
    if not auth:raise ValueError('Digest')
    code,_,raw=self._request('GET',STATUS,dict(headers,Authorization='Digest '+auth),None,deadline)
    s=json.loads(raw,object_pairs_hook=unique)
    if code!=200 or set(s)!={'protocol','device','build','boot','sequence','mode','format','proof'} or type(s['protocol']) is not int or s['protocol']!=1 or any(s[k]!=self.identity[k] for k in ('device','build','boot')) or type(s['mode']) is not int or s['mode'] not in range(3) or type(s['sequence']) is not int or not 0<=s['sequence']<0xffffffff or s['format']!='P8_64_RGB565LE':raise ValueError('media capability')
    result=f'{s["sequence"]:08x}{s["mode"]:02x}'
    if not hmac.compare_digest(s['proof'],tag(self.password,s,nonce,result,status=True)):raise ValueError('status proof')
    guard()
   deadline.check();self.sequence=s['sequence'];return s
  except Exception:self.failed=True;raise
  finally:deadline.close()
 def send(self,op,tx,offset=0,body=b'',*,budget_seconds=1.5):
  self.budget_exhausted=False;self.ack_validated_at=None
  attempt=dict(phase='LOCAL_VALIDATION',classification=NOT_SENT_PROVED,exception_class=None,http_status=None)
  self._send_attempt=attempt;deadline=None
  try:
   if self.failed:
    attempt.update(classification=SEND_OUTCOME_UNKNOWN,phase='STOPPED');raise ValueError('stopped after ambiguity')
   if type(budget_seconds) not in (float,int) or not .25<=budget_seconds<=1.5:raise ValueError('telemetry priority')
   if self.sequence is None:raise ValueError('not admitted')
   command=envelope(op,self.sequence,tx,offset,body)
   headers={'Content-Type':'application/octet-stream','Content-Length':str(len(body)),
    'X-Shino-Nonce':command,'X-Shino-Proof':tag(self.password,self.identity,command)}
   deadline=ControlDeadline(time.monotonic,threading.Timer,budget_seconds)
   self._stage('LEASE')
   with self.lease() as guard:
    self._stage('COORDINATOR')
    with self.coordinator(self.host,wait_seconds=0):
     self._stage('GUARD');guard();deadline.check()
     # Conservative boundary BEFORE invoking even an injected/overridden request,
     # its connection factory or connect(). Any failure from here stays UNKNOWN.
     attempt.update(classification=SEND_OUTCOME_UNKNOWN,phase='REQUEST')
     code,_,raw=self._request('POST',PATH,headers,body,deadline)
     self._stage('ACK',code)
     ack=verified_ack(self.password,self.identity,command,json.loads(raw,object_pairs_hook=unique))
     if code!=200 or not ack['accepted']:raise ValueError('media refused')
     # The authenticated accepted ACK itself must qualify BEFORE the deadline.
     # Retain that instant; later local proof IO must not renew a native lease.
     ack_stamp=time.monotonic();deadline.check();self.ack_validated_at=ack_stamp
     self._stage('POST_ACK_GUARD');guard()
   # Every post-ACK guard AND context exit above has succeeded. Only this final
   # scheduler check may report exhausted idle time, never a guard exception.
   try:deadline.check()
   except DiagnosticStop as error:
    if error.code!='TIMEOUT':raise
    self.budget_exhausted=True
    trace_event(self.trace,'POST_ACK_BUDGET_EXHAUSTED',phase='POST_ACK_GUARD')
   self.sequence=ack['sequence']
   attempt.update(classification=ACK_VALIDATED,phase='COMPLETE');return ack
  except Exception as error:
   kind=exception_class(error);attempt['exception_class']=kind
   unknown=attempt['classification']==SEND_OUTCOME_UNKNOWN
   if unknown:self.failed=True
   retryable=(not unknown and attempt['phase']=='COORDINATOR' and
    isinstance(error,CoordinationBusy) and error.code=='coordination_busy')
   raise MediaSendError(attempt['classification'],attempt['phase'],kind,retryable=retryable) from None
  finally:
   if deadline is not None:deadline.close()
   self.last_result=dict(attempt);self._send_attempt=None
   if self.trace is not None:
    try:self.trace.record(opcode=op,**attempt)
    except Exception:pass # Observability can never turn an ACK into a retry.
