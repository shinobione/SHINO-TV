"""Disconnected virtual-clock absolute HTTP deadline and source lock.

Compiles the real pure bounded ingress header on HOST. No actual device,
sleeping slow client, public listener, live Wi-Fi/HTTP auth or firmware upload.
"""
from pathlib import Path
import shutil
import subprocess
import tempfile
import unittest

ROOT=Path(__file__).resolve().parent.parent
HEADER=ROOT/"firmware/include/boot/NativeOtaSingleIngressShadow.h"
CPP=ROOT/"tools/native_ota_single_ingress_absolute_deadline_probe.cpp"
BRIDGE=ROOT/"firmware/src/boot/FirstBootBridge.cpp"
DEVICE=ROOT/"firmware/src/boot/NativeOtaDevicePumpCompileProbe.cpp"


@unittest.skipUnless(shutil.which("g++"),"CI host compiler required")
class SlowClientAbsoluteDeadlineTests(unittest.TestCase):
    def test_real_cpp_virtual_clock_deadlines_fail_closed(self):
        with tempfile.TemporaryDirectory(prefix="shino-ingress-deadline-") as dirname:
            exe=Path(dirname)/"absolute-deadline"
            built=subprocess.run(
                ["g++","-std=c++17","-Wall","-Wextra","-Werror","-pedantic",
                 "-I",str(ROOT/"firmware/include"),str(CPP),"-o",str(exe)],
                capture_output=True,text=True,timeout=35,check=False)
            self.assertEqual(built.returncode,0,built.stdout+built.stderr)
            run=subprocess.run([str(exe)],capture_output=True,text=True,
                               timeout=10,check=False)
            self.assertEqual(run.returncode,0,run.stdout+run.stderr)
            self.assertIn("PASS: total-body 30s cap",run.stdout)
            self.assertIn("wrap-safe",run.stdout)
            self.assertIn("HOST ONLY NO HTTP/FLASH",run.stdout)

    def test_total_limit_stays_separate_from_idle_and_is_not_wired_live(self):
        source=HEADER.read_text(encoding="utf-8")
        probe=CPP.read_text(encoding="utf-8")
        bridge=BRIDGE.read_text(encoding="utf-8")
        device=DEVICE.read_text(encoding="utf-8")
        self.assertIn("kHeaderDeadlineMs=10000u",source)
        self.assertIn("kBodyIdleDeadlineMs=15000u",source)
        self.assertIn("kBodyTotalDeadlineMs=30000u",source)
        self.assertIn("bodyStartedMs_=nowMs;",source)
        self.assertIn("nowMs-bodyStartedMs_",source)
        self.assertIn("nowMs-lastReadMs_",source)
        self.assertIn("kLegacyMetricsBytes=384u",source)
        self.assertIn("start+30000u",probe)
        self.assertIn("static_assert(sizeof(ShinoNativeOta::NativeOtaSingleIngressShadow) <= 3072u",device)
        self.assertNotIn("NativeOtaSingleIngressShadow.h",bridge)
        self.assertEqual(bridge.count("ESP8266WebServer server(80)"),1)
        self.assertNotIn('server.on("/api/v1/bridge/ota/arm"',bridge)
        self.assertNotIn('server.on("/api/v1/bridge/ota/upload"',bridge)
        for unsafe in ("Update.begin(", "Update.write(", "Update.end(",
                       "LittleFS.begin(", "EEPROM.commit(", "ESP.restart("):
            self.assertNotIn(unsafe,probe)


if __name__=="__main__":
    unittest.main()
