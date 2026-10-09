"""M9 HTTP regression at the *generated maintenance policy* boundary.

Host-only: no private credentials, sockets, COM, reboot, OTA or device contact.
The regression pairs POST telemetry and GET status/maintenance in both orders;
it compiles the *same policy header body* injected into StageA's owner graph.
"""
import shutil
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from shino_transition_build import maintenance_http_policy, authenticated_prebody_snapshot
from m9_stagea_build import ROOT

BASE_POLICY = ROOT / "firmware/include/boot/M9NormalHttpPolicy.h"
STAGE_A = ROOT / "firmware/src/boot/M9NormalStageA.cpp"
CXX = r"""
#include <cstring>
#include "boot/M9NormalHttpPolicy.h"
using M9NormalHttpPolicy::classify;
struct Request { bool get, post; const char *path, *length, *type, *transfer; int code; };
int main() {
    const Request requests[] = {
      {true,false,"/api/v1/m9/normal/status","","","",200},
      {true,false,"/api/v1/m9/maintenance/result","","","",200},
      {false,true,"/api/v1/bridge/metrics","100","application/json","",200},
      {true,false,"/api/v1/m9/normal/status","","","",200},
      {true,false,"/api/v1/m9/maintenance/challenge","","","",200},
      {true,false,"/api/v1/m9/maintenance/probe","","","",200},
      {true,false,"/api/v1/m9/maintenance/install","","","",200},
      {true,false,"/api/v1/m9/maintenance/result","","","",200},
      {true,false,"/status","","","",200},
      {true,false,"/api/v1/m9/normal/resources","","","",200},
      {true,false,"/api/v1/bridge/metrics","","","",200},
      {true,false,"/api/v1/m9/normal/status","","","",200},
      {true,false,"/api/v1/m9/maintenance/result","","","",200},
      {true,false,"/api/v1/m9/normal/status","1","","",404},
      {true,false,"/api/v1/m9/normal/status","bad","","",413},
      {true,false,"/api/v1/m9/normal/status","","","chunked",400},
      {true,false,"/api/v1/m9/maintenance/not-real","","","",404},
      {true,false,"/api/v1/m9/maintenance/result?go=1","","","",404},
      {false,true,"/api/v1/bridge/metrics","14","application/json","",413},
      {false,true,"/api/v1/bridge/metrics","100","text/plain","",415},
      {false,true,"/api/v1/m9/maintenance/install","100","application/json","",404},
      {false,false,"/api/v1/m9/normal/status","","","",404},
    };
    for (const auto& req : requests) {
       if (classify(req.get,req.post,req.path,req.length,req.type,req.transfer) != req.code) return 2;
    }
    return 0;
}
"""


class PrebodyRegression(unittest.TestCase):
    def test_generated_private_get_allowlist_compiles_and_is_strict(self):
        cxx = shutil.which("g++") or shutil.which("clang++")
        if not cxx:
            self.skipTest("C++ host toolchain required for compiled policy test")
        with tempfile.TemporaryDirectory(prefix="m9-http-policy-") as t:
            root = Path(t)
            header = root / "boot/M9NormalHttpPolicy.h"
            header.parent.mkdir(parents=True)
            header.write_text(maintenance_http_policy(BASE_POLICY.read_text(encoding="utf-8")),
                              encoding="utf-8")
            driver = root / "policy.cpp"
            driver.write_text(CXX, encoding="utf-8")
            exe = root / ("policy.exe" if sys.platform == "win32" else "policy")
            subprocess.run([cxx, "-std=c++17", "-Wall", "-Wextra", "-Werror",
                            "-I", str(root), str(driver), "-o", str(exe)],
                           check=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE, timeout=60)
            subprocess.run([str(exe)], check=True, stdout=subprocess.PIPE,
                           stderr=subprocess.PIPE, timeout=10)

    def test_digest_not_allowed_to_mutate_prebody_decision(self):
        source = authenticated_prebody_snapshot(STAGE_A.read_text(encoding="utf-8"))
        before = source.split("bool beforeBody() {", 1)[1].split("void telemetry() {", 1)[0]
        self.assertLess(before.index("M9NormalHttpPolicy::classify("),
                        before.index("if (!auth()) return false;"))
        self.assertLess(before.index("if (!auth()) return false;"),
                        before.index("if (result != 200)"))
        self.assertIn("server.keepAlive(false)", before)
        self.assertIn('respond(result, "{\\"error\\":\\"STAGE_A_PREBODY\\"}")', before)

    def test_public_stagea_cannot_use_private_maintenance_route_by_default(self):
        base = BASE_POLICY.read_text(encoding="utf-8")
        self.assertNotIn('"/api/v1/m9/maintenance/result"', base)
        generated = maintenance_http_policy(base)
        self.assertEqual(generated.count('"/api/v1/m9/maintenance/result"'), 1)
        self.assertEqual(generated.count('"/api/v1/m9/normal/status"'), 1)
        with self.assertRaises(AssertionError):
            maintenance_http_policy(generated)


if __name__ == "__main__":
    unittest.main()
