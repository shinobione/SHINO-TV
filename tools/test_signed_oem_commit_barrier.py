"""Host-only signed OEM last-mile ordering and *real host RSA* failure tests.

The host fake models pinned ESP8266 core's RSA check inside end(false) before
eboot_command_write. This DOES NOT execute the actual ESP8266 Updater,
guarantee power-cut recovery, configure owner credentials, or touch a device.
"""
from pathlib import Path
import hashlib
import shutil
import struct
import subprocess
import tempfile
import unittest

ROOT = Path(__file__).resolve().parent.parent
BARRIER = ROOT/"firmware/include/recovery/SignedOemCommitBarrier.h"
BRIDGE = ROOT/"firmware/src/boot/FirstBootBridge.cpp"
OEM = ROOT/"firmware/src/recovery/FactoryRollback.cpp"
HOST = ROOT/"tools/signed_oem_commit_barrier_probe.cpp"
RAW_LEN = 494144


def run(*args):
    p = subprocess.run(args, capture_output=True, text=True, timeout=35, check=False)
    if p.returncode:
        raise AssertionError("Fixture command failed: " + p.stderr[:400])


@unittest.skipUnless(shutil.which("openssl") and shutil.which("g++"),
                     "OpenSSL and host g++ are mandatory for signed OTA gate tests")
class SignedOemCommitOrderHostTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.temp = tempfile.TemporaryDirectory(prefix="shino-oem-commit-host-")
        cls.root = Path(cls.temp.name)
        cls.private = cls.root/"ephemeral-private.pem"
        cls.public = cls.root/"ephemeral-public.pem"
        cls.other_private = cls.root/"other-ephemeral-private.pem"
        run("openssl","genpkey","-algorithm","RSA","-pkeyopt","rsa_keygen_bits:2048",
            "-out",str(cls.private))
        run("openssl","pkey","-in",str(cls.private),"-pubout","-out",str(cls.public))
        run("openssl","genpkey","-algorithm","RSA","-pkeyopt","rsa_keygen_bits:2048",
            "-out",str(cls.other_private))
        cls.raw = bytearray(RAW_LEN)
        cls.raw[:8] = bytes([0xE9, 2, 2, 0x40, 0, 0, 0, 0])
        for offset in range(8,len(cls.raw),32):
            cls.raw[offset:offset+32] = hashlib.sha256(
                offset.to_bytes(4,"little")).digest()[:min(32,len(cls.raw)-offset)]
        digest = hashlib.sha256(cls.raw).hexdigest()
        (cls.root/"test_pin.h").write_text(
            '#define SHINO_TEST_PIN_SHA256 "'+digest+'"\n',encoding="utf-8")
        cls.host = cls.root/"signed-oem-commit-test"
        built = subprocess.run(
            ["g++","-std=c++17","-Wall","-Wextra","-Werror","-pedantic",
             "-I",str(ROOT/"firmware/include"),"-I",str(cls.root),
             str(HOST),"-o",str(cls.host),"-lcrypto"],
            capture_output=True,text=True,timeout=45,check=False)
        if built.returncode:
            raise AssertionError("Host C++ signed core probe compilation failed: "+built.stderr)
        cls.sample = cls.root/"sample.bin"

    @classmethod
    def tearDownClass(cls):
        cls.temp.cleanup()  # Deletes both temporary fixture private keys.

    def signed(self, raw=None, signer=None):
        raw_bytes = bytes(self.raw if raw is None else raw)
        payload = self.root/"to-sign.bin"
        signature = self.root/"signature.bin"
        payload.write_bytes(raw_bytes)
        run("openssl","dgst","-sha256","-sign",str(signer or self.private),
            "-out",str(signature),str(payload))
        sig=signature.read_bytes()
        self.assertEqual(len(sig),256)
        return raw_bytes+sig+struct.pack("<I",256)

    def check(self, mode, data=None, *, chunk=4096, expected_end_calls=0, scheduled=False):
        self.sample.write_bytes(self.signed() if data is None else data)
        result=subprocess.run(
            [str(self.host),str(self.sample),str(self.public),mode,str(chunk)],
            capture_output=True,text=True,timeout=40,check=False)
        self.assertEqual(result.returncode,0,
                         "mode="+mode+" "+result.stdout+" "+result.stderr)
        self.assertIn("HOST_EMULATION_ONLY NO_DEVICE_WRITER",result.stdout)
        self.assertIn("core_end_calls="+str(expected_end_calls),result.stdout)
        self.assertIn("eboot_scheduled="+str(int(scheduled)),result.stdout)

    def test_signed_exact_original_reaches_core_and_can_schedule_simulated_eboot(self):
        for chunk in (1,3,257,4095,4096):
            with self.subTest(chunk=chunk):
                self.check("success",chunk=chunk,expected_end_calls=1,scheduled=True)

    def test_invalid_rsa_signature_reaches_core_verifier_but_cannot_schedule_eboot(self):
        p=bytearray(self.signed())
        p[RAW_LEN+100] ^= 1  # raw OEM stays EXACT, signature changes.
        self.check("rsa_invalid",p,expected_end_calls=1,scheduled=False)
        wrong_key=self.signed(signer=self.other_private)
        self.check("rsa_invalid",wrong_key,expected_end_calls=1,scheduled=False)

    def test_signed_modified_oem_must_not_call_end_even_with_valid_signature(self):
        raw=bytearray(self.raw); raw[12345] ^= 1
        self.check("raw_invalid",self.signed(raw=raw),expected_end_calls=0)

    def test_wrong_header_rejected_before_core_end(self):
        for idx in range(4):
            with self.subTest(byte=idx):
                raw=bytearray(self.raw); raw[idx] ^= 1
                self.check("raw_invalid",self.signed(raw=raw),chunk=1)

    def test_truncation_extra_bytes_and_unsigned_rejected_without_core_end(self):
        valid=self.signed()
        for data in (bytes(self.raw), valid[:-1], valid[:-260], valid+b"x"):
            with self.subTest(bytes=len(data)):
                self.check("raw_invalid",data)

    def test_malformed_rsa_length_rejected_before_core_end(self):
        valid=self.signed()
        for n in (0,1,255,257,0xffffffff):
            with self.subTest(trailer=n):
                self.check("raw_invalid",valid[:-4]+struct.pack("<I",n))

    def test_privileged_denial_and_missing_core_verifier_do_not_begin_or_end(self):
        self.check("denied")
        self.check("signer_off")
        self.check("wrong_size")

    def test_stage_begin_write_error_or_short_write_never_reaches_end(self):
        self.check("begin_fail")
        self.check("short_write")
        self.check("stage_fail")

    def test_owner_abort_wrong_final_bytes_and_large_chunk_deny_end(self):
        self.check("abort")
        self.check("wrong_total")
        self.check("raw_invalid",chunk=4097)

    def test_duplicate_finish_or_rearm_after_simulated_acceptance_never_repeats_end(self):
        self.check("duplicate",expected_end_calls=1,scheduled=True)

    def test_host_contract_is_unwired_and_cannot_expose_actual_update(self):
        code=BARRIER.read_text(encoding="utf-8")
        bridge=BRIDGE.read_text(encoding="utf-8")
        oem=OEM.read_text(encoding="utf-8")
        self.assertIn("adapter_.end(false)",code)
        self.assertIn("raw_.finish(reportedTransportBytes)",code)
        self.assertLess(code.index("raw_.finish(reportedTransportBytes)"),
                        code.index("adapter_.end(false)"))
        self.assertNotIn("adapter_.end(true)",code)
        self.assertNotIn("SignedOemCommitBarrier.h",bridge)
        self.assertNotIn("SignedOemCommitBarrier.h",oem)
        for endpoint in ("/api/v1/bridge/ota/arm","/api/v1/bridge/ota/upload",
                         "/api/v1/bridge/ota/install"):
            self.assertNotIn('server.on("'+endpoint+'"',bridge)
        for forbidden in ("#include <Updater", "ESP8266WebServer", "ESP.restart(",
                          "LittleFS.begin(", "EEPROM.commit("):
            without_comments="\n".join(line for line in code.splitlines()
                                       if not line.lstrip().startswith("//"))
            self.assertNotIn(forbidden,without_comments)

if __name__=="__main__":
    unittest.main()
