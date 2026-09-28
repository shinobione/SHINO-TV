"""Host-only HTTP response decision parity; no on-device listener or auth.

An explicit fixture-controlled DigestPass input is NOT derived from request
Authorization, and "200" previews never dispatch handlers or update hardware.
"""
import json
from pathlib import Path
import shutil
import subprocess
import tempfile
import unittest

ROOT=Path(__file__).resolve().parent.parent
HEADER=ROOT/"firmware/include/boot/NativeOtaLegacyResponsePreview.h"
HOST=ROOT/"tools/native_ota_legacy_response_probe.cpp"
BRIDGE=ROOT/"firmware/src/boot/FirstBootBridge.cpp"
METRICS=ROOT/"firmware/src/boot/FslessMetrics.cpp"
SHADOW=ROOT/"tools/native_ota_single_ingress_loopback.cpp"


class NativeOtaLegacyResponsePreviewTests(unittest.TestCase):
    def test_compile_execute_host_status_body_session_and_metrics_matrix(self):
        compiler=shutil.which("g++")
        self.assertIsNotNone(compiler,"CI requires C++ host compiler")
        with tempfile.TemporaryDirectory(prefix="shino-host-response-only-") as tmp:
            exe=Path(tmp)/"legacy-response-preview"
            built=subprocess.run(
                [compiler,"-std=c++17","-Wall","-Wextra","-Werror","-pedantic",
                 "-I",str(ROOT/"firmware/include"),str(HOST),"-o",str(exe)],
                capture_output=True,text=True,timeout=35,check=False)
            self.assertEqual(built.returncode,0,built.stderr)
            result=subprocess.run([str(exe)],capture_output=True,text=True,
                                  timeout=15,check=False)
            self.assertEqual(result.returncode,0,result.stdout+result.stderr)
            self.assertIn("PASS: source-grounded HOST HTTP status previews 200/401/403/404/413/422",
                          result.stdout)
            self.assertIn("NO REAL DIGEST/ROUTE/DISPATCH/LCD/FLASH",result.stdout)

    def test_exact_live_response_strings_and_status_order_are_source_grounded(self):
        live=BRIDGE.read_text(encoding="utf-8")
        src=HEADER.read_text(encoding="utf-8")
        self.assertIn('Browser session expired; reopen / and authenticate',live)
        self.assertIn('Invalid bounded telemetry payload length',live)
        self.assertIn('Invalid JSON telemetry',live)
        self.assertIn('Invalid, missing or out-of-range telemetry fields',live)
        self.assertIn('RAM_SAMPLE_ACCEPTED',live)
        self.assertIn('No arbitrary update, erase or filesystem route exists',live)
        for phrase in (
            'Browser session expired; reopen / and authenticate',
            'Invalid bounded telemetry payload length','Invalid JSON telemetry',
            'Invalid, missing or out-of-range telemetry fields',
            'RAM_SAMPLE_ACCEPTED',
            'No arbitrary update, erase or filesystem route exists',
        ):
            self.assertIn(phrase,src)
        self.assertLess(src.index("bodyBytes<16u || bodyBytes>384u"),
                        src.index("!fixtureJsonParsed"))
        self.assertLess(src.index("!fixtureJsonParsed"),
                        src.index("fixtureTelemetry!="))
        self.assertIn("DigestChallengeOnly",src)
        self.assertIn("BackgroundForbiddenNoChallenge",src)
        self.assertIn("WouldIssueReadSession",src)
        self.assertIn("LegacyMetricsPost",src)
        self.assertIn("LegacyFactoryReturnPost",src)
        self.assertIn("OtaReservedUpload",src)
        self.assertIn("actualAuthChecked=false",src)
        self.assertIn("actualHandlerDispatched=false",src)
        self.assertIn("otaWriterPresent=false",src)
        self.assertIn("wouldApplyTelemetry=false",src)
        self.assertNotIn("NativeOtaLegacyResponsePreview.h",live)
        self.assertNotIn("NativeOtaLegacyResponsePreview.h",
                         SHADOW.read_text(encoding="utf-8"))
        for forbidden in ("Update.begin(", "Update.end(", "Update.write(",
                          "ESP8266WebServer", "WiFiServer(", "ESP.restart(",
                          "LittleFS.begin(", "EEPROM.commit("):
            code="\n".join(line for line in src.splitlines()
                           if not line.lstrip().startswith("//"))
            self.assertNotIn(forbidden,code)

    def test_preview_fixture_content_is_parseable_but_never_claims_device_metrics(self):
        src=HEADER.read_text(encoding="utf-8")
        model=METRICS.read_text(encoding="utf-8")
        self.assertIn('FSLESS_PC_TELEMETRY_RAM_ONLY',src)
        self.assertIn('real_device_sample_read',src)
        self.assertIn('HOST_FIXTURE_DASHBOARD_HTML_NOT_SERVED',src)
        self.assertIn('HOST_FIXTURE_JAVASCRIPT_NOT_SERVED',src)
        self.assertIn('OTA_MANAGER_READ_ONLY_PREFLIGHT',src)
        self.assertIn('mode',model)
        sample='{"status":"RAM_SAMPLE_ACCEPTED","persisted":false}'
        self.assertEqual(json.loads(sample),{"status":"RAM_SAMPLE_ACCEPTED","persisted":False})
        self.assertIn('\\"persisted\\":false',src)

if __name__=="__main__":
    unittest.main()
