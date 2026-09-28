"""Run actual standalone C++ bounded OTA stream review with host SHA-256.

This deliberately has no real socket, device HTTP route, ESP Updater, private
production key, manufacturer firmware, reboot or physical flash capability.
"""
from pathlib import Path
import shutil
import subprocess
import tempfile
import unittest

ROOT=Path(__file__).resolve().parent.parent
HEADER=ROOT/"firmware/include/boot/NativeOtaStreamingReview.h"
PROBE=ROOT/"tools/native_ota_streaming_review_probe.cpp"
BRIDGE=ROOT/"firmware/src/boot/FirstBootBridge.cpp"
OEM=ROOT/"firmware/src/recovery/FactoryRollback.cpp"

class OtaStreamingReviewHostTests(unittest.TestCase):
    def test_compile_and_execute_host_stream_auth_and_failure_matrix(self):
        self.assertIsNotNone(shutil.which("g++"),"CI must have g++")
        self.assertIsNotNone(shutil.which("openssl"),"CI must have OpenSSL")
        with tempfile.TemporaryDirectory(prefix="shino-ota-stream-") as directory:
            exe=Path(directory)/"streaming-review"
            build=subprocess.run(
                ["g++","-std=c++17","-Wall","-Wextra","-Werror","-pedantic",
                 "-I",str(ROOT/"firmware/include"),str(PROBE),"-o",str(exe),"-lcrypto"],
                capture_output=True,text=True,check=False,timeout=35)
            self.assertEqual(build.returncode,0,build.stderr)
            probe=subprocess.run([str(exe)],capture_output=True,text=True,
                                 check=False,timeout=30)
            self.assertEqual(probe.returncode,0,probe.stdout+probe.stderr)
            self.assertIn("PASS: streaming HTTP fragment/combined-frame",probe.stdout)
            self.assertIn("RAM REVIEW ONLY NO FLASH",probe.stdout)

    def test_stream_is_disconnected_from_live_firmware_and_has_no_writer(self):
        src=HEADER.read_text(encoding="utf-8")
        active=BRIDGE.read_text(encoding="utf-8")
        rollback=OEM.read_text(encoding="utf-8")
        for expected in (
            "NativeOtaRawHeaderGate.h","NativeOtaStrictDigestGate.h",
            "NativeOtaManualConsentGate.h","NativeOtaRequestPolicy.h",
            "NativeOtaIntentGate.h","RawOtaHeaderGate::inspect",
            "digest_.verify(","consent_.consume(","intent_.arm(",
            "intent_.acceptChunk(","finishAfterExactFraming(",
            "transportSha_.end(calculated)","sink_.completeForReview()",
            "kHeaderDeadlineMs = 10'000u",
            "BytesAcceptedForOfflineReviewOnly",
            "static constexpr size_t kHeaderMax = RawOtaHeaderGate::kMaxHeaderBytes",
        ):
            self.assertIn(expected,src)
        self.assertNotIn("NativeOtaStreamingReview.h",active)
        self.assertNotIn("NativeOtaStreamingReview.h",rollback)
        for route in ("/api/v1/bridge/ota/upload","/api/v1/bridge/ota/arm"):
            self.assertNotIn('server.on("'+route+'"',active)
        real_source="\n".join(line for line in src.splitlines()
                              if not line.lstrip().startswith("//"))
        for forbidden in (
            "Update.begin(","Update.write(","Update.end(","installSignature(",
            "#include <Updater","#include <ESP8266WebServer",
            "LittleFS.begin(","EEPROM.commit(","ESP.restart(",
            "WiFiServer","WiFiClient",
        ):
            self.assertNotIn(forbidden,real_source)

if __name__=="__main__":
    unittest.main()
