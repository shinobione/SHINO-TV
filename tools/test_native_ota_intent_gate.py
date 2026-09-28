"""Compile/run the firmware-intended *pure* OTA gate on host: no Arduino/device/network."""
from pathlib import Path
import shutil
import subprocess
import tempfile
import unittest

ROOT = Path(__file__).resolve().parent.parent
PROBE = ROOT / "tools/native_ota_intent_gate_probe.cpp"
HEADER = ROOT / "firmware/include/boot/NativeOtaIntentGate.h"
BRIDGE = ROOT / "firmware/src/boot/FirstBootBridge.cpp"


class NativeOtaIntentGateHostTests(unittest.TestCase):
    def test_real_cpp_gate_compiles_and_rejects_replay_timeout_truncation(self):
        compiler = shutil.which("g++")
        self.assertIsNotNone(compiler, "CI must provide g++ for source-executed transfer-gate tests")
        with tempfile.TemporaryDirectory(prefix="shino-no-flash-") as directory:
            binary = Path(directory) / "intent-gate-probe"
            build = subprocess.run(
                [compiler, "-std=c++17", "-Wall", "-Wextra", "-Werror", "-pedantic",
                 "-I", str(ROOT / "firmware/include"), str(PROBE), "-o", str(binary)],
                capture_output=True, text=True, timeout=30, check=False,
            )
            self.assertEqual(build.returncode, 0, build.stderr)
            test = subprocess.run([str(binary)], capture_output=True, text=True,
                                  timeout=10, check=False)
            self.assertEqual(test.returncode, 0, test.stdout + test.stderr)
            self.assertIn("PASS: 7 offline groups", test.stdout)
            self.assertIn("NO HTTP/flash/firmware writer", test.stdout)

    def test_gate_has_no_arduino_or_writer_dependency_and_is_not_wired_as_http_route(self):
        gate = HEADER.read_text(encoding="utf-8")
        bridge = BRIDGE.read_text(encoding="utf-8")
        self.assertIn("BytesCompleteAwaitingSignatureCheck", gate)
        self.assertIn("IntentGate(const IntentGate&) = delete;", gate)
        self.assertIn("kArmLifetimeMs = 60'000", gate)
        self.assertIn("kStreamInactivityMs = 15'000", gate)
        # Security scan compiled declarations/statements, not truthful comments
        # explaining what the gate must never become.
        source_only = "\\n".join(line for line in gate.splitlines()
                                if not line.lstrip().startswith("//"))
        for forbidden in ("Update.begin(", "Update.write(", "Update.end(",
                          "#include <Arduino", "#include <Updater", "ESP8266WebServer",
                          "LittleFS", "EEPROM.", "HTTP_POST"):
            self.assertNotIn(forbidden, source_only)
        self.assertNotIn("NativeOtaIntentGate.h", bridge)
        self.assertNotIn('server.on("/api/v1/bridge/ota/install"', bridge)
        self.assertNotIn('server.on("/api/v1/bridge/ota/arm"', bridge)
        self.assertNotIn('server.on("/api/v1/bridge/ota/upload"', bridge)


if __name__ == "__main__":
    unittest.main()
