"""One event-driven GSMTC collector; media uses the existing metrics idle slot."""
import asyncio,threading,time,secrets,hashlib
from media_sessions import capture,probe_manager,MediaCapture,MediaSnapshot,POLL_SECONDS
from media_wire_v1 import track_identity
from media_music import prepare,metadata,update
from link_display_control import command_budget
from music_transport import MediaSendError,NOT_SENT_PROVED,trace_event

CAPTURE_SECONDS=1.0  # Existing collector bound, unchanged.
MEDIA_LEASE_SECONDS=6.0  # Exact installed MusicMedia::State lease.
LOCAL_TRANSACTION_SECONDS=7.5  # Existing margin below firmware 8 seconds.
HEARTBEAT_SECONDS=2.0  # Existing normal PC metrics interval.

class Feed:
 """Callbacks only wake this single owner loop; they never send network data."""
 def __init__(self,*,manager_factory=probe_manager,capture_fn=capture,clock=time.monotonic,trace=None):
  self.lock=threading.Lock();self.latest=None;self.serial=0;self.stop=threading.Event();self.wake=threading.Event();self.thread=None
  self.factory=manager_factory;self.capture=capture_fn;self.bindings=[];self.events=0;self.clock=clock;self.observed_at=None
  self.trace=trace;self._source=None;self._track=None;self._state=None
 def publish(self,value):
  if self.trace is not None:
   try:self._trace_snapshot(value.snapshot)
   except Exception:pass # Diagnostics cannot discard a collected sample.
  with self.lock:self.latest=value;self.serial+=1;self.observed_at=self.clock()
 def _trace_snapshot(self,snapshot):
  state=snapshot.state;previous=self._state
  if state in ('PLAYING','PAUSED'):
   key=track_identity(snapshot) # Private comparison only; NEVER recorded.
   event='SESSION_ACQUIRED' if self._source is None or snapshot.source!=self._source else 'SESSION_RESTORED' if previous not in ('PLAYING','PAUSED') else 'TRACK_CHANGED' if key!=self._track else 'SESSION_STATE' if state!=previous else None
   self._source=snapshot.source;self._track=key
  else:event='SESSION_LOST' if state in ('NO_SESSION','STOPPED','CLOSED') else 'SESSION_UNAVAILABLE'
  if event is not None and (state in ('PLAYING','PAUSED') or state!=previous):trace_event(self.trace,event,phase='CAPTURE',from_state=previous,to_state=state)
  self._state=state
 def read(self):
  with self.lock:return self.serial,self.latest
 def observation(self):
  with self.lock:return self.serial,self.latest,self.observed_at
 def _event(self,kind=None,*_):
  event={'sessions_changed':'SESSIONS_CHANGED','current_session_changed':'CURRENT_SESSION_CHANGED',
   'media_properties_changed':'MEDIA_PROPERTIES_CHANGED','playback_info_changed':'PLAYBACK_INFO_CHANGED'}.get(kind,'GSMTC_EVENT')
  self.events+=1;trace_event(self.trace,event,phase='CALLBACK');self.wake.set()
 def _detach(self):
  for owner,name,token in reversed(self.bindings):
   try:getattr(owner,'remove_'+name)(token)
   except Exception:pass
  self.bindings=[]
 def _attach(self,manager):
  self._detach()
  owners=[(manager,('sessions_changed','current_session_changed'))]
  try:owners += [(s,('media_properties_changed','playback_info_changed')) for s in manager.get_sessions()]
  except Exception:pass
  for owner,names in owners:
   for name in names:
    try:self.bindings.append((owner,name,getattr(owner,'add_'+name)(lambda *args,_kind=name:self._event(_kind))))
    except (AttributeError,RuntimeError):pass
 def start(self):
  if self.thread:return
  trace_event(self.trace,'COLLECTOR_START',phase='START')
  def collect():
   manager=None
   try:
    with asyncio.Runner() as runner:
     while not self.stop.is_set():
      self.wake.clear()
      try:
       phase='GSMTC_MANAGER'
       if manager is None:manager=runner.run(asyncio.wait_for(self.factory(),CAPTURE_SECONDS))
       phase='GSMTC_BIND'
       self._attach(manager)
       phase='CAPTURE'
       value=runner.run(asyncio.wait_for(self.capture(manager,include_cover=True),CAPTURE_SECONDS))
      except Exception as error:
       trace_event(self.trace,'COLLECTOR_EXCEPTION',phase=phase,error=error)
       value=MediaCapture(MediaSnapshot(state='UNAVAILABLE'));self._detach();manager=None
      self.publish(value)
      if not self.stop.is_set():self.wake.wait(POLL_SECONDS) # Original fallback; events wake sooner.
   except Exception as error:
    trace_event(self.trace,'COLLECTOR_EXCEPTION',phase='COLLECTOR_RUNNER',error=error);raise
   finally:
    self._detach();trace_event(self.trace,'COLLECTOR_STOP',phase='CLOSE')
  self.thread=threading.Thread(target=collect,name='SHINO-GSMTC-collector',daemon=True);self.thread.start()
 def close(self):
  self.stop.set();self.wake.set()
  if self.thread and self.thread is not threading.current_thread():self.thread.join(timeout=1.25)
  trace_event(self.trace,'COLLECTOR_STOP_REQUESTED',phase='CLOSE')

class Service:
 def __init__(self,transport,feed,*,clock=time.monotonic):
  self.transport=transport;self.feed=feed;self.clock=clock;self.seen=0;self.sent_serial=0
  self.track=None;self.artwork=None;self.tx=secrets.token_bytes(16);self.queue=[];self.started=0
  self.active=False;self.pending=False;self.failed=False;self.quiet=False;self.lock=threading.Lock()
  self.latest=None;self.valid_at=None;self.absence_at=None;self.ended=False;self.last_ack=None
  self.target_serial=0;self.phase='WAITING';self.error=None;self.accepted=0
  self.deferred_slot=None
  self.trace=getattr(transport,'trace',None);self._dashboard_wait=False
  trace_event(self.trace,'SERVICE_START',phase='START',to_state=self.phase)
 def pump(self,engine):
  if not self.lock.acquire(False):return False
  before=self.phase
  try:return False if self.quiet else self._pump(engine)
  except Exception as error:
   trace_event(self.trace,'SERVICE_EXCEPTION',phase='PUMP',error=error);raise
  finally:
   if self.phase!=before:
    trace_event(self.trace,'MUSIC_STATE',phase='PUMP',from_state=before,to_state=self.phase)
    if self.phase in ('HOLD','LOCAL_HOLD'):
     trace_event(self.trace,'DASHBOARD_DECISION',phase='PUMP',decision='NO_RETRY_WAIT_NATIVE_LEASE')
    elif self.phase in ('LOCAL_EXPIRED_NOT_SENT','SOURCE_EXPIRED_NOT_SENT'):
     trace_event(self.trace,'DASHBOARD_DECISION',phase='PUMP',decision='WAIT_NATIVE_LEASE')
   self.lock.release()
 def _pump(self,engine):
  if self.failed or command_budget(engine)<.25:return False
  if self.deferred_slot is not None and engine.next_due==self.deferred_slot:return False
  self.deferred_slot=None
  now=self.clock();serial,captured,observed=self.feed.observation()
  if serial!=self.seen and captured is not None:
   self.seen=serial;s=captured.snapshot
   if s.state in ('PLAYING','PAUSED'):
    self.latest=captured;self.valid_at=observed;self.absence_at=None;self.ended=False
   elif s.state in ('NO_SESSION','STOPPED','CLOSED'):
    if self.absence_at is None:self.absence_at=observed
    elif observed-self.absence_at>=POLL_SECONDS:self.ended=True;self.latest=None
    self.phase='CONFIRMING_END'
   else:
    self.absence_at=None;self.phase='TRANSITION' # Unknown is not proof of playback ending.
  if not self.pending and self.last_ack is not None and now-self.last_ack>=MEDIA_LEASE_SECONDS:
   self.active=False;self.track=None # Receiver may have expired: next valid capture needs BEGIN.
  if not self.queue:
   fresh=self.latest is not None and self.valid_at is not None and 0<=now-self.valid_at<MEDIA_LEASE_SECONDS
   if fresh:self._dashboard_wait=False
   elif self.valid_at is not None and not self._dashboard_wait:
    self._dashboard_wait=True;trace_event(self.trace,'DASHBOARD_DECISION',phase='PUMP',decision='WAIT_NATIVE_LEASE')
   if self.ended:
    if self.active:
     trace_event(self.trace,'DASHBOARD_DECISION',phase='PUMP',decision='CONFIRMED_NO_SESSION')
     self.queue=[(5,self.tx,0,b'')]
   elif fresh:
    s=self.latest.snapshot;key=track_identity(s)
    art=hashlib.sha256(self.latest.preview_jpeg).digest() if self.latest.preview_jpeg else None
    if not self.active or key!=self.track or art is not None and art!=self.artwork:
     try:cover=prepare(self.latest.preview_jpeg)
     except (OSError,ValueError):cover=None
     self.tx=secrets.token_bytes(16);self.track=key;self.artwork=art;self.started=self.clock();self.target_serial=self.seen
     self.queue=[(1,self.tx,0,metadata(s,cover))]
     if cover:self.queue += [(2,self.tx,off,cover[off:off+512]) for off in range(0,4608,512)]+[(3,self.tx,0,b'')]
    elif not self.pending and (self.seen!=self.sent_serial or self.last_ack is None or now-self.last_ack>=HEARTBEAT_SECONDS):
     self.target_serial=self.seen;self.queue=[(4,self.tx,0,update(s))]
  if not self.queue:return False
  op,tx,offset,body=self.queue[0]
  if self.pending and self.valid_at is not None and now-self.valid_at>=MEDIA_LEASE_SECONDS:
   self.queue=[];self.track=None;self.active=False;self.pending=False;self.phase='SOURCE_EXPIRED_NOT_SENT';return False
  if op in (1,2,3) and self.clock()-self.started>=LOCAL_TRANSACTION_SECONDS:
   # All preceding packets were ACKed. No call to send for this expired packet.
   # Abandon locally; a later fresh BEGIN gets a new tx, never replays this tile.
   self.queue=[];self.track=None;self.active=False;self.pending=False;self.phase='LOCAL_EXPIRED_NOT_SENT';return False
  budget=command_budget(engine) # Preparation/proof work must not borrow the next metrics slot.
  if budget<.25:return False
  try:self.transport.send(op,tx,offset,body,budget_seconds=budget)
  except MediaSendError as error:
   if error.classification==NOT_SENT_PROVED:
    # Only lock contention before the request boundary is automatically deferred.
    # Prior queue entries were ACKed. This entry was never submitted; retain its
    # sequence/tx/offset and recheck source age / transaction expiry next slot.
    if error.retryable and error.phase=='COORDINATOR' and not self.transport.failed:
     self.deferred_slot=engine.next_due;self.phase='LOCAL_DEFERRED'
     self.error='NOT_SENT_PROVED_COORDINATOR_BUSY';return False
    self.failed=True;self.queue=[];self.phase='LOCAL_HOLD'
    self.error='NOT_SENT_PROVED_'+error.phase+'_'+error.exception_class;return False
   self.failed=True;self.queue=[];self.phase='HOLD'
   self.error='SEND_OUTCOME_UNKNOWN_'+error.phase+'_'+error.exception_class;return False
  except Exception as error:
   # After entering send(), never infer safety from posts==0 or reset sequence.
   trace_event(self.trace,'SERVICE_EXCEPTION',phase='REQUEST',error=error)
   self.failed=True;self.queue=[];self.phase='HOLD';self.error='SEND_AMBIGUOUS_'+type(error).__name__;return False
  self.queue.pop(0)
  stamp=getattr(self.transport,'ack_validated_at',None)
  self.last_ack=stamp if type(stamp) in (int,float) and 0<=stamp<=self.clock() else self.clock()
  self.accepted+=1;self.active=op!=5
  if op==1:self.pending=bool(body[-1])
  if op in (3,5):self.pending=False
  if op==5:self.track=None;self.latest=None
  if not self.pending:self.sent_serial=self.target_serial
  self.phase='PENDING_ARTWORK' if self.pending else 'ACTIVE' if self.active else 'IDLE'
  if getattr(self.transport,'budget_exhausted',False):
   self.deferred_slot=engine.next_due # No next frame, even on another pump().
   return False # Yield to the unchanged metrics worker, never replay this ACK.
  return True
 def quiesce(self):
  if not self.lock.acquire(False):raise ValueError('media busy: OTA not admissible')
  try:
   trace_event(self.trace,'SERVICE_STOP',phase='CLOSE',from_state=self.phase)
   self.quiet=True;self.feed.close();self.queue=[]
   if self.failed:raise ValueError('ambiguous music operation: wait for lease expiry')
   self.transport.send(5,self.tx);self.active=False
  finally:self.lock.release()
 def close(self):
  with self.lock:self.quiet=True;self.failed=True;self.queue=[];self.feed.close()
  trace_event(self.trace,'SERVICE_STOP',phase='CLOSE',from_state=self.phase)
