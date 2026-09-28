"""Disconnected host coverage for prospective heap-minimum instrumentation.

This exercise NEVER reads a real device: the only sensor is a deterministic
fake, while the pinned Xtensa ESP.getHeapStats API is checked in existing
CI's compile-only firmware probe, not wired into FirstBootBridge.
"""
from pathlib import Path
import shutil
import subprocess
import tempfile
import unittest

ROOT=Path(__file__).resolve().parent.parent
PROBE=ROOT/"tools/native_ota_heap_review_probe.cpp"
HEADER=ROOT/"firmware/include/boot/NativeOtaHeapReview.h"
DEVICE=ROOT/"firmware/src/boot/NativeOtaDevicePumpCompileProbe.cpp"
BRIDGE=ROOT/"firmware/src/boot/FirstBootBridge.cpp"
WEB=ROOT/"firmware/src/boot/FslessWebUI.cpp"


@unittest.skipUnless(shutil.which("g++"),"Host C++17 compiler required")
class HeapReviewUnwiredTests(unittest.TestCase):
    def test_actual_disconnected_cpp_minimum_and_bad_sensor_sequences(self):
        with tempfile.TemporaryDirectory(prefix="shino-heap-review-") as dirname:
            executable=Path(dirname)/"heap-review"
            built=subprocess.run(
                ["g++","-std=c++17","-Wall","-Wextra","-Werror","-pedantic",
                 "-I",str(ROOT/"firmware/include"),str(PROBE),"-o",str(executable)],
                capture_output=True,text=True,timeout=35,check=False)
            self.assertEqual(built.returncode,0,built.stdout+built.stderr)
            ran=subprocess.run([str(executable)],capture_output=True,text=True,
                               timeout=10,check=False)
            self.assertEqual(ran.returncode,0,ran.stdout+ran.stderr)
            self.assertIn("minimum OBSERVED only",ran.stdout)
            self.assertIn("HOST ONLY NO ROUTES NO DEVICE NO FLASH",ran.stdout)

    def test_probe_uses_pinned_core_32bit_heap_stats_without_live_handler(self):
        source=DEVICE.read_text(encoding="utf-8")
        header=HEADER.read_text(encoding="utf-8")
        bridge=BRIDGE.read_text(encoding="utf-8")
        web=WEB.read_text(encoding="utf-8")
        self.assertIn('#include "boot/NativeOtaHeapReview.h"',source)
        self.assertIn("ESP.getHeapStats(&freeBytes,&largestBlock,&fragmentation);",source)
        self.assertIn("NativeOtaHeapReview<NativeDeviceHeapSource>",source)
        self.assertIn("kMaxSamples=1024u",header)
        self.assertIn("lowestObservedFreeBytes",header)
        self.assertIn("lowestObservedLargestBlockBytes",header)
        self.assertIn("highestObservedFragmentationPercent",header)
        self.assertNotIn("NativeOtaHeapReview.h",bridge)
        self.assertNotIn("NativeOtaHeapReview.h",web)
        self.assertEqual(bridge.count("ESP8266WebServer server(80)"),1)
        self.assertNotIn('server.on("/api/v1/bridge/ota/arm"',bridge)
        self.assertNotIn('server.on("/api/v1/bridge/ota/upload"',bridge)
        for path in (HEADER,PROBE):
            clean="\n".join(line for line in path.read_text(encoding="utf-8").splitlines()
                            if not line.lstrip().startswith("//"))
            for forbidden in ("Update.begin(", "Update.write(", "Update.end(",
                              "EEPROM.commit(", "LittleFS.begin(", "ESP.restart(",
                              "WiFiServer(", "ESP8266WebServer(", "malloc(", "new "):
                self.assertNotIn(forbidden,clean)


if __name__=="__main__":
    unittest.main()
