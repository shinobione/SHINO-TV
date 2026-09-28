"""Host-only single-owner port80 migration route-table parity with current bridge.

Does not start a second listener or monkeypatch the legacy webserver.
"""
from pathlib import Path
import re
import shutil
import subprocess
import tempfile
import unittest

ROOT=Path(__file__).resolve().parent.parent
HEADER=ROOT/"firmware/include/boot/NativeOtaPort80Plan.h"
PROBE=ROOT/"tools/native_ota_port80_plan_probe.cpp"
BRIDGE=ROOT/"firmware/src/boot/FirstBootBridge.cpp"
NATIVE_PUMP=ROOT/"firmware/src/boot/NativeOtaDevicePumpCompileProbe.cpp"


class OwnerPort80MigrationPlanTests(unittest.TestCase):
    def test_route_classification_builds_and_runs_without_a_listener(self):
        compiler=shutil.which("g++")
        self.assertIsNotNone(compiler,"CI requires g++")
        with tempfile.TemporaryDirectory(prefix="shino-ota-port80-plan-") as d:
            exe=Path(d)/"source-only-route-matrix"
            b=subprocess.run([compiler,"-std=c++17","-Wall","-Wextra","-Werror",
                              "-pedantic","-I",str(ROOT/"firmware/include"),str(PROBE),
                              "-o",str(exe)],capture_output=True,text=True,
                             timeout=30,check=False)
            self.assertEqual(b.returncode,0,b.stderr)
            r=subprocess.run([str(exe)],capture_output=True,text=True,
                             timeout=10,check=False)
            self.assertEqual(r.returncode,0,r.stdout+r.stderr)
            self.assertIn("PASS: source-only port80 route parity",r.stdout)
            self.assertIn("NO listener or upload writer",r.stdout)

    def test_exact_legacy_bridge_route_parity_is_documented_without_activation(self):
        original=BRIDGE.read_text(encoding="utf-8")
        plan=HEADER.read_text(encoding="utf-8")
        actual=set(re.findall(r'server\.on\("([^"]+)",\s*(HTTP_GET|HTTP_POST)',original))
        expected={
            ("/","HTTP_GET"),("/ui.js","HTTP_GET"),
            ("/api/v1/bridge/metrics","HTTP_GET"),
            ("/api/v1/bridge/metrics","HTTP_POST"),
            ("/api/v1/bridge/status","HTTP_GET"),
            ("/api/v1/bridge/fs-plan","HTTP_GET"),
            ("/api/v1/bridge/ota/capabilities","HTTP_GET"),
            ("/api/v1/bridge/factory-return","HTTP_GET"),
            ("/api/v1/bridge/factory-return","HTTP_POST"),
        }
        self.assertEqual(actual,expected,"Live bridge route changes require a fresh port-80 audit")
        self.assertEqual(original.count("ESP8266WebServer server(80)"),1)
        self.assertEqual(original.count("server.handleClient()"),1)
        self.assertIn("server.onNotFound",original)
        self.assertIn("SHINO_ENABLE_FACTORY_RESTORE",original)
        for path,method in actual:
            self.assertIn(path,plan)
        self.assertIn("OtaReservedArm",plan)
        self.assertIn("OtaReservedUpload",plan)
        self.assertIn("OtaReservedReject",plan)
        self.assertIn("LegacyAuthenticatedNotFound",plan)
        self.assertIn("LegacyMetricsPost",plan)
        self.assertIn("LegacyFactoryReturnPost",plan)
        self.assertIn("currentlyRegisteredInFirstBootBridge=false",plan)
        self.assertNotIn("NativeOtaPort80Plan.h",original)
        self.assertIn("NativeOtaPort80Plan.h",NATIVE_PUMP.read_text(encoding="utf-8"))
        self.assertIn("SHINO_ENABLE_NATIVE_SIGNED_OTA == 0",
                      NATIVE_PUMP.read_text(encoding="utf-8"))
        for code in (plan,PROBE.read_text(encoding="utf-8")):
            without_comments="\n".join(line for line in code.splitlines()
                                        if not line.lstrip().startswith("//"))
            for forbidden in ("WiFiServer", "server.begin(", "server.handleClient(",
                              "Update.begin(", "Update.write(", "Update.end(",
                              "ESP.restart(", "LittleFS.", "EEPROM."):
                self.assertNotIn(forbidden,without_comments)

if __name__=="__main__":
    unittest.main()
