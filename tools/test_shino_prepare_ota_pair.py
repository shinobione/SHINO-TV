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
        before.write_bytes(b"\\xff"*0x400000)
        after.write_bytes(self.raw+b"\\xff"*(0x400000-len(self.raw)))
        run=subprocess.run([sys.executable,"-I",str(entry),str(self.binary),
                            str(before),str(after),"--expected-sha256",self.sha],
                           cwd=self.directory,capture_output=True,text=True,timeout=35)
        self.assertEqual(run.returncode,0,run.stderr)
        report=json.loads(run.stdout)
        self.assertEqual(report["status"],"PASS_LOCAL_STAGE1_READBACK_MODEL")
        self.assertTrue(report["protected_byte_exact"])
        self.assertEqual(report["protected_bytes_compared"],0x400000-0x64000)
        self.assertFalse(report["serial_io_performed"])

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


if __name__=="__main__":unittest.main()
