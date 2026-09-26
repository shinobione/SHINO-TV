import hashlib
import json
import tempfile
import unittest
from pathlib import Path
from zipfile import ZipFile, ZIP_DEFLATED

from verify_factory_ota import FactoryOtaError, inspect_archive, verify_archive


def sample_image():
    # Synthetic input generated locally: no OEM code/binary is redistributed.
    payload = b"".join(hashlib.sha256(i.to_bytes(4, "little")).digest() for i in range(2400))
    return bytes([0xE9, 3, 0, 0x40, 0x40, 0, 0, 0]) + payload


class OfficialOtaGateTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.root = Path(self.temp.name)
        self.path = self.root / "factory.zip"
        with ZipFile(self.path, "w", compression=ZIP_DEFLATED) as z:
            z.writestr("FW-Smalltv-Ultra-V9.0.44.bin", sample_image())

    def tearDown(self):
        self.temp.cleanup()

    def manifest(self):
        manifest = self.root / "pin.json"
        manifest.write_text(json.dumps(inspect_archive(self.path)), encoding="utf-8")
        return manifest

    def test_pinned_reference_matches(self):
        manifest = self.manifest()
        metadata = verify_archive(self.path, manifest)
        self.assertEqual(metadata["firmware_magic"], "0xE9")
        self.assertEqual(metadata["firmware_segments"], 3)
        self.assertIn("NOT a complete flash backup", metadata["recovery_scope"])

    def test_modified_reference_rejected(self):
        manifest = self.manifest()
        with ZipFile(self.path, "w", compression=ZIP_DEFLATED) as z:
            z.writestr("FW-Smalltv-Ultra-V9.0.44.bin", sample_image() + b"tampered")
        with self.assertRaisesRegex(FactoryOtaError, "PIN MISMATCH"):
            verify_archive(self.path, manifest)

    def test_bad_header_rejected(self):
        with ZipFile(self.path, "w", compression=ZIP_DEFLATED) as z:
            z.writestr("bad.bin", b"NOTESP86" + sample_image()[8:])
        with self.assertRaisesRegex(FactoryOtaError, "0xE9"):
            inspect_archive(self.path)

    def test_zip_slip_rejected(self):
        with ZipFile(self.path, "w", compression=ZIP_DEFLATED) as z:
            z.writestr("../firmware.bin", sample_image())
        with self.assertRaisesRegex(FactoryOtaError, "Unsafe"):
            inspect_archive(self.path)

    def test_zero_or_multiple_bin_members_rejected(self):
        with ZipFile(self.path, "w", compression=ZIP_DEFLATED) as z:
            z.writestr("notes.txt", sample_image())
        with self.assertRaisesRegex(FactoryOtaError, "exactly one"):
            inspect_archive(self.path)
        with ZipFile(self.path, "w", compression=ZIP_DEFLATED) as z:
            z.writestr("firmware1.bin", sample_image())
            z.writestr("firmware2.bin", sample_image())
        with self.assertRaisesRegex(FactoryOtaError, "exactly one"):
            inspect_archive(self.path)

    def test_wrong_digest_even_with_same_zip_filename_rejected(self):
        manifest = self.manifest()
        data = json.loads(manifest.read_text())
        data["zip_sha256"] = "0" * 64
        manifest.write_text(json.dumps(data))
        with self.assertRaisesRegex(FactoryOtaError, "zip_sha256"):
            verify_archive(self.path, manifest)


if __name__ == "__main__":
    unittest.main()
