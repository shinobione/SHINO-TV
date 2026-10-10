"""Windows updater consent, compatibility and real-boot acceptance contract."""
import hashlib
import json
import sys
import tempfile
import unittest
import contextlib
import io
from pathlib import Path
from unittest.mock import patch
from urllib.error import HTTPError,URLError
import shino_update as update
import shino_qualify as qualification
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/"tools"))
from test_shino_http_ota import fixture

class UpdaterTests(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory();self.addCleanup(self.temp.cleanup);root=Path(self.temp.name)
        self.identity=dict(device="1123456789abcdef",build="d"*64,ap_psk="p"*32,api_token="t"*32,digest_password="h"*32,maintenance_password="m"*32)
        self.raw=fixture(device=self.identity["device"]);self.binary=root/"firmware.bin";self.binary.write_bytes(self.raw)
        self.m=dict(schema=1,family="SHINO-StageA",layout="4m2m",protocol="shino-http-ota-1",device=self.identity["device"],bytes=len(self.raw),sha256=hashlib.sha256(self.raw).hexdigest(),build_id="b"*64)
        self.manifest=root/"release.json";self.manifest.write_text(json.dumps(self.m),encoding="utf-8")
        self.credentials=root/"private.json";self.credentials.write_text(json.dumps(self.identity),encoding="utf-8")
        self.before=dict(protocol="shino-http-ota-1",device=self.identity["device"],build_id="a"*64,sha256="a"*64,bytes=399264,nonce="1"*32,boot_id="1"*32,
                         ota_enabled=True,fs_ok=True,fs_files=24,fs_bytes=181402,metrics_fresh=True,heap=30000,block=28000,stack=3200,frag=1)
        self.after=dict(self.before,build_id=self.m["build_id"],sha256=self.m["sha256"],bytes=len(self.raw),boot_id="2"*32)
        self.ticks=0
    def sleep(self,n):self.ticks+=n
    def io(self,after=None,lost=False):
        test=self
        class IO:
            posts=0;gets=0;headers=None
            def status(self):
                self.gets+=1;return dict(test.before if self.gets==1 else (after or test.after))
            def upload(self,headers,raw,progress):
                self.posts+=1;self.headers=headers;test.assertEqual(raw,test.raw)
                progress(len(raw),len(raw))
                if lost:raise update.UpdateError("lost reply")
                return dict(status="STAGED_PENDING_BOOT",heap_min=23000,block_min=20000,stack_min=2400,frag_max=2,samples=800)
        return IO()
    def install(self,io,confirm=None):
        return update.install(self.binary,self.manifest,self.credentials,confirm or self.m["sha256"],transport=io,clock=lambda:self.ticks,sleep=self.sleep)
    def test_offline_does_not_load_credentials_or_network(self):
        with patch("socket.create_connection",side_effect=AssertionError("network")),patch.object(update,"load_identity",side_effect=AssertionError("credentials")):
            self.assertEqual(update.inspect(self.binary,self.manifest),(self.m,self.raw))
    def test_exact_consent_before_network_or_secret_load(self):
        io=self.io()
        with patch.object(update,"load_identity",side_effect=AssertionError("credentials")):
            with self.assertRaises(update.UpdateError):self.install(io,"0"*64)
        self.assertEqual(io.gets+io.posts,0)
    def test_exact_boot_and_metrics_confirms_once(self):
        io=self.io();result=self.install(io)
        self.assertEqual(result["status"],"BOOT_AND_TELEMETRY_CONFIRMED");self.assertEqual(io.posts,1)
        self.assertEqual(io.headers["X-Shino-Proof"],update.signature(self.identity,self.before["nonce"],self.m))
    def test_lost_reply_resolved_by_new_boot_never_retries(self):
        io=self.io(lost=True);result=self.install(io)
        self.assertEqual(result["status"],"BOOT_AND_TELEMETRY_CONFIRMED");self.assertEqual(io.posts,1)
        self.assertEqual(result["transfer_measurements"],"REPLY_LOST_UNKNOWN")
    def test_ack_never_suffices_for_boot(self):
        for field,value in (("boot_id",self.before["boot_id"]),("sha256","c"*64),("build_id","c"*64),("metrics_fresh",False),("fs_ok",False),("heap",20479),("heap",25599),("ota_enabled",False)):
            with self.subTest(field=field):
                self.ticks=0;io=self.io(dict(self.after,**{field:value}));result=self.install(io)
                self.assertEqual(result["status"],"POSTBOOT_ACCEPTANCE_UNCONFIRMED");self.assertEqual(io.posts,1)
    def test_lost_reply_unresolved_unknown(self):
        io=self.io(self.before,True);self.assertEqual(self.install(io)["status"],"UNKNOWN_NO_RETRY");self.assertEqual(io.posts,1)
    def test_bad_initial_resources_prevent_upload(self):
        self.before["heap"]=25599;io=self.io()
        with self.assertRaises(update.UpdateError):self.install(io)
        self.assertEqual(io.posts,0)
    def test_one_shot_exact_current_A_one_status_then_one_post(self):
        marker=self.binary.parent/"once.marker"
        transport=self.io()
        upload=transport.upload
        def checked_upload(headers,raw,progress):
            self.assertEqual(transport.gets,1)
            self.assertFalse(transport.posts)
            self.assertEqual(marker.read_text(),"OTA_ONE_SHOT_STARTED_NO_AUTOMATIC_RETRY\n")
            return upload(headers,raw,progress)
        transport.upload=checked_upload
        result=update.install(
            self.binary,self.manifest,self.credentials,self.m["sha256"],
            transport=transport,clock=lambda:self.ticks,sleep=self.sleep,
            expected_current_sha256=self.before["sha256"],attempt_marker=marker)
        self.assertEqual(result["status"],"BOOT_AND_TELEMETRY_CONFIRMED")
        self.assertEqual(transport.posts,1)
        again=self.io()
        with self.assertRaisesRegex(update.UpdateError,"marker"):
            update.install(self.binary,self.manifest,self.credentials,self.m["sha256"],
                           transport=again,expected_current_sha256=self.before["sha256"],
                           attempt_marker=marker)
        self.assertEqual(again.gets+again.posts,0)

    def test_one_shot_mismatched_A_never_creates_marker_or_uploads(self):
        marker=self.binary.parent/"once.marker"
        transport=self.io()
        with self.assertRaisesRegex(update.UpdateError,"does not match"):
            update.install(self.binary,self.manifest,self.credentials,self.m["sha256"],
                           transport=transport,expected_current_sha256="c"*64,
                           attempt_marker=marker)
        self.assertEqual((transport.gets,transport.posts),(1,0))
        self.assertFalse(marker.exists())

    def test_one_shot_resource_floor_failure_does_not_reserve_attempt(self):
        self.before["stack"]=1904
        marker=self.binary.parent/"once.marker"
        transport=self.io()
        with self.assertRaisesRegex(update.UpdateError,"floors"):
            update.install(self.binary,self.manifest,self.credentials,self.m["sha256"],
                           transport=transport,expected_current_sha256=self.before["sha256"],
                           attempt_marker=marker)
        self.assertEqual((transport.gets,transport.posts),(1,0))
        self.assertFalse(marker.exists())

    def test_one_shot_lost_reply_blocks_all_repeat_uploads(self):
        marker=self.binary.parent/"once.marker"
        transport=self.io(self.before,True)
        result=update.install(
            self.binary,self.manifest,self.credentials,self.m["sha256"],
            transport=transport,clock=lambda:self.ticks,sleep=self.sleep,
            expected_current_sha256=self.before["sha256"],attempt_marker=marker)
        self.assertEqual(result["status"],"UNKNOWN_NO_RETRY")
        self.assertEqual(transport.posts,1)
        with self.assertRaisesRegex(update.UpdateError,"marker"):
            update.install(self.binary,self.manifest,self.credentials,self.m["sha256"],
                           transport=self.io(),expected_current_sha256=self.before["sha256"],
                           attempt_marker=marker)

    def test_changed_bin_before_install_prevents_network(self):
        self.binary.write_bytes(self.raw[:-1]+b"x");io=self.io()
        with self.assertRaises(update.UpdateError):self.install(io)
        self.assertEqual(io.posts+io.gets,0)
    def test_manifest_identity_must_be_in_binary(self):
        self.m["build_id"]="f"*64;self.manifest.write_text(json.dumps(self.m),encoding="utf-8")
        with self.assertRaises(update.UpdateError):update.inspect(self.binary,self.manifest)
    def test_duplicate_manifest_key_rejected(self):
        self.manifest.write_text('{"schema":1,"schema":1}',encoding="utf-8")
        with self.assertRaises(update.UpdateError):update.inspect(self.binary,self.manifest)
    def test_only_private_ap_target(self):
        with patch("socket.create_connection",side_effect=AssertionError("network")):
            with self.assertRaises(update.UpdateError):update.Transport(self.identity,"127.0.0.1")

class QualifierTests(unittest.TestCase):
    setUp=UpdaterTests.setUp

    def reader(self,status=None,faults=None):
        test=self;status=status or self.after;faults=faults or {}
        class Reader:
            paths=[]
            def open(self,request,timeout):
                self.paths.append(request.full_url.removeprefix("http://192.168.4.1"))
                value=faults.get(len(self.paths))
                if isinstance(value,Exception):raise value
                if value is None:value={"mode":"M9_NORMAL_STAGE_A"} if self.paths[-1]=="/api/v1/m9/normal/status" else dict(status)
                response=io.BytesIO(value if isinstance(value,bytes) else json.dumps(value).encode())
                response.status=200;return response
        class Transport:
            base="http://192.168.4.1"
            reader=Reader()
        return Transport()

    def run_qualification(self,transport,cycles=2):
        with patch("socket.create_connection",side_effect=AssertionError("network")):
            return qualification.qualify(self.binary,self.manifest,self.credentials,True,cycles,transport,lambda n:None)

    def test_print_only_never_loads_secrets_or_creates_transport(self):
        with patch.object(qualification,"load_identity",side_effect=AssertionError("secret")),patch.object(qualification,"Transport",side_effect=AssertionError("network")):
            self.assertEqual(qualification.qualify(self.binary,self.manifest,self.credentials,False)["status"],"PRINT_ONLY")

    def test_full_read_only_cycles_and_alias_are_checked(self):
        transport=self.reader();result=self.run_qualification(transport)
        self.assertEqual(result["status"],"PHYSICAL_READONLY_QUALIFICATION_PASS")
        self.assertEqual(len(transport.reader.paths),6)
        self.assertEqual(result["minima"],{k:self.after[k] for k in ("heap","block","stack")})

    def test_observed_1632_is_specific_and_stops_first_cycle(self):
        transport=self.reader(dict(self.after,heap=31912,block=29744,stack=1632,frag=7))
        with self.assertRaises(qualification.QualificationFailure) as caught:self.run_qualification(transport)
        d=caught.exception.diagnostic
        self.assertEqual(d,{"code":"RESOURCE_FLOOR_FAILED","cycle":1,"operation":"GET /api/v1/update/status","violations":[{"field":"stack","observed":1632,"minimum":2048}]})
        self.assertEqual(len(transport.reader.paths),1)

    def test_http_error_reports_exact_cycle_route_and_status_without_secret(self):
        secret="DO-NOT-PRINT-AUTHORIZATION"
        error=HTTPError("http://private/"+secret,404,secret,{"Authorization":secret},io.BytesIO(secret.encode()))
        transport=self.reader(faults={5:error})
        with self.assertRaises(qualification.QualificationFailure) as caught:self.run_qualification(transport)
        d=caught.exception.diagnostic
        self.assertEqual(d,{"code":"HTTP_STATUS","cycle":2,"operation":"GET /api/v1/m9/normal/status","http_status":404})
        self.assertNotIn(secret,json.dumps(caught.exception.result()));self.assertEqual(len(transport.reader.paths),5)

    def test_timeout_is_specific_and_never_retried(self):
        transport=self.reader(faults={3:URLError(TimeoutError("SECRET"))})
        with self.assertRaises(qualification.QualificationFailure) as caught:self.run_qualification(transport)
        self.assertEqual(caught.exception.diagnostic,{"code":"NETWORK_TIMEOUT","cycle":1,"operation":"GET /api/v1/m9/maintenance/result"})
        self.assertEqual(len(transport.reader.paths),3)

    def test_json_errors_are_sanitized(self):
        for raw in (b'{"nonce":"SECRET","nonce":"SECRET"}',b'SECRET',b'\xff'):
            with self.subTest(raw=raw):
                with self.assertRaises(qualification.QualificationFailure) as caught:self.run_qualification(self.reader(faults={1:raw}))
                self.assertEqual(caught.exception.diagnostic["code"],"JSON_INVALID")
                self.assertNotIn("SECRET",json.dumps(caught.exception.result()))

    def test_legacy_alias_must_match_release(self):
        with self.assertRaises(qualification.QualificationFailure) as caught:self.run_qualification(self.reader(faults={3:dict(self.after,sha256="c"*64)}))
        self.assertEqual(caught.exception.diagnostic["code"],"RELEASE_IDENTITY_MISMATCH")
        self.assertEqual(caught.exception.diagnostic["fields"],["sha256"])

    def test_reboot_is_reported_at_its_cycle(self):
        with self.assertRaises(qualification.QualificationFailure) as caught:self.run_qualification(self.reader(faults={4:dict(self.after,boot_id="3"*32)}))
        self.assertEqual(caught.exception.diagnostic["code"],"UNEXPECTED_REBOOT")
        self.assertEqual(caught.exception.diagnostic["cycle"],2)

    def test_future_ota_heap_floor_remains_25600(self):
        with self.assertRaises(qualification.QualificationFailure) as caught:self.run_qualification(self.reader(dict(self.after,heap=25599)))
        self.assertEqual(caught.exception.diagnostic["violations"],[{"field":"heap","observed":25599,"minimum":25600}])

    def test_boolean_is_not_an_integer_measurement(self):
        with self.assertRaises(qualification.QualificationFailure) as caught:self.run_qualification(self.reader(dict(self.after,stack=True)))
        self.assertEqual(caught.exception.diagnostic["code"],"MEASUREMENTS_INVALID")

    def test_invalid_cycles_cannot_print_false_pass(self):
        for cycles in (0,-1,31,True):
            with self.subTest(cycles=cycles),patch.object(qualification,"inspect",side_effect=AssertionError("inspection")):
                with self.assertRaises(qualification.QualificationFailure):self.run_qualification(self.reader(),cycles)

    def test_cli_failure_preserves_diagnostic_receipt_and_nonzero_exit(self):
        error=qualification.QualificationFailure("RESOURCE_FLOOR_FAILED",1,"GET /api/v1/update/status",violations=[dict(field="stack",observed=1632,minimum=2048)])
        receipt=self.binary.parent/"read-failure.json";out=io.StringIO();err=io.StringIO()
        with patch.object(qualification,"qualify",side_effect=error),contextlib.redirect_stdout(out),contextlib.redirect_stderr(err):
            code=qualification.main(["--bin",str(self.binary),"--manifest",str(self.manifest),"--receipt",str(receipt),"--authorize-read"])
        self.assertEqual(code,2);self.assertEqual(json.loads(out.getvalue()),json.loads(receipt.read_text()))
        self.assertIn("observed=1632, minimum=2048",err.getvalue());self.assertNotIn("QUALIFICATION_PASS",out.getvalue())

    def test_existing_receipt_is_not_changed_and_causes_no_reads(self):
        receipt=self.binary.parent/"keep.json";receipt.write_text("KEEP")
        with patch.object(qualification,"qualify",side_effect=AssertionError("reads")),contextlib.redirect_stdout(io.StringIO()),contextlib.redirect_stderr(io.StringIO()):
            self.assertEqual(qualification.main(["--bin",str(self.binary),"--manifest",str(self.manifest),"--receipt",str(receipt)]),2)
        self.assertEqual(receipt.read_text(),"KEEP")

    def test_receipt_write_failure_never_prints_pass(self):
        out=io.StringIO()
        with patch.object(qualification,"qualify",return_value=dict(status="PHYSICAL_READONLY_QUALIFICATION_PASS")),contextlib.redirect_stdout(out),contextlib.redirect_stderr(io.StringIO()):
            code=qualification.main(["--bin",str(self.binary),"--manifest",str(self.manifest),"--receipt",str(self.binary.parent/"absent"/"receipt.json")])
        self.assertEqual(code,2);self.assertEqual(json.loads(out.getvalue())["diagnostic"]["code"],"RECEIPT_WRITE_FAILED")

if __name__=="__main__":unittest.main()
