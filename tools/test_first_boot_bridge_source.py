"""Source safety regressions only; hardware boot/restore remains unverified."""
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
MAIN = (ROOT / "firmware/src/main.cpp").read_text()
BRIDGE = (ROOT / "firmware/src/boot/FirstBootBridge.cpp").read_text()
POLICY = (ROOT / "tools/generate_shino_device_policy.py").read_text()
WEB = (ROOT / "firmware/src/web/Webserver.cpp").read_text()
RECOVERY = (ROOT / "firmware/src/recovery/FactoryRollback.cpp").read_text()


class FirstBootGate(unittest.TestCase):
    def test_default_generator_has_only_conservative_boot_mode(self):
        self.assertIn("'#define SHINO_BOOT_PROFILE 0", POLICY)
        self.assertNotIn("--enable-normal-boot", POLICY)
        self.assertNotIn("--format-stock", POLICY)

    def test_main_enters_bridge_before_any_legacy_storage_calls(self):
        self.assertLess(MAIN.index("FirstBootBridge::run();"), MAIN.index("LittleFS.begin();"))
        self.assertLess(MAIN.index("FirstBootBridge::run();"), MAIN.index("configManager.secure.begin()"))
        self.assertLess(MAIN.index("FirstBootBridge::run();"), MAIN.index("RescueMode::checkBootLoop()"))
        self.assertIn("#if SHINO_BOOT_PROFILE == 0", MAIN)
        self.assertIn("#if SHINO_BOOT_PROFILE != 0", MAIN)
        self.assertIn('#error "Normal SHINO boot is prohibited', MAIN)
        self.assertIn("FirstBootBridge::loop();", MAIN)

    def test_bridge_has_no_direct_fs_eeprom_or_persisted_wifi_calls(self):
        for forbidden in (
            "LittleFS.begin(", "LittleFS.format(", "SPIFFS.begin(", "SPIFFS.format(",
            "EEPROM.begin(", "EEPROM.commit(", "SecureStorage::", "configManager.",
            "WiFi.begin(", "WiFi.persistent(true)", "Update.begin(", "Update.end(",
            "ESP.rtcUserMemoryWrite(",
        ):
            with self.subTest(forbidden=forbidden):
                self.assertNotIn(forbidden, BRIDGE)
        self.assertLess(BRIDGE.index("WiFi.persistent(false)"), BRIDGE.index("WiFi.mode(WIFI_AP)"))
        self.assertIn('SHINO_SETUP_AP_PSK', BRIDGE)
        self.assertIn('SHINO_RESCUE_HTTP_PASSWORD', BRIDGE)
        self.assertIn('DIGEST_AUTH', BRIDGE)

    def test_bridge_has_readonly_status_and_only_optional_exact_oem_writer(self):
        self.assertIn('FIRST_BOOT_BRIDGE', BRIDGE)
        self.assertIn('server.on("/api/v1/bridge/status", HTTP_GET', BRIDGE)
        self.assertIn('server.on("/api/v1/bridge/factory-return", HTTP_GET', BRIDGE)
        self.assertIn('#if SHINO_ENABLE_FACTORY_RESTORE', BRIDGE)
        self.assertIn('FactoryRollback::upload(', BRIDGE)
        self.assertNotIn('U_FS', BRIDGE)
        self.assertNotIn('"/api/v1/ota/fw"', BRIDGE)
        self.assertNotIn('"/api/v1/ota/fs"', BRIDGE)
        self.assertNotIn('"/api/v1/bridge/migrate"', BRIDGE)
        self.assertIn('FactoryRollback::status(', BRIDGE)
        self.assertIn('SHINO_FACTORY_BYTES == 494144', RECOVERY)
        self.assertIn('Update.setMD5(SHINO_FACTORY_MD5)', RECOVERY)

    def test_fs_migration_is_informational_only_and_compile_disabled(self):
        self.assertIn('SHINO_ENABLE_FS_MIGRATION == 0', BRIDGE)
        self.assertIn('SHINO_FS_BYTES == 2072576', BRIDGE)
        self.assertIn('SHINO_FS_SHA256', BRIDGE)
        self.assertIn('server.on("/api/v1/bridge/fs-plan", HTTP_GET', BRIDGE)
        self.assertIn('standard_updater_erases_and_writes_active_fs_BEFORE_MD5_validation', BRIDGE)
        self.assertIn('filesystem_writer_compiled', BRIDGE)
        self.assertNotIn('server.on("/api/v1/bridge/fs-plan", HTTP_POST', BRIDGE)
        self.assertNotIn('Update.begin(', BRIDGE)
        self.assertNotIn('U_FS', BRIDGE)
        self.assertIn("'#define SHINO_ENABLE_FS_MIGRATION 0", POLICY)
        self.assertIn('fs_image', POLICY)

    def test_no_automatic_format_in_legacy_mount_helper(self):
        self.assertIn("LittleFS.setConfig(LittleFSConfig(false))", WEB)
        self.assertIn("if (formatIfFailed)", WEB)
        self.assertNotIn("return LittleFS.begin();\n    };\n\n    if (formatIfFailed)", WEB)

    def test_status_never_claims_proven_stock_geometry_or_full_restore(self):
        self.assertIn('inferred_stock_FS_start_offset_UNVERIFIED', BRIDGE)
        self.assertIn('manufacturer_original_flash_backup_available', BRIDGE)
        self.assertIn('physical_flash_installation_authorized', BRIDGE)
        self.assertIn('linker_declared_free_sketch_bytes_NOT_stock_OTA_capacity', BRIDGE)

    def test_no_first_boot_image_or_fs_released_from_ci(self):
        for workflow in ("firmware-build.yml", "wifi-path-preflight.yml"):
            code=(ROOT / ".github/workflows" / workflow).read_text()
            self.assertIn('generate_shino_device_policy.py', code)
            self.assertNotIn('upload-artifact@', code)


if __name__ == "__main__":
    unittest.main()
