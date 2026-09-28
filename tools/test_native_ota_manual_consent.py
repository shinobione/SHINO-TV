"""Host-only one-use manual consent contract; never produces install approval."""
from pathlib import Path
import shutil
import subprocess
import tempfile
import unittest

ROOT=Path(__file__).resolve().parent.parent
GATE=ROOT/"firmware/include/boot/NativeOtaManualConsentGate.h"
PROBE=ROOT/"tools/native_ota_manual_consent_probe.cpp"
BRIDGE=ROOT/"firmware/src/boot/FirstBootBridge.cpp"
OEM=ROOT/"firmware/src/recovery/FactoryRollback.cpp"


class OtaManualConsentHostTests(unittest.TestCase):
    def test_host_cpp_manual_consent_replay_timeout_and_cookie_only(self):
        compiler=shutil.which("g++")
        self.assertIsNotNone(compiler,"CI must provide g++ for real consent gate tests")
        with tempfile.TemporaryDirectory(prefix="shino-ota-consent-") as directory:
            exe=Path(directory)/"manual-consent"
            c=subprocess.run(
                [compiler,"-std=c++17","-Wall","-Wextra","-Werror","-pedantic",
                 "-I",str(ROOT/"firmware/include"),str(PROBE),"-o",str(exe)],
                capture_output=True,text=True,timeout=30,check=False)
            self.assertEqual(c.returncode,0,c.stderr)
            p=subprocess.run([str(exe)],capture_output=True,text=True,timeout=10,check=False)
            self.assertEqual(p.returncode,0,p.stdout+p.stderr)
            self.assertIn("PASS: manual consent single-use",p.stdout)
            self.assertIn("HOST ONLY NO WRITER",p.stdout)

    def test_consent_policy_is_unwired_and_unprivileged_cookies_never_authenticate(self):
        src=GATE.read_text(encoding="utf-8")
        bridge=BRIDGE.read_text(encoding="utf-8")
        oem=OEM.read_text(encoding="utf-8")
        self.assertIn("kLifetimeMs = 60'000",src)
        self.assertIn("ConsumedForReviewOnly",src)
        self.assertIn("ownerDeliberatelyConfirmed",src)
        self.assertIn("digestAuthenticated",src)
        self.assertIn("requestEnvelopeAccepted",src)
        self.assertIn("selectedTransportSha256",src)
        self.assertIn("Wrong guess consumes",src)
        self.assertNotIn("NativeOtaManualConsentGate.h",bridge)
        self.assertNotIn("NativeOtaManualConsentGate.h",oem)
        implementation="\n".join(line for line in src.splitlines()
                                  if not line.lstrip().startswith("//"))
        for forbidden in ("Update.begin(", "Update.write(", "Update.end(",
                          "#include <Updater", "#include <ESP8266WebServer",
                          "LittleFS.", "EEPROM.", "ESP.restart("):
            self.assertNotIn(forbidden,implementation)

if __name__=="__main__":
    unittest.main()
