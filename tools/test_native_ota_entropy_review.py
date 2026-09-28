"""Host failure cases and compile-only ESP8266 entropy source safety lock."""
from pathlib import Path
import shutil
import subprocess
import tempfile
import unittest

ROOT=Path(__file__).resolve().parent.parent
GATE=ROOT/"firmware/include/boot/NativeOtaEntropyReview.h"
CHALLENGE=ROOT/"firmware/include/boot/NativeOtaDigestChallengeReview.h"
PROBE=ROOT/"tools/native_ota_entropy_review_probe.cpp"
DEVICE_PROBE=ROOT/"firmware/src/boot/NativeOtaDevicePumpCompileProbe.cpp"
BRIDGE=ROOT/"firmware/src/boot/FirstBootBridge.cpp"


@unittest.skipUnless(shutil.which("g++"), "Host C++ compiler required for CI")
class EntropyReviewTests(unittest.TestCase):
    def test_one_attempt_ap_guard_and_bad_entropy_host_probe(self):
        with tempfile.TemporaryDirectory(prefix="shino-native-entropy-review-") as temp:
            exe=Path(temp)/"entropy-review"
            c=subprocess.run(
                ["g++","-std=c++17","-Wall","-Wextra","-Werror","-pedantic",
                 "-I",str(ROOT/"firmware/include"),str(PROBE),"-o",str(exe)],
                capture_output=True,text=True,timeout=35,check=False)
            self.assertEqual(c.returncode,0,c.stdout+c.stderr)
            r=subprocess.run([str(exe)],capture_output=True,text=True,
                             timeout=15,check=False)
            self.assertEqual(r.returncode,0,r.stdout+r.stderr)
            self.assertIn("PASS: AP readiness before entropy",r.stdout)
            self.assertIn("HOST ONLY NO HTTP/FLASH",r.stdout)

    def test_only_compile_probe_references_device_entropy_never_running_bridge(self):
        source=GATE.read_text(encoding="utf-8")
        challenge=CHALLENGE.read_text(encoding="utf-8")
        native=DEVICE_PROBE.read_text(encoding="utf-8")
        bridge=BRIDGE.read_text(encoding="utf-8")
        self.assertIn("EntropySource::privateApReady()",source)
        self.assertIn("EntropySource::fill(entropy.data(),entropy.size())",source)
        self.assertIn("fromExternalEntropy",source)
        self.assertIn("attempted_=true",source)
        self.assertIn("NativeOtaEntropyReview.h",native)
        self.assertIn("WiFi.getMode()==WIFI_AP",native)
        self.assertIn("WiFi.softAPIP()==IPAddress(192,168,4,1)",native)
        self.assertIn("ESP.random(bytes,length)==bytes",native)
        self.assertIn("template class NativeOtaEntropyReview<NativeDeviceEntropySource>;",native)
        self.assertNotIn("NativeOtaEntropyReview.h",bridge)
        self.assertNotIn("NativeOtaDigestChallengeReview.h",bridge)
        self.assertNotIn('server.on("/api/v1/bridge/ota/arm"',bridge)
        self.assertNotIn('server.on("/api/v1/bridge/ota/upload"',bridge)
        self.assertIn('doc["native_ota_writer_compiled"] = false',bridge)
        self.assertIn('doc["native_ota_upload_route_registered"] = false',bridge)
        pure="\n".join(line for line in (source+"\n"+challenge).splitlines()
                       if not line.lstrip().startswith("//"))
        for blocked in ("ESP.random(", "WiFiServer(", "server.on(", "Update.begin(",
                        "Update.write(", "Update.end(", "ESP.restart(", "EEPROM.commit("):
            self.assertNotIn(blocked,pure)


if __name__=="__main__":
    unittest.main()
