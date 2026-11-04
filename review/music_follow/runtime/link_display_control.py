"""Manual display control, one bounded transaction, no automatic retry."""
from __future__ import annotations
import hashlib,hmac,http.client,json,secrets,threading,time,re
from pathlib import Path
from urllib.request import HTTPPasswordMgrWithDefaultRealm,Request,HTTPDigestAuthHandler
from shino_digest_coord import digest_exchange
from shino_b5_get_diagnostic import Deadline,check_challenge
from push_fsless_metrics import validate_host,read_credentials
from link_display_modes import DisplayMode

STATUS='/api/v1/display/status';MODE='/api/v1/display/mode'
SUPPORTED=(DisplayMode.AUTO,DisplayMode.CLOCK_WEATHER,DisplayMode.MONITORING)
BUILD='2e782e5af08ef4c65aed8b6011b06d4b7cc175eadab6e44c43d1bdadc8e7e316'
def command_budget(engine):
 """Use only idle time before the existing telemetry deadline; never defer it."""
 if engine.state!='CONNECTED' or engine.last_success is None:return 0.0
 now=engine.clock()
 if not 0<=now-engine.last_success<2:return 0.0
 remaining=min(1.5,engine.next_due-now-.1)
 return remaining if remaining>=.25 else 0.0

class ControlDeadline(Deadline):
 def __init__(self,clock,timer_factory,seconds):
  self.clock=clock;self.until=clock()+seconds;self.expired=threading.Event();self.sockets=[]
  self.timer=timer_factory(seconds,self.abort);self.timer.daemon=True;self.timer.start()
def unique(pairs):
 out={}
 for k,v in pairs:
  if k in out:raise ValueError('duplicate field')
  out[k]=v
 return out
def hexstr(v,n):return type(v) is str and re.fullmatch('[0-9a-f]{'+str(n)+'}',v) is not None
def validate_status(s):
 if type(s) is not dict or set(s)!={'protocol','device','build','boot','revision','mode'}:raise ValueError('schema')
 if type(s['protocol']) is not int or s['protocol']!=1 or not hexstr(s['device'],16) or not hexstr(s['build'],64) or not hexstr(s['boot'],32):raise ValueError('identity')
 if type(s['revision']) is not int or not 0<=s['revision']<0xffffffff or type(s['mode']) is not int or s['mode'] not in range(3):raise ValueError('state')
 return s
def tag(password,s,cmd,revision=None):
 domain='SHINO-DISPLAY-REQ-1\nPOST\n'+MODE+'\n' if revision is None else 'SHINO-DISPLAY-ACK-1\n'
 message=domain+s['device']+'\n'+s['build']+'\n'+s['boot']+'\n'+cmd+'\n'
 if revision is not None:message+=f'{revision:08x}\n'
 return hmac.new(password.encode('utf-8'),message.encode('ascii'),hashlib.sha256).hexdigest()
def verified_ack(s,cmd,mode,ack,password):
 if type(ack) is not dict or set(ack)!={'protocol','mode','revision','command','proof'}:raise ValueError('ACK schema')
 if type(ack['protocol']) is not int or ack['protocol']!=1 or type(ack['mode']) is not int or ack['mode']!=mode or type(ack['revision']) is not int or ack['revision']!=s['revision']+1 or ack['command']!=cmd or not hexstr(ack['proof'],64):raise ValueError('ACK binding')
 if not hmac.compare_digest(ack['proof'],tag(password,s,cmd,ack['revision'])):raise ValueError('ACK authentication')
 return ack

class Transport:
 """Real shared lock, Digest GET (401+200), exactly one zero-body HMAC POST.

 One timer (maximum 1.5 seconds) bounds all sockets, headers and response.
 No redirect, proxy, DNS scan, urllib retry or post-error status read.
 """
 def __init__(self,host,user,password,*,expected_device,expected_build=BUILD,
              connection_factory=http.client.HTTPConnection,coordinator=digest_exchange,
              clock=time.monotonic,timer_factory=threading.Timer,guard=lambda:True,expected_boot=None):
  self.host=validate_host(host);self.user=user;self.password=password
  if not hexstr(expected_device,16) or not hexstr(expected_build,64):raise ValueError('local identity')
  self.device,self.build=expected_device,expected_build
  if expected_boot is not None and not hexstr(expected_boot,32):raise ValueError('local boot')
  self.boot=expected_boot
  self.factory,self.coordinator,self.clock,self.timer_factory,self.guard=connection_factory,coordinator,clock,timer_factory,guard
  self.gets=self.posts=0
 def execute(self,mode,*,budget_seconds=1.5):
  if type(mode) is not DisplayMode or mode not in SUPPORTED:return {'state':'HOLD','reason':'MODE_UNAVAILABLE'}
  return self._exchange(mode,budget_seconds)
 def probe(self,*,budget_seconds=1.5):
  return self._exchange(None,budget_seconds)
 def _exchange(self,mode,budget_seconds):
  if type(budget_seconds) not in (float,int) or not .25<=budget_seconds<=1.5:return {'state':'HOLD','reason':'TELEMETRY_PRIORITY'}
  deadline=ControlDeadline(self.clock,self.timer_factory,budget_seconds)
  phase='LOCAL_GUARD'
  try:
   if not self.guard():return {'state':'HOLD','reason':'OTA_COORDINATION_HOLD'}
   with self.coordinator(self.host,wait_seconds=0):
    deadline.check()
    def request(method,path,headers):
     deadline.check();peer=self.factory(self.host,80,timeout=deadline.timeout())
     try:
      peer.connect();deadline.register(peer.sock)
      if method=='POST':self.posts+=1
      else:self.gets+=1
      peer.request(method,path,body=b'' if method=='POST' else None,headers={'Host':self.host,'Connection':'close','Accept':'application/json',**headers})
      response=peer.getresponse();deadline.check()
      raw=response.read(769);deadline.check()
      # The real Core sends chunked JSON. http.client decodes it under the
      # same absolute timer and read cap; ambiguous framing remains forbidden.
      transfer=response.getheader('Transfer-Encoding')
      lengths=response.headers.get_all('Content-Length',[])
      if len(raw)>768 or transfer not in (None,'chunked') or len(lengths)>1 or transfer and lengths:raise ValueError('response bound')
      return response.status,response.headers,raw
     finally:peer.close()
    phase='CHALLENGE';code,headers,raw=request('GET',STATUS,{})
    if code!=401:raise ValueError('Digest challenge required')
    challenge=check_challenge(headers)
    manager=HTTPPasswordMgrWithDefaultRealm();base='http://'+self.host
    manager.add_password('SHINO-StageA',base,self.user,self.password)
    auth=HTTPDigestAuthHandler(manager).get_authorization(Request(base+STATUS),challenge)
    if not auth:raise ValueError('Digest authorization')
    phase='STATUS';code,_,raw=request('GET',STATUS,{'Authorization':'Digest '+auth})
    if code!=200:raise ValueError('status refused')
    s=validate_status(json.loads(raw,object_pairs_hook=unique))
    if s['device']!=self.device or s['build']!=self.build:raise ValueError('unsupported firmware')
    if self.boot is not None and s['boot']!=self.boot:raise ValueError('different boot')
    if mode is None:return {'state':'CAPABLE','status':s}
    cmd=f'01{SUPPORTED.index(mode):02x}{s["revision"]:08x}'+secrets.token_hex(16)
    if not self.guard():raise ValueError('OTA coordination')
    phase='COMMAND';code,_,raw=request('POST',MODE,{'Content-Length':'0','X-Shino-Nonce':cmd,'X-Shino-Proof':tag(self.password,s,cmd)})
    if code!=200:raise ValueError('command refused')
    ack=verified_ack(s,cmd,SUPPORTED.index(mode),json.loads(raw,object_pairs_hook=unique),self.password)
    return {'state':'APPLIED','mode':mode.value,'revision':ack['revision'],'checked':time.time()}
  except Exception as error:
   kind='TIMEOUT' if isinstance(error,TimeoutError) else 'VALIDATION' if isinstance(error,ValueError) else 'TRANSPORT'
   return {'state':'UNKNOWN' if self.posts else 'HOLD','reason':'NO_AUTHENTICATED_ACK' if self.posts else 'PREFLIGHT_REFUSED','phase':phase,'kind':kind}
  finally:deadline.close()

class ManualController:
 """One manual slot executed by the existing telemetry worker's observe hook."""
 def __init__(self,apply):
  self.apply=apply;self.lock=threading.Lock();self.pending=None;self.busy=False
  self.selected=DisplayMode.AUTO;self.result={'state':'UNVERIFIED'};self.last_ack=None
 def choose(self,mode):
  if type(mode) is not DisplayMode or mode not in SUPPORTED:return False
  with self.lock:
   if self.busy or self.pending is not None:return False
   self.selected=mode;self.pending=mode;self.result={'state':'QUEUED'};return True
 def mode(self):
  with self.lock:return self.selected
 def drain(self,*_):
  with self.lock:
   if self.busy or self.pending is None:return
   mode=self.pending;self.pending=None;self.busy=True;self.result={'state':'SENDING'}
  try:result=self.apply(mode)
  except Exception:result={'state':'UNKNOWN','reason':'COMMAND_INTERRUPTED'}
  with self.lock:
   self.busy=False
   self.result=result if type(result) is dict and result.get('state') in ('APPLIED','HOLD','UNKNOWN') else {'state':'UNKNOWN'}
   if self.result['state']=='APPLIED':self.last_ack=dict(self.result)
 def label(self):
  with self.lock:
   state=self.result['state']
   if state=='APPLIED':return 'Mode acquitté : '+self.result['mode']+' (dernière commande)'
   return {'UNVERIFIED':'Mode SmallTV : non vérifié','QUEUED':'Mode : commande en attente','SENDING':'Mode : acquittement attendu','HOLD':'Mode : indisponible / HOLD','UNKNOWN':'Mode : résultat inconnu — aucun retry'}.get(state,'Mode : non vérifié')

def from_config(host,config,directory):
 """No embedded owner identity: require an exact local BIN/manifest descriptor."""
 from shino_update import inspect
 from link_v2_ota_guard import command_allowed
 if not command_allowed(directory):raise ValueError('Display endpoint not installed / HOLD')
 path=Path(directory)/'display-control.json'
 if not path.is_file() or path.is_symlink() or path.stat().st_size>4096:raise ValueError('local binding required')
 data=json.loads(path.read_text(),object_pairs_hook=unique)
 if type(data) is not dict or set(data)!={'schema','bin','manifest'} or type(data['schema']) is not int or data['schema']!=1:raise ValueError('local binding')
 if any(type(data[k]) is not str or not Path(data[k]).is_absolute() for k in ('bin','manifest')):raise ValueError('local paths')
 release,_=inspect(Path(data['bin']),Path(data['manifest']))
 if release['build_id']!=BUILD:raise ValueError('unsupported control firmware')
 user,password=read_credentials(Path(config['credentials_file']))
 return Transport(host,user,password,expected_device=release['device'],guard=lambda:command_allowed(directory))
