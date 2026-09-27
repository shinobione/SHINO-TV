"""Host-compiled hostile raw HTTP/1.1 header preflight. No network/firmware access."""
from pathlib import Path
import shutil
import subprocess
import tempfile
import unittest

ROOT=Path(__file__).resolve().parent.parent
GATE=ROOT/"firmware/include/boot/NativeOtaRawHeaderGate.h"
PROBE=ROOT/"tools/native_ota_raw_header_probe.cpp"
BRIDGE=ROOT/"firmware/src/boot/FirstBootBridge.cpp"
WEBUI=ROOT/"firmware/src/boot/FslessWebUI.cpp"


class OtaRawHttpHeaderTests(unittest.TestCase):
    def test_execute_raw_header_security_probe(self):
        compiler=shutil.which("g++")
        self.assertIsNotNone(compiler,"CI must provide a C++ compiler")
        with tempfile.TemporaryDirectory(prefix="shino-ota-header-") as directory:
            exe=Path(directory)/"header-test"
            cmd=[compiler,"-std=c++17","-Wall","-Wextra","-Werror","-pedantic",
                 "-I",str(ROOT/"firmware/include"),str(PROBE),"-o",str(exe)]
            c=subprocess.run(cmd,capture_output=True,text=True,timeout=30,check=False)
            self.assertEqual(c.returncode,0,c.stderr)
            r=subprocess.run([str(exe)],capture_output=True,text=True,timeout=10,check=False)
            self.assertEqual(r.returncode,0,r.stdout+r.stderr)
            self.assertIn("PASS: bounded raw header parser",r.stdout)
            self.assertIn("NO DIGEST PROOF/HTTP SOCKET/FLASH",r.stdout)

    def test_dedicated_raw_header_path_not_exposed_by_buffered_webserver(self):
        gate=GATE.read_text(encoding="utf-8")
        active=BRIDGE.read_text(encoding="utf-8")
        ui=WEBUI.read_text(encoding="utf-8")
        self.assertIn("kMaxHeaderBytes = 2048u",gate)
        self.assertIn("kMaxDigestHeaderBytes = 640u",gate)
        self.assertIn("data[len-4u] != '\\r'",gate)
        self.assertIn("if (sameHeader(names[i],name)) return false",gate)
        self.assertIn("transfer-encoding",gate)
        self.assertIn("digestHeaderPresent = gotAuth",gate)
        self.assertIn("readCookiePresent",gate)
        self.assertNotIn("NativeOtaRawHeaderGate.h",active)
        self.assertNotIn("NativeOtaRawHeaderGate.h",ui)
        for forbidden in ('server.on("/api/v1/bridge/ota/arm"',
                          'server.on("/api/v1/bridge/ota/upload"',
                          'server.on("/api/v1/bridge/ota/install"'):
            self.assertNotIn(forbidden,active)
        for forbidden in ("#include <Updater", "Update.begin(", "Update.write(",
                          "Update.end(", "LittleFS.begin(", "EEPROM.commit("):
            source="\n".join(line for line in gate.splitlines()
                             if not line.lstrip().startswith("//"))
            self.assertNotIn(forbidden,source)

if __name__=="__main__":
    unittest.main()
