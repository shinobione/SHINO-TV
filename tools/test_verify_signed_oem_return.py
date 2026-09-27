"""Offline signed+exact manufacturer-return tests using synthetic OEM fixtures.

Production immutable OEM hash constants are patched ONLY inside fixture
unit tests. Fixture RSA signing private keys are generated in a disposable
temporary directory and deleted. No production manufacturer image, private
owner key, device network connection or firmware writer is used.
"""
from pathlib import Path
import hashlib
import json
import shutil
import struct
import subprocess
import sys
import tempfile
import unittest
from unittest.mock import patch
import zipfile

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "tools"))
import verify_signed_oem_return as oem
from verify_factory_ota import inspect_archive


def openssl(*args):
    r = subprocess.run(["openssl", *map(str, args)], capture_output=True,
                       text=True, timeout=30, check=False)
    if r.returncode:
        raise AssertionError("OpenSSL fixture command failed: " + r.stderr[:240])


@unittest.skipUnless(shutil.which("openssl"), "OpenSSL fixture command required")
class SignedPinnedOemResearchTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.tmp = tempfile.TemporaryDirectory(prefix="shino-test-oem-signing-")
        cls.root = Path(cls.tmp.name)
        cls.priv = cls.root / "test-signing-private.pem"
        cls.pub = cls.root / "test-signing-public.pem"
        openssl("genpkey", "-algorithm", "RSA", "-pkeyopt", "rsa_keygen_bits:2048",
                "-out", cls.priv)
        openssl("pkey", "-in", cls.priv, "-pubout", "-out", cls.pub)
        cls.pub_hash = hashlib.sha256(cls.pub.read_bytes()).hexdigest()

    @classmethod
    def tearDownClass(cls):
        cls.tmp.cleanup()  # Ephemeral fixture key is deleted; never added to repo.

    def setUp(self):
        self.work = tempfile.TemporaryDirectory(prefix="fixture-", dir=self.root)
        self.addCleanup(self.work.cleanup)
        self.dir = Path(self.work.name)
        self.original = self.dir / "FW-Smalltv-Ultra-V9.0.44.bin"
        self.archive = self.dir / "FW-Smalltv-Ultra-V9.0.44.zip"
        self.signed = self.dir / "OEM-OWNER-SIGNED.bin"
        self.signature = self.dir / "signed-fixture.sig"
        self.manifest = self.dir / "manifest.json"
        self.ini = self.dir / "platformio.ini"
        self.ini.write_text("[env:esp12e]\nboard = esp12e\n"
                            "board_build.flash_mode = dio\n"
                            "board_build.flash_size = 4MB\n"
                            "board_build.ldscript = eagle.flash.4m3m.ld\n")
        # A 494144-byte plausible test image; NEVER actual manufacturer firmware.
        image = bytearray(oem.OEM_BYTES)
        image[:8] = bytes([0xE9, 2, 2, 0x40, 0, 0, 0, 0])
        # Nontrivial member: ZIP meets existing archival lower-size bound.
        for offset in range(8, len(image), 32):
            image[offset:offset+32] = hashlib.sha256(
                offset.to_bytes(4, "little")).digest()[:min(32,len(image)-offset)]
        self.original.write_bytes(image)
        with zipfile.ZipFile(self.archive, "w", compression=zipfile.ZIP_DEFLATED) as z:
            z.write(self.original, self.original.name)
        self.metadata = inspect_archive(self.archive)
        self.manifest.write_text(json.dumps(self.metadata), encoding="utf-8")
        self.raw_hash = hashlib.sha256(image).hexdigest()
        # Patch production hard pins strictly inside the synthetic fixture's scope.
        p1 = patch.object(oem, "PINNED_OEM_SHA256", self.metadata["firmware_sha256"])
        p2 = patch.object(oem, "PINNED_OEM_ZIP_SHA256", self.metadata["zip_sha256"])
        p1.start(); self.addCleanup(p1.stop)
        p2.start(); self.addCleanup(p2.stop)
        self.make_signed(image)

    def make_signed(self, raw, signer=None):
        unsigned = self.dir / "unsigned-to-sign.bin"
        unsigned.write_bytes(raw)
        openssl("dgst", "-sha256", "-sign", signer or self.priv,
                "-out", self.signature, unsigned)
        signature = self.signature.read_bytes()
        self.assertEqual(len(signature), 256)
        self.signed.write_bytes(raw + signature + struct.pack("<I", len(signature)))

    def check(self, **overrides):
        kwargs = dict(expected_owner_public_key_sha256=self.pub_hash,
                      current_sketch_bytes=400592,
                      reported_free_sketch_bytes=647168,
                      observed_physical_flash_bytes=4194304,
                      platformio_ini=self.ini)
        kwargs.update(overrides)
        return oem.assess_signed_oem(
            self.signed, self.pub, self.archive, self.manifest, **kwargs)

    def test_positive_synthetic_oem_is_both_signed_and_byte_exact_but_no_flash_permission(self):
        result = self.check()
        self.assertEqual(result["status"], "SIGNED_EXACT_OEM_OFFLINE_VERIFIED__NO_INSTALL_PERMISSION")
        self.assertEqual(result["signed_transport_bytes"], 494404)
        self.assertEqual(result["manufacturer_application_bytes"], 494144)
        self.assertTrue(result["manufacturer_original_byte_for_byte_equal"])
        self.assertTrue(result["owner_signature_verified"])
        self.assertTrue(result["staging_uses_entire_signed_transport"])
        for name in ("on_device_signed_oem_writer_compiled", "hardware_or_network_access",
                     "permission_to_flash"):
            self.assertIs(result[name], False)

    def test_signed_but_modified_oem_is_rejected_even_under_owner_key(self):
        raw = bytearray(self.original.read_bytes())
        raw[9000] ^= 1
        self.make_signed(raw)
        with self.assertRaisesRegex(oem.SignedOemReturnError, "NOT exact pinned OEM"):
            self.check()

    def test_unsigned_legacy_oem_image_rejected(self):
        self.signed.write_bytes(self.original.read_bytes())
        with self.assertRaisesRegex(oem.SignedOemReturnError, "494404"):
            self.check()

    def test_signature_corruption_rejected(self):
        pkg = bytearray(self.signed.read_bytes()); pkg[-30] ^= 1
        self.signed.write_bytes(pkg)
        with self.assertRaisesRegex(oem.SignedOemReturnError, "signature did not verify"):
            self.check()

    def test_trailer_length_corruption_rejected(self):
        pkg = bytearray(self.signed.read_bytes()); pkg[-4:] = struct.pack("<I", 255)
        self.signed.write_bytes(pkg)
        with self.assertRaisesRegex(oem.SignedOemReturnError, "256-byte"):
            self.check()

    def test_appended_or_truncated_bytes_rejected(self):
        pkg = self.signed.read_bytes()
        self.signed.write_bytes(pkg + b"Z")
        with self.assertRaises(oem.SignedOemReturnError): self.check()
        self.signed.write_bytes(pkg[:-1])
        with self.assertRaises(oem.SignedOemReturnError): self.check()

    def test_wrong_owner_public_key_pin_rejected(self):
        with self.assertRaisesRegex(oem.SignedOemReturnError, "trust pin"):
            self.check(expected_owner_public_key_sha256="0"*64)

    def test_wrong_owner_key_even_with_corresponding_self_supplied_hash_rejected(self):
        priv = self.dir/"wrong-private.pem"; pub = self.dir/"wrong-public.pem"
        openssl("genpkey", "-algorithm", "RSA", "-pkeyopt", "rsa_keygen_bits:2048",
                "-out", priv)
        openssl("pkey", "-in", priv, "-pubout", "-out", pub)
        wrong_hash = hashlib.sha256(pub.read_bytes()).hexdigest()
        with self.assertRaisesRegex(oem.SignedOemReturnError, "signature did not verify"):
            oem.assess_signed_oem(
                self.signed, pub, self.archive, self.manifest,
                expected_owner_public_key_sha256=wrong_hash,
                current_sketch_bytes=400592, reported_free_sketch_bytes=647168,
                observed_physical_flash_bytes=4194304, platformio_ini=self.ini)

    def test_pinned_zip_mismatch_is_rejected_even_when_manifest_matches_substitute(self):
        with patch.object(oem, "PINNED_OEM_ZIP_SHA256", "e"*64):
            with self.assertRaisesRegex(oem.SignedOemReturnError, "immutable pinned"):
                self.check()

    def test_manifest_mismatch_rejected(self):
        m = json.loads(self.manifest.read_text()); m["firmware_sha256"] = "f"*64
        self.manifest.write_text(json.dumps(m))
        with self.assertRaisesRegex(oem.SignedOemReturnError, "pinned ZIP"):
            self.check()

    def test_wrong_flash_mode_or_layout_or_physical_capacity_rejected(self):
        with self.assertRaisesRegex(oem.SignedOemReturnError, "not 4 MiB"):
            self.check(observed_physical_flash_bytes=2097152)
        self.ini.write_text(self.ini.read_text().replace("4m3m","4m2m"))
        with self.assertRaisesRegex(oem.SignedOemReturnError, "4m3m"):
            self.check()

    def test_signed_payload_with_insufficient_staging_is_rejected(self):
        with self.assertRaisesRegex(oem.SignedOemReturnError, "staging"):
            self.check(reported_free_sketch_bytes=494404)

    def test_symlinked_signed_payload_or_trust_anchor_is_rejected(self):
        link = self.dir/"alias.bin"
        try: link.symlink_to(self.signed)
        except (OSError, NotImplementedError): self.skipTest("symlink unsupported")
        with self.assertRaisesRegex(oem.SignedOemReturnError, "regular local"):
            oem.assess_signed_oem(link,self.pub,self.archive,self.manifest,
                                  expected_owner_public_key_sha256=self.pub_hash,
                                  current_sketch_bytes=400592,
                                  reported_free_sketch_bytes=647168,
                                  observed_physical_flash_bytes=4194304,
                                  platformio_ini=self.ini)

    def test_production_oem_pins_are_immutable_literals_no_cli_override(self):
        src = (ROOT/"tools/verify_signed_oem_return.py").read_text()
        self.assertIn("a6421f5bfee7860d97bed26620c346b8008f503e513702d4bfdf6e01010a7718",src)
        self.assertIn("cfbef50754ec552f9791878931c5f3643734de15f3c81cebdecf7ce05b28230f",src)
        self.assertNotIn("--expected-oem-sha256",src)
        self.assertNotIn("--expected-oem-zip-sha256",src)
        self.assertNotIn("urllib.request",src)
        self.assertNotIn("Update.begin(",src)
        self.assertIn('"permission_to_flash": False',src)


if __name__ == "__main__":
    unittest.main()
