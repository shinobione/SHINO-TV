"""Host-only regression of disconnected prospective heap sample cadence."""
from pathlib import Path
import shutil
import subprocess
import tempfile
import unittest

ROOT=Path(__file__).resolve().parent.parent
CPP=ROOT/"tools/native_ota_heap_cadence_probe.cpp"
HEADER=ROOT/"firmware/include/boot/NativeOtaHeapSampleCadence.h"
BRIDGE=ROOT/"firmware/src/boot/FirstBootBridge.cpp"
DEVICE=ROOT/"firmware/src/boot/NativeOtaDevicePumpCompileProbe.cpp"


@unittest.skipUnless(shutil.which("g++"),"Host C++17 compiler required")
class HeapCadenceUnwiredTests(unittest.TestCase):
    def test_real_cpp_virtual_clock_no_burst_and_wrap(self):
        with tempfile.TemporaryDirectory(prefix="shino-heap-cadence-") as dirname:
            exe=Path(dirname)/"heap-cadence"
            build=subprocess.run(
                ["g++","-std=c++17","-Wall","-Wextra","-Werror","-pedantic",
                 "-I",str(ROOT/"firmware/include"),str(CPP),"-o",str(exe)],
                capture_output=True,text=True,timeout=35,check=False)
            self.assertEqual(build.returncode,0,build.stdout+build.stderr)
            run=subprocess.run([str(exe)],capture_output=True,text=True,
                               timeout=10,check=False)
            self.assertEqual(run.returncode,0,run.stdout+run.stderr)
            self.assertIn("1Hz heap cadence",run.stdout)
            self.assertIn("no catch-up bursts",run.stdout)
            self.assertIn("NO TIMER NO DEVICE NO FLASH",run.stdout)

    def test_source_stays_disconnected_from_live_bridge(self):
        source=HEADER.read_text(encoding="utf-8")
        bridge=BRIDGE.read_text(encoding="utf-8")
        device=DEVICE.read_text(encoding="utf-8")
        self.assertIn("kIntervalMs=1000u",source)
        self.assertIn("nowMs-lastAttemptMs_",source)
        self.assertIn("lastAttemptMs_=nowMs;",source)
        self.assertNotIn("NativeOtaHeapSampleCadence.h",bridge)
        self.assertEqual(bridge.count("ESP8266WebServer server(80)"),1)
        self.assertIn("NativeOtaHeapReview.h",device)
        clean="\n".join(line for line in source.splitlines()
                        if not line.lstrip().startswith("//"))
        for forbidden in ("delay(", "Ticker", "attach(", "timer", "yield(",
                          "Update.", "ESP.restart(", "WiFiServer(",
                          "ESP8266WebServer(", "malloc(", "new "):
            self.assertNotIn(forbidden,clean)


if __name__=="__main__":
    unittest.main()
