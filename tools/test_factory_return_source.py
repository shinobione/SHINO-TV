"""Static deployment-gate regression assertions; NOT physical security/runtime tests."""
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
APP = (ROOT / "firmware" / "src" / "web" / "Api.cpp").read_text()
MAIN = (ROOT / "firmware" / "src" / "main.cpp").read_text()
RESCUE = (ROOT / "firmware" / "src" / "boot" / "RescueMode.cpp").read_text()
RESTORE = (ROOT / "firmware" / "src" / "recovery" / "FactoryRollback.cpp").read_text()
WEB = (ROOT / "firmware" / "src" / "web" / "Webserver.cpp").read_text()


class FactoryReturnSourceGate(unittest.TestCase):
    def test_no_generic_ota_routes_in_normal_app(self):
        self.assertNotIn('"/api/v1/ota/fw", HTTP_POST', APP)
        self.assertNotIn('"/api/v1/ota/fs", HTTP_POST', APP)
        self.assertIn('"/api/v1/shino/factory-restore", HTTP_GET', APP)
        self.assertIn('#if SHINO_ENABLE_FACTORY_RESTORE', APP)
        self.assertIn('FactoryRollback::upload(', APP)

    def test_no_open_legacy_update_or_direct_config_file(self):
        self.assertNotIn('httpUpdater.setup(', MAIN)
        self.assertNotIn('serveStaticC("/config.json"', MAIN)
        self.assertNotIn('"$str0ngPa$$w0rd"', MAIN)
        self.assertIn('SHINO_SETUP_AP_PSK', MAIN)
        self.assertIn('SHINO_BOOTSTRAP_API_TOKEN', MAIN)
        self.assertNotIn('Access-Control-Allow-Origin", "*"' , APP)
        self.assertNotIn('Access-Control-Allow-Origin", "*"' , WEB)

    def test_static_file_fallback_has_explicit_allowlist(self):
        self.assertIn('Static file not allowed', WEB)
        self.assertIn('uri == "/header.html"', WEB)
        self.assertIn('uri.indexOf("..")', WEB)
        self.assertIn('uri.indexOf(\'%\')', WEB)

    def test_rescue_has_private_auth_and_no_generic_writes(self):
        self.assertIn('SHINO_RESCUE_HTTP_PASSWORD', RESCUE)
        self.assertIn('DIGEST_AUTH', RESCUE)
        self.assertNotIn('"/api/v1/rescue/ota"', RESCUE)
        for path in ('token', 'reboot', 'reset'):
            self.assertNotIn(f'"/api/v1/rescue/{path}"', RESCUE)
        self.assertIn('"/api/v1/rescue/factory-restore"', RESCUE)

    def test_exact_image_and_incomplete_write_guard(self):
        for expected in ('SHINO_FACTORY_BYTES == 494144', 'Update.setMD5(SHINO_FACTORY_MD5)',
                         'Update.end(false)', 'item.totalSize != SHINO_FACTORY_BYTES',
                         'ESP.getFlashChipRealSize()', 'SHINO_ENABLE_FACTORY_RESTORE'):
            self.assertIn(expected, RESTORE)

    def test_generated_secret_and_factory_pin_not_committed(self):
        ignore = (ROOT / ".gitignore").read_text()
        self.assertIn("firmware/include/shino_private_policy.h", ignore)
        self.assertIn("firmware/private/", ignore)
        self.assertFalse((ROOT / "firmware" / "include" / "shino_private_policy.h").is_file())


if __name__ == "__main__":
    unittest.main()
