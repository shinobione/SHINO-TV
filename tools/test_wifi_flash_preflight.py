import hashlib
import json
import tempfile
import unittest
from pathlib import Path
from zipfile import ZIP_DEFLATED, ZipFile

from verify_factory_ota import inspect_archive
from wifi_flash_preflight import (PreflightError, evaluate, inspect_image,
                                  platformio_layout, staging_model)


def fake_image(size: int, mode: int = 2, sizeflag: int = 4) -> bytes:
    body = b"".join(hashlib.sha256(i.to_bytes(4, "little")).digest() for i in range((size + 31) // 32))
    return bytes([0xE9, 2, mode, sizeflag << 4, 0x40, 0xF4, 0x10, 0x40]) + body[:size - 8]


class WiFiPreflightTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.root = Path(self.tmp.name)
        self.oem_zip = self.root / "original.zip"
        self.oem = fake_image(494144)
        with ZipFile(self.oem_zip, "w", compression=ZIP_DEFLATED) as z:
            z.writestr("FW-Smalltv-Ultra-V9.0.44.bin", self.oem)
        self.manifest = self.root / "pin.json"
        self.manifest.write_text(json.dumps(inspect_archive(self.oem_zip)))
        self.candidate = self.root / "candidate.bin"
        oem_md5 = hashlib.md5(self.oem, usedforsecurity=False).hexdigest().encode()
        # Synthetic candidate explicitly embeds the OEM image pin as our C++ route must.
        self.candidate.write_bytes(fake_image(469968) + oem_md5)
        self.loader = self.root / "loader.bin"
        candidate_md5 = hashlib.md5(self.candidate.read_bytes(), usedforsecurity=False).hexdigest().encode()
        self.loader.write_bytes(fake_image(300000) + oem_md5 + candidate_md5)
        self.loader_ini = self.root / "loader.ini"
        self.shino_ini = self.root / "candidate.ini"
        self.loader_ini.write_text("[env:esp12e_recovery]\nboard = esp12e\nboard_build.flash_size=4MB\nboard_build.flash_mode=dio\nboard_build.ldscript=eagle.flash.4m1m.ld\n")
        self.shino_ini.write_text("[env:esp12e]\nboard = esp12e\nboard_build.flash_size=4MB\nboard_build.flash_mode=dio\nboard_build.ldscript=eagle.flash.4m2m.ld\n")

    def tearDown(self):
        self.tmp.cleanup()

    def check(self):
        return evaluate(self.oem_zip, self.manifest, self.loader, self.candidate,
                        self.loader_ini, self.shino_ini)

    def test_offline_preflight_never_approves_flash(self):
        result = self.check()
        self.assertFalse(result["permission_to_flash"])
        self.assertFalse(result["device_access_performed"])
        self.assertIn("NOT MEASURED", result["transitions"]["factory_to_loader"]["actual_owner_factory_OTA_available_bytes"])
        self.assertTrue(result["transitions"]["loader_to_shino"]["nominal_no_overlap"])
        self.assertTrue(result["transitions"]["shino_to_factory"]["nominal_no_overlap"])
        self.assertEqual(result["source_layouts"]["OEM_internal_FS_layout"], "UNKNOWN_FROM_APPLICATION_IMAGE_ALONE")

    def test_reject_readonly_loader_missing_pinned_oem(self):
        self.loader.write_bytes(fake_image(300000))
        with self.assertRaisesRegex(PreflightError, "OEM image digest"):
            self.check()

    def test_shino_application_missing_own_factory_return_is_rejected(self):
        self.candidate.write_bytes(fake_image(470000))
        with self.assertRaisesRegex(PreflightError, "own exact compiled OEM"):
            self.check()

    def test_reject_unpinned_candidate(self):
        b = bytearray(self.candidate.read_bytes())
        b[99] ^= 1
        self.candidate.write_bytes(b)
        with self.assertRaisesRegex(PreflightError, "candidate digest"):
            self.check()

    def test_reject_wrong_flash_mode_or_size(self):
        self.candidate.write_bytes(fake_image(470000, mode=0))
        with self.assertRaisesRegex(PreflightError, "DIO"):
            self.check()
        self.candidate.write_bytes(fake_image(470000, sizeflag=2))
        with self.assertRaisesRegex(PreflightError, "4-MiB"):
            self.check()

    def test_unknown_layout_rejected(self):
        self.loader_ini.write_text(self.loader_ini.read_text().replace("4m1m", "4m2m"))
        with self.assertRaisesRegex(PreflightError, "Unexpected source layout"):
            self.check()

    def test_wrong_original_manifest_fails(self):
        d = json.loads(self.manifest.read_text())
        d["zip_sha256"] = "0" * 64
        self.manifest.write_text(json.dumps(d))
        with self.assertRaisesRegex(ValueError, "PIN MISMATCH"):
            self.check()

    def test_staging_model_flags_overlap(self):
        model = staging_model(1_500_000, 1_000_000, 2 * 1024 * 1024)
        self.assertFalse(model["nominal_no_overlap"])
        self.assertLess(model["free_gap_bytes"], 0)

    def test_header_interpretation(self):
        x = inspect_image(fake_image(80000, mode=2, sizeflag=4), "test")
        self.assertEqual(x["flash_mode"], "DIO")
        self.assertEqual(x["flash_size_bytes_from_header"], 4 * 1024 * 1024)
        with self.assertRaisesRegex(PreflightError, "unsupported"):
            inspect_image(fake_image(80000, mode=9), "invalid")

    def test_reviewed_platformio_layout(self):
        name, fs_start = platformio_layout(self.shino_ini, "env:esp12e")
        self.assertEqual(name, "eagle.flash.4m2m.ld")
        self.assertEqual(fs_start, 2 * 1024 * 1024)


if __name__ == "__main__":
    unittest.main()
