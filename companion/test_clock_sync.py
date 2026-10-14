"""Targeted clock provider tests: fake transports only; any socket is forbidden."""
import contextlib
import io
import json
import math
import socket
import struct
import unittest
from datetime import datetime,timezone,timedelta
from unittest.mock import patch,Mock
import clock_sync as clock

UTC=1791980760
class FakeTransport:
    def __init__(self):
        self.calls=[]
        self.error=None
        self.clock_key=clock.derive_key("PUBLIC-INERT-CLOCK-FIXTURE")
        self.status={"protocol":clock.PROTOCOL,"clock_enabled":True,"boot":"11"*16,"challenge":"22"*16,"challenge_ms":2000}
    def prepare(self):
        self.calls.append("GET")
        return self.status
    def post(self,raw):
        self.calls.append(raw)
        if self.error:raise self.error
        return {"status":"CLOCK_SAMPLE_ACCEPTED","persisted":False}

class ClockTests(unittest.TestCase):
    def setUp(self):
        self.guard=patch.object(socket,"create_connection",side_effect=AssertionError("NO NETWORK"))
        self.guard.start()
    def tearDown(self):self.guard.stop()
    def local(self,epoch):return datetime.fromtimestamp(epoch,timezone(timedelta(hours=2)))
    def sample(self):
        return clock.capture_pc_clock(wall=lambda:UTC,local=self.local)
    def test_real_source_utc_and_os_offset(self):
        sample=self.sample()
        self.assertEqual(sample,dict(schema=1,utc_s=UTC,offset_min=120,lease_s=120))
    def test_fixed_frame(self):
        raw=clock.encode(self.sample())
        self.assertEqual(len(raw),16)
        self.assertEqual(raw,b"SHINOCL2"+struct.pack("<IhH",UTC,120,120))
    def test_bad_clock_values(self):
        for value in (float("nan"),float("inf"),0,1577836799,4102444800):
            with self.subTest(value=value),self.assertRaises(clock.ClockHold):
                clock.capture_pc_clock(wall=lambda:value,local=self.local)
    def test_offset_and_dst_cutoff(self):
        def dst(epoch):
            return datetime.fromtimestamp(epoch,timezone(timedelta(hours=2 if epoch<UTC+50 else 1)))
        self.assertEqual(clock.capture_pc_clock(wall=lambda:UTC,local=dst)["lease_s"],42)
        def too_near(epoch):
            return datetime.fromtimestamp(epoch,timezone(timedelta(hours=2 if epoch<UTC+8 else 1)))
        with self.assertRaises(clock.ClockHold):
            clock.capture_pc_clock(wall=lambda:UTC,local=too_near)
    def test_nonminute_offset_rejected(self):
        with self.assertRaises(clock.ClockHold):
            clock.capture_pc_clock(wall=lambda:UTC,local=lambda n:datetime.fromtimestamp(n,timezone(timedelta(seconds=30))))
    def test_encoder_strict_shape_and_types(self):
        cases=[]
        for key,value in (("schema",True),("utc_s",float(UTC)),("offset_min",841),("offset_min",-721),("lease_s",0),("lease_s",121)):
            bad=self.sample();bad[key]=value;cases.append(bad)
        bad=self.sample();bad["extra"]=1;cases.append(bad)
        for bad in cases:
            with self.subTest(bad=bad),self.assertRaises(clock.ClockHold):clock.encode(bad)
    def test_disabled_has_no_io(self):
        tr=FakeTransport()
        self.assertEqual(clock.publish_clock("192.168.1.70",tr),"CLOCK_DISABLED_NO_IO")
        self.assertEqual(tr.calls,[])
    def test_authorized_fake_single_post(self):
        tr=FakeTransport()
        with patch.object(clock,"digest_exchange",lambda *a,**k:contextlib.nullcontext()),patch.object(clock,"capture_pc_clock",return_value=self.sample()):
            self.assertEqual(clock.publish_clock("192.168.1.70",tr,authorize_clock_sync=True),"CLOCK_SAMPLE_ACCEPTED")
        self.assertEqual(tr.calls,["GET",clock.seal(self.sample(),tr.status,tr.clock_key)])
    def test_unknown_result_never_retries_or_prints_secret(self):
        tr=FakeTransport();tr.error=TimeoutError("secret-credential-do-not-log")
        stdout=io.StringIO()
        with contextlib.redirect_stdout(stdout),patch.object(clock,"digest_exchange",lambda *a,**k:contextlib.nullcontext()),patch.object(clock,"capture_pc_clock",return_value=self.sample()):
            self.assertEqual(clock.publish_clock("192.168.1.70",tr,authorize_clock_sync=True),"CLOCK_UNKNOWN_NO_RETRY")
        self.assertEqual(len(tr.calls),2)
        self.assertEqual(stdout.getvalue(),"")
    def test_busy_does_not_touch_transport(self):
        tr=FakeTransport()
        with patch.object(clock,"digest_exchange",side_effect=clock.CoordinationBusy("busy")):
            self.assertEqual(clock.publish_clock("192.168.1.70",tr,authorize_clock_sync=True),"CLOCK_COORDINATION_HOLD")
        self.assertEqual(tr.calls,[])
    def test_unsupported_receiver_stops_before_capture_post(self):
        tr=FakeTransport();tr.status["protocol"]="other"
        with patch.object(clock,"digest_exchange",lambda *a,**k:contextlib.nullcontext()),patch.object(clock,"capture_pc_clock",side_effect=AssertionError("must not capture")):
            self.assertEqual(clock.publish_clock("192.168.1.70",tr,authorize_clock_sync=True),"CLOCK_COMPATIBILITY_HOLD")
        self.assertEqual(tr.calls,["GET"])
    def test_public_and_noncanonical_hosts_rejected_before_io(self):
        for host in ("127.0.0.1","example.com","8.8.8.8","http://192.168.4.1","192.168.004.1"):
            tr=FakeTransport()
            with self.subTest(host=host),self.assertRaises(ValueError):
                clock.publish_clock(host,tr,authorize_clock_sync=True)
            self.assertEqual(tr.calls,[])
    def test_missing_clock_no_post(self):
        tr=FakeTransport()
        with patch.object(clock,"digest_exchange",lambda *a,**k:contextlib.nullcontext()),patch.object(clock,"capture_pc_clock",side_effect=clock.ClockHold("CLOCK_UNAVAILABLE")):
            self.assertEqual(clock.publish_clock("192.168.1.70",tr,authorize_clock_sync=True),"CLOCK_SOURCE_HOLD")
        self.assertEqual(tr.calls,["GET"])
    def test_inspect_only_cli_does_not_offer_writer(self):
        with contextlib.redirect_stderr(io.StringIO()),self.assertRaises(SystemExit):clock.main(["publish"])
    def test_post_401_is_not_replayed(self):
        mgr=clock.HTTPPasswordMgrWithDefaultRealm()
        handler=clock.ClockDigest(mgr,"http://192.168.1.70")
        req=clock.Request("http://192.168.1.70/api/v1/clock/sync",data=b"x",method="POST")
        fp=io.BytesIO(b"denied")
        with self.assertRaises(clock.HTTPError):
            handler.http_error_401(req,fp,401,"Denied",{})
    def test_http_error_response_is_closed(self):
        transport=clock.ClockTransport("192.168.1.70","shino","PUBLIC-INERT-CLOCK-FIXTURE")
        fp=io.BytesIO(b"denied")
        error=clock.HTTPError(transport.base,401,"Denied",{},fp)
        transport.reader=Mock()
        transport.reader.open.side_effect=error
        with transport.session(),self.assertRaises(clock.HTTPError):transport.post(clock.encode(self.sample()))
        self.assertTrue(fp.closed)
    def test_malformed_or_uncertain_receipt_not_success(self):
        class Bad(FakeTransport):
            def post(self,raw):self.calls.append(raw);return {"status":"OTHER"}
        tr=Bad()
        with patch.object(clock,"digest_exchange",lambda *a,**k:contextlib.nullcontext()),patch.object(clock,"capture_pc_clock",return_value=self.sample()):
            self.assertEqual(clock.publish_clock("192.168.1.70",tr,authorize_clock_sync=True),"CLOCK_UNKNOWN_NO_RETRY")
        self.assertEqual(len(tr.calls),2)

if __name__=="__main__":unittest.main()

