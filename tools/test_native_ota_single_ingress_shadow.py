"""Single-owner port-80 SHADOW metadata-only ingress: source and compiled C++.

No legacy handler dispatched, no Digest proof, no manufacturer firmware,
no socket on the ESP8266, no private owner credential or OTA writer.
"""
from pathlib import Path
import shutil
import subprocess
import tempfile
import unittest

ROOT=Path(__file__).resolve().parent.parent
HEADER=ROOT/"firmware/include/boot/NativeOtaSingleIngressShadow.h"
PROBE=ROOT/"tools/native_ota_single_ingress_shadow_probe.cpp"
BRIDGE=ROOT/"firmware/src/boot/FirstBootBridge.cpp"
PORT_PLAN=ROOT/"firmware/include/boot/NativeOtaPort80Plan.h"


class SingleIngressShadowTest(unittest.TestCase):
    def test_one_owner_shadow_compiles_and_tests_existing_routes_and_ota_denials(self):
        gpp=shutil.which("g++")
        self.assertIsNotNone(gpp,"Host compiler is mandatory in CI")
        with tempfile.TemporaryDirectory(prefix="shino-shadow-single-owner-") as tmp:
            exe=Path(tmp)/"shadow"
            built=subprocess.run(
                [gpp,"-std=c++17","-Wall","-Wextra","-Werror","-pedantic",
                 "-I",str(ROOT/"firmware/include"),str(PROBE),"-o",str(exe)],
                capture_output=True,text=True,timeout=35,check=False)
            self.assertEqual(built.returncode,0,built.stderr)
            r=subprocess.run([str(exe)],capture_output=True,text=True,
                             timeout=30,check=False)
            self.assertEqual(r.returncode,0,r.stdout+r.stderr)
            self.assertIn("PASS: one-owner HTTP shadow legacy route metadata",r.stdout)
            self.assertIn("NO legacy dispatch/auth/flash",r.stdout)

    def test_shadow_not_connected_to_live_bridge_or_any_writer(self):
        header=HEADER.read_text(encoding="utf-8")
        bridge=BRIDGE.read_text(encoding="utf-8")
        plan=PORT_PLAN.read_text(encoding="utf-8")
        self.assertIn("LegacyMetricsPost",header)
        self.assertIn("kLegacyMetricsBytes=384u",header)
        self.assertIn("OtaReservedNoWriter",header)
        self.assertIn("FactoryWriteDisabled",header)
        self.assertIn("routeWasActuallyDispatched=false",header)
        self.assertIn("otaWriterCompiled=false",header)
        self.assertIn("NativeOtaPort80Plan.h",header)
        self.assertIn('equal(route,"/api/v1/bridge/ota/capabilities")',plan)
        self.assertNotIn("NativeOtaSingleIngressShadow.h",bridge)
        self.assertEqual(bridge.count("ESP8266WebServer server(80)"),1)
        self.assertEqual(bridge.count("server.handleClient()"),1)
        for path in (HEADER,PROBE):
            code="\n".join(line for line in path.read_text(encoding="utf-8").splitlines()
                           if not line.lstrip().startswith("//"))
            for forbidden in (
                "WiFiServer(", "INADDR_ANY", "server.begin(", "server.handleClient(",
                "Update.begin(", "Update.write(", "Update.end(", "installSignature(",
                "LittleFS.begin(", "EEPROM.commit(", "ESP.restart(",
            ):
                self.assertNotIn(forbidden,code)

if __name__=="__main__":
    unittest.main()
