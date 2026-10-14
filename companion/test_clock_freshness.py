"""Fresh proof/PC ordering tests; no socket, secret loader or live publisher."""
import contextlib
import hmac
import socket
import struct
import unittest
from unittest.mock import patch
import clock_sync as c

PASSWORD="PUBLIC-INERT-CLOCK-FIXTURE"
SAMPLE=dict(schema=1,utc_s=1791980760,offset_min=120,lease_s=120)
STATUS=dict(protocol=c.PROTOCOL,clock_enabled=True,boot="11"*16,challenge="22"*16,challenge_ms=2000)

class FreshnessTests(unittest.TestCase):
    def setUp(self):
        self.guard=patch.object(socket,"create_connection",side_effect=AssertionError("NO NETWORK"));self.guard.start()
    def tearDown(self):self.guard.stop()
    def test_domain_separated_exact_binary_proof(self):
        key=c.derive_key(PASSWORD)
        self.assertEqual(key,hmac.digest(PASSWORD.encode(),b"SHINO-PC-CLOCK-KEY-2\n","sha256"))
        self.assertNotEqual(key,hmac.digest(PASSWORD.encode(),b"OTHER-OPERATION\n","sha256"))
        frame=c.seal(SAMPLE,STATUS,key)
        self.assertEqual(len(frame),64)
        self.assertEqual(frame[:32],b"SHINOCL2"+struct.pack("<IhH",1791980760,120,120)+bytes.fromhex(STATUS["challenge"]))
        self.assertEqual(frame[32:],hmac.digest(key,b"SHINO-PC-CLOCK-SYNC-2\n"+bytes.fromhex(STATUS["boot"])+frame[:32],"sha256"))
    def test_each_field_boot_and_challenge_bound(self):
        key=c.derive_key(PASSWORD);base=c.seal(SAMPLE,STATUS,key)
        for field,value in (("utc_s",SAMPLE["utc_s"]+1),("offset_min",60),("lease_s",119)):
            altered=dict(SAMPLE);altered[field]=value
            self.assertNotEqual(base[32:],c.seal(altered,STATUS,key)[32:])
        for field in ("boot","challenge"):
            altered=dict(STATUS);altered[field]="33"*16
            self.assertNotEqual(base[32:],c.seal(SAMPLE,altered,key)[32:])
    def test_challenge_strict_shape(self):
        for field,value in (("boot",None),("boot","00"*16),("boot","FF"*16),("challenge","11"*16),
                            ("challenge","x"*32),("challenge_ms",True),("challenge_ms",2001),("protocol","shino-pc-clock-1")):
            altered=dict(STATUS);altered[field]=value
            with self.subTest(field=field,value=value),self.assertRaises(c.ClockHold):c.challenge_tokens(altered)
    def test_capture_after_challenge_under_lock_one_post(self):
        events=[]
        class Transport:
            clock_key=c.derive_key(PASSWORD)
            def prepare(self):events.append("challenge");return STATUS
            def post(self,frame):events.append("post");self.frame=frame;return dict(status="CLOCK_SAMPLE_ACCEPTED",persisted=False)
        @contextlib.contextmanager
        def lock(*args,**kwargs):
            events.append("lock")
            try:yield
            finally:events.append("unlock")
        def sample():events.append("capture");return SAMPLE
        tr=Transport()
        with patch.object(c,"digest_exchange",lock),patch.object(c,"capture_pc_clock",sample):
            self.assertEqual(c.publish_clock("192.168.4.1",tr,authorize_clock_sync=True),"CLOCK_SAMPLE_ACCEPTED")
        self.assertEqual(events,["lock","challenge","capture","post","unlock"])
        self.assertEqual(tr.frame,c.seal(SAMPLE,STATUS,tr.clock_key))
    def test_bad_challenge_prevents_capture_and_post(self):
        class Transport:
            def prepare(self):return dict(STATUS,challenge_ms=0)
            def post(self,_):raise AssertionError("NO POST")
        with patch.object(c,"digest_exchange",lambda *a,**k:contextlib.nullcontext()),patch.object(c,"capture_pc_clock",side_effect=AssertionError("NO CAPTURE")):
            self.assertEqual(c.publish_clock("192.168.4.1",Transport(),authorize_clock_sync=True),"CLOCK_SOURCE_HOLD")

if __name__=="__main__":unittest.main()
