"""Public inert UART binding: exactly one transaction, no serial object."""
import hashlib
import importlib.util
import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch
from m9_signed_fixture_image import inert_image
from shino_prepare_ota_pair import prepare_uart,OWNER,ENV,ROOT


class BindingTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.raw=inert_image(407008) # Public non-executable fixture, same 100-block geometry.
        cls.sha=hashlib.sha256(cls.raw).hexdigest()

    def setUp(self):
        OWNER.mkdir(parents=True,exist_ok=True)
        self.temp=tempfile.TemporaryDirectory(dir=OWNER,prefix="inert-uart-test-");self.addCleanup(self.temp.cleanup)
        self.directory=Path(self.temp.name);binary=self.directory/"A/.pio/build"/ENV/"firmware.bin"
        binary.parent.mkdir(parents=True);binary.write_bytes(self.raw)
        (self.directory/"A/report.json").write_text(json.dumps(dict(private=True,bytes=len(self.raw),sha256=self.sha)))
        self.original=(ROOT/"tools/m9_single_attempt_app_write.py").read_bytes()
        self.commands=prepare_uart(self.directory);self.binary=binary
        spec=importlib.util.spec_from_file_location("inert_bound_writer",self.directory/"uart-A/m9_single_attempt_app_write.py")
        self.app=importlib.util.module_from_spec(spec);spec.loader.exec_module(self.app)
        self.assertEqual((ROOT/"tools/m9_single_attempt_app_write.py").read_bytes(),self.original)

    def transport(self,fail=None):
        test=self
        class Transport:
            identity=("ESP8266",2,0x400000)
            calls=[];payload=bytearray()
            def step(self,key):
                self.calls.append(key)
                if key==fail:raise RuntimeError("Simulated missing acknowledgement")
            def begin(self):self.step("begin")
            def data(self,block,sequence):
                self.step(sequence);test.assertEqual(len(block),4096);self.payload.extend(block)
            def finish(self):self.step("finish")
            def md5(self):self.step("md5");return hashlib.md5(self.payload[:len(test.raw)]).hexdigest()
        return Transport()

    def test_exact_100_unique_blocks_no_original_rebind(self):
        t=self.transport();result=self.app.SingleAttempt().write(self.binary,self.sha,lambda:t,self.app.GO_TEXT)
        self.assertEqual(t.calls,["begin",*range(100),"finish","md5"])
        self.assertEqual(t.payload[:len(self.raw)],self.raw)
        self.assertEqual(t.payload[len(self.raw):],b"\xff"*2592)
        self.assertEqual(result["automatic_retries"],0)
        self.assertEqual(self.commands["rounded_end"],0x64000)
        self.assertFalse(self.commands["physical_authorized"])

    def test_exact_offline_pre_post_verifier_under_isolated_python(self):
        # Regression for the owner's ModuleNotFoundError on post-readback.
        # Exercise exact generated argv shape under -I, with two local fake
        # 4MiB files, no COM port or hardware access.
        args=self.commands["verify_post_argv"]
        entry=self.directory/"uart-A/verify_post_entry.py"
        self.assertEqual(args[1],"-I")
        self.assertEqual(Path(args[2]),entry)
        before=self.directory/"PRE-4MiB.bin"
        after=self.directory/"POST-4MiB.bin"
        before.write_bytes(b"\xff"*0x400000)
        after.write_bytes(self.raw+b"\xff"*(0x400000-len(self.raw)))
        run=subprocess.run([sys.executable,"-I",str(entry),str(self.binary),
                            str(before),str(after),"--expected-sha256",self.sha],
                           cwd=self.directory,capture_output=True,text=True,timeout=35)
        self.assertEqual(run.returncode,0,run.stderr)
        report=json.loads(run.stdout)
        self.assertEqual(report["status"],"PASS_LOCAL_STAGE1_READBACK_MODEL")
        self.assertTrue(report["protected_byte_exact"])
        self.assertEqual(report["protected_bytes_compared"],0x400000-0x64000)
        self.assertFalse(report["serial_io_performed"])

    def test_a2_launchers_bind_exact_book_and_candidate(self):
        target=self.directory/"A2/.pio/build"/ENV/"firmware.bin"
        target.parent.mkdir(parents=True);target.write_bytes(self.raw)
        (self.directory/"A2/report.json").write_text(json.dumps(dict(private=True,bytes=len(self.raw),sha256=self.sha)))
        commands=prepare_uart(self.directory,"A2")
        book=self.directory/"uart-commands.json";book_sha=hashlib.sha256(book.read_bytes()).hexdigest()
        self.assertEqual(commands["physical_control"]["candidate"],str(target))
        for caption in ("PRE","WRITE","POST"):
            command=(self.directory/(caption+"-A2.cmd")).read_text()
            self.assertIn('--expected-sha256 '+book_sha,command)
            self.assertIn('--execute --owner-go "'+commands["physical_control"]["owner_go"][caption.lower()]+ '"',command)
            self.assertIn('if errorlevel 2 exit /b 1',command)
        verify=(self.directory/"VERIFY-POST-A2.cmd").read_text()
        self.assertNotIn("--execute",verify)
        self.assertIn('"'+str(target)+'"',verify)
        self.assertIn('"'+self.sha+'"',verify)

    def test_each_failure_is_terminal_without_second_attempt(self):
        # Inspect the unchanged fixture once; this matrix targets the writer's
        # command/exception boundary, not repeated CRC implementations.
        data,identity=self.app.candidate(self.binary,self.sha)
        with patch.object(self.app,"candidate",return_value=(data,identity)):
            for command in ("begin",*range(100),"finish","md5"):
                with self.subTest(command=command):
                    t=self.transport(command);session=self.app.SingleAttempt()
                    with self.assertRaises(RuntimeError):session.write(self.binary,self.sha,lambda:t,self.app.GO_TEXT)
                    previous=list(t.calls)
                    with self.assertRaises(self.app.WriteError):session.write(self.binary,self.sha,lambda:t,self.app.GO_TEXT)
                    self.assertEqual(t.calls,previous)
                    self.assertEqual(t.calls[-1],command)



class B3InstalledTransitionTests(unittest.TestCase):
    """Offline-only B2-image/archived-FS binding, never serial or sockets."""
    def setUp(self):
        import shino_prepare_ota_pair as packet
        self.packet=packet
        self.td=tempfile.TemporaryDirectory(prefix="b3-owner-offline-")
        self.addCleanup(self.td.cleanup)
        self.owner=Path(self.td.name)/"m9-owner"
        self.owner.mkdir()
        self.raw=inert_image(407008)
        self.old_sha=hashlib.sha256(self.raw).hexdigest()
        self.device="0123456789abcdef"
        self.config=dict(device=self.device,ap_psk="B3TestSecretAP",
                         api_token="B3TestSecretToken",
                         digest_password="B3TestDigest",
                         maintenance_password="B3TestMaintenance")
        self.installed_bin=self.owner/"installed-B2.bin"
        self.installed_bin.write_bytes(self.raw)
        self.manifest=self.owner/"installed-B2-release.json"
        self.old=dict(schema=1,family="SHINO-StageA",layout="4m2m",
                      protocol="shino-http-ota-1",device=self.device,
                      bytes=len(self.raw),sha256=self.old_sha,build_id="b"*64)
        self.manifest.write_text(json.dumps(self.old))
        self.reference=self.owner/"archived-before-B2-full-flash.bin"
        self.reference.write_bytes(b"\xff"*0x400000)
        for f in ("transition-build/.pio/build/"+ENV+"/firmware.bin",
                  "owner-credentials.json","transition-report.json",
                  "transition-manifest.json"):
            p=self.owner/f;p.parent.mkdir(parents=True,exist_ok=True)
            p.write_bytes(b"Protected owner artifact")
        self.output=self.owner/"b3-new-owner-packet"
        self.head="c"*40
        self.build_calls=0;self.uart_calls=[]
    def git(self,args,**kwargs):
        if args==["git","branch","--show-current"]:return "feature/shino-tv-b3-telemetry-scratch-experiment\n"
        if args==["git","status","--porcelain"]:return ""
        if args==["git","rev-parse","HEAD"]:return self.head+"\n"
        raise AssertionError("Unexpected Git command")
    def fake_build(self,output,private):
        self.assertTrue(private);self.build_calls+=1
        body=b"fake B3 content"+b"".join(self.config[k].encode() for k in ("ap_psk","api_token","digest_password"))
        body+=hashlib.sha256(self.config["maintenance_password"].encode()).digest()
        body=body.ljust(407488,b"X")
        sha=hashlib.sha256(body).hexdigest()
        target=output/".pio/build"/ENV/"firmware.bin"
        target.parent.mkdir(parents=True)
        target.write_bytes(body)
        report=dict(private=True,source_dirty=False,source_commit=self.head,
                    device=self.device,sha256=sha,bytes=len(body),
                    build_id="a"*64,layout="4m2m")
        (output/"report.json").write_text(json.dumps(report))
        return report
    def fake_uart(self,output,label,reference):
        self.uart_calls.append((output,label,reference))
        return dict(status="OFFLINE")
    def exercise(self):
        p=self.packet
        with patch.object(p,"OWNER",self.owner),patch.object(p.subprocess,"check_output",side_effect=self.git),patch.object(p,"load",return_value=self.config),patch.object(p,"build",side_effect=self.fake_build),patch.object(p,"prepare_uart",side_effect=self.fake_uart):
            return p.prepare_installed_b3(self.output,self.installed_bin,self.manifest,self.reference)

    def test_b3_packet_is_offline_and_ties_precheck_to_installed_b2_and_archived_tail(self):
        result=self.exercise()
        self.assertEqual(self.build_calls,1)
        self.assertEqual(len(self.uart_calls),1)
        _,label,reference=self.uart_calls[0]
        self.assertEqual(label,"B3")
        self.assertEqual(reference["installed_sha256"],self.old_sha)
        self.assertEqual(reference["installed_bytes"],len(self.raw))
        self.assertEqual(reference["path"],str(self.reference))
        self.assertFalse(result["physical_authorized"])
        self.assertEqual(result["device_contacts"],0)
        self.assertEqual(result["flash_writes"],0)
        self.assertIn("WRITE-B3.cmd",result["commands"])
        self.assertNotIn("UPDATE-B.cmd",result["commands"])
        guide=(self.output/"B3-OWNER-OPERATIONS.md").read_text()
        self.assertIn("PRE-B3.cmd",guide)
        self.assertIn("B2",guide)
        self.assertIn("0x200000",guide)
        self.assertIn("\n",guide)
        qualify=(self.output/"QUALIFY-B3.cmd").read_text()
        self.assertIn("--authorize-read",qualify)
        self.assertIn("\ncd /d",qualify)
        self.assertNotIn("--install",qualify)
        self.assertNotIn("--execute",qualify)

    def test_b3_rejects_installed_image_mismatch_before_build_or_device_contact(self):
        self.installed_bin.write_bytes(self.raw+b"x")
        with self.assertRaisesRegex(ValueError,"BIN and manifest do not match"):
            self.exercise()
        self.assertEqual(self.build_calls,0)
        self.assertFalse(self.output.exists())

    def test_b3_rejects_non_4mib_reference_before_build(self):
        self.reference.write_bytes(b"x"*4096)
        with self.assertRaisesRegex(ValueError,"exactly 4MiB"):
            self.exercise()
        self.assertEqual(self.build_calls,0)

    def test_b3_rejects_installed_device_mismatch_before_build(self):
        self.old["device"]="ffffffffffffffff"
        self.manifest.write_text(json.dumps(self.old))
        with self.assertRaisesRegex(ValueError,"compatible private 4m2m"):
            self.exercise()
        self.assertEqual(self.build_calls,0)

    def test_b3_rejects_wrong_branch_or_dirty_tree(self):
        with patch.object(self.packet,"OWNER",self.owner),patch.object(self.packet.subprocess,"check_output",return_value="main\n"),patch.object(self.packet,"build",side_effect=AssertionError("no build")):
            with self.assertRaisesRegex(ValueError,"reviewed PR #47 branch"):
                self.packet.prepare_installed_b3(self.output,self.installed_bin,self.manifest,self.reference)
        self.assertFalse(self.output.exists())


if __name__=="__main__":unittest.main()
