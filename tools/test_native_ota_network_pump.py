"""Compile the ESP8266-compatible nonwriting TCP pump on host and in firmware CI."""
from pathlib import Path
import shutil
import subprocess
import tempfile
import unittest

ROOT=Path(__file__).resolve().parent.parent
HEADER=ROOT/"firmware/include/boot/NativeOtaNetworkPump.h"
EMBEDDED=ROOT/"firmware/src/boot/NativeOtaDevicePumpCompileProbe.cpp"
PROBE=ROOT/"tools/native_ota_network_pump_probe.cpp"
BRIDGE=ROOT/"firmware/src/boot/FirstBootBridge.cpp"
ROLLBACK=ROOT/"firmware/src/recovery/FactoryRollback.cpp"

class OtaDeviceNetworkPumpTests(unittest.TestCase):
    def test_host_executes_cooperative_bounded_wifi_client_like_reader(self):
        compiler=shutil.which("g++")
        self.assertIsNotNone(compiler, "CI requires g++ for C++ device reader probe")
        with tempfile.TemporaryDirectory(prefix="shino-no-flash-pump-") as directory:
            exe=Path(directory)/"bounded-network-probe"
            cmd=[compiler,"-std=c++17","-Wall","-Wextra","-Werror","-pedantic",
                 "-I",str(ROOT/"firmware/include"),str(PROBE),"-o",str(exe)]
            build=subprocess.run(cmd,capture_output=True,text=True,timeout=30,check=False)
            self.assertEqual(build.returncode,0,build.stderr)
            result=subprocess.run([str(exe)],capture_output=True,text=True,
                                  timeout=20,check=False)
            self.assertEqual(result.returncode,0,result.stdout+result.stderr)
            self.assertIn("PASS: cooperative bounded ESP8266-style WiFiClient reader",result.stdout)
            self.assertIn("NO DEVICE WRITER",result.stdout)

    def test_real_core_compile_probe_is_standalone_and_noninstalling(self):
        src=HEADER.read_text(encoding="utf-8")
        device=EMBEDDED.read_text(encoding="utf-8")
        bridge=BRIDGE.read_text(encoding="utf-8")
        rollback=ROLLBACK.read_text(encoding="utf-8")
        self.assertIn("kReadBytes = 512u",src)
        self.assertIn("kReadsPerPoll = 2u",src)
        self.assertIn("finishAfterExactFraming(nowMs)",src)
        self.assertIn("!client.connected()",src)
        self.assertIn("review.disconnect()",src)
        self.assertIn("template class NativeOtaNetworkPump<WiFiClient, UnwiredDeviceReview>",device)
        self.assertIn("template class StrictOtaDigestGate<NativeBearSslSha256>",device)
        self.assertIn("ARDUINOJSON_VERSION_REVISION == 3",device)
        self.assertIn("ARDUINOJSON_VERSION_MINOR == 4",device)
        self.assertIn("ARDUINOJSON_VERSION_MAJOR == 7",device)
        self.assertIn("br_sha256_init",device)
        self.assertIn("br_sha256_update",device)
        self.assertIn("br_sha256_out",device)
        self.assertIn("struct NativeRejectAllSink final",device)
        self.assertIn("bool beginForReview(uint32_t) { return false; }",device)
        self.assertIn("SHINO_ENABLE_NATIVE_SIGNED_OTA == 0",device)
        self.assertNotIn("NativeOtaNetworkPump.h",bridge)
        self.assertNotIn("NativeOtaDevicePumpCompileProbe",bridge)
        self.assertNotIn("NativeOtaNetworkPump.h",rollback)
        self.assertIn("ESP8266WebServer server(80)",bridge)
        self.assertIn("server.handleClient()",bridge)
        for content in (src,device):
            code="\n".join(line for line in content.splitlines()
                           if not line.lstrip().startswith("//"))
            for forbidden in (
                "Update.begin(", "Update.write(", "Update.end(",
                "installSignature(", "WiFiServer(", "WiFiServer ",
                "server.begin(", "LittleFS.begin(", "EEPROM.commit(", "ESP.restart(",
            ):
                self.assertNotIn(forbidden,code)
        for forbidden in ('server.on("/api/v1/bridge/ota/arm"',
                          'server.on("/api/v1/bridge/ota/upload"',
                          'server.on("/api/v1/bridge/ota/install"'):
            self.assertNotIn(forbidden,bridge)

if __name__=="__main__":
    unittest.main()
