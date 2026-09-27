"""Host-only strict RFC7616 SHA-256 Digest, exact URI and one-shot replay tests."""
from pathlib import Path
import shutil
import subprocess
import tempfile
import unittest

ROOT=Path(__file__).resolve().parent.parent
GATE=ROOT/"firmware/include/boot/NativeOtaStrictDigestGate.h"
HOST=ROOT/"tools/native_ota_strict_digest_probe.cpp"
BRIDGE=ROOT/"firmware/src/boot/FirstBootBridge.cpp"
OEM=ROOT/"firmware/src/recovery/FactoryRollback.cpp"

@unittest.skipUnless(shutil.which("openssl") and shutil.which("g++"),
                     "CI must have OpenSSL EVP and host C++ compiler")
class StrictNativeOtaDigestTests(unittest.TestCase):
    def test_real_host_crypto_proof_exact_route_and_one_shot_challenge(self):
        with tempfile.TemporaryDirectory(prefix="shino-ota-sha256-digest-") as path:
            exe=Path(path)/"sha256-digest-probe"
            c=subprocess.run(["g++","-std=c++17","-Wall","-Wextra","-Werror",
                              "-pedantic","-I",str(ROOT/"firmware/include"),
                              str(HOST),"-o",str(exe),"-lcrypto"],
                              capture_output=True,text=True,timeout=35,check=False)
            self.assertEqual(c.returncode,0,c.stderr)
            r=subprocess.run([str(exe)],capture_output=True,text=True,
                             timeout=15,check=False)
            self.assertEqual(r.returncode,0,r.stdout+r.stderr)
            self.assertIn("PASS: dedicated SHA-256 Digest qop-auth",r.stdout)
            self.assertIn("HOST ONLY NO HTTP/FLASH",r.stdout)

    def test_strict_gate_is_not_the_existing_core_digest_or_active_ota_writer(self):
        gate=GATE.read_text(encoding="utf-8")
        bridge=BRIDGE.read_text(encoding="utf-8")
        recovery=OEM.read_text(encoding="utf-8")
        self.assertIn("StrictDigestPhase::VerifiedForReviewOnly",gate)
        self.assertIn('equals(f.uri,route)',gate)
        self.assertIn('equals(f.nc,"00000001")',gate)
        self.assertIn('equals(f.qop,"auth")',gate)
        self.assertIn('equals(f.algorithm,"SHA-256")',gate)
        self.assertIn('POST:%s',gate)
        self.assertIn("kLifetimeMs = 60'000u",gate)
        self.assertIn("if(used & bit)return false",gate)
        self.assertNotIn("NativeOtaStrictDigestGate.h",bridge)
        self.assertNotIn("NativeOtaStrictDigestGate.h",recovery)
        src="\n".join(line for line in gate.splitlines()
                      if not line.lstrip().startswith("//"))
        for unsafe in ("Update.begin(", "Update.end(", "Update.write(",
                       "#include <Updater", "ESP8266WebServer",
                       "LittleFS.begin(", "EEPROM.commit(", "ESP.restart("):
            self.assertNotIn(unsafe,src)

if __name__=="__main__":
    unittest.main()
