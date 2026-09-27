"""No-network synthetic safety tests for the private owner Windows build kit."""
import hashlib
import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch
from zipfile import ZipFile, ZIP_DEFLATED

import build_private_owner_packet as kit
from verify_factory_ota import inspect_archive


def fake_image(size):
    seed = b"".join(hashlib.sha256(i.to_bytes(4,"little")).digest()
                    for i in range((size+31)//32))
    return bytes([0xE9,2,2,0x40,0x40,0xF4,0x10,0x40]) + seed[:size-8]


class OwnerKitTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.base = Path(self.tmp.name)
        self.root = self.base / "source"
        (self.root / ".git").mkdir(parents=True)
        (self.root / "firmware/include").mkdir(parents=True)
        (self.root / "firmware/private").mkdir(parents=True)
        (self.root / "firmware/.pio/build/esp12e").mkdir(parents=True)
        (self.root / "firmware/data").mkdir(parents=True)
        (self.root / "recovery").mkdir(parents=True)
        self.original = fake_image(494144)
        self.oem_zip = self.base / "manufacturer.zip"
        with ZipFile(self.oem_zip, "w", ZIP_DEFLATED) as z:
            z.writestr("FW-Smalltv-Ultra-V9.0.44.bin", self.original)
        (self.root / "recovery/factory_ota_v9_0_44.json").write_text(
            json.dumps(inspect_archive(self.oem_zip)))
        (self.root / "firmware/platformio.ini").write_text(
            "[env:esp12e]\nboard=esp12e\nboard_build.flash_size=4MB\n"
            "board_build.flash_mode=dio\nboard_build.ldscript=eagle.flash.4m3m.ld\n")
        self.policy = self.root / "firmware/include/shino_private_policy.h"
        self.creds = self.root / "firmware/private/credentials.txt"
        self.app = self.root / "firmware/.pio/build/esp12e/firmware.bin"
        self.output = self.base / "only-private-local" / "kit-001"
        self.output.parent.mkdir()
        self.sha = "a" * 40
        self.ap = "random_ap_password_000000000"
        self.http = "random_digest_password_1111111111"
        self.token = "random_api_token_22222222222222"

    def tearDown(self):
        self.tmp.cleanup()

    def make_build(self):
        self.policy.write_text(
            '#define SHINO_BOOT_PROFILE 0\n'
            '#define SHINO_ENABLE_FACTORY_RESTORE 1\n'
            '#define SHINO_FS_IMAGE_PRESENT 0\n'
            '#define SHINO_ENABLE_FS_MIGRATION 0\n'
            '#define SHINO_FACTORY_BYTES 494144\n'
            f'#define SHINO_FACTORY_MD5 "{hashlib.md5(self.original,usedforsecurity=False).hexdigest()}"\n'
            f'#define SHINO_FACTORY_SHA256 "{hashlib.sha256(self.original).hexdigest()}"\n'
            f'#define SHINO_SETUP_AP_PSK "{self.ap}"\n'
            f'#define SHINO_BOOTSTRAP_API_TOKEN "{self.token}"\n'
            '#define SHINO_RESCUE_HTTP_USER "shino"\n'
            f'#define SHINO_RESCUE_HTTP_PASSWORD "{self.http}"\n'
        )
        self.creds.write_text(
            "PRIVATE owner credentials\n"
            "First-boot Wi-Fi SSID: SHINO-FirstBoot-<chip-id>\n"
            f"Setup/rescue Wi-Fi password: {self.ap}\n"
            f"Initial API bearer token: {self.token}\n"
            "Rescue HTTP Digest user: shino\n"
            f"Rescue HTTP Digest password: {self.http}\n"
        )
        markers = (b"FIRST_BOOT_BRIDGE" + b"FSLESS_PC_TELEMETRY_RAM_ONLY"
                   + b"READ_ONLY_FS_MIGRATION_PLAN" + b"RAM_SAMPLE_ACCEPTED"
                   + b"Verified OEM application image"
                   + hashlib.md5(self.original,usedforsecurity=False).hexdigest().encode()
                   + self.ap.encode() + self.http.encode())
        self.app.write_bytes(fake_image(398848-len(markers)) + markers)

    def make_candidate_only(self):
        markers = (b"FIRST_BOOT_BRIDGE" + b"FSLESS_PC_TELEMETRY_RAM_ONLY"
                   + b"READ_ONLY_FS_MIGRATION_PLAN" + b"RAM_SAMPLE_ACCEPTED"
                   + b"Verified OEM application image"
                   + hashlib.md5(self.original,usedforsecurity=False).hexdigest().encode()
                   + self.ap.encode() + self.http.encode())
        self.app.write_bytes(fake_image(398848-len(markers)) + markers)

    def patch_paths(self):
        return patch.multiple(kit, ROOT=self.root, POLICY=self.policy,
                              CREDENTIALS=self.creds, APP=self.app)

    def test_refuses_output_inside_repository_or_existing_and_old_credentials(self):
        with self.patch_paths():
            with self.assertRaisesRegex(kit.OwnerKitError, "OUTSIDE"):
                kit.output_policy(self.oem_zip, self.root / "research-local" / "kit")
            self.output.mkdir()
            with self.assertRaisesRegex(kit.OwnerKitError, "exists"):
                kit.output_policy(self.oem_zip, self.output)
            self.output.rmdir()
            self.policy.write_text("older private keys")
            with self.assertRaisesRegex(kit.OwnerKitError, "Old generated"):
                kit.output_policy(self.oem_zip, self.output)

    def test_requires_explicit_frozen_source_sha_even_with_clean_checkout(self):
        with self.patch_paths(), patch.object(kit, "require_clean_frozen_checkout", return_value=self.sha):
            with self.assertRaisesRegex(kit.OwnerKitError, "reviewed source SHA"):
                kit.write_private_kit(self.oem_zip, self.output, "b" * 40)

    def test_private_kit_all_checks_are_local_and_public_manifest_has_no_secrets(self):
        calls=[]
        def local(command, *, cwd=None, output=True):
            calls.append(command)
            if any(str(arg).endswith("generate_shino_device_policy.py") for arg in command):
                self.make_build()
                self.app.unlink()
            if "platformio" in command:
                self.make_candidate_only()
            if "image-info" in command:
                return "Detected image type: ESP8266\nChecksum: 0x2b (valid)"
            return ""
        with self.patch_paths(), patch.object(kit, "require_clean_frozen_checkout", return_value=self.sha), \
                patch.object(kit, "run", side_effect=local):
            result=kit.write_private_kit(self.oem_zip, self.output, self.sha)
            self.assertEqual(result["status"], "PRIVATE_KIT_READY_FOR_REVIEW__OWNER_FLASH_NOT_AUTHORIZED")
            self.assertFalse(result["device_contacted"])
            self.assertTrue(self.output.exists())
            self.assertFalse(self.creds.exists(), "No generated credentials left in working checkout")
            self.assertFalse(self.policy.exists(), "No generated policy left in working checkout")
            self.assertFalse(self.app.exists(), "No duplicate application BIN left inside working checkout")
            manifest=json.loads((self.output/"REVIEW-ONLY-MANIFEST.json").read_text())
            self.assertFalse(manifest["owner_ready_to_flash"])
            self.assertFalse(manifest["review"]["permission_to_flash"])
            self.assertEqual(manifest["source_commit"], self.sha)
            self.assertEqual(manifest["files"][kit.APP_NAME]["bytes"],398848)
            self.assertEqual(manifest["files"][kit.OEM_NAME]["bytes"],494144)
            body=json.dumps(manifest)
            for value in (self.ap,self.http,self.token):
                self.assertNotIn(value,body)
            self.assertEqual((self.output/"credentials.txt").is_file(),True)
            self.assertEqual((self.output/"shino_private_policy.h").is_file(),True)
            self.assertEqual(sum("image-info" in cmd for cmd in calls),2)
            for cmd in calls:
                self.assertFalse(any("/update" in str(t) or "--port" == str(t) or
                                     "write-flash" == str(t) for t in cmd))

    def test_failure_keeps_no_incomplete_private_kit_or_checkout_secret(self):
        def local(command, *, cwd=None, output=True):
            if any(str(arg).endswith("generate_shino_device_policy.py") for arg in command):
                self.make_build()
            if "platformio" in command:
                raise kit.OwnerKitError("Expected synthetic compile failure")
            return ""
        with self.patch_paths(), patch.object(kit, "require_clean_frozen_checkout", return_value=self.sha), \
                patch.object(kit, "run", side_effect=local):
            with self.assertRaisesRegex(kit.OwnerKitError, "compile failure"):
                kit.write_private_kit(self.oem_zip, self.output, self.sha)
            self.assertFalse(self.output.exists())
            self.assertFalse(self.policy.exists())
            self.assertFalse(self.creds.exists())
            self.assertFalse(any(self.output.parent.glob(".shino-review-incomplete-*")))


if __name__ == "__main__":
    unittest.main()
