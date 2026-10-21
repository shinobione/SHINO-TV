import hashlib,hmac,json,os,socket,sys,time,unittest
from pathlib import Path
R=Path(os.environ['SHINO_M3R_LAB_OUT']).resolve();AREA=os.environ.get('M3_AREA','patched');sys.path[:0]=[str(R/AREA/'tests'),str(R/AREA)]
import test_weather as wx
os.environ['P0_B54_HOST_EXE']=str(R/AREA/'.build'/('receiver.exe' if os.name=='nt' else 'receiver'))
ROUTE='/api/v1/display/mode';KEY=bytes(range(32));BOOT='1'*32;DEV='0123456789abcdef';TX='2'*32
def frame():
 body=json.dumps(dict(boot=BOOT,device=DEV,mode='AUTO',protocol='shino-display-control-1',revision=0,tx=TX),separators=(',',':')).encode()
 digest=hashlib.sha256(body).hexdigest();proof=hmac.new(KEY,f'SHINO-M3-CONTROL-1\nPOST\n{ROUTE}\n10.23.42.82\n{DEV}\n{BOOT}\n0\nAUTO\n{TX}\n{len(body)}\n{digest}'.encode(),hashlib.sha256).hexdigest()
 fields={'Host':'10.23.42.82','Content-Type':'application/json','Content-Length':str(len(body)),'Connection':'close','X-Shino-Device':DEV,'X-Shino-Boot':BOOT,'X-Shino-Revision':'0','X-Shino-Mode':'AUTO','X-Shino-Tx':TX,'X-Shino-Body-Sha256':digest,'X-Shino-Proof':proof}
 return (f'POST {ROUTE} HTTP/1.1\r\n'+''.join(f'{k}: {v}\r\n' for k,v in fields.items())+'\r\n').encode(),body
class Handoff(unittest.TestCase):
 setUp=wx.IntegratedWeather.setUp;tearDown=wx.IntegratedWeather.tearDown;command=wx.IntegratedWeather.command;auth=wx.IntegratedWeather.auth;wire=wx.IntegratedWeather.wire
 def exchange(self,raw,parts=None,fin=True):
  start=time.monotonic();reply=b''
  with socket.create_connection(('127.0.0.1',self.port),timeout=4) as s:
   for p in parts or [raw]:s.sendall(p);time.sleep(.003 if parts else 0)
   if fin:s.shutdown(socket.SHUT_WR)
   try:
    while True:
     b=s.recv(4096)
     if not b:break
     reply+=b
   except (ConnectionResetError,ConnectionAbortedError):pass
  return reply,time.monotonic()-start
 def test_00_valid_verified_but_no_command(self):
  head,body=frame();reply,_=self.exchange(head+body);self.assertIn(b'503',reply)
  stats=self.command('stats');self.assertEqual(stats['m3_verified'],1);self.assertEqual(stats['m3_body'],len(body));self.assertEqual(stats['m3_taken'],1);self.assertEqual(stats['m3_busy'],0);self.assertEqual(stats['http_busy'],0)
  self.assertEqual(stats['bytes_read'],len(head+body));self.assertEqual(stats['m3_headers'],len(head));self.assertEqual(stats['accepted'],1)
  (R/'host-resource-observation.json').write_text(json.dumps(stats,indent=2))
 def unlocked(self):
  s=self.command('stats');self.assertEqual(s['m3_busy'],0);self.assertEqual(s['http_busy'],0);self.assertEqual(s['sdk_writes'],0);self.assertEqual(s['flash_writes'],0);self.assertEqual(s['restarts'],0)
  return s
 def test_fragmented_real_socket(self):
  h,b=frame();raw=h+b;parts=[raw[i:i+7] for i in range(0,len(raw),7)];reply,_=self.exchange(raw,parts);self.assertIn(b'503',reply)
  s=self.unlocked();self.assertEqual(s['m3_verified'],1);self.assertEqual(s['bytes_read'],len(raw))
 def test_unauthenticated_body_unread(self):
  h,b=frame();h=h.replace(b'X-Shino-Proof: ',b'X-Shino-Proof: 0',1) # too long, rejected
  self.exchange(h+b);s=self.unlocked();self.assertEqual(s['m3_body'],0);self.assertEqual(s['m3_verified'],0);self.assertEqual(s['bytes_read'],len(h))
 def test_wrong_hmac_body_unread(self):
  h,b=frame();a=h.index(b'X-Shino-Proof: ')+15;h=h[:a]+bytes([ord('f') if h[a]!=ord('f') else ord('e')])+h[a+1:]
  self.exchange(h+b);s=self.unlocked();self.assertEqual(s['m3_body'],0);self.assertEqual(s['m3_verified'],0);self.assertEqual(s['bytes_read'],len(h))
 def test_cumulative_header_limit(self):
  line=b'POST /api/v1/display/mode HTTP/1.1\r\n';raw=line+(b'X: '+b'A'*298+b'\r\n')*4+b'\r\nBODY'
  self.exchange(raw);s=self.unlocked();self.assertEqual(s['m3_body'],0);self.assertEqual(s['m3_verified'],0);self.assertEqual(s['bytes_read'],len(line)+960)
 def test_invalid_or_oversized_request_lines(self):
  h,b=frame();tail=h.split(b'\r\n',1)[1]
  for line in (b'GET '+ROUTE.encode()+b' HTTP/1.1',b'POST '+ROUTE.encode()+b' HTTP/1.0',b'POST '+ROUTE.encode()+b' HTTP/1.2',b'POST '+ROUTE.encode()+b' HTTP/1.1 EXTRA',b'POST '+ROUTE.encode()+b'?x=1 HTTP/1.1',b'POST '+b'x'*257,b'POST /api/v1/display/mode HTTP/1.1\x00'):
   with self.subTest(line=line[:70]):self.exchange(line+b'\r\n'+tail+b);self.assertEqual(self.unlocked()['m3_taken'],0)
 def test_invalid_oversized_duplicate_unknown_headers(self):
  h,b=frame()
  variants=[h.replace(b'Host:',b'Bad Header:'),h.replace(b'Host: 10.23.42.82',b'Host: '+b'A'*321),h.replace(b'Host: 10.23.42.82',b'Host: 10.23.42.82\r\nHost: 10.23.42.82'),h.replace(b'Host: 10.23.42.82',b'Host: 10.23.42.82\r\nOrigin: http://unit.invalid'),h.replace(b'\r\n',b'\n',1),h.replace(b'Content-Length:',b'Transfer-Encoding:'),h.replace(b'Host: 10.23.42.82',b'Host: other.invalid')]
  for head in variants:
   with self.subTest(header=head[:70]):self.exchange(head+b);s=self.unlocked();self.assertEqual(s['m3_verified'],0);self.assertEqual(s['m3_body'],0)
 def test_timeout_headers_and_release(self):
  h,b=frame();reply,elapsed=self.exchange(h[:70],fin=False);self.assertLess(elapsed,2);self.assertGreater(elapsed,.7);self.assertEqual(self.unlocked()['m3_body'],0)
  self.assertEqual(self.auth('/api/v1/clock/status')[0],200)
 def test_original_deadline_includes_request_line(self):
  h,b=frame();line,tail=h.split(b'\r\n',1)
  with socket.create_connection(('127.0.0.1',self.port),timeout=4) as s:
   s.sendall(line[:5]);time.sleep(1.08);s.sendall(line[5:]+b'\r\n'+tail+b);s.shutdown(socket.SHUT_WR)
   try:s.recv(4096)
   except (ConnectionResetError,ConnectionAbortedError):pass
  self.assertEqual(self.unlocked()['m3_verified'],0);self.assertEqual(self.command('stats')['m3_body'],0)
 def test_header_eof_and_disconnect(self):
  h,b=frame();self.exchange(h[:100]);self.assertEqual(self.unlocked()['m3_body'],0)
  with socket.create_connection(('127.0.0.1',self.port),timeout=4) as s:s.sendall(h[:100])
  time.sleep(.1);self.unlocked();self.assertEqual(self.auth('/api/v1/clock/status')[0],200)
 def test_body_timeout_partial_and_missing_fin(self):
  h,b=frame()
  for body in (b[:10],b):
   with self.subTest(length=len(body)):
    _,elapsed=self.exchange(h+body,fin=False);self.assertLess(elapsed,2.8);self.assertGreater(elapsed,1.6);self.assertEqual(self.unlocked()['m3_verified'],0)
 def test_body_eof_extra_byte_wrong_sha(self):
  h,b=frame()
  for body in (b[:-1],b+b'X',bytes([b[0]^1])+b[1:]):
   with self.subTest(length=len(body)):self.exchange(h+body);self.assertEqual(self.unlocked()['m3_verified'],0)
 def test_nested_loop_cannot_reenter(self):
  self.command('arm nested');h,b=frame();self.exchange(h+b);self.command('disarm nested');s=self.unlocked();self.assertGreater(s['nested_calls'],0);self.assertEqual(s['m3_verified'],1)
 def test_queued_peer_cancels_without_stuck_lock(self):
  h,b=frame()
  with socket.create_connection(('127.0.0.1',self.port),timeout=4) as first:
   first.sendall(h[:90]);time.sleep(.03)
   with socket.create_connection(('127.0.0.1',self.port),timeout=4) as second:
    second.sendall(h+b);second.shutdown(socket.SHUT_WR)
    try:
     while second.recv(4096):pass
    except (ConnectionResetError,ConnectionAbortedError):pass
  s=self.unlocked();self.assertEqual(s['accepted'],2);self.assertLessEqual(s['m3_verified'],1);self.assertEqual(self.auth('/api/v1/clock/status')[0],200)
 def test_admission_config_and_response_busy(self):
  h,b=frame();self.command('hold response');self.exchange(h+b);self.command('release response');self.assertEqual(self.unlocked()['m3_taken'],0)
  self.command('config off');self.exchange(h+b);self.assertEqual(self.unlocked()['m3_taken'],0)
 def test_ap_foreign_and_lost_network(self):
  h,b=frame()
  for cmd in ('mode ap','mode lan','peer foreign','network lost'):
   self.command(cmd)
   if cmd=='mode lan':continue
   self.exchange(h+b);self.assertEqual(self.unlocked()['m3_taken'],0)
 def test_low_heap_frozen_journal_admission(self):
  h,b=frame();self.command('heap low');self.exchange(h+b);self.command('heap normal');self.exchange(h+b);self.assertEqual(self.unlocked()['m3_taken'],0)
 def test_repeated_requests_no_context_leak(self):
  h,b=frame()
  for i in range(6):
   self.exchange(h+b);s=self.unlocked();self.assertEqual(s['m3_verified'],i+1);self.assertEqual(s['live_sockets'],1)
 def test_signed_weather_and_legacy_after_handoff(self):
  h,b=frame();self.exchange(h+b);self.assertEqual(self.auth('/api/v1/clock/status')[0],200)
  wx.IntegratedWeather.status(self) # signed status on the very same server after handoff
if __name__=='__main__':unittest.main(verbosity=2)
