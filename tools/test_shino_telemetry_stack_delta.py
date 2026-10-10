"""Offline, synthetic positive and negative B2 candidate gates."""
import copy
import json
import unittest
from pathlib import Path

import shino_telemetry_stack_delta as gate


BASE = json.loads((Path(__file__).parent / "fixtures/shino_b2_public_stack_baseline.json").read_text())


def candidate(telemetry=144):
    s = {"status":"COMPILED_NORMAL_HANDLER_FRAMES_NOT_NATIVE_STACK_BOUND",
         "stack_free_floor":2048,"stack_budget_total":4096,
         "native_highwater_is_historical":True,"reset_during_poll":False,
         "complete_normal_native_upper_bound":False,"physical":"NOT_RUN",
         "device_contacts":0,"ota_posts":0,"serial_writes":0,
         "handler_frames":{k:{"state":"MEASURED_STATIC","frame_bytes":v}
                           for k,v in BASE["handler_frames"].items()}}
    s["handler_frames"]["telemetry_post"]["frame_bytes"] = telemetry
    b = {"layout":"4m2m","noinit":56,"core_buffer":4096,"physical":"NOT_RUN",
         "device_contacts":0,"layout_symbols":copy.deepcopy(BASE["layout_symbols"]),
         "static_ram":BASE["static_ram"]+64,"bytes":407900,
         "stack_frames":copy.deepcopy(BASE["retained_frame_caps"])}
    return s,b


class TestB2StackDelta(unittest.TestCase):
    def hold(self, change):
        s,b=candidate()
        change(s,b)
        with self.assertRaises(gate.Hold):gate.compare(BASE,s,b)

    def test_real_b3_compiled_delta_not_synthetic(self):
        # The HTTP CI builds research-local/http-ota-ci BEFORE invoking this
        # suite. Baseline B2 branches retain synthetic-only unit coverage.
        from shino_b2_stack_forensics import audit
        root = Path(__file__).resolve().parents[1]
        normal = (root / "ota/firmware/Normal.cpp").read_text(encoding="utf-8")
        if "TelemetryScratchLease scratch;" not in normal:
            self.skipTest("No B3 telemetry scratch candidate in this source tree")
        folder = root / "research-local/http-ota-ci"
        report = folder / "report.json"
        self.assertTrue(report.is_file(), "B3 must have a real public PIO build")
        actual_stack = audit(folder)
        actual_build = json.loads(report.read_text(encoding="utf-8"))
        result = gate.compare(BASE, actual_stack, actual_build)
        self.assertGreater(result["compiled_frame_reduction_bytes"], 0)
        self.assertLess(result["candidate_frame_bytes"], BASE["baseline_telemetry_frame_bytes"])
        self.assertEqual(result["physical_qualification"], "HOLD")
        self.assertFalse(result["ota_authorized"])
        print("B3_ACTUAL_COMPILED_DELTA=" + json.dumps(result, sort_keys=True))

    def test_positive_is_only_compiled_frame_not_native_or_ota(self):
        s,b=candidate()
        result=gate.compare(BASE,s,b)
        self.assertEqual(result["compiled_frame_reduction_bytes"],80)
        self.assertEqual(result["physical_qualification"],"HOLD")
        self.assertFalse(result["native_highwater_proven"])
        self.assertFalse(result["ota_authorized"])

    def test_unmodified_frame_holds(self):
        self.hold(lambda s,b:s["handler_frames"]["telemetry_post"].update(frame_bytes=224))

    def test_dynamic_frame_is_unknown_not_zero(self):
        self.hold(lambda s,b:s["handler_frames"]["telemetry_post"].update(state="DYNAMIC_UNKNOWN",frame_bytes=None))

    def test_other_http_frame_regression_holds(self):
        self.hold(lambda s,b:s["handler_frames"]["identity_get"].update(frame_bytes=164))

    def test_static_ram_cap_enforced(self):
        self.hold(lambda s,b:b.update(static_ram=BASE["static_ram"]+257))

    def test_partition_and_core_buffer_preserved(self):
        self.hold(lambda s,b:b["layout_symbols"].update(_FS_start=0x40300000))
        self.hold(lambda s,b:b.update(core_buffer=1024))

    def test_stack_floor_unchanged(self):
        self.hold(lambda s,b:s.update(stack_free_floor=1968))

    def test_repainting_highwater_is_not_an_optimization(self):
        self.hold(lambda s,b:s.update(reset_during_poll=True))

    def test_uncertainty_cannot_be_promoted_to_full_native_proof(self):
        self.hold(lambda s,b:s.update(complete_normal_native_upper_bound=True))

    def test_private_or_physical_contact_rejected(self):
        self.hold(lambda s,b:s.update(device_contacts=1))
        self.hold(lambda s,b:b.update(physical="PASS"))

    def test_original_ota_frame_caps_retained(self):
        self.hold(lambda s,b:b["stack_frames"].update(ota_segments=244))

    def test_baseline_hash_pinned(self):
        s,b=candidate()
        changed=dict(BASE,source_sha256="f"*64)
        with self.assertRaises(gate.Hold):gate.compare(changed,s,b)


if __name__ == "__main__":
    unittest.main()
