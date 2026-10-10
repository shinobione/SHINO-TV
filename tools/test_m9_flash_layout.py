import tempfile
import unittest
from pathlib import Path

from m9_flash_layout import (
    FLASH_BYTES,
    FS_END,
    FS_START,
    LINKER_MAX_APP_BYTES,
    P1_APP_BYTES,
    LayoutError,
    align_sector,
    inspect_platformio,
    ota_geometry,
)


class Mission9FlashLayoutTests(unittest.TestCase):
    def test_exact_4m2m_geometry(self):
        self.assertEqual(FLASH_BYTES, 4_194_304)
        self.assertEqual(FS_START, 0x200000)
        self.assertEqual(FS_END, 0x3FA000)
        self.assertEqual(FS_END - FS_START, 2_072_576)
        self.assertEqual(FLASH_BYTES - FS_END, 24_576)

    def test_linker_max_rounds_to_ff000(self):
        self.assertEqual(LINKER_MAX_APP_BYTES, 1_044_464)
        self.assertEqual(align_sector(LINKER_MAX_APP_BYTES), 0xFF000)

    def test_max_to_max_has_two_sector_gap(self):
        result = ota_geometry(LINKER_MAX_APP_BYTES, LINKER_MAX_APP_BYTES)
        self.assertTrue(result["candidate_passes"])
        self.assertEqual(result["stage_start"], 0x101000)
        self.assertEqual(result["gap_between_current_and_staging_bytes"], 0x2000)

    def test_installed_p1_can_stage_linker_max(self):
        result = ota_geometry(P1_APP_BYTES, LINKER_MAX_APP_BYTES)
        self.assertTrue(result["candidate_passes"])
        self.assertEqual(result["current_rounded_bytes"], 0x72000)
        self.assertEqual(result["stage_start"], 0x101000)
        self.assertEqual(result["gap_between_current_and_staging_bytes"], 585_728)

    def test_reject_non_linkable_target_even_if_geometry_would_fit(self):
        result = ota_geometry(P1_APP_BYTES, 0x100000)
        self.assertTrue(result["ota_geometry_fits"])
        self.assertFalse(result["linker_target_fits"])
        self.assertFalse(result["candidate_passes"])

    def test_invalid_sizes_are_rejected(self):
        with self.assertRaises(LayoutError):
            ota_geometry(0, 4096)
        with self.assertRaises(LayoutError):
            ota_geometry(4096, -1)

    def test_platformio_mission_env_is_opt_in(self):
        text = """[platformio]
default_envs = esp12e

[env:esp12e]
board_build.ldscript = eagle.flash.4m3m.ld

[env:esp12e_m9_4m2m]
extends = env:esp12e
board_build.ldscript = eagle.flash.4m2m.ld
"""
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "platformio.ini"
            path.write_text(text, encoding="utf-8")
            result = inspect_platformio(path)
        self.assertEqual(result["default_env"], "esp12e")
        self.assertEqual(result["baseline_ldscript"], "eagle.flash.4m3m.ld")
        self.assertEqual(result["mission9_ldscript"], "eagle.flash.4m2m.ld")
        self.assertFalse(result["mission9_is_default"])

    def test_platformio_rejects_default_switch(self):
        text = """[platformio]
default_envs = esp12e_m9_4m2m

[env:esp12e]
board_build.ldscript = eagle.flash.4m3m.ld

[env:esp12e_m9_4m2m]
extends = env:esp12e
board_build.ldscript = eagle.flash.4m2m.ld
"""
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "platformio.ini"
            path.write_text(text, encoding="utf-8")
            with self.assertRaises(LayoutError):
                inspect_platformio(path)


if __name__ == "__main__":
    unittest.main()
