"""Offline OpenSSL fixtures for ESP8266 signed OTA: no real key/device/flash."""
import hashlib
from pathlib import Path
import shutil
import struct
import subprocess
import sys
import tempfile
import unittest

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "tools"))
from verify_signed_ota_package import assess_signed, SignedPackageError


def cmd(*args):
    p = subprocess.run(args, capture_output=True, text=True, timeout=30, check=False)
    if p.returncode:
        raise RuntimeError("fixture OpenSSL command failed: " + p.stderr[:350])


@unittest.skipUnless(shutil.which("openssl"), "OpenSSL fixture utility unavailable")
class SignedPackageOfflineTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.root_ctx = tempfile.TemporaryDirectory(prefix="signed-ota-tests-")
        cls.root = Path(cls.root_ctx.name)
        cls.private = cls.root / "fixture-private.pem"
        cls.public = cls.root / "fixture-public.pem"
        cmd("openssl", "genpkey", "-algorithm", "RSA", "-pkeyopt",
            "rsa_keygen_bits:2048", "-out", str(cls.private))
        cmd("openssl", "pkey", "-in", str(cls.private),
            "-pubout", "-out", str(cls.public))
        cls.public_hash = hashlib.sha256(cls.public.read_bytes()).hexdigest()

    @classmethod
    def tearDownClass(cls):
        cls.root_ctx.cleanup()  # Deletes ephemeral fixture private key.

    def setUp(self):
        self.work = tempfile.TemporaryDirectory(prefix="test-", dir=self.root)
        self.addCleanup(self.work.cleanup)
        self.path = Path(self.work.name)
        self.raw = self.path / "candidate.bin"
        self.signed = self.path / "candidate.bin.signed"
        self.sig = self.path / "signature.bin"
        self.ini = self.path / "platformio.ini"
        self.ini.write_text(
            "[env:esp12e]\nboard = esp12e\nboard_build.flash_mode = dio\n"
            "board_build.flash_size = 4MB\nboard_build.ldscript = eagle.flash.4m3m.ld\n"
        )
        data = bytearray(100000)
        data[0:8] = bytes((0xE9, 2, 2, 0x40, 0, 0, 0, 0))
        for i, marker in enumerate((b"FIRST_BOOT_BRIDGE",
                                    b"FSLESS_PC_TELEMETRY_RAM_ONLY",
                                    b"RAM_SAMPLE_ACCEPTED")):
            start = 32 + i * 80
            data[start:start+len(marker)] = marker
        self.raw.write_bytes(data)
        self.raw_hash = hashlib.sha256(data).hexdigest()
        cmd("openssl", "dgst", "-sha256", "-sign", str(self.private),
            "-out", str(self.sig), str(self.raw))
        signature = self.sig.read_bytes()
        self.assertEqual(len(signature), 256)
        self.signed.write_bytes(data + signature + struct.pack("<I", len(signature)))

    def check(self, **overrides):
        kwargs = dict(
            expected_unsigned_sha256=self.raw_hash,
            expected_public_key_sha256=self.public_hash,
            current_sketch_bytes=400592,
            reported_free_sketch_bytes=647168,
            observed_physical_flash_bytes=4194304,
            platformio_ini=self.ini,
        )
        kwargs.update(overrides)
        return assess_signed(self.signed, self.public, **kwargs)

    def test_valid_real_rsa_signature_is_still_no_flash_permission(self):
        report = self.check()
        self.assertTrue(report["signature_verified_by_openssl"])
        self.assertEqual(report["signature_bytes"], 256)
        self.assertTrue(report["staging_model_uses_signed_transport_bytes"])
        self.assertEqual(report["unsigned_application_bytes"], 100000)
        for key in ("signature_verification_compiled_on_device",
                    "native_ota_writer_compiled", "hardware_or_network_contact",
                    "permission_to_flash"):
            self.assertIs(report[key], False)

    def test_rejects_unsigned_firmware(self):
        self.signed.write_bytes(self.raw.read_bytes())
        with self.assertRaises(SignedPackageError):
            self.check()

    def test_rejects_broken_signature_with_same_valid_raw_hash(self):
        data = bytearray(self.signed.read_bytes())
        data[-10] ^= 0x01
        self.signed.write_bytes(data)
        with self.assertRaisesRegex(SignedPackageError, "verification FAILED"):
            self.check()

    def test_rejects_mutated_payload_even_if_trailer_still_valid(self):
        data = bytearray(self.signed.read_bytes())
        data[2000] ^= 0x01
        self.signed.write_bytes(data)
        with self.assertRaisesRegex(SignedPackageError, "Unsigned image"):
            self.check()

    def test_rejects_trailer_length_mismatch(self):
        data = bytearray(self.signed.read_bytes())
        data[-4:] = struct.pack("<I", 100)
        self.signed.write_bytes(data)
        with self.assertRaisesRegex(SignedPackageError, "256-byte"):
            self.check()

    def test_rejects_appended_arbitrary_bytes(self):
        self.signed.write_bytes(self.signed.read_bytes() + b"garbage")
        with self.assertRaises(SignedPackageError):
            self.check()

    def test_rejects_altered_independent_trust_anchor(self):
        with self.assertRaisesRegex(SignedPackageError, "trust anchor"):
            self.check(expected_public_key_sha256="a" * 64)

    def test_rejects_altered_independent_unsigned_hash(self):
        with self.assertRaisesRegex(SignedPackageError, "independently reviewed"):
            self.check(expected_unsigned_sha256="b" * 64)

    def test_rejects_wrong_public_key_even_if_its_hash_is_supplied(self):
        other_private = self.path / "other-private.pem"
        other_public = self.path / "other-public.pem"
        cmd("openssl", "genpkey", "-algorithm", "RSA", "-pkeyopt",
            "rsa_keygen_bits:2048", "-out", str(other_private))
        cmd("openssl", "pkey", "-in", str(other_private), "-pubout", "-out", str(other_public))
        other_hash = hashlib.sha256(other_public.read_bytes()).hexdigest()
        with self.assertRaisesRegex(SignedPackageError, "verification FAILED"):
            assess_signed(self.signed, other_public,
                          expected_unsigned_sha256=self.raw_hash,
                          expected_public_key_sha256=other_hash,
                          current_sketch_bytes=400592,
                          reported_free_sketch_bytes=647168,
                          observed_physical_flash_bytes=4194304,
                          platformio_ini=self.ini)

    def test_rejects_overlong_signed_transport_though_raw_would_fit(self):
        with self.assertRaisesRegex(SignedPackageError, "staging model"):
            self.check(reported_free_sketch_bytes=102400)

    def test_rejects_wrong_layout(self):
        self.ini.write_text(self.ini.read_text().replace("eagle.flash.4m3m.ld",
                                                         "eagle.flash.4m2m.ld"))
        with self.assertRaisesRegex(SignedPackageError, "linker"):
            self.check()

    def test_rejects_unsigned_file_symlink(self):
        link = self.path / "link.bin.signed"
        try:
            link.symlink_to(self.signed)
        except (NotImplementedError, OSError):
            self.skipTest("No symlink privileges")
        with self.assertRaisesRegex(SignedPackageError, "regular local"):
            assess_signed(link, self.public,
                          expected_unsigned_sha256=self.raw_hash,
                          expected_public_key_sha256=self.public_hash,
                          current_sketch_bytes=400592,
                          reported_free_sketch_bytes=647168,
                          observed_physical_flash_bytes=4194304,
                          platformio_ini=self.ini)


if __name__ == "__main__":
    unittest.main()
