"""Disconnected host-only digest challenge serialization / strict-gate regression."""
from pathlib import Path
import shutil
import subprocess
import tempfile
import unittest

ROOT=Path(__file__).resolve().parent.parent
CHALLENGE=ROOT/"firmware/include/boot/NativeOtaDigestChallengeReview.h"
GATE=ROOT/"firmware/include/boot/NativeOtaStrictDigestGate.h"
HOST=ROOT/"tools/native_ota_digest_challenge_probe.cpp"
BRIDGE=ROOT/"firmware/src/boot/FirstBootBridge.cpp"


@unittest.skipUnless(shutil.which("g++") and shutil.which("openssl"),
                     "CI must have a host C++ compiler and OpenSSL")
class DigestChallengePreviewTests(unittest.TestCase):
    def test_external_entropy_rfc7616_header_joins_real_strict_host_proof(self):
        with tempfile.TemporaryDirectory(prefix="shino-ota-challenge-review-") as temp:
            exe=Path(temp)/"digest-challenge-host"
            compiled=subprocess.run(
                ["g++","-std=c++17","-Wall","-Wextra","-Werror","-pedantic",
                 "-I",str(ROOT/"firmware/include"),str(HOST),"-o",str(exe),"-lcrypto"],
                capture_output=True,text=True,timeout=35,check=False)
            self.assertEqual(compiled.returncode,0,compiled.stdout+compiled.stderr)
            result=subprocess.run([str(exe)],capture_output=True,text=True,
                                  timeout=15,check=False)
            self.assertEqual(result.returncode,0,result.stdout+result.stderr)
            self.assertIn("PASS: external-entropy challenge format",result.stdout)
            self.assertIn("HOST ONLY NO HTTP/FLASH",result.stdout)

    def test_challenge_contract_is_disconnected_and_does_not_claim_entropy(self):
        challenge=CHALLENGE.read_text(encoding="utf-8")
        digest=GATE.read_text(encoding="utf-8")
        bridge=BRIDGE.read_text(encoding="utf-8")
        self.assertIn("fromExternalEntropy",challenge)
        self.assertIn('algorithm=SHA-256, qop=\\"auth\\"',challenge)
        self.assertIn("VerifiedForReviewOnly",digest)
        self.assertNotIn("NativeOtaDigestChallengeReview.h",bridge)
        self.assertNotIn("NativeOtaStrictDigestGate.h",bridge)
        self.assertIn('doc["native_ota_upload_route_registered"] = false',bridge)
        self.assertNotIn('server.on("/api/v1/bridge/ota/arm"',bridge)
        self.assertNotIn('server.on("/api/v1/bridge/ota/upload"',bridge)
        source="\n".join(line for line in challenge.splitlines()
                         if not line.lstrip().startswith("//"))
        for unsafe in ("Update.begin(", "Update.write(", "Update.end(",
                       "ESP.random(", "WiFiServer(", "server.on(",
                       "SHINO_RESCUE_HTTP_PASSWORD", "EEPROM.commit("):
            self.assertNotIn(unsafe,source)


if __name__=="__main__":
    unittest.main()
