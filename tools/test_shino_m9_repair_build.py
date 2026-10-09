"""Fail-closed regressions for the owner-only M9 repair/OTA-smoke builder."""
import json
import sys
import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parent))
import shino_m9_repair_build as repair

OWNER_CONFIG = {
    "device": "fedcba9876543210", "build": "b"*64,
    "ap_psk": "P"*34, "api_token": "T"*40,
    "digest_password": "D"*42, "maintenance_password": "M"*64,
}


class OwnerBuildGate(unittest.TestCase):
    def test_original_cannot_be_overwritten(self):
        with tempfile.TemporaryDirectory() as tmp:
            with patch.object(repair, "OWNER", Path(tmp)), \
                 patch.object(repair, "check_checkout"), \
                 patch.object(repair, "load", return_value=dict(OWNER_CONFIG)):
                target = Path(tmp) / repair.TARGETS["uart-repair"]
                target.mkdir()
                with self.assertRaisesRegex(ValueError,"Refusing to overwrite"):
                    repair.build("uart-repair")
                self.assertTrue(target.is_dir())

    def test_missing_toolchain_never_calls_private_generator(self):
        with tempfile.TemporaryDirectory() as tmp:
            with patch.object(repair, "OWNER", Path(tmp)), \
                 patch.object(repair, "check_checkout"), \
                 patch.object(repair, "load", return_value=dict(OWNER_CONFIG)), \
                 patch.object(repair.shutil, "which", return_value=None), \
                 patch.object(repair, "private_source") as gen:
                with self.assertRaisesRegex(RuntimeError,"PlatformIO unavailable"):
                    repair.build("uart-repair")
                gen.assert_not_called()

    def test_smoke_rotates_only_build_id_and_stays_offline(self):
        with tempfile.TemporaryDirectory() as tmp:
            target = Path(tmp)
            fresh = "c" * 64
            def fake_source(where, config):
                self.assertEqual(config["build"], fresh)
                for name in ("ap_psk","api_token","digest_password","maintenance_password","device"):
                    self.assertEqual(config[name], OWNER_CONFIG[name])
                binpath = where / ".pio/build" / repair.ENV / "firmware.bin"
                binpath.parent.mkdir(parents=True)
                binpath.write_bytes(b"Z" * 65000)
            def run(*args, **kwargs):
                self.assertEqual(kwargs["stdin"], repair.subprocess.DEVNULL)
                self.assertEqual(args[0][:2], ["pio","run"])
                return SimpleNamespace(returncode=0)
            resources = {"bin_bytes":65000,"noinit":56,"static_ram":42060,"linked_flash":60000}
            with patch.object(repair, "OWNER", target), \
                 patch.object(repair, "check_checkout"), \
                 patch.object(repair, "load", return_value=dict(OWNER_CONFIG)), \
                 patch.object(repair.secrets, "token_hex", return_value=fresh), \
                 patch.object(repair.shutil, "which", return_value="pio"), \
                 patch.object(repair, "private_source", side_effect=fake_source), \
                 patch.object(repair, "validate_image"), \
                 patch.object(repair, "one", return_value=resources), \
                 patch.object(repair.subprocess, "run", side_effect=run), \
                 patch.object(repair.subprocess, "check_output", return_value="a"*40):
                repair.build("wifi-smoke")
                result=json.loads((target/"m9-wifi-smoke-build-report.json").read_text())
                self.assertEqual(result["build_id"],fresh)
                self.assertFalse(result["physical_flash_authorized"])
                self.assertFalse(result["live_ota_authorized"])
                self.assertEqual(result["network_contacts"],0)
                self.assertEqual(result["flash_writes"],0)
                self.assertEqual(result["firmware_bytes"],65000)
                self.assertFalse((target/"transition-build").exists())
                self.assertFalse((target/"owner-credentials.json").exists())


if __name__ == "__main__":
    unittest.main()
