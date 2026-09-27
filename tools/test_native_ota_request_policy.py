"""Host-run negative tests for a standalone privileged OTA envelope policy.

This does NOT test real Digest handler, manual consent, a running HTTP server
or any flash writer; there is intentionally no on-device route integration.
"""
from pathlib import Path
import shutil
import subprocess
import tempfile
import unittest

ROOT = Path(__file__).resolve().parent.parent
HEADER = ROOT / "firmware/include/boot/NativeOtaRequestPolicy.h"
PROBE = ROOT / "tools/native_ota_request_policy_probe.cpp"
BRIDGE = ROOT / "firmware/src/boot/FirstBootBridge.cpp"

class RequestPolicyHostTests(unittest.TestCase):
    def test_host_policy_compiles_and_enforces_reject_cases(self):
        compiler = shutil.which("g++")
        self.assertIsNotNone(compiler, "CI must provide g++")
        with tempfile.TemporaryDirectory(prefix="shino-ota-request-host-") as directory:
            executable = Path(directory) / "ota-request-probe"
            built = subprocess.run(
                [compiler, "-std=c++17", "-Wall", "-Wextra", "-Werror", "-pedantic",
                 "-I", str(ROOT / "firmware/include"), str(PROBE), "-o", str(executable)],
                capture_output=True, text=True, timeout=30, check=False
            )
            self.assertEqual(built.returncode, 0, built.stderr)
            result = subprocess.run([str(executable)], capture_output=True, text=True,
                                    timeout=10, check=False)
            self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
            self.assertIn("PASS: privilege request policy", result.stdout)
            self.assertIn("NO HTTP route or writer", result.stdout)

    def test_policy_not_exposed_through_bridge_or_updater(self):
        header = HEADER.read_text(encoding="utf-8")
        active_bridge = BRIDGE.read_text(encoding="utf-8")
        source = "\n".join(line for line in header.splitlines()
                           if not line.lstrip().startswith("//"))
        for forbidden in ("Update.begin(", "Update.write(", "Update.end(",
                          "#include <Arduino", "#include <Updater",
                          "ESP8266WebServer", "LittleFS", "EEPROM."):
            self.assertNotIn(forbidden, source)
        self.assertIn("digestAuthenticated", header)
        self.assertIn("reachedFromPrivateAp", header)
        self.assertIn('http://192.168.4.1', header)
        self.assertNotIn("NativeOtaRequestPolicy.h", active_bridge)
        for path in ("/api/v1/bridge/ota/arm", "/api/v1/bridge/ota/upload",
                     "/api/v1/bridge/ota/install"):
            self.assertNotIn('server.on("' + path + '"', active_bridge)

if __name__ == "__main__":
    unittest.main()
