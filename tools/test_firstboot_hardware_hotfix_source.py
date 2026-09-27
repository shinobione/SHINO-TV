"""Offline source regression for owner's first real LCD/Web findings (NO device contact)."""
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
BRIDGE = (ROOT / "firmware/src/boot/FirstBootBridge.cpp").read_text(encoding="utf-8")
DISPLAY = (ROOT / "firmware/src/display/DisplayManager.cpp").read_text(encoding="utf-8")
HEADER = (ROOT / "firmware/include/display/DisplayManager.h").read_text(encoding="utf-8")
WEB = (ROOT / "firmware/src/boot/FslessWebUI.cpp").read_text(encoding="utf-8")


class HardwareFeedbackSourceTests(unittest.TestCase):
    def test_runtime_only_unmirrored_panel_does_not_write_config(self):
        self.assertEqual(BRIDGE.count("DisplayManager::begin(0);"), 2)
        self.assertIn("rotationOverride <= 7 ? rotationOverride : configManager.getLCDRotationSafe()", DISPLAY)
        self.assertIn("static void begin(uint8_t rotationOverride = 255)", HEADER)
        self.assertIn("g_lcd.setRotation(rotation);", DISPLAY)
        for forbidden in ("configManager.setLCDRotation(", "configManager.save(",
                          "LittleFS.begin(", "EEPROM.begin("):
            self.assertNotIn(forbidden, BRIDGE)

    def test_browser_session_issued_only_after_digest_login(self):
        root = BRIDGE.split('server.on("/", HTTP_GET, []() {', 1)[1].split(
            'server.on("/ui.js", HTTP_GET', 1)[0]
        self.assertIn("if (!browserSessionValid())", root)
        self.assertLess(root.index("if (!requireAuth()) return;"),
                        root.index("issueBrowserReadSession();"))
        self.assertIn('server.collectHeaders("Cookie");', BRIDGE)
        self.assertIn("ESP.random(randomBytes, sizeof(randomBytes))", BRIDGE)
        self.assertIn("uint8_t randomBytes[16]", BRIDGE)
        self.assertIn("SameSite=Strict", BRIDGE)
        self.assertIn("HttpOnly", BRIDGE)
        self.assertIn("BROWSER_SESSION_LIFETIME_MS", BRIDGE)
        self.assertIn("session.peer != peer", BRIDGE)
        self.assertIn("reject duplicate cookie names", BRIDGE)
        self.assertNotIn("SHINO_READ_SESSION=1", BRIDGE)

    def test_cookie_scope_never_authorizes_post_restore_or_diagnostics(self):
        metrics_get = BRIDGE.split("void sendMetrics() {", 1)[1].split("void acceptMetrics()", 1)[0]
        metrics_post = BRIDGE.split("void acceptMetrics() {", 1)[1].split("// Only four little", 1)[0]
        self.assertIn("if (!requireBrowserMetricsRead()) return;", metrics_get)
        self.assertIn("if (!requireAuth()) return;", metrics_post)
        restore = BRIDGE.split('server.on("/api/v1/bridge/factory-return", HTTP_POST,', 1)[1]
        self.assertIn("if (!requireAuth()) return;", restore)
        status = BRIDGE.split("void sendStatus() {", 1)[1].split("void sendMetrics()", 1)[0]
        self.assertIn("if (!requireAuth()) return;", status)
        self.assertNotIn("browserSessionValid()", metrics_post)
        self.assertNotIn("browserSessionValid()", restore)
        self.assertIn("respond(403", BRIDGE)
        self.assertIn("Browser session expired", BRIDGE)

    def test_browser_polls_same_origin_but_stops_if_session_denied(self):
        self.assertIn("credentials:'same-origin'", WEB)
        self.assertIn("if(pollingDenied)return;", WEB)
        self.assertIn("response.status===401||response.status===403", WEB)
        self.assertIn("pollingDenied=true", WEB)
        self.assertIn("SESSION EXPIRED · REOPEN /", WEB)
        self.assertIn("poll();setInterval(poll,2000);", WEB)
        self.assertNotIn("http://192.168.4.1", WEB)


if __name__ == "__main__":
    unittest.main()
