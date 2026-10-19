"""Actual complete P0+512+WX HTTP graph; localhost only, synthetic keys.
The original VM publisher/protocol are used byte-exact, with loopback _connect.
"""
import http.client,json,os,socket,subprocess,tempfile,time,unittest
from pathlib import Path
from concurrent.futures import ThreadPoolExecutor
from urllib.request import Request,HTTPPasswordMgrWithDefaultRealm,HTTPDigestAuthHandler,build_opener
from weather_vm import protocol as p,publisher as pub
from weather_vm.test_publisher import cache
KEY=bytes(range(32));DEVICE=bytes.fromhex('0123456789abcdef');NONCE=b'12345678';STATUS='/api/v1/weather/status/'
class IntegratedWeather(unittest.TestCase):
 def setUp(self):
  exe=os.environ['P0_B54_HOST_EXE']
  self.proc=subprocess.Popen([exe],stdin=subprocess.PIPE,stdout=subprocess.PIPE,stderr=subprocess.PIPE,text=True,bufsize=1)
  line=self.proc.stdout.readline()
  if not line:raise AssertionError(self.proc.stderr.read()[-1000:])
  self.port=int(line);self.command('mode lan');self.command('sntp')
 def tearDown(self):
  self.command('stop',False);self.proc.wait(timeout=6);self.proc.stdin.close();self.proc.stdout.close()
  error=self.proc.stderr.read();self.proc.stderr.close();self.assertEqual(self.proc.returncode,0,error[-1000:])
 def command(self,s,reply=True):
  self.proc.stdin.write(s+'\n');self.proc.stdin.flush()
  return json.loads(self.proc.stdout.readline()) if reply else None
 def wire(self,path,method='GET',body=None,headers=None):
  peer=http.client.HTTPConnection('127.0.0.1',self.port,timeout=4)
  h={'Host':'10.23.42.82','Connection':'close'};h.update(headers or {})
  try:
   peer.request(method,path,body=body,headers=h);r=peer.getresponse();return r.status,r.read(8193)
  except (ConnectionResetError,http.client.RemoteDisconnected):return 0,b''
  finally:peer.close()
 def status(self):
  code,wire=self.wire(STATUS+NONCE.hex());self.assertEqual(code,200,wire)
  return p.verify(KEY,wire,2,DEVICE,challenge=NONCE)
 def sample(self,**overrides):
  s=self.status();values=dict(key=KEY,device=DEVICE,boot=s['boot'],sequence=s['sequence']+1,observed=s['utc'],ttl=2700,tenths=182,wmo=3,location=p.LOCATION);values.update(overrides)
  return p.sample(**values)
 def post(self,frame):return self.wire('/api/v1/weather','POST',frame,{'Content-Type':'application/octet-stream'})
 def auth(self,path,body=None,content_type="application/json"):
  manager=HTTPPasswordMgrWithDefaultRealm();manager.add_password('SHINO-StageA',f'http://127.0.0.1:{self.port}','shino','PUBLIC-INERT-LAB-HTTP-FIXTURE')
  opener=build_opener(HTTPDigestAuthHandler(manager))
  request=Request(f'http://127.0.0.1:{self.port}'+path,data=body,headers={'Host':'10.23.42.82','Content-Type':content_type} if body else {'Host':'10.23.42.82'})
  with opener.open(request,timeout=4) as r:return r.status,json.loads(r.read())
 def test_status_sample_ack_and_replay(self):
  frame=self.sample();code,ack=self.post(frame);self.assertEqual(code,200,ack)
  status=self.status();verified=p.verify(KEY,ack,3,DEVICE,boot=status['boot'],challenge=frame[48:56]);self.assertEqual(verified['sequence'],1)
  self.assertEqual(self.post(frame)[0],409);self.assertEqual(self.status()['sequence'],1)
 def test_bad_hmac_identity_boot_location_sequence_and_expiry(self):
  for override in ({'key':b'X'*32},{'device':b'OTHERDEV'},{'boot':b'OLDBOOT0'},{'location':b'OTHERLOC'},{'sequence':2},{'observed':int(time.time())-2800}):
   with self.subTest(kind=next(iter(override))):self.assertEqual(self.post(self.sample(**override))[0],409)
  self.assertEqual(self.status()['sequence'],0)
 def test_real_parser_methods_paths_queries_headers_and_short_body(self):
  for path in (STATUS+'00',STATUS+'A'*16,STATUS+NONCE.hex()+'/',STATUS+NONCE.hex()+'?x=1','/api/v1/weather?x=1'):
   self.assertNotEqual(self.wire(path)[0],200,path)
  for method in ('PUT','DELETE','HEAD','POST'):
   self.assertNotEqual(self.wire(STATUS+NONCE.hex(),method)[0],200,method)
  frame=self.sample()
  for h in ({'Origin':'http://unit.invalid'},{'Expect':'100-continue'},{'Transfer-Encoding':'chunked'}):
   h={'Content-Type':'application/octet-stream',**h};self.assertNotEqual(self.wire('/api/v1/weather','POST',frame,h)[0],200)
  self.assertNotEqual(self.post(frame[:79])[0],200)
  self.assertEqual(self.status()['sequence'],0)
 def test_body_timeout_no_commit(self):
  frame=self.sample()
  with socket.create_connection(('127.0.0.1',self.port),timeout=4) as peer:
   peer.sendall(b'POST /api/v1/weather HTTP/1.1\r\nHost: 10.23.42.82\r\nContent-Type: application/octet-stream\r\nContent-Length: 80\r\nConnection: close\r\n\r\n'+frame[:10])
   try:response=peer.recv(4096)
   except (ConnectionAbortedError,ConnectionResetError):response=b''
   self.assertTrue(b'408' in response or not response,response[:100])
  self.assertEqual(self.status()['sequence'],0)
 def test_ap_low_heap_and_frozen_journal_refused(self):
  self.command('mode ap');self.assertEqual(self.wire(STATUS+NONCE.hex())[0],503)
  self.command('mode lan');self.command('heap low');self.assertEqual(self.wire(STATUS+NONCE.hex())[0],503)
  self.command('heap normal');self.assertEqual(self.wire(STATUS+NONCE.hex())[0],503) # Real journal safety latch stays frozen.
  self.assertEqual(self.command('stats')['flash_writes'],0)
 def test_link_clock_and_digest_remain_after_weather(self):
  code,_=self.auth('/api/v1/bridge/metrics',json.dumps(dict(ok=True,gpu_available=True,cpu_usage=22.5,gpu_usage=34.5,memory_used_gb=8,memory_total_gb=16,gpu_vram_mb=2048,gpu_temp_c=56,gpu_power=120)).encode());self.assertEqual(code,200)
  self.assertEqual(self.post(self.sample())[0],200)
  stats=self.command('stats')
  self.assertEqual([stats[k] for k in ('cpu','gpu','ram','temperature')],[22.5,34.5,8,56]);self.assertEqual(stats['sdk_writes'],0);self.assertEqual(stats['flash_writes'],0)
  self.assertEqual(self.wire('/api/v1/m9/normal/resources')[0],401)
  self.assertEqual(self.auth('/api/v1/clock/status')[0],200)
 def test_concurrent_requests_and_nested_loop(self):
  self.command('arm nested');frame=self.sample()
  with ThreadPoolExecutor(max_workers=2) as pool:codes=list(pool.map(lambda _:self.post(frame)[0],range(2)))
  self.command('disarm nested');self.assertLessEqual(codes.count(200),1)
  self.assertIn(self.status()['sequence'],(0,1));stats=self.command('stats');self.assertEqual(stats['sdk_writes'],0);self.assertEqual(stats['flash_writes'],0)
 def until_drawn(self,criterion,description,seconds=3):
  deadline=time.monotonic()+seconds
  last={}
  while time.monotonic()<deadline:
   last=self.command('display')
   if criterion(last):return last
   time.sleep(.012)
  self.fail('LCD HOST '+description+': '+repr(last))
 def test_http_signed_weather_reaches_lcd_when_pc_off(self):
  # Actual HTTP POST -> native B54 receiver -> B52Clock/renderer -> HOST GFX print.
  self.command('display reset')
  self.assertEqual(self.post(self.sample())[0],200)
  frame=self.until_drawn(lambda d:d['temp'] and d['condition'],'autonomous weather')
  self.assertFalse(any(frame[x] for x in ('cpu','gpu','ram','gpu_temp')))
  self.command('display reset')
  self.command('advance 2701000')
  stale=self.until_drawn(lambda d:d['stale'],'expired weather')
  self.assertFalse(stale['temp'] or stale['condition'])
  self.assertEqual(self.command('stats')['sdk_writes'],0)
 def test_http_weather_and_link_share_actual_lcd(self):
  self.command('display reset')
  raw=json.dumps(dict(ok=True,gpu_available=True,cpu_usage=22.5,gpu_usage=34.5,
   memory_used_gb=8,memory_total_gb=16,gpu_vram_mb=2048,gpu_temp_c=56,gpu_power=120)).encode()
  self.assertEqual(self.auth('/api/v1/bridge/metrics',raw)[0],200)
  self.assertEqual(self.post(self.sample())[0],200)
  frame=self.until_drawn(lambda d:d['temp'] and d['condition'] and
   all(d[x] for x in ('cpu','gpu','ram','gpu_temp')),'combined weather + four cards')
  self.assertGreater(frame['operations'],0)
  self.assertEqual(self.command('stats')['flash_writes'],0)
 def publisher(self,lost=False):
  owner=self
  class Loopback(pub.LanTransport):
   calls=[]
   def _connect(s,peer,ip):peer.connect(('127.0.0.1',owner.port))
   def exchange(s,ip,method,path,body=b''):
    s.calls.append(method);answer=super().exchange(ip,method,path,body)
    if lost and method=='POST':raise TimeoutError('HOST discarded ACK')
    return answer
  status=self.status();now=status['utc']
  with tempfile.TemporaryDirectory() as temp:
   root=Path(temp);key=root/'key';key.write_bytes(KEY);key.chmod(0o600)
   cfg=root/'publisher.json';cached=root/'cache.json';state=root/'intent.json'
   cfg.write_text(json.dumps(dict(schema=1,enabled=True,authorization=pub.APPROVAL,target='10.23.42.82',device=DEVICE.hex(),location=p.LOCATION.hex(),key_file=str(key))))
   cached.write_text(json.dumps(cache(now)));transport=Loopback()
   result=pub.run_once(cfg,cached,state,transport=transport,now=now)
   self.assertEqual(result,'UNKNOWN_NO_RETRY' if lost else 'PUBLISHED');self.assertEqual(transport.calls,['GET','POST'])
   self.assertEqual(self.status()['sequence'],1)
   self.assertEqual(pub.run_once(cfg,cached,state,transport=transport,now=now+1),'CADENCE_HOLD');self.assertEqual(transport.calls,['GET','POST'])
 def test_existing_publisher_status_sample_ack(self):self.publisher()
 def test_existing_publisher_lost_ack_no_retry(self):self.publisher(True)
if __name__=='__main__':unittest.main()
