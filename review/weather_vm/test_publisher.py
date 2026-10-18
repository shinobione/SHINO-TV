import copy
import datetime as dt
import hashlib
import hmac
import http.server
import json
import os
from pathlib import Path
import random
import socket
import subprocess
import tempfile
import threading
import unittest
from unittest.mock import patch
from weather_vm import protocol as p,publisher as pub
from weather_vm.test_protocol import KEY,DEVICE,BOOT

NOW=1791955392
def iso(t):return dt.datetime.fromtimestamp(t,dt.timezone.utc).strftime('%Y-%m-%dT%H:%M:%SZ')
def cache(now=NOW):
    return dict(schema=1,source='open-meteo-https',location=dict(name='DEMO-CITY',latitude=0.0,longitude=0.0),
                temperature_c=18.2,wmo_code=3,observed_at_utc=iso(now),fetched_at_utc=iso(now),expires_at_utc=iso(now+2700))

class Native:
    def __init__(self):
        exe=os.environ.get('B54_LAN_NATIVE_EXE')
        if not exe:raise unittest.SkipTest('native executable provided by grouped runner')
        self.process=subprocess.Popen([exe,'--serve'],stdin=subprocess.PIPE,stdout=subprocess.PIPE,stderr=subprocess.PIPE,text=True,bufsize=1)
    def call(self,text):
        self.process.stdin.write(text+'\n');self.process.stdin.flush()
        value=self.process.stdout.readline().strip()
        if not value:raise AssertionError('native receiver stopped')
        return value
    def close(self):
        self.process.stdin.close();self.process.wait(timeout=5)
        self.process.stdout.close();err=self.process.stderr.read();self.process.stderr.close()
        if self.process.returncode:raise AssertionError('native receiver: '+err[-300:])

class Workspace(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory();self.root=Path(self.temp.name)
        self.cfg=self.root/'publisher.json';self.key=self.root/'key';self.key.write_bytes(KEY);self.key.chmod(0o600)
        self.cached=self.root/'latest.json';self.state=self.root/'state.json'
        self.settings=dict(schema=1,enabled=True,authorization=pub.APPROVAL,target='10.23.42.200',
                           device=DEVICE.hex(),location=p.LOCATION.hex(),key_file=str(self.key))
        self.write()
    def write(self,data=None):
        self.cfg.write_text(json.dumps(self.settings));self.cached.write_text(json.dumps(cache() if data is None else data))
    def tearDown(self):self.temp.cleanup()
    def run_publish(self,**kwargs):return pub.run_once(self.cfg,self.cached,self.state,now=kwargs.pop('now',NOW),**kwargs)

class PublisherPolicy(Workspace):
    def test_disabled_touches_no_cache_key_state_or_network(self):
        self.settings['enabled']=False;self.write();self.key.unlink();self.cached.unlink()
        with patch.object(socket,'socket',side_effect=AssertionError('NO SOCKET')):
            self.assertEqual(self.run_publish(),'DISABLED')
        self.assertFalse(self.state.exists())
    def test_configuration_has_no_implicit_authority_or_target_discovery(self):
        for k,v in [('authorization',None),('target','example.com'),('target','127.0.0.1'),('target','8.8.8.8'),
                    ('target','10.23.42.1/ota'),('device','bad'),('location','0'*16),('enabled',1)]:
            with self.subTest(key=k,value=v):
                before=copy.deepcopy(self.settings);self.settings[k]=v;self.write()
                with self.assertRaises((ValueError,TypeError)):pub.config(self.cfg)
                self.settings=before
    def test_cache_invalid_or_expired_does_not_contact_target(self):
        invalid=[dict(cache(),temperature_c=float('nan')),dict(cache(),temperature_c=True),dict(cache(),temperature_c=18.25),
                 dict(cache(),wmo_code=100),dict(cache(),source='http'),cache(NOW-2700),cache(NOW+61),
                 dict(cache(),expires_at_utc=iso(NOW+7200)),dict(cache(),observed_at_utc='missing'),
                 dict(cache(),location=dict(name='elsewhere',latitude=43.2,longitude=2.7))]
        for d in invalid:
            self.write(d)
            with self.subTest(cache=d),patch.object(socket,'socket',side_effect=AssertionError('NO LAN')):
                with self.assertRaises(ValueError):self.run_publish()
        self.cached.write_bytes(b'x'*16385)
        with self.assertRaises(ValueError):self.run_publish()
    def test_duplicate_json_and_bad_key_are_refused(self):
        self.cached.write_text('{"schema":1,"schema":1}')
        with self.assertRaises(ValueError):self.run_publish()
        self.write();self.key.write_bytes(b'bad')
        with self.assertRaises(ValueError):self.run_publish()
    def test_untrusted_capability_never_produces_post_or_ledger(self):
        for how in ('mac','device','location','clock','challenge'):
            class Bad:
                calls=[]
                def exchange(s,ip,method,path,body=b''):
                    s.calls.append(method)
                    nonce=bytes.fromhex(path.rsplit('/',1)[1])
                    response=p.status(KEY,b'OTHERDEV' if how=='device' else DEVICE,BOOT,0,
                        bytes(8) if how=='challenge' else nonce,0 if how=='clock' else NOW,
                        b'BADLOC00' if how=='location' else p.LOCATION)
                    return response[:-1]+bytes([response[-1]^1]) if how=='mac' else response
            bad=Bad()
            with self.subTest(failure=how),self.assertRaises(ValueError):self.run_publish(transport=bad,nonce=b'12345678')
            self.assertEqual(bad.calls,['GET']);self.assertFalse(self.state.exists())
    def test_corrupt_ledger_or_clock_rollback_cannot_repeat_a_post(self):
        good=dict(schema=1,device=DEVICE.hex(),boot=BOOT.hex(),sequence=1,observed=NOW,attempted=NOW+10)
        self.state.write_text(json.dumps(good))
        with patch.object(socket,'socket',side_effect=AssertionError('NO LAN')):
            self.assertEqual(self.run_publish(),'CADENCE_HOLD')
            for k,v in [('schema',True),('sequence',0),('observed',0),('boot','x'*16)]:
                self.state.write_text(json.dumps(dict(good,**{k:v})))
                with self.subTest(field=k),self.assertRaises(ValueError):self.run_publish()
    def test_concurrent_publisher_lock_fails_before_network(self):
        with pub.locked(self.state),patch.object(socket,'socket',side_effect=AssertionError('NO LAN')):
            with self.assertRaises(OSError):self.run_publish()
    def test_deep_json_is_a_controlled_refusal(self):
        self.cached.write_bytes(b'['*1500+b']'*1500)
        with self.assertRaises(ValueError):self.run_publish()

class EndToEnd(Workspace):
    def setUp(self):
        super().setUp();self.native=Native();self.now=NOW;self.calls=[];self.mode='normal'
        owner=self
        class Handler(http.server.BaseHTTPRequestHandler):
            def log_message(self,*args):pass
            def do_GET(self):
                owner.calls.append(('GET',self.path))
                if owner.mode=='unsupported':self.send_response(404);self.end_headers();return
                nonce=self.path.rsplit('/',1)[1]
                wire=bytes.fromhex(owner.native.call(f'STATUS {nonce} {owner.now} 1000'))
                self.send_response(200);self.send_header('Content-Length','80')
                self.send_header('Content-Type','application/octet-stream');self.end_headers();self.wfile.write(wire)
            def do_POST(self):
                owner.calls.append(('POST',self.path))
                if owner.mode=='critical':self.send_response(503);self.end_headers();return
                raw=self.rfile.read(int(self.headers['Content-Length']))
                code,wire=owner.native.call(f'SAMPLE {raw.hex()} {owner.now} 1 1000').split()
                if owner.mode=='lost_ack':self.connection.shutdown(socket.SHUT_RDWR);return
                self.send_response(200 if code=='0' else 409)
                self.send_header('Content-Length','80');self.send_header('Content-Type','application/octet-stream');self.end_headers()
                if code=='0':self.wfile.write(bytes.fromhex(wire))
        self.server=http.server.HTTPServer(('127.0.0.1',0),Handler)
        self.thread=threading.Thread(target=self.server.serve_forever,daemon=True);self.thread.start()
        class Loopback(pub.LanTransport):
            def _connect(s,peer,ip):peer.connect(('127.0.0.1',owner.server.server_port))
        self.transport=Loopback()
    def tearDown(self):
        self.server.shutdown();self.thread.join(timeout=3);self.server.server_close();self.native.close();super().tearDown()
    def test_signed_status_sample_ack_and_temperature(self):
        self.assertEqual(self.run_publish(transport=self.transport),'PUBLISHED')
        self.assertEqual(self.native.call(f'POLL {NOW} 1 1000'),'1 1 182')
        self.assertEqual([x[0] for x in self.calls],['GET','POST'])
        self.assertEqual(self.calls[1][1],'/api/v1/weather')
    def test_lost_ack_persisted_intent_and_no_blind_repeat_after_vm_restart(self):
        self.mode='lost_ack';self.assertEqual(self.run_publish(transport=self.transport),'UNKNOWN_NO_RETRY')
        self.assertEqual(self.native.call(f'POLL {NOW} 1 1000'),'1 1 182')
        self.assertEqual(self.run_publish(transport=self.transport,now=NOW+1),'CADENCE_HOLD')
        self.now=NOW+1800;self.mode='normal'
        self.assertEqual(self.run_publish(transport=self.transport,now=self.now),'ALREADY_ATTEMPTED')
        self.assertEqual(sum(m=='POST' for m,_ in self.calls),1)
        self.write(cache(self.now));self.assertEqual(self.run_publish(transport=self.transport,now=self.now),'PUBLISHED')
    def test_smalltv_reboot_rebinds_boot_and_sequence_without_replay(self):
        self.assertEqual(self.run_publish(transport=self.transport),'PUBLISHED')
        self.native.call('RESET 1122334455667788');self.now=NOW+1800
        self.assertEqual(self.run_publish(transport=self.transport,now=self.now),'PUBLISHED')
        self.assertEqual(self.native.call(f'POLL {self.now} 1 1000'),'1 1 182')
    def test_incompatible_firmware_has_one_get_no_post(self):
        self.mode='unsupported'
        with self.assertRaises(ValueError):self.run_publish(transport=self.transport)
        self.assertEqual([x[0] for x in self.calls],['GET']);self.assertFalse(self.state.exists())
    def test_critical_interruption_does_not_mutate_native_weather(self):
        self.mode='critical';self.assertEqual(self.run_publish(transport=self.transport),'UNKNOWN_NO_RETRY')
        self.assertEqual(self.native.call(f'POLL {NOW} 1 1000'),'0 0 0')
    def test_expiration_and_clock_rollback_never_revive_sample(self):
        self.assertEqual(self.run_publish(transport=self.transport),'PUBLISHED')
        self.assertEqual(self.native.call(f'POLL {NOW+2700} 1 1001'),'1 0 182')
        self.assertEqual(self.native.call(f'POLL {NOW} 1 1002'),'1 0 182')
    def test_pinned_native_hmac_matches_python_many_lengths(self):
        rng=random.Random(54)
        for n in (1,2,31,32,47,48,55,56,63,64,65,80,127,128,256,511,768,1024):
            body=bytes(rng.randrange(256) for _ in range(n))
            self.assertEqual(self.native.call('MAC '+body.hex()),hmac.digest(KEY,body,'sha256').hex())

class NativeContract(unittest.TestCase):
    def setUp(self):self.native=Native()
    def tearDown(self):self.native.close()
    def send(self,wire,utc=NOW,trust=1,now=1000):
        return int(self.native.call(f'SAMPLE {wire.hex()} {utc} {trust} {now}').split()[0])
    def test_authenticated_semantic_rejections_leave_replay_and_measurement_unchanged(self):
        base=p.sample(KEY,DEVICE,BOOT,1,NOW,2700,182,3)
        cases=[]
        for offset,data in [(8,b'OTHERDEV'),(16,b'OLDBOOT0'),(40,b'BADLOC00'),(24,(0).to_bytes(4,'big')),
                (24,(2).to_bytes(4,'big')),(28,(NOW+61).to_bytes(4,'big')),(28,(NOW-2700).to_bytes(4,'big')),
                (28,bytes(4)),(32,bytes(2)),(32,(2701).to_bytes(2,'big')),(34,(-901).to_bytes(2,'big',signed=True)),
                (34,(651).to_bytes(2,'big',signed=True)),(36,b'\xff'),(37,b'\x01'),(38,b'\x01'),(39,b'\x01')]:
            fields=bytearray(base[:48]);fields[offset:offset+len(data)]=data;cases.append(p.sign(KEY,bytes(fields)))
        cases.extend([p.sample(b'X'*32,DEVICE,BOOT,1,NOW,2700,182,3),base+b'X',base[:79]])
        for frame in cases:
            with self.subTest(frame=frame.hex()[:24]):
                self.assertNotEqual(self.send(frame),0)
                self.assertEqual(self.native.call(f'POLL {NOW} 1 1000'),'0 0 0')
        for utc,trust in [(NOW,0),(0,1),(4102444800,1)]:self.assertNotEqual(self.send(base,utc,trust),0)
        self.assertEqual(self.send(base),0);self.assertEqual(self.send(base),4)
    def test_all_supported_wmo_temperature_edges_and_millis_wrap(self):
        sequence=0
        for code in sorted(p.WMO):
            for temp in (-900,-1,0,650):
                sequence+=1
                self.assertEqual(self.send(p.sample(KEY,DEVICE,BOOT,sequence,NOW,1,temp,code),now=0xfffffff0),0)
        self.assertEqual(self.native.call(f'POLL {NOW} 1 1000'),f'{sequence} 0 650')
    def test_lost_trust_rollback_expiry_are_sticky_until_new_authenticated_sample(self):
        for utc,trust,now in [(NOW,0,1001),(NOW-3,1,1001),(NOW+2700,1,1001),(NOW,1,2701000)]:
            self.native.call('RESET '+BOOT.hex())
            self.assertEqual(self.send(p.sample(KEY,DEVICE,BOOT,1,NOW,2700,182,3)),0)
            self.assertEqual(self.native.call(f'POLL {utc} {trust} {now}'),'1 0 182')
            self.assertEqual(self.native.call(f'POLL {NOW} 1 1002'),'1 0 182')
            self.assertEqual(self.send(p.sample(KEY,DEVICE,BOOT,2,NOW,2700,-12,61)),0)

class HttpBounds(unittest.TestCase):
    def test_strict_path_and_method_policy_precedes_socket_creation(self):
        bad=[('GET','/api/v1/weather',b''),('GET','/api/v1/weather?challenge=3132333435363738',b''),
             ('GET','/api/v1/weather/status/'+'A'*16,b''),('GET','/api/v1/weather/status/'+'a'*15,b''),
             ('GET','/api/v1/weather/status/'+'a'*17,b''),('POST','/api/v1/weather/status/'+'a'*16,b'X'*80),
             ('POST','/api/v1/weather',b'X'*79),('GET','/api/v1/update/status',b'')]
        for method,path,body in bad:
            with self.subTest(path=path),patch.object(socket,'socket',side_effect=AssertionError('NO SOCKET')):
                with self.assertRaises(ValueError):pub.LanTransport().exchange('10.23.42.200',method,path,body)
    def exchange(self,response,method='GET',body=b''):
        server=socket.socket();server.bind(('127.0.0.1',0));server.listen(1);port=server.getsockname()[1]
        def worker():
            try:
                client,_=server.accept()
                with client:
                    client.recv(4096)
                    if response is None:
                        # Deterministic socket timeout injected below; no long sleep.
                        return
                    client.sendall(response)
            finally:server.close()
        thread=threading.Thread(target=worker);thread.start()
        class Local(pub.LanTransport):
            def _connect(s,peer,ip):peer.connect(('127.0.0.1',port))
        try:return Local().exchange('10.23.42.200',method,('/api/v1/weather/status/3132333435363738' if method=='GET' else '/api/v1/weather'),body)
        finally:thread.join(timeout=3)
    def test_reject_redirect_chunked_duplicate_truncated_oversized_and_error(self):
        good=b'HTTP/1.1 200 OK\r\nContent-Type: application/octet-stream\r\nContent-Length: 80\r\n\r\n'+b'X'*80
        self.assertEqual(self.exchange(good),b'X'*80)
        cases=[good.replace(b'200 OK',b'302 Found'),good.replace(b'200 OK',b'401 Unauthorized'),
               good.replace(b'Content-Length: 80',b'Content-Length: 79'),
               good.replace(b'\r\n\r\n',b'\r\nTransfer-Encoding: chunked\r\n\r\n'),
               good.replace(b'Content-Length: 80',b'Content-Length: 80\r\ncontent-length: 80'),
               good[:-1],good+b'X',b'HTTP/1.1 200 OK\r\n'+b'X'*2048,good[:10]]
        for response in cases:
            with self.subTest(response=response[:50]),self.assertRaises((ValueError,OSError)):self.exchange(response)
    def test_timeout_is_not_retried(self):
        class Peer:
            def __enter__(s):return s
            def __exit__(s,*a):pass
            def settimeout(s,t):pass
            def connect(s,where):pass
            def sendall(s,data):pass
            def recv(s,n):raise TimeoutError('fixture')
        with patch.object(socket,'socket',return_value=Peer()) as factory:
            with self.assertRaises(TimeoutError):pub.LanTransport().exchange('10.23.42.200','GET','/api/v1/weather/status/3132333435363738')
            self.assertEqual(factory.call_count,1)

if __name__=='__main__':unittest.main()
