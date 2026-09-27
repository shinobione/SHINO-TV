"""Host-only integration test for heap cadence + bounded observer."""
from pathlib import Path
import shutil
import subprocess
import tempfile
import unittest

ROOT=Path(__file__).resolve().parent.parent
CPP=ROOT/"tools/native_ota_heap_observer_integration_probe.cpp"
BRIDGE=ROOT/"firmware/src/boot/FirstBootBridge.cpp"


@unittest.skipUnless(shutil.which("g++"),"Host C++17 compiler required")
class HeapObserverIntegrationTests(unittest.TestCase):
    def test_sensor_read_count_is_exactly_cadence_gated(self):
        with tempfile.TemporaryDirectory(prefix="shino-heap-observer-") as dirname:
            exe=Path(dirname)/"heap-observer"
            build=subprocess.run(
                ["g++","-std=c++17","-Wall","-Wextra","-Werror","-pedantic",
                 "-I",str(ROOT/"firmware/include"),str(CPP),"-o",str(exe)],
                capture_output=True,text=True,timeout=35,check=False)
            self.assertEqual(build.returncode,0,build.stdout+build.stderr)
            run=subprocess.run([str(exe)],capture_output=True,text=True,
                               timeout=10,check=False)
            self.assertEqual(run.returncode,0,run.stdout+run.stderr)
            self.assertIn("cadence gates every heap source read",run.stdout)
            self.assertIn("no catch-up burst",run.stdout)
            self.assertIn("HOST ONLY NO DEVICE NO FLASH",run.stdout)

    def test_integration_probe_remains_absent_from_live_bridge(self):
        source=CPP.read_text(encoding="utf-8")
        bridge=BRIDGE.read_text(encoding="utf-8")
        self.assertIn("NativeOtaHeapReview",source)
        self.assertIn("NativeOtaHeapSampleCadence",source)
        self.assertIn("source.reads==1u",source)
        self.assertIn("source.reads==3u",source)
        self.assertNotIn("native_ota_heap_observer_integration_probe",bridge)
        self.assertNotIn("NativeOtaHeapReview.h",bridge)
        self.assertNotIn("NativeOtaHeapSampleCadence.h",bridge)
        for unsafe in ("Update.begin(", "Update.write(", "Update.end(",
                       "EEPROM.commit(", "LittleFS.begin(", "ESP.restart(",
                       "WiFiServer(", "ESP8266WebServer("):
            self.assertNotIn(unsafe,source)


if __name__=="__main__":
    unittest.main()
