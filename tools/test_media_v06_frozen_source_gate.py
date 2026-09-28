"""V0.6 immutable-source compatibility gate; only reads checked-in text.

An intentionally narrow regression snapshot of the frozen owner's V2.1 native
bridge. Passing is NOT a firmware/media receiver, actual heap measurement,
HTTP parser proof, successful recovery, or authorization to flash the device.
"""
from pathlib import Path
import re
import unittest

ROOT = Path(__file__).resolve().parents[1]
MAIN = ROOT / "firmware/src/main.cpp"
BRIDGE = ROOT / "firmware/src/boot/FirstBootBridge.cpp"
METRICS = ROOT / "firmware/src/boot/FslessMetrics.cpp"
DASHBOARD = ROOT / "firmware/include/boot/DashboardV2.h"
ROLLBACK = ROOT / "firmware/src/recovery/FactoryRollback.cpp"
HEAP = ROOT / "firmware/include/boot/NativeOtaHeapReview.h"
PLATFORM = ROOT / "firmware/platformio.ini"
WIRE = ROOT / "companion/media_wire_v1.py"

def source(path):
    return path.read_text(encoding="utf-8")


class NativeV06PreflightSourceGate(unittest.TestCase):
    def test_legacy_v21_boot_profile_still_uses_fsless_path(self):
        main = source(MAIN)
        self.assertIn("#if SHINO_BOOT_PROFILE == 0", main)
        self.assertIn("FirstBootBridge::run();", main)
        self.assertLess(main.index("FirstBootBridge::run();"), main.index("LittleFS.begin();"))
        self.assertIn("FirstBootBridge::loop();", main)
        bridge = source(BRIDGE)
        self.assertIn("WiFi.persistent(false);", bridge)
        self.assertIn("WiFi.mode(WIFI_AP);", bridge)
        for forbidden in ("LittleFS.begin();", "LittleFS.format();", "EEPROM.begin(",
                          "EEPROM.commit(", "SPIFFS.begin(", "SPIFFS.format("):
            # Comments can mention the forbidden APIs. Only executable uses
            # are counted, not doc-comments explaining the safety boundary.
            code = "\n".join(x for x in bridge.splitlines()
                             if not x.lstrip().startswith("//"))
            self.assertNotIn(forbidden, code)

    def test_only_known_numeric_metrics_handler_and_no_media_receiver_is_registered(self):
        bridge = source(BRIDGE)
        routes = re.findall(r'server\.on\("([^"]+)",\s*HTTP_(GET|POST)', bridge)
        self.assertEqual(routes, [
            ("/", "GET"), ("/ui.js", "GET"),
            ("/api/v1/bridge/metrics", "GET"),
            ("/api/v1/bridge/metrics", "POST"),
            ("/api/v1/bridge/status", "GET"),
            ("/api/v1/bridge/fs-plan", "GET"),
            ("/api/v1/bridge/ota/capabilities", "GET"),
            ("/api/v1/bridge/factory-return", "GET"),
            ("/api/v1/bridge/factory-return", "POST"),
        ])
        self.assertIn('const String payload = server.arg("plain");', bridge)
        accept = bridge[bridge.index("void acceptMetrics()"):bridge.index("// Only four little")]
        self.assertLess(accept.index("if (!requireAuth()) return;"),
                        accept.index('server.arg("plain")'))
        self.assertIn("payload.length() > 384", accept)
        self.assertIn("FslessMetrics::apply(", accept)
        self.assertNotIn("media/", bridge)
        self.assertNotIn("cover/", bridge)

    def test_digest_is_for_posts_cookie_is_get_only(self):
        bridge = source(BRIDGE)
        self.assertIn('server.authenticate(SHINO_RESCUE_HTTP_USER, SHINO_RESCUE_HTTP_PASSWORD)', bridge)
        self.assertIn('server.requestAuthentication(DIGEST_AUTH, "SHINO-FirstBoot")', bridge)
        self.assertIn("if (!requireAuth()) return;", bridge)
        self.assertIn("Only GET of the", bridge)
        self.assertIn("Never authenticates POST telemetry", bridge)
        # Not a proof of HTTP parser/body allocation. That remains a blocker.

    def test_metrics_remain_separate_four_values_and_stale_after_six_seconds(self):
        bridge = source(BRIDGE)
        metrics = source(METRICS)
        dashboard = source(DASHBOARD)
        self.assertIn("METRICS_STALE_MS = 6000", metrics)
        self.assertIn("state = next; // Invalid payload never replaces the previous good sample.", metrics)
        self.assertIn("FslessMetrics::stale()", bridge)
        self.assertIn("Card cards[4]", bridge)
        self.assertIn("paintCard(i, cards[i])", bridge)
        self.assertIn("constexpr int CANVAS = 240", dashboard)
        self.assertIn("constexpr int CARD_SIZE = 108", dashboard)
        self.assertIn("constexpr int X[4]", dashboard)
        self.assertIn("constexpr int Y[4]", dashboard)

    def test_oem_return_is_distinct_only_pinned_application_and_writer_gated(self):
        bridge = source(BRIDGE)
        rollback = source(ROLLBACK)
        self.assertIn("#if SHINO_ENABLE_FACTORY_RESTORE", bridge)
        self.assertIn("FactoryRollback::upload(", bridge)
        self.assertIn("FactoryRollback::complete(server, true)", bridge)
        self.assertIn("SHINO_FACTORY_BYTES == 494144", rollback)
        self.assertIn("SHINO_ENABLE_NATIVE_SIGNED_OTA != 0", rollback)
        self.assertIn("ESP.getFlashChipRealSize() != PHYSICAL_FLASH_BYTES", rollback)
        self.assertIn("Update.setMD5(SHINO_FACTORY_MD5)", rollback)
        self.assertIn("Update.end(false)", rollback)
        self.assertIn("Update.isRunning()", rollback)
        self.assertIn("if (!authenticated) return;", rollback)
        self.assertNotIn("Update.begin(", bridge)
        self.assertNotIn("Update.write(", bridge)
        self.assertNotIn("Update.end(", bridge)
        # This source check cannot verify the owner's private image digest
        # nor resurrect a device that no longer boots Wi-Fi.

    def test_readonly_heap_observer_is_historical_and_saturates(self):
        bridge = source(BRIDGE)
        heap = source(HEAP)
        self.assertIn("#if SHINO_ENABLE_HEAP_DIAGNOSTICS", bridge)
        self.assertIn("heapDiagnostic.pollAfterExistingWork(millis());", bridge)
        self.assertIn("kMaxSamples=1024u", heap)
        self.assertIn("if(summary_.samples==kMaxSamples)return false;", heap)
        self.assertIn("not true in-flight peak usage", heap)

    def test_pinned_toolchain_and_nonproduction_host_emulator(self):
        platform = source(PLATFORM)
        wire = source(WIRE)
        self.assertIn("espressif8266@4.2.1", platform)
        self.assertIn("framework-arduinoespressif8266@3.30102.0", platform)
        self.assertIn("eagle.flash.4m3m.ld", platform)
        self.assertIn("COVER_RAW_BYTES = COVER_EDGE * COVER_EDGE * 2", wire)
        self.assertIn("CHUNK_BYTES = 512", wire)
        self.assertIn('test-injected boolean gate', wire)
        self.assertIn("NO SmallTV HTTP endpoint", wire)


if __name__ == "__main__":
    unittest.main()
