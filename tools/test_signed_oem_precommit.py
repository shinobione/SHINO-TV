"""Host-executed EXACT C++ precommit guard; never calls ESP Updater or network.

The public test binary uses a disposable synthetic manufacturer reference and
OpenSSL EVP SHA-256 test adapter. The dormant firmware adapter uses ESP8266's
native BearSSL SHA-256. A passing RAW hash is *not* an RSA signature check.
"""
import hashlib
import json
from pathlib import Path
import shutil
import struct
import subprocess
import tempfile
import unittest

ROOT = Path(__file__).resolve().parent.parent
HEADER = ROOT / "firmware/include/recovery/SignedOemPrecommitGate.h"
INTEGRATION = ROOT / "firmware/src/recovery/SignedOemPrecommitProbe.cpp"
HARNESS = ROOT / "tools/signed_oem_precommit_host_probe.cpp"
BRIDGE = ROOT / "firmware/src/boot/FirstBootBridge.cpp"
ROLLBACK = ROOT / "firmware/src/recovery/FactoryRollback.cpp"
RAW_LEN = 494144
SIGNED_LEN = RAW_LEN + 256 + 4


@unittest.skipUnless(shutil.which("g++"), "CI must provide a host C++ compiler")
class ExactOemPrecommitHostTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.temp = tempfile.TemporaryDirectory(prefix="shino-oem-precommit-fixtures-")
        cls.root = Path(cls.temp.name)
        cls.bin = cls.root / "raw-precommit-probe"
        raw = bytearray(RAW_LEN)
        raw[0:8] = bytes([0xE9, 2, 2, 0x40, 0, 0, 0, 0])
        for offset in range(8, len(raw), 32):
            chunk = hashlib.sha256(offset.to_bytes(4, "little")).digest()
            raw[offset:offset+32] = chunk[:min(32, len(raw)-offset)]
        cls.raw = bytes(raw)
        digest = hashlib.sha256(cls.raw).hexdigest()
        (cls.root / "test_pin.h").write_text(
            '#define SHINO_TEST_PIN_SHA256 "' + digest + '"\n', encoding="utf-8"
        )
        build = subprocess.run(
            ["g++", "-std=c++17", "-Wall", "-Wextra", "-Werror", "-pedantic",
             "-I", str(ROOT/"firmware/include"), "-I", str(cls.root),
             str(HARNESS), "-o", str(cls.bin), "-lcrypto"],
            capture_output=True, text=True, timeout=40, check=False,
        )
        if build.returncode:
            raise AssertionError("C++ precommit probe compilation failed: " + build.stderr)

    @classmethod
    def tearDownClass(cls):
        cls.temp.cleanup()

    def setUp(self):
        self.package = self.root / "scenario.bin"
        self.trailer = bytes(range(256)) + struct.pack("<I", 256)
        self.package.write_bytes(self.raw + self.trailer)

    def probe(self, expected=True, *, chunk=4096, data=None):
        self.package.write_bytes(self.raw + self.trailer if data is None else data)
        result = subprocess.run(
            [str(self.bin), str(self.package), str(chunk), "1" if expected else "0"],
            capture_output=True, text=True, timeout=40, check=False,
        )
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        self.assertIn("no signature acceptance/HTTP/Update/flash writer", result.stdout)

    def test_exact_payload_in_split_chunks_including_header_and_trailer_boundaries(self):
        for chunk in (1, 2, 3, 7, 257, 4095, 4096):
            with self.subTest(chunk=chunk):
                self.probe(chunk=chunk)

    def test_signed_transport_length_is_exact_and_only_raw_bytes_are_hashed(self):
        self.assertEqual(len(self.raw), RAW_LEN)
        self.assertEqual(len(self.raw+self.trailer), SIGNED_LEN)
        # The precommit guard must accept raw-exact even when RSA trailer is
        # modified. The separate core RSA verifier MUST reject bad signatures.
        corrupt_signature = bytearray(self.trailer)
        corrupt_signature[12] ^= 0x01
        self.probe(data=self.raw+corrupt_signature)

    def test_rejects_one_changed_raw_byte_even_if_trailer_length_is_valid(self):
        raw = bytearray(self.raw)
        raw[12345] ^= 1
        self.probe(expected=False, data=raw+self.trailer)

    def test_rejects_header_changes_at_every_first_header_byte(self):
        for position in range(4):
            with self.subTest(position=position):
                raw = bytearray(self.raw)
                raw[position] ^= 1
                self.probe(expected=False, data=raw+self.trailer, chunk=1)

    def test_rejects_wrong_rsa_trailer_sizes(self):
        for length in (0, 1, 255, 257, 65536, 0xffffffff):
            with self.subTest(length=length):
                self.probe(expected=False,
                           data=self.raw+self.trailer[:256]+struct.pack("<I",length))

    def test_rejects_short_or_overlong_package_without_recursing(self):
        data = self.raw + self.trailer
        for sample in (data[:-1], data[:RAW_LEN], data[:-260], data + b"x"):
            with self.subTest(length=len(sample)):
                self.probe(expected=False, data=sample)

    def test_rejects_oversized_chunk_even_if_image_is_correct(self):
        self.probe(expected=False, chunk=4097)

    def test_source_has_no_writer_routes_and_frozen_pin_matches_manifest(self):
        gate=HEADER.read_text(encoding="utf-8")
        integration=INTEGRATION.read_text(encoding="utf-8")
        bridge=BRIDGE.read_text(encoding="utf-8")
        rollback=ROLLBACK.read_text(encoding="utf-8")
        manifest=json.loads((ROOT/"recovery/factory_ota_v9_0_44.json").read_text(encoding="utf-8"))
        self.assertIn(manifest["firmware_sha256"],gate)
        self.assertEqual(manifest["firmware_bytes"],RAW_LEN)
        self.assertIn("br_sha256_init",integration)
        self.assertIn("br_sha256_update",integration)
        self.assertIn("br_sha256_out",integration)
        self.assertIn("template class SignedOemPrecommitGate<BearSslSha256, ProductionV9044Pin>;",integration)
        self.assertNotIn("compiledReadOnlyExactOemProbe",integration)
        self.assertNotIn("SignedOemPrecommitProbe.cpp",bridge)
        self.assertNotIn("SignedOemPrecommitGate.h",bridge)
        self.assertNotIn("SignedOemPrecommitGate.h",rollback)
        for text in (gate,integration):
            without_comments="\n".join(line for line in text.splitlines()
                                         if not line.lstrip().startswith("//"))
            for forbidden in ("Update.begin(", "Update.end(", "Update.write(",
                              "installSignature(", "ESP8266WebServer",
                              "LittleFS.", "EEPROM.", "ESP.restart("):
                self.assertNotIn(forbidden,without_comments)

if __name__ == "__main__":
    unittest.main()
