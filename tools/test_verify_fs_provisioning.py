import hashlib
import json
import tempfile
import unittest
from pathlib import Path

from verify_fs_provisioning import (
    FsInspectionError, EXPECTED_BLANK_CONFIG, SHINO_FS_BYTES,
    inspect, validate_source, check_platformio,
)


class LittleFsOfflineSafetyTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.root = Path(self.tmp.name)
        self.data = self.root / "data"
        (self.data / "web" / "js").mkdir(parents=True)
        (self.data / "web" / "index.html").write_text("<h1>SHINO</h1>")
        (self.data / "web" / "js" / "main.js").write_text("/* no update handler */")
        (self.data / "config.json").write_text(json.dumps(EXPECTED_BLANK_CONFIG))
        self.ini = self.root / "platformio.ini"
        self.ini.write_text(
            "[env:esp12e]\nboard=esp12e\nboard_build.flash_size=4MB\n"
            "board_build.flash_mode=dio\nboard_build.filesystem=littlefs\n"
            "board_build.ldscript=eagle.flash.4m2m.ld\n"
        )
        self.image = self.root / "littlefs.bin"
        self.image.write_bytes(b"\x5a" * SHINO_FS_BYTES)

    def tearDown(self):
        self.tmp.cleanup()

    def test_exact_image_reports_destructive_overlap_and_no_permission(self):
        result = inspect(self.image, self.data, self.ini)
        self.assertEqual(result["image_bytes"], 2072576)
        self.assertEqual(result["image_sha256"], hashlib.sha256(self.image.read_bytes()).hexdigest())
        self.assertEqual(result["shino_fs_overlaps_inferred_stock_bytes"], SHINO_FS_BYTES)
        self.assertEqual(result["full_fs_atomic_staging_candidate_start"], "0x006000")
        self.assertFalse(result["full_fs_atomic_staging_can_coexist_with_running_bridge"])
        self.assertFalse(result["owner_FS_migration_permission"])
        self.assertFalse(result["first_boot_migration_writer_compiled"])
        self.assertFalse(result["device_read_or_upload_performed"])

    def test_truncated_image_rejected(self):
        self.image.write_bytes(b"x" * 4096)
        with self.assertRaisesRegex(FsInspectionError, "exactly"):
            inspect(self.image, self.data, self.ini)

    def test_no_real_passwords_in_seed_config(self):
        config = dict(EXPECTED_BLANK_CONFIG, wifi_password="my-password")
        (self.data / "config.json").write_text(json.dumps(config))
        with self.assertRaisesRegex(FsInspectionError, "no credentials"):
            inspect(self.image, self.data, self.ini)

    def test_legacy_generic_ota_script_refused(self):
        (self.data / "web" / "js" / "otaUploadHandler.js").write_text(
            "fetch('/api/v1/ota/fs')"
        )
        with self.assertRaisesRegex(FsInspectionError, "Legacy arbitrary-OTA"):
            inspect(self.image, self.data, self.ini)

    def test_no_unreviewed_private_files(self):
        (self.data / "private.txt").write_text("secret")
        with self.assertRaisesRegex(FsInspectionError, "Unreviewed"):
            inspect(self.image, self.data, self.ini)

    def test_source_symlink_refused(self):
        target = self.root / "elsewhere"
        target.write_text("unsafe")
        (self.data / "web" / "linked.html").symlink_to(target)
        with self.assertRaisesRegex(FsInspectionError, "Symlinks"):
            validate_source(self.data)

    def test_layout_change_rejected(self):
        self.ini.write_text(self.ini.read_text().replace("4m2m", "4m1m"))
        with self.assertRaisesRegex(FsInspectionError, "geometry"):
            check_platformio(self.ini)

    def test_no_inferred_stock_fs_backup_from_valid_image(self):
        report = inspect(self.image, self.data, self.ini)
        self.assertTrue(report["OEM_application_OTA_zip_cannot_restore_stock_filesystem"])
        self.assertTrue(report["incorrect_or_interrupted_stream_can_erase_original_data_BEFORE_MD5_check"])
        self.assertEqual(report["status"], "OFFLINE_IMAGE_INTEGRITY_ONLY__FS_WRITER_NOT_AUTHORIZED")


if __name__ == "__main__":
    unittest.main()
