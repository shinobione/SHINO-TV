import hashlib
import json
import tempfile
import unittest
from pathlib import Path
from zipfile import ZIP_DEFLATED, ZipFile

from generate_shino_device_policy import generate, FactoryOtaError
from verify_factory_ota import inspect_archive


class ShinoDevicePolicyTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.root = Path(self.tmp.name)
        self.zip = self.root / "oem.zip"
        self.header = self.root / "include" / "shino_private_policy.h"
        self.cred = self.root / "private" / "credentials.txt"
        self.manifest = self.root / "reference.json"
        payload = b"".join(hashlib.sha256(i.to_bytes(4, "little")).digest() for i in range(2400))
        self.image = bytes([0xE9, 2, 2, 0x40, 0x80, 0xF4, 0x10, 0x40]) + payload
        with ZipFile(self.zip, "w", compression=ZIP_DEFLATED) as z:
            z.writestr("FW-Smalltv-Ultra-V9.0.44.bin", self.image)
        self.manifest.write_text(json.dumps(inspect_archive(self.zip)))
        self.fsroot = self.root / "data"
        (self.fsroot / "web").mkdir(parents=True)
        (self.fsroot / "web" / "index.html").write_text("<h1>SHINO</h1>")
        (self.fsroot / "config.json").write_text(json.dumps({
            "wifi_ssid": "", "wifi_password": "", "api_token": "", "lcd_rotation": 0
        }))
        self.fsimage = self.root / "littlefs.bin"
        self.fsimage.write_bytes(b"x" * 2072576)
        self.fsini = self.root / "platformio.ini"
        self.fsini.write_text(
            "[env:esp12e]\nboard=esp12e\nboard_build.flash_size=4MB\n"
            "board_build.flash_mode=dio\nboard_build.filesystem=littlefs\n"
            "board_build.ldscript=eagle.flash.4m2m.ld\n"
        )

    def tearDown(self):
        self.tmp.cleanup()

    def test_exact_pinned_reference_produces_distinct_private_secrets(self):
        report = generate(self.zip, self.manifest, self.header, self.cred,
                          fs_image=self.fsimage, fs_source_root=self.fsroot, fs_ini=self.fsini)
        self.assertEqual(report["device_operation"], "none")
        text = self.header.read_text()
        self.assertIn(hashlib.md5(self.image, usedforsecurity=False).hexdigest(), text)
        self.assertIn(hashlib.sha256(self.image).hexdigest(), text)
        self.assertIn("SHINO_RESCUE_HTTP_PASSWORD", text)
        self.assertIn("#define SHINO_BOOT_PROFILE 0", text)
        self.assertIn("#define SHINO_ENABLE_FACTORY_RESTORE 0", text)
        self.assertIn("#define SHINO_ENABLE_FS_MIGRATION 0", text)
        self.assertIn('#define SHINO_FS_BYTES 2072576', text)
        self.assertIn("#define SHINO_FS_IMAGE_PRESENT 1", text)
        self.assertIn(hashlib.sha256(self.fsimage.read_bytes()).hexdigest(), text)
        self.assertTrue(self.cred.exists())
        self.assertNotIn("Initial API bearer token:", json.dumps(report))
        self.assertNotIn("SHINO_SETUP_AP_PSK", json.dumps(report))

    def test_experimental_return_does_not_enable_full_boot_or_fs_format(self):
        result = generate(self.zip, self.manifest, self.header, self.cred, enable_restore=True,
                          fs_image=self.fsimage, fs_source_root=self.fsroot, fs_ini=self.fsini)
        policy = self.header.read_text()
        self.assertIn("#define SHINO_ENABLE_FACTORY_RESTORE 1", policy)
        self.assertIn("#define SHINO_BOOT_PROFILE 0", policy)
        self.assertEqual(result["boot_profile"], "FIRST_BOOT_BRIDGE_ONLY")

    def test_default_fsless_policy_needs_no_image_and_no_writer(self):
        report = generate(self.zip, self.manifest, self.header, self.cred)
        policy = self.header.read_text()
        self.assertEqual(report["fs_image_present"], False)
        self.assertEqual(report["fs_image_sha256"], None)
        self.assertIn("#define SHINO_FS_IMAGE_PRESENT 0", policy)
        self.assertIn('#define SHINO_FS_SHA256 ""', policy)
        self.assertIn("#define SHINO_ENABLE_FS_MIGRATION 0", policy)
        self.assertNotIn("littlefs.bin", policy)


    def test_refuses_changed_fs_image_size(self):
        from verify_fs_provisioning import FsInspectionError
        self.fsimage.write_bytes(b"x" * 4096)
        with self.assertRaisesRegex(FsInspectionError, "length"):
            generate(self.zip, self.manifest, self.header, self.cred,
                     fs_image=self.fsimage, fs_source_root=self.fsroot, fs_ini=self.fsini)
        self.assertFalse(self.header.exists())

    def test_rejects_wrong_oem_digest_without_creating_credentials(self):
        pin = json.loads(self.manifest.read_text())
        pin["firmware_sha256"] = "0" * 64
        self.manifest.write_text(json.dumps(pin))
        with self.assertRaisesRegex(FactoryOtaError, "PIN MISMATCH"):
            generate(self.zip, self.manifest, self.header, self.cred,
                          fs_image=self.fsimage, fs_source_root=self.fsroot, fs_ini=self.fsini)
        self.assertFalse(self.header.exists())

    def test_never_overwrites_existing_keys(self):
        self.cred.parent.mkdir(parents=True)
        self.cred.write_text("retain original secret")
        with self.assertRaisesRegex(FactoryOtaError, "already exists"):
            generate(self.zip, self.manifest, self.header, self.cred,
                          fs_image=self.fsimage, fs_source_root=self.fsroot, fs_ini=self.fsini)
        self.assertEqual(self.cred.read_text(), "retain original secret")
        self.assertFalse(self.header.exists())

    def test_different_builds_use_different_keys(self):
        first = self.root / "first.h"
        first_private = self.root / "first.txt"
        second = self.root / "second.h"
        second_private = self.root / "second.txt"
        generate(self.zip, self.manifest, first, first_private,
                 fs_image=self.fsimage, fs_source_root=self.fsroot, fs_ini=self.fsini)
        generate(self.zip, self.manifest, second, second_private,
                 fs_image=self.fsimage, fs_source_root=self.fsroot, fs_ini=self.fsini)
        self.assertNotEqual(first.read_text(), second.read_text())


if __name__ == "__main__":
    unittest.main()
