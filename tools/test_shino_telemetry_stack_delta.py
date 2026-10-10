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
        if not report.is_file():
            # The full repository audit job discovers this same unit test
            # without compiling PlatformIO. Only the HTTP OTA job owns the
            # compiled public evidence and must fail if it is missing.
            import os
            if os.environ.get("GITHUB_WORKFLOW") == "SHINO normal HTTP OTA":
                self.fail("HTTP OTA CI missing required B3 public PIO build")
            self.skipTest("Source-only job: compiled B3 delta runs in HTTP OTA CI")
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


def physical_fixture():
    # All synthetic values: never claim this is a real SmallTV measurement.
    manifest = {"layout":"4m2m","protocol":"shino-http-ota-1",
                "device":"0123456789abcdef","build_id":"a"*64,
                "sha256":"b"*64,"bytes":407776}
    identity = {key:manifest[key] for key in ("device","build_id","sha256","bytes")}
    identity.update(protocol=manifest["protocol"],ota_enabled=True,fs_ok=True,
                    boot_id="c"*32)
    status = {"config_loaded_readonly":True,"private_ap_ready":True,
              "mounted":True,"inventory_exact":True,"config_seed_exact":True,
              "resource_measurements_valid":True,"design_floors_observed":True,
              "heap_floor":20480,"block_floor":16384,
              "fragmentation_ceiling":25,"continuation_floor":2048,
              "rejected_sample_count":0,
              "setup_cont_stack_start":3800,"setup_cont_stack_min":3540,
              "fs_config_cont_stack_start":3800,"fs_config_cont_stack_min":3580,
              "runtime_cont_stack_start":3800}
    observations = []
    for count,stack,heap,block,frag in (
        (1,3400,31000,27000,7),
        (100,2400,28000,23000,12),
        (202,2200,26500,19500,18)):
        current = copy.deepcopy(status)
        current.update(resource_sample_count=count,runtime_cont_stack_min=stack,
                       lowest_heap=heap,lowest_block=block,
                       highest_fragmentation_percent=frag)
        observations.append(dict(identity=copy.deepcopy(identity),status=current))
    return dict(schema=1,source="OWNER_CAPTURED_READONLY_STATUS",
                expected_manifest=manifest,observations=observations)


class B3ResourceTranscriptTests(unittest.TestCase):
    def test_synthetic_resource_transcript_is_reviewable_but_never_ota_authority(self):
        from shino_b3_resource_evidence import review
        result=review(physical_fixture())
        self.assertEqual(result["poll_span"],201)
        self.assertEqual(result["min_free_cont_stack_bytes"],2200)
        self.assertEqual(result["min_free_heap_bytes"],26500)
        self.assertEqual(result["min_largest_free_block_bytes"],19500)
        self.assertEqual(result["physical_qualification"],"HOLD")
        self.assertFalse(result["ota_authorized"])
        self.assertTrue(result["measurement_origin_not_cryptographically_attested"])

    def test_stack_and_heap_below_floor_are_rejected(self):
        from shino_b3_resource_evidence import review,EvidenceHold
        for key,value in (("runtime_cont_stack_min",1968),
                          ("lowest_heap",20479),
                          ("lowest_block",16383),
                          ("highest_fragmentation_percent",26)):
            report=physical_fixture()
            report["observations"][-1]["status"][key]=value
            with self.subTest(key=key),self.assertRaises(EvidenceHold):
                review(report)

    def test_reboot_watermark_repaint_and_untrusted_identity_hold(self):
        from shino_b3_resource_evidence import review,EvidenceHold
        scenarios=(
            ("identity","boot_id","f"*32),
            ("identity","sha256","f"*64),
            ("status","runtime_cont_stack_min",3600),
            ("status","lowest_heap",32000),
            ("status","rejected_sample_count",1),
            ("status","resource_sample_count",101),
            ("status","continuation_floor",1968),
            ("status","design_floors_observed",False),
        )
        for section,key,value in scenarios:
            report=physical_fixture()
            report["observations"][-1][section][key]=value
            with self.subTest(key=key),self.assertRaises(EvidenceHold):
                review(report)

    def test_short_window_or_unknown_samples_remain_hold(self):
        from shino_b3_resource_evidence import review,EvidenceHold
        report=physical_fixture()
        report["observations"][-1]["status"]["resource_sample_count"]=180
        with self.assertRaises(EvidenceHold):review(report)
        report=physical_fixture()
        report["observations"][-1]["status"]["lowest_block"]=4294967295
        with self.assertRaises(EvidenceHold):review(report)
        report=physical_fixture()
        report["observations"]=report["observations"][:2]
        with self.assertRaises(EvidenceHold):review(report)


if __name__ == "__main__":
    unittest.main()
