"""Source-grounded host-only legacy browser-session and PC telemetry parity.

C++ session/typed metrics model tests do NOT authenticate real Digest, decode
ArduinoJson, dispatch HTTP handlers, repaint LCD or authorize firmware writes.
Python JSON fixtures check the ACTUAL live FslessMetrics keys, not the old
illustrative but incompatible {cpu,gpu,memoryGb} sample.
"""
import json
import math
from pathlib import Path
import re
import shutil
import subprocess
import tempfile
import unittest

ROOT=Path(__file__).resolve().parent.parent
SESSION=ROOT/"firmware/include/boot/NativeOtaLegacySessionReview.h"
TELEMETRY=ROOT/"firmware/include/boot/NativeOtaLegacyTelemetryReview.h"
PROBE=ROOT/"tools/native_ota_legacy_compatibility_probe.cpp"
BRIDGE=ROOT/"firmware/src/boot/FirstBootBridge.cpp"
ACTUAL=ROOT/"firmware/src/boot/FslessMetrics.cpp"
ACTUAL_HEADER=ROOT/"firmware/include/boot/FslessMetrics.h"
WEBUI=ROOT/"firmware/src/boot/FslessWebUI.cpp"
FIELDS={
    "cpu_usage":(0,100),
    "gpu_usage":(0,100),
    "memory_used_gb":(0,256),
    "gpu_vram_mb":(0,65536),
    "gpu_temp_c":(-40,130),
    "gpu_power":(0,1200),
}
EXAMPLE={
    "ok":True,"gpu_available":True,
    "cpu_usage":22.5,"gpu_usage":34.5,"memory_used_gb":8.0,
    "memory_total_gb":16.0,"gpu_vram_mb":2048,"gpu_temp_c":56,
    "gpu_power":120,
}
def fixture_wire(sample):
    return json.dumps(sample,separators=(",",":"),allow_nan=False).encode("ascii")

def schema_oracle(sample):
    # Host test oracle only; ArduinoJson parsing occurs in original firmware.
    if type(sample) is not dict or type(sample.get("ok")) is not bool or not sample["ok"]:
        return False
    if type(sample.get("gpu_available")) is not bool:
        return False
    for key,(low,high) in FIELDS.items():
        value=sample.get(key)
        if type(value) not in (int,float) or not math.isfinite(value) or not low<=value<=high:
            return False
    if "memory_total_gb" in sample and sample["memory_total_gb"] is not None:
        total=sample["memory_total_gb"]
        if (type(total) not in (int,float) or not math.isfinite(total) or
            not 0.01<=total<=256 or sample["memory_used_gb"]>total):
            return False
    return True

class LegacyBrowserAndTelemetryCompatibility(unittest.TestCase):
    def test_host_cpp_session_and_typed_telemetry_behavior(self):
        gpp=shutil.which("g++")
        self.assertIsNotNone(gpp,"CI must compile actual host C++ policy")
        with tempfile.TemporaryDirectory(prefix="shino-legacy-parity-") as tmp:
            exe=Path(tmp)/"legacy-fixture-proof"
            b=subprocess.run(
                [gpp,"-std=c++17","-Wall","-Wextra","-Werror","-pedantic",
                 "-I",str(ROOT/"firmware/include"),str(PROBE),"-o",str(exe)],
                capture_output=True,text=True,timeout=30,check=False)
            self.assertEqual(b.returncode,0,b.stderr)
            r=subprocess.run([str(exe)],capture_output=True,text=True,
                             timeout=20,check=False)
            self.assertEqual(r.returncode,0,r.stdout+r.stderr)
            self.assertIn("PASS: HOST synthetic 2-slot GET-only",r.stdout)
            self.assertIn("NO real auth/server/LCD/OTA/flash",r.stdout)

    def test_source_contract_and_host_model_fail_together_on_schema_drift(self):
        source=ACTUAL.read_text(encoding="utf-8")
        first=BRIDGE.read_text(encoding="utf-8")
        model=TELEMETRY.read_text(encoding="utf-8")
        header=ACTUAL_HEADER.read_text(encoding="utf-8")
        self.assertIn("METRICS_STALE_MS = 6000",source)
        self.assertIn("state = next; // Invalid payload never replaces",source)
        self.assertIn("bool apply(JsonVariantConst input, String& error)",source)
        self.assertIn('!input["ok"].is<bool>()',source)
        self.assertIn('!input["gpu_available"].is<bool>()',source)
        for key,(low,high) in FIELDS.items():
            regex=r'bounded\(input,\s*"'+re.escape(key)+r'",\s*'+str(float(low))+r'F,\s*'+str(float(high))+r'F'
            self.assertRegex(source,regex)
        self.assertIn('JsonVariantConst total = input["memory_total_gb"]',source)
        self.assertIn('next.memoryGb > next.memoryTotalGb',source)
        self.assertIn('next.received = true',source)
        self.assertIn('state = next',source)
        self.assertIn('std::isfinite(numeric)',source)
        for literal in ("kStaleMs=6000u","kMemoryMaxGb=256.0",
                        "kTempMinC=-40.0","kPowerMaxW=1200.0"):
            self.assertIn(literal,model)
        self.assertIn("float memoryTotalGb = 0.0F",header)
        self.assertIn('server.arg("plain")',first)
        self.assertIn('payload.length() < 16 || payload.length() > 384',first)
        self.assertIn('FslessMetrics::apply(doc.as<JsonVariantConst>(), error)',first)
        self.assertIn('telemetryNeedsRedraw = true',first)

    def test_actual_browser_session_route_and_cookie_rules_are_frozen(self):
        source=BRIDGE.read_text(encoding="utf-8")
        model=SESSION.read_text(encoding="utf-8")
        self.assertIn("std::array<BrowserSession, 2> browserSessions",source)
        self.assertIn("BROWSER_SESSION_LIFETIME_MS = 2UL * 60UL * 60UL * 1000UL",source)
        self.assertIn('raw.length() > 256',source)
        self.assertIn('if (seen) return String()',source)
        self.assertIn("session.peer != peer",source)
        self.assertIn("if (browserSessionValid()) return true;",source)
        self.assertIn('Only the Digest-authenticated GET / can create a new browser session.',source)
        self.assertIn("issueBrowserReadSession();",source)
        self.assertIn("if (!requireAuth()) return;",source)
        self.assertIn('server.on("/api/v1/bridge/metrics", HTTP_GET, sendMetrics)',source)
        self.assertIn('server.on("/api/v1/bridge/metrics", HTTP_POST, acceptMetrics)',source)
        self.assertIn("kReadLifetimeMs=2u*60u*60u*1000u",model)
        self.assertIn("kMaxCookieHeaderBytes=256u",model)
        self.assertIn("kSlots=2u",model)
        self.assertIn("BackgroundForbiddenNoChallenge",model)
        self.assertIn("WouldAcceptMetricsPost",model)
        self.assertNotIn("NativeOtaLegacySessionReview.h",source)
        self.assertNotIn("NativeOtaLegacyTelemetryReview.h",source)
        for code in (SESSION.read_text(encoding="utf-8"),
                     TELEMETRY.read_text(encoding="utf-8")):
            without_comments="\n".join(x for x in code.splitlines()
                                       if not x.lstrip().startswith("//"))
            for unsafe in ("Update.begin(", "Update.write(", "Update.end(",
                           "WiFiServer", "ESP8266WebServer",
                           "LittleFS.", "EEPROM.", "ESP.restart("):
                self.assertNotIn(unsafe,without_comments)

    def test_real_json_fixture_accepts_all_four_card_fields_and_under_384_bytes(self):
        sample=json.loads(fixture_wire(EXAMPLE))
        self.assertTrue(schema_oracle(sample))
        self.assertLessEqual(len(fixture_wire(EXAMPLE)),384)
        for name in ("cpu_usage","gpu_usage","memory_used_gb","gpu_temp_c"):
            self.assertIn(name,sample)
        browser=WEBUI.read_text(encoding="utf-8")
        for name in ("CPU usage","GPU usage","RAM in use","temperature"):
            self.assertIn(name,browser)

    def test_old_illustrative_json_keys_are_not_a_valid_companion_packet(self):
        old={"cpu":22.5,"gpu":34.5,"memoryGb":8,"memoryTotalGb":16,"gpuTempC":56}
        self.assertFalse(schema_oracle(json.loads(fixture_wire(old))))
        self.assertFalse(schema_oracle({"ok":True,"gpu_available":False,**old}))

    def test_optional_ram_total_and_invalid_good_sample_contract(self):
        without=dict(EXAMPLE);without.pop("memory_total_gb")
        self.assertTrue(schema_oracle(json.loads(fixture_wire(without))))
        for key,value in (
            ("ok",False),("ok","true"),("gpu_available",1),
            ("cpu_usage",True),("gpu_usage","35"),
            ("memory_used_gb",-1),("gpu_vram_mb",65537),
            ("gpu_temp_c",131),("gpu_power",1201),
            ("memory_total_gb",0),("memory_total_gb",4),
        ):
            with self.subTest(key=key,value=value):
                changed=dict(EXAMPLE);changed[key]=value
                self.assertFalse(schema_oracle(changed))
        # Invalid fixture is rejected before any simulated previous-good state replacement.
        self.assertTrue(schema_oracle(EXAMPLE))
        self.assertFalse(schema_oracle({"ok":True,"gpu_available":True}))
        self.assertTrue(schema_oracle(without))

if __name__=="__main__":
    unittest.main()
