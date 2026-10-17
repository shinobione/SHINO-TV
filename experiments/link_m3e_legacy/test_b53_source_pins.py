"""B5.3 exact Git-blob source route closure. Lab only, no device I/O.

Pins are real git blob IDs fetched for B5.3 autonomous and LEAN branches;
these three source blobs are identical in the M3-D base.
Never infer from them the actual installed firmware image or runtime profile.
"""
import re
import subprocess
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
SOURCE_BLOBS = {
    "firmware/src/boot/FirstBootBridge.cpp":
        "705028430a854537924ef30a83a1761d0670387e",
    "firmware/src/boot/HomeLan.cpp":
        "70f9922829dfb27be39955c1583648c32d05ceeb",
    "firmware/include/boot/HomeLanPolicy.h":
        "903ab6484a04a2d179fa8d62877a3a3e55131801",
}
FIRMWARE_ROUTES = {
    ("GET", "/"),
    ("GET", "/ui.js"),
    ("GET", "/api/v1/bridge/metrics"),
    ("POST", "/api/v1/bridge/metrics"),
    ("GET", "/api/v1/bridge/status"),
    ("GET", "/api/v1/m9/fs-probe/status"),  # profile 2 only
    ("GET", "/api/v1/bridge/fs-plan"),
    ("GET", "/api/v1/bridge/ota/capabilities"),
    ("GET", "/api/v1/bridge/factory-return"),
    ("POST", "/api/v1/bridge/factory-return"),  # factory flag only
    ("POST", "/api/v1/bridge/wifi/recovery"),  # home-LAN flag
    ("GET", "/api/v1/bridge/wifi/intent"),
    ("POST", "/api/v1/bridge/wifi"),
}
STA_PATHS = {
    "/", "/ui.js", "/api/v1/bridge/metrics",
    "/api/v1/bridge/status", "/api/v1/bridge/wifi/recovery",
    "/api/v1/bridge/ota/capabilities",
}


class B53SourcePinTests(unittest.TestCase):
    def test_exact_three_git_blobs_or_fail_closed(self):
        for path, expected in SOURCE_BLOBS.items():
            with self.subTest(path=path):
                self.assertTrue((ROOT/path).is_file())
                computed = subprocess.check_output(
                    ["git", "hash-object", path], cwd=ROOT,
                    text=True, timeout=5,
                ).strip()
                self.assertEqual(computed, expected)

    def test_all_declared_routes_exhaustively_accounted(self):
        first = (ROOT/"firmware/src/boot/FirstBootBridge.cpp").read_text()
        lan = (ROOT/"firmware/src/boot/HomeLan.cpp").read_text()
        pairs = set()
        for text in (first, lan):
            matches = re.findall(
                r'\b(?:server|s)\.on\("([^"]+)",\s*HTTP_(GET|POST)\b',
                text,
            )
            pairs.update((method, target) for target, method in matches)
        self.assertEqual(pairs, FIRMWARE_ROUTES)
        self.assertNotIn(("POST", "/api/v1/display/mode"), pairs)
        self.assertNotIn(("POST", "/api/v1/bridge/ota/upload"), pairs)

    def test_conditional_factory_wifi_and_probe_have_original_guards(self):
        first = (ROOT/"firmware/src/boot/FirstBootBridge.cpp").read_text()
        lan = (ROOT/"firmware/src/boot/HomeLan.cpp").read_text()
        self.assertIn("#if SHINO_ENABLE_FACTORY_RESTORE\n"
                      "    server.on(\"/api/v1/bridge/factory-return\", HTTP_POST",
                      first)
        self.assertIn("#if SHINO_BOOT_PROFILE == 2\n"
                      "    server.on(\"/api/v1/m9/fs-probe/status\", HTTP_GET",
                      first)
        self.assertIn("#if SHINO_ENABLE_HOME_LAN", first)
        self.assertIn("HomeLan::registerRoutes(server", first)
        self.assertIn("void registerRoutes(ESP8266WebServer& s,", lan)
        self.assertIn("if(!digest(s,user,password)) return;", lan)
        self.assertIn("server.begin();", first)
        self.assertIn("server.handleClient();", first)

    def test_sta_path_allowlist_is_exact_inspected_source(self):
        policy = (ROOT/"firmware/include/boot/HomeLanPolicy.h").read_text()
        block = policy.split("inline bool endpoint(bool ap, const char* path) {", 1)[1].split("class Intent", 1)[0]
        self.assertIn("if(ap) return true;", block)
        allowed = set(re.findall(r'!strcmp\(path,"([^"]+)"\)', block))
        self.assertEqual(allowed, STA_PATHS)
        self.assertNotIn("/api/v1/display/mode", allowed)
        self.assertNotIn("/api/v1/display/status", allowed)

    def test_no_legacy_handler_parity_claim_for_new_route_table(self):
        source = (ROOT/"experiments/link_m3e_legacy/M3ELegacyRouteGate.h").read_text()
        self.assertIn("bool allowedToDispatch = false", source)
        self.assertNotIn("server.on(", source)
        self.assertNotIn("WiFiServer", source.replace("// INERT. No WiFiServer,", ""))
        self.assertNotIn("setHomeLanPrebody(", source)
        self.assertNotIn("Update.begin(", source)


if __name__ == "__main__":
    unittest.main()
