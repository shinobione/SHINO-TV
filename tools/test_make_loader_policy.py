import hashlib
import json
import tempfile
import unittest
from pathlib import Path
from zipfile import ZIP_DEFLATED, ZipFile

from make_loader_policy import FactoryOtaError, generate
from verify_factory_ota import inspect_archive


def synthetic_image():
    randomish = b"".join(hashlib.sha256(i.to_bytes(4, "little")).digest()
                         for i in range(2600))
    return bytes([0xE9, 2, 0, 0x40, 0x40, 0, 0, 0]) + randomish


class LoaderPolicyTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.root = Path(self.tmp.name)
        self.zip = self.root / "factory.zip"
        self.manifest = self.root / "pin.json"
        self.header = self.root / "local_policy.h"
        self.secrets = self.root / "private" / "credentials.txt"
        self.image = synthetic_image()
        with ZipFile(self.zip, "w", compression=ZIP_DEFLATED) as z:
            z.writestr("FW-Smalltv-Ultra-V9.0.44.bin", self.image)
        self.manifest.write_text(json.dumps(inspect_archive(self.zip)))

    def tearDown(self):
        self.tmp.cleanup()

    def test_readonly_default_has_unique_private_secrets(self):
        result = generate(self.zip, self.manifest, self.header, self.secrets)
        cfg = self.header.read_text()
        self.assertIn("#define SHINO_ENABLE_LOADER_WRITES 0", cfg)
        self.assertIn("#define SHINO_FACTORY_BYTES", cfg)
        self.assertIn("SHINO_FACTORY_MD5", cfg)
        self.assertEqual(result["candidate_size"], 0)
        self.assertTrue(self.secrets.is_file())
        self.assertNotIn("Wi-Fi password:", json.dumps(result))

    def test_write_enabled_requires_pinned_candidate(self):
        with self.assertRaisesRegex(FactoryOtaError, "REQUIRE"):
            generate(self.zip, self.manifest, self.header, self.secrets, writes=True)
        self.assertFalse(self.header.exists())

    def test_write_enabled_header_pins_candidate(self):
        candidate = self.root / "candidate.bin"
        candidate.write_bytes(self.image + b"another safe test payload")
        result = generate(self.zip, self.manifest, self.header, self.secrets,
                          candidate=candidate, writes=True)
        cfg = self.header.read_text()
        self.assertIn("#define SHINO_ENABLE_LOADER_WRITES 1", cfg)
        self.assertIn(str(result["candidate_size"]), cfg)
        self.assertIn(hashlib.md5(candidate.read_bytes(), usedforsecurity=False).hexdigest(), cfg)

    def test_existing_policy_or_credentials_not_overwritten(self):
        self.header.write_text("do not replace")
        with self.assertRaisesRegex(FactoryOtaError, "never overwrite"):
            generate(self.zip, self.manifest, self.header, self.secrets)
        self.assertEqual(self.header.read_text(), "do not replace")

    def test_wrong_factory_archive_refused_before_creating_keys(self):
        wrong = json.loads(self.manifest.read_text())
        wrong["zip_sha256"] = "1" * 64
        self.manifest.write_text(json.dumps(wrong))
        with self.assertRaisesRegex(FactoryOtaError, "PIN MISMATCH"):
            generate(self.zip, self.manifest, self.header, self.secrets)
        self.assertFalse(self.header.exists())

    def test_bad_candidate_refused(self):
        candidate = self.root / "not_esp.bin"
        candidate.write_bytes(b"x" * 100_000)
        with self.assertRaisesRegex(FactoryOtaError, "ESP8266"):
            generate(self.zip, self.manifest, self.header, self.secrets,
                     candidate=candidate, writes=True)
        self.assertFalse(self.header.exists())


if __name__ == "__main__":
    unittest.main()
