"""General UTF-8 JSON HOST oracle against exact existing FslessMetrics source.

Not ArduinoJson. Verifies a broad wire-input space unavailable to the earlier
two-literal C++ localhost fixture, while never touching a device or listener.
"""
import json
import math
from pathlib import Path
import re
import unittest
from native_ota_host_json_oracle import (
    HostTelemetryJsonOracle, RANGES, ACCEPTED, INVALID_JSON, INVALID_LENGTH,
    INVALID_VALUES,
)

ROOT=Path(__file__).resolve().parent.parent
LIVE=ROOT/"firmware/src/boot/FslessMetrics.cpp"
BRIDGE=ROOT/"firmware/src/boot/FirstBootBridge.cpp"
ORACLE=ROOT/"tools/native_ota_host_json_oracle.py"
VALID={
    "ok": True,
    "gpu_available": True,
    "cpu_usage": 22.5,
    "gpu_usage": 34.5,
    "memory_used_gb": 8.0,
    "memory_total_gb": 16,
    "gpu_vram_mb": 2048,
    "gpu_temp_c": 56,
    "gpu_power": 120,
}

def wire(obj, **kwargs):
    return json.dumps(obj,separators=(",",":"),allow_nan=False,**kwargs).encode("utf-8")


class HostGeneralJsonOracleTests(unittest.TestCase):
    def setUp(self):
        self.oracle=HostTelemetryJsonOracle()

    def test_source_numeric_field_names_bounds_and_error_strings_stay_frozen(self):
        live=LIVE.read_text(encoding="utf-8")
        bridge=BRIDGE.read_text(encoding="utf-8")
        oracle=ORACLE.read_text(encoding="utf-8")
        for key,(low,high) in RANGES.items():
            needle=rf'bounded\(input,\s*"{key}",\s*{low:.1f}F,\s*{high:.1f}F'
            self.assertRegex(live,needle)
        self.assertIn('JsonVariantConst total = input["memory_total_gb"]',live)
        self.assertIn('value.as<float>()',live)
        self.assertIn("state = next; // Invalid payload never replaces",live)
        self.assertIn('METRICS_STALE_MS = 6000',live)
        self.assertIn('payload.length() < 16 || payload.length() > 384',bridge)
        for phrase in ("Invalid bounded telemetry payload length",
                       "Invalid JSON telemetry",
                       "Invalid, missing or out-of-range telemetry fields",
                       "RAM_SAMPLE_ACCEPTED"):
            self.assertIn(phrase,bridge)
            self.assertIn(phrase,oracle)
        self.assertIn('std::isfinite(numeric)',live)
        for banned in ("Updater.h","Update.begin(","Update.write(","Update.end(",
                       "WiFiServer","ESP8266WebServer","LittleFS.","EEPROM.",
                       "ESP.restart("):
            self.assertNotIn(banned,oracle)

    def test_valid_arbitrary_json_key_order_whitespace_exponents_and_extra_key(self):
        variants=[
            wire(VALID),
            wire(dict(reversed(list(VALID.items())))),
            wire(VALID,indent=1),
            wire({**VALID,"extra_marker":"ignored"}),
            wire({**VALID,"cpu_usage":2.25e1,"gpu_vram_mb":2.048e3}),
        ]
        for i,body in enumerate(variants):
            with self.subTest(variant=i):
                self.assertLessEqual(len(body),384)
                preview=self.oracle.preview_authenticated_post(body,100+i)
                self.assertEqual(preview.status,200)
                self.assertEqual(json.loads(preview.body),
                                 {"status":"RAM_SAMPLE_ACCEPTED","persisted":False})
                self.assertFalse(preview.device_write_performed)
                self.assertFalse(preview.actual_digest_checked)
                self.assertFalse(preview.actual_lcd_repainted)
                self.assertAlmostEqual(self.oracle.sample.cpu_usage,22.5)
                self.assertEqual(self.oracle.sample.last_received_ms,100+i)

    def test_optional_total_missing_and_explicit_null_do_not_invent_denominator(self):
        for total in ("omitted","null"):
            sample=dict(VALID)
            if total=="omitted":sample.pop("memory_total_gb")
            else:sample["memory_total_gb"]=None
            self.assertEqual(self.oracle.preview_authenticated_post(wire(sample),200).status,200)
            self.assertEqual(self.oracle.sample.memory_total_gb,0.0)
            self.assertEqual(self.oracle.sample.memory_used_gb,8.0)

    def test_invalid_json_and_utf8_have_dedicated_422_path_without_mutating_last_good(self):
        self.assertEqual(self.oracle.preview_authenticated_post(wire(VALID),100).status,200)
        previous=self.oracle.sample
        cases=[
            b'{"ok": truue, "gpu_available":true}',
            b'{"ok":true,',
            b'{"ok":true,\xff,"gpu_available":true}',
            b'{"ok":NaN,"gpu_available":true}',
            b'{"ok":Infinity,"gpu_available":true}',
            b'{"ok":-Infinity,"gpu_available":true}',
            b'not-json-for-test',
        ]
        for i,body in enumerate(cases):
            with self.subTest(case=i):
                # For tiny truncated cases the *original* 16..384 check wins.
                result=self.oracle.preview_authenticated_post(body,200+i)
                self.assertEqual(result.status,413 if len(body)<16 else 422)
                self.assertEqual(result.body,
                                 INVALID_LENGTH if len(body)<16 else INVALID_JSON)
                self.assertEqual(self.oracle.sample,previous)

    def test_bounded_post_length_takes_precedence_over_syntax(self):
        for body in (b"",b"X"*15,b"X"*385,b"X"*494404):
            self.assertEqual(self.oracle.preview_authenticated_post(body,200).status,413)
            self.assertEqual(self.oracle.preview_authenticated_post(body,200).body,INVALID_LENGTH)
            self.assertFalse(self.oracle.sample.received)

    def test_numeric_type_finiteness_and_source_ranges_preserve_last_valid_sample(self):
        self.assertEqual(self.oracle.preview_authenticated_post(wire(VALID),100).status,200)
        before=self.oracle.sample
        invalid=[
            {"ok":False},{"ok":"true"},{"gpu_available":"false"},
            {"gpu_available":1},{"cpu_usage":True},{"gpu_usage":"34.5"},
            {"cpu_usage":-0.01},{"cpu_usage":101},{"gpu_usage":-1},
            {"memory_used_gb":257},{"gpu_vram_mb":65537},
            {"gpu_temp_c":-41},{"gpu_temp_c":131},{"gpu_power":1201},
            {"memory_total_gb":0},{"memory_total_gb":7},
            {"memory_total_gb":"16"},{"memory_total_gb":True},
            {"cpu_usage":1e100},{"ok":None}
        ]
        for i,delta in enumerate(invalid):
            case={**VALID,**delta}
            with self.subTest(case=i,delta=delta):
                response=self.oracle.preview_authenticated_post(wire(case),200+i)
                self.assertEqual(response.status,422)
                self.assertEqual(response.body,INVALID_VALUES)
                self.assertEqual(self.oracle.sample,before)
        for removed in ("ok","gpu_available",*RANGES):
            with self.subTest(missing=removed):
                case=dict(VALID);case.pop(removed)
                self.assertEqual(self.oracle.preview_authenticated_post(wire(case),500).status,422)
                self.assertEqual(self.oracle.sample,before)

    def test_stale_strictly_after_six_seconds_and_millis_wraparound(self):
        self.assertTrue(self.oracle.stale(0))
        self.assertEqual(self.oracle.preview_authenticated_post(wire(VALID),100).status,200)
        self.assertFalse(self.oracle.stale(6100))
        self.assertTrue(self.oracle.stale(6101))
        self.assertEqual(self.oracle.preview_authenticated_post(wire(VALID),0xfffffff0).status,200)
        self.assertFalse(self.oracle.stale(0x40))

    def test_out_of_range_huge_exponent_and_non_json_nan_are_never_accepted(self):
        base=wire(VALID)
        substitute=base.replace(b'"cpu_usage":22.5',b'"cpu_usage":1e999')
        self.assertLessEqual(len(substitute),384)
        self.assertEqual(self.oracle.preview_authenticated_post(substitute,100).status,422)
        self.assertEqual(self.oracle.preview_authenticated_post(substitute,100).body,INVALID_VALUES)
        self.assertFalse(self.oracle.sample.received)

if __name__=="__main__":
    unittest.main()
