import hashlib
import json
import tempfile
import unittest
from pathlib import Path
from zipfile import ZIP_DEFLATED, ZipFile

from prepare_factory_rollback import prepare_factory_bin
from verify_factory_ota import FactoryOtaError, inspect_archive


class OfflineRollbackPreparationTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.root = Path(self.tmp.name)
        self.archive = self.root / "oem.zip"
        self.manifest = self.root / "manifest.json"
        self.destination = self.root / "verified.bin"
        payload = b"".join(hashlib.sha256(i.to_bytes(4, "little")).digest() for i in range(2400))
        self.image = bytes([0xE9, 2, 0, 0x40, 0x40, 0, 0, 0]) + payload
        with ZipFile(self.archive, "w", compression=ZIP_DEFLATED) as z:
            z.writestr("FW-Smalltv-Ultra-V9.0.44.bin", self.image)
        self.manifest.write_text(json.dumps(inspect_archive(self.archive)), encoding="utf-8")

    def tearDown(self):
        self.tmp.cleanup()

    def test_only_extracts_an_exactly_matching_archive(self):
        result = prepare_factory_bin(self.archive, self.manifest, self.destination)
        self.assertEqual(self.destination.read_bytes(), self.image)
        self.assertEqual(result["sha256"], hashlib.sha256(self.image).hexdigest())
        self.assertEqual(result["device_communication"], "none")

    def test_existing_output_is_never_overwritten(self):
        self.destination.write_bytes(b"important old backup")
        with self.assertRaisesRegex(FactoryOtaError, "overwrite"):
            prepare_factory_bin(self.archive, self.manifest, self.destination)
        self.assertEqual(self.destination.read_bytes(), b"important old backup")

    def test_manifest_mismatch_makes_no_output(self):
        manifest = json.loads(self.manifest.read_text())
        manifest["firmware_sha256"] = "0" * 64
        self.manifest.write_text(json.dumps(manifest), encoding="utf-8")
        with self.assertRaisesRegex(FactoryOtaError, "PIN MISMATCH"):
            prepare_factory_bin(self.archive, self.manifest, self.destination)
        self.assertFalse(self.destination.exists())

    def test_refuse_non_bin_output(self):
        with self.assertRaisesRegex(FactoryOtaError, "end with .bin"):
            prepare_factory_bin(self.archive, self.manifest, self.root / "not-a-bin.txt")


if __name__ == "__main__":
    unittest.main()
