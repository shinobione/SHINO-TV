"""Host-only single-owner port80 migration route-table parity with current bridge.

Does not start a second listener or monkeypatch the legacy webserver.
"""
from pathlib import Path
import re
import shutil
import subprocess
import tempfile
import unittest

ROOT=Path(__file__).resolve().parent.parent
HEADER=ROOT/"firmware/include/boot/NativeOtaPort80Plan.h"
PROBE=ROOT/"tools/native_ota_port80_plan_probe.cpp"
BRIDGE=ROOT/"firmware/src/boot/FirstBootBridge.cpp"
NATIVE_PUMP=ROOT/"firmware/src/boot/NativeOtaDevicePumpCompileProbe.cpp"


def probe_route_block(source):
    """Fail closed on the sole audited opt-in route; never widen legacy parity."""
    blocks=re.findall(r'^#if SHINO_BOOT_PROFILE == 2\n'
                      r'(    server\.on\("/api/v1/m9/fs-probe/status",.*?\n)'
                      r'#endif\n',source,re.M|re.S)
    assert len(blocks)==1,"Probe route must have its own exact profile-2 guard"
    body=blocks[0]
    assert re.findall(r'server\.on\("([^"]+)",\s*(HTTP_GET|HTTP_POST)',body)==[
        ("/api/v1/m9/fs-probe/status","HTTP_GET")]
    assert body.startswith('    server.on("/api/v1/m9/fs-probe/status", HTTP_GET, []() {\n'
                           '        if (!requireAuth()) return;')
    assert 'char body[M9LittleFsMountProbe::STATUS_JSON_BYTES];' in body
    assert 'M9LittleFsMountProbe::json(body, sizeof(body))' in body
    assert 'respond(500,' in body and 'respond(200, body);' in body
    for forbidden in ('browserSessionValid', 'LittleFS.', 'Update.', 'ESP.restart(',
                      'server.begin(', 'HTTP_POST'):
        assert forbidden not in body
    return '#if SHINO_BOOT_PROFILE == 2\n'+body+'#endif\n'


class OwnerPort80MigrationPlanTests(unittest.TestCase):
    def test_route_classification_builds_and_runs_without_a_listener(self):
        compiler=shutil.which("g++")
        self.assertIsNotNone(compiler,"CI requires g++")
        with tempfile.TemporaryDirectory(prefix="shino-ota-port80-plan-") as d:
            exe=Path(d)/"source-only-route-matrix"
            b=subprocess.run([compiler,"-std=c++17","-Wall","-Wextra","-Werror",
                              "-pedantic","-I",str(ROOT/"firmware/include"),str(PROBE),
                              "-o",str(exe)],capture_output=True,text=True,
                             timeout=30,check=False)
            self.assertEqual(b.returncode,0,b.stderr)
            r=subprocess.run([str(exe)],capture_output=True,text=True,
                             timeout=10,check=False)
            self.assertEqual(r.returncode,0,r.stdout+r.stderr)
            self.assertIn("PASS: source-only port80 route parity",r.stdout)
            self.assertIn("NO listener or upload writer",r.stdout)

    def test_exact_legacy_bridge_route_parity_is_documented_without_activation(self):
        original=BRIDGE.read_text(encoding="utf-8")
        plan=HEADER.read_text(encoding="utf-8")
        legacy=original.replace(probe_route_block(original),"")
        actual=set(re.findall(r'server\.on\("([^"]+)",\s*(HTTP_GET|HTTP_POST)',legacy))
        expected={
            ("/","HTTP_GET"),("/ui.js","HTTP_GET"),
            ("/api/v1/bridge/metrics","HTTP_GET"),
            ("/api/v1/bridge/metrics","HTTP_POST"),
            ("/api/v1/bridge/status","HTTP_GET"),
            ("/api/v1/bridge/fs-plan","HTTP_GET"),
            ("/api/v1/bridge/ota/capabilities","HTTP_GET"),
            ("/api/v1/bridge/factory-return","HTTP_GET"),
            ("/api/v1/bridge/factory-return","HTTP_POST"),
        }
        self.assertEqual(actual,expected,"Live bridge route changes require a fresh port-80 audit")
        self.assertEqual(original.count("ESP8266WebServer server(80)"),1)
        self.assertEqual(original.count("server.handleClient()"),1)
        self.assertIn("server.onNotFound",original)
        self.assertIn("SHINO_ENABLE_FACTORY_RESTORE",original)
        for path,method in actual:
            self.assertIn(path,plan)
        self.assertIn("OtaReservedArm",plan)
        self.assertIn("OtaReservedUpload",plan)
        self.assertIn("OtaReservedReject",plan)
        self.assertIn("LegacyAuthenticatedNotFound",plan)
        self.assertIn("LegacyMetricsPost",plan)
        self.assertIn("LegacyFactoryReturnPost",plan)
        self.assertIn("currentlyRegisteredInFirstBootBridge=false",plan)
        self.assertNotIn("NativeOtaPort80Plan.h",original)
        self.assertIn("NativeOtaPort80Plan.h",NATIVE_PUMP.read_text(encoding="utf-8"))
        self.assertIn("SHINO_ENABLE_NATIVE_SIGNED_OTA == 0",
                      NATIVE_PUMP.read_text(encoding="utf-8"))
        for code in (plan,PROBE.read_text(encoding="utf-8")):
            without_comments="\n".join(line for line in code.splitlines()
                                        if not line.lstrip().startswith("//"))
            for forbidden in ("WiFiServer", "server.begin(", "server.handleClient(",
                              "Update.begin(", "Update.write(", "Update.end(",
                              "ESP.restart(", "LittleFS.", "EEPROM."):
                self.assertNotIn(forbidden,without_comments)

    def test_profile2_probe_route_is_get_only_digest_and_bounded_on_same_owner(self):
        original=BRIDGE.read_text(encoding="utf-8")
        block=probe_route_block(original)
        self.assertEqual(original.count('server.on("/api/v1/m9/fs-probe/status"'),1)
        self.assertNotIn('/api/v1/m9/fs-probe/status',original.replace(block,''))
        self.assertEqual(original.count("ESP8266WebServer server(80)"),1)
        self.assertEqual(original.count("server.handleClient()"),1)

    def test_probe_route_guard_auth_method_and_bound_mutations_fail_audit(self):
        original=BRIDGE.read_text(encoding="utf-8")
        block=probe_route_block(original)
        for old,new in (('#if SHINO_BOOT_PROFILE == 2','#if SHINO_BOOT_PROFILE == 0'),
                        ('HTTP_GET','HTTP_POST'),
                        ('if (!requireAuth()) return;',
                         'if (!browserSessionValid() && !requireAuth()) return;'),
                        ('if (!requireAuth()) return;',''),
                        ('STATUS_JSON_BYTES','4096')):
            with self.subTest(mutation=old):
                with self.assertRaises(AssertionError):
                    probe_route_block(original.replace(block,block.replace(old,new)))

if __name__=="__main__":
    unittest.main()
