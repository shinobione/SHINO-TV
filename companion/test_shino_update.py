"""Windows updater consent, compatibility and real-boot acceptance contract."""
import hashlib
import json
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch
import shino_update as update
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
        for field,value in (("boot_id",self.before["boot_id"]),("sha256","c"*64),("build_id","c"*64),("metrics_fresh",False),("fs_ok",False),("heap",20479),("ota_enabled",False)):
            with self.subTest(field=field):
                self.ticks=0;io=self.io(dict(self.after,**{field:value}));result=self.install(io)
                self.assertEqual(result["status"],"STAGED_BOOT_OR_TELEMETRY_UNCONFIRMED");self.assertEqual(io.posts,1)
    def test_lost_reply_unresolved_unknown(self):
        io=self.io(self.before,True);self.assertEqual(self.install(io)["status"],"UNKNOWN_NO_RETRY");self.assertEqual(io.posts,1)
    def test_bad_initial_resources_prevent_upload(self):
        self.before["heap"]=25599;io=self.io()
        with self.assertRaises(update.UpdateError):self.install(io)
        self.assertEqual(io.posts,0)
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

if __name__=="__main__":unittest.main()
