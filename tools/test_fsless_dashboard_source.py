"""Software-only source regressions for first boot FS-less LCD and Web UI."""
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
BRIDGE = (ROOT / "firmware/src/boot/FirstBootBridge.cpp").read_text()
METRICS = (ROOT / "firmware/src/boot/FslessMetrics.cpp").read_text()
UI = (ROOT / "firmware/src/boot/FslessWebUI.cpp").read_text()
POLICY = (ROOT / "tools/generate_shino_device_policy.py").read_text()


class FslessDashboardSafetyTests(unittest.TestCase):
    def test_ui_and_native_display_have_no_fs_mount_or_writes(self):
        for content in (BRIDGE, METRICS, UI):
            for forbidden in ("LittleFS.begin(", "LittleFS.format(", "SPIFFS.begin(",
                              "EEPROM.begin(", "EEPROM.commit(", "Update.begin(",
                              "WiFi.persistent(true)", "ESP.rtcUserMemoryWrite("):
                self.assertNotIn(forbidden, content)
        self.assertIn("FslessWebUI::PAGE", BRIDGE)
        self.assertIn("FslessWebUI::SCRIPT", BRIDGE)
        self.assertIn("DashboardV2::fillPixels(", BRIDGE)
        self.assertIn("gfx->fillRoundRect(trackX, trackY, 90, 6, 3", BRIDGE)

    def test_ui_requires_digest_and_no_external_scripts_or_submit_forms(self):
        self.assertIn("DIGEST_AUTH", BRIDGE)
        self.assertIn('server.on("/ui.js", HTTP_GET', BRIDGE)
        self.assertIn("script-src 'self'", BRIDGE)
        self.assertIn("connect-src 'self'", BRIDGE)
        self.assertNotIn("https://", UI)
        self.assertNotIn("<form", UI)
        self.assertNotIn("innerHTML", UI)
        self.assertIn("textContent", UI)

    def test_metrics_endpoint_exactly_bounded_and_ram_only(self):
        self.assertIn('server.on("/api/v1/bridge/metrics", HTTP_POST, acceptMetrics);', BRIDGE)
        self.assertIn('server.on("/api/v1/bridge/metrics", HTTP_GET, sendMetrics);', BRIDGE)
        self.assertIn('const String payload = server.arg("plain");', BRIDGE)
        self.assertIn("payload.length() > 384", BRIDGE)
        self.assertIn("if (!requireAuth()) return;", BRIDGE)
        self.assertIn("RAM_SAMPLE_ACCEPTED", BRIDGE)
        self.assertIn("std::isfinite(numeric)", METRICS)
        self.assertIn('"memory_total_gb"', METRICS)
        self.assertIn('"memory_total_available"', METRICS)
        self.assertIn("Snapshot next{}", METRICS)
        self.assertIn("state = next;", METRICS)
        self.assertIn("METRICS_STALE_MS = 6000", METRICS)
        self.assertIn('"filesystem_or_eeprom_write_performed"', METRICS)
        self.assertNotIn("File ", METRICS)

    def test_build_requires_no_littlefs_seed_or_artifact(self):
        for path in ("firmware-build.yml", "wifi-path-preflight.yml"):
            code = (ROOT / ".github/workflows" / path).read_text()
            self.assertIn("SHINO_FS_IMAGE_PRESENT 0", code)
            self.assertNotIn("pio run -e esp12e -t buildfs", code)
            self.assertNotIn("--fs-image", code)
            self.assertIn("generate_shino_device_policy.py", code)
        self.assertIn("if fs_image is not None else None", POLICY)
        self.assertIn("'#define SHINO_ENABLE_FS_MIGRATION 0", POLICY)

    def test_littlefs_research_tool_remains_separate_for_future_consented_work(self):
        research = (ROOT / "tools/verify_fs_provisioning.py").read_text()
        self.assertIn("OFFLINE_IMAGE_INTEGRITY_ONLY__FS_WRITER_NOT_AUTHORIZED", research)
        self.assertNotIn("urllib.request", research)
        self.assertNotIn("socket.connect", research)


if __name__ == "__main__":
    unittest.main()
