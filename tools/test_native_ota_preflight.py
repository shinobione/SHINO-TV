"""Offline-only native OTA research tests; no hardware, Wi-Fi or flash operations."""
import hashlib
from pathlib import Path
import sys
import tempfile
import unittest

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "tools"))
from native_ota_preflight import assess, NativeOtaGateError


def sample_image(*, mode=2, sizeflag=4, markers=True, size=100000):
    image = bytearray(size)
    image[0:8] = bytes((0xE9, 2, mode, (sizeflag << 4), 0, 0, 0, 0))
    if markers:
        image[20:20 + len(b"FIRST_BOOT_BRIDGE")] = b"FIRST_BOOT_BRIDGE"
        image[100:100 + len(b"FSLESS_PC_TELEMETRY_RAM_ONLY")] = b"FSLESS_PC_TELEMETRY_RAM_ONLY"
        image[200:200 + len(b"RAM_SAMPLE_ACCEPTED")] = b"RAM_SAMPLE_ACCEPTED"
    return bytes(image)


class NativeOtaOfflineGateTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.ini = self.root / "platformio.ini"
        self.ini.write_text(
            "[env:esp12e]\nboard = esp12e\nboard_build.flash_mode = dio\n"
            "board_build.flash_size = 4MB\nboard_build.ldscript = eagle.flash.4m3m.ld\n"
        )
        self.image = self.root / "candidate.bin"
        self.write(sample_image())

    def write(self, data):
        self.image.write_bytes(data)
        self.digest = hashlib.sha256(data).hexdigest()

    def check(self, **changes):
        args = dict(current_sketch_bytes=400592,
                    reported_free_sketch_bytes=647168,
                    observed_physical_flash_bytes=4194304,
                    platformio_ini=self.ini)
        args.update(changes)
        return assess(self.image, self.digest, **args)

    def test_valid_feasibility_is_still_explicit_no_install_no_network(self):
        result = self.check()
        self.assertEqual(result["source_layout"], "eagle.flash.4m3m.ld")
        self.assertEqual(result["estimated_inferred_stock_fs_sector_overlap_bytes"], 0)
        self.assertEqual(result["status"],
                         "OFFLINE_NATIVE_OTA_FEASIBILITY_ONLY__NO_INSTALL_PERMISSION")
        for key in ("signature_verification_implemented", "native_device_writer_compiled",
                    "hardware_or_network_contact", "firmware_or_filesystem_write",
                    "permission_to_flash"):
            self.assertIs(result[key], False)

    def test_rejects_mismatched_independently_reviewed_digest(self):
        with self.assertRaisesRegex(NativeOtaGateError, "SHA-256"):
            assess(self.image, "0" * 64, current_sketch_bytes=400592,
                   reported_free_sketch_bytes=647168,
                   observed_physical_flash_bytes=4194304, platformio_ini=self.ini)

    def test_rejects_invalid_digest_format(self):
        with self.assertRaisesRegex(NativeOtaGateError, "64-hex"):
            assess(self.image, "not-a-digest", current_sketch_bytes=400592,
                   reported_free_sketch_bytes=647168,
                   observed_physical_flash_bytes=4194304, platformio_ini=self.ini)

    def test_rejects_other_flash_mode_and_flash_size(self):
        self.write(sample_image(mode=0))
        with self.assertRaisesRegex(NativeOtaGateError, "header"):
            self.check()
        self.write(sample_image(sizeflag=2))
        with self.assertRaisesRegex(NativeOtaGateError, "header"):
            self.check()

    def test_rejects_absent_fsless_runtime_markers(self):
        self.write(sample_image(markers=False))
        with self.assertRaisesRegex(NativeOtaGateError, "marker"):
            self.check()

    def test_rejects_wrong_physical_flash_capacity(self):
        with self.assertRaisesRegex(NativeOtaGateError, "4-MiB"):
            self.check(observed_physical_flash_bytes=2097152)

    def test_rejects_short_runtime_free_sketch_space(self):
        with self.assertRaisesRegex(NativeOtaGateError, "margin"):
            self.check(reported_free_sketch_bytes=102400)

    def test_rejects_alternative_linker_layout(self):
        self.ini.write_text(self.ini.read_text().replace("eagle.flash.4m3m.ld", "eagle.flash.4m2m.ld"))
        with self.assertRaisesRegex(NativeOtaGateError, "4m3m"):
            self.check()

    def test_rejects_beyond_current_review_size_cap(self):
        self.write(sample_image(size=494145))
        with self.assertRaisesRegex(NativeOtaGateError, "research window"):
            self.check()

    def test_rejects_symlink_candidate(self):
        alias = self.root / "alias.bin"
        try:
            alias.symlink_to(self.image)
        except (OSError, NotImplementedError):
            self.skipTest("No symlink support on this platform")
        with self.assertRaisesRegex(NativeOtaGateError, "regular local"):
            assess(alias, self.digest, current_sketch_bytes=400592,
                   reported_free_sketch_bytes=647168,
                   observed_physical_flash_bytes=4194304, platformio_ini=self.ini)


class NativeOtaSourceBoundaries(unittest.TestCase):
    def test_no_new_writer_route_or_fs_writer_in_first_boot_bridge(self):
        bridge = (ROOT / "firmware/src/boot/FirstBootBridge.cpp").read_text()
        ui = (ROOT / "firmware/src/boot/FslessWebUI.cpp").read_text()
        self.assertIn('server.on("/api/v1/bridge/ota/capabilities", HTTP_GET', bridge)
        self.assertNotIn('server.on("/api/v1/bridge/ota/capabilities", HTTP_POST', bridge)
        self.assertIn('doc["native_ota_writer_compiled"] = false;', bridge)
        self.assertIn('doc["native_ota_upload_route_registered"] = false;', bridge)
        self.assertIn('if (!browserSessionValid() && !requireAuth()) return;', bridge)
        self.assertIn('READ-ONLY PREFLIGHT', ui)
        self.assertNotIn("<input type=\"file\"", ui)
        self.assertNotIn("Update.begin(", bridge)
        self.assertNotIn("LittleFS.begin(", bridge)
        self.assertNotIn("EEPROM.commit(", bridge)


if __name__ == "__main__":
    unittest.main()
