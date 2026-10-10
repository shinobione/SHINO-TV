"""Offline B3 read-only capture regressions. Never call a network endpoint."""
import io
import json
import tempfile
import unittest
from contextlib import redirect_stdout
from pathlib import Path
from unittest.mock import patch

import shino_b3_capture as cap
from shino_b3_resource_evidence import review, EvidenceHold

RELEASE = {"layout":"4m2m", "protocol":"shino-http-ota-1",
           "device":"0123456789abcdef", "build_id":"a"*64,
           "sha256":"b"*64, "bytes":407776}


class Fake:
    def __init__(self, mutation=None):
        self.calls = []
        self.sleeps = []
        self.mutation = mutation

    def read(self, io, path, cycle):
        self.calls.append((path, cycle))
        result = self.identity() if path == cap.IDENTITY else self.normal(cycle)
        if self.mutation:
            result = self.mutation(result, path, cycle, len(self.calls))
        return result

    def sleep(self, seconds):
        self.sleeps.append(seconds)

    def identity(self):
        return dict(protocol=RELEASE["protocol"], device=RELEASE["device"],
                    build_id=RELEASE["build_id"], sha256=RELEASE["sha256"],
                    bytes=RELEASE["bytes"], boot_id="c"*32,
                    ota_enabled=True, fs_ok=True, nonce="private-secret-omit",
                    last_update="NONE")

    def normal(self, cycle):
        return dict(mode="M9_NORMAL_STAGE_A",
                    config_loaded_readonly=True, private_ap_ready=True,
                    mounted=True, inventory_exact=True, config_seed_exact=True,
                    resource_measurements_valid=True, design_floors_observed=True,
                    heap_floor=20480, block_floor=16384,
                    fragmentation_ceiling=25, continuation_floor=2048,
                    rejected_sample_count=0,
                    resource_sample_count=1+(cycle-1)*20,
                    runtime_cont_stack_min=3000-4*cycle,
                    lowest_heap=34000-200*cycle,
                    lowest_block=30000-250*cycle,
                    highest_fragmentation_percent=cycle,
                    setup_cont_stack_start=3800, setup_cont_stack_min=3500,
                    fs_config_cont_stack_start=3800, fs_config_cont_stack_min=3450,
                    runtime_cont_stack_start=3800,
                    unexpected_private_field="must-not-be-written")


class CaptureTests(unittest.TestCase):
    def run_capture(self, mutation=None):
        fake=Fake(mutation)
        result=cap.collect(object(),RELEASE,reader=fake.read,sleep=fake.sleep)
        return result,fake

    def test_default_is_print_only_even_with_bad_local_files(self):
        output=io.StringIO()
        with patch.object(cap, "inspect", side_effect=AssertionError("read forbidden")), \
             patch.object(cap, "Transport", side_effect=AssertionError("network forbidden")), \
             redirect_stdout(output):
            self.assertEqual(cap.main([]),0)
        self.assertEqual(json.loads(output.getvalue())["status"],
                         "PRINT_ONLY_NO_DEVICE_CONTACT")

    def test_exact_bounded_gets_and_private_field_redaction(self):
        transcript,fake=self.run_capture()
        self.assertEqual(len(fake.calls),33)
        self.assertEqual(fake.sleeps,[20]*10)
        self.assertEqual({p for p,c in fake.calls},{cap.IDENTITY,cap.NORMAL})
        self.assertEqual([p for p,c in fake.calls[:3]],
                         [cap.IDENTITY,cap.NORMAL,cap.IDENTITY])
        for entry in transcript["observations"]:
            self.assertNotIn("nonce",entry["identity"])
            self.assertNotIn("last_update",entry["identity"])
            self.assertNotIn("unexpected_private_field",entry["status"])
        result=review(transcript)
        self.assertEqual(result["poll_span"],200)
        self.assertEqual(result["physical_qualification"],"HOLD")
        self.assertFalse(result["ota_authorized"])

    def test_pair_identity_drift_rejects_before_more_gets(self):
        def changed(data,path,cycle,number):
            if cycle==2 and path==cap.IDENTITY and number==6:
                data["boot_id"]="d"*32
            return data
        fake=Fake(changed)
        with self.assertRaisesRegex(cap.CaptureHold,"IDENTITY_CHANGED"):
            cap.collect(object(),RELEASE,reader=fake.read,sleep=fake.sleep)
        self.assertEqual(len(fake.calls),6)

    def test_wrong_release_and_normal_mode_are_rejected(self):
        cases = (
            lambda data,path,cycle,num: (dict(data,bytes=1) if path==cap.IDENTITY else data),
            lambda data,path,cycle,num: (dict(data,mode="OTHER") if path==cap.NORMAL else data),
        )
        for change in cases:
            fake=Fake(change)
            with self.assertRaises(cap.CaptureHold):
                cap.collect(object(),RELEASE,reader=fake.read,sleep=fake.sleep)

    def test_window_and_read_bounds_are_fixed(self):
        for cycles,interval in ((2,20),(11,5),(100,20),(11,45)):
            fake=Fake()
            with self.subTest(cycles=cycles,interval=interval),self.assertRaises(cap.CaptureHold):
                cap.collect(object(),RELEASE,reader=fake.read,sleep=fake.sleep,
                            cycles=cycles,interval=interval)
            self.assertFalse(fake.calls)

    def test_low_stack_is_saved_for_hold_not_turned_into_pass(self):
        transcript,_=self.run_capture()
        transcript["observations"][-1]["status"]["runtime_cont_stack_min"]=1968
        with self.assertRaises(EvidenceHold):
            review(transcript)

    def test_local_receipt_never_overwritten_and_never_in_tracked_tree(self):
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp)
            (root/"research-local").mkdir()
            with patch.object(cap,"ROOT",root):
                transcript,_=self.run_capture()
                bad=root/"companion"/"leak.json"
                with self.assertRaises(cap.CaptureHold):cap.private_output(bad)
                allowed=root/"research-local"/"owner-b3.json"
                cap.save_private(allowed,transcript)
                self.assertTrue(allowed.is_file())
                self.assertEqual(json.loads(allowed.read_text())["schema"],1)
                with self.assertRaises(cap.CaptureHold):cap.save_private(allowed,transcript)
                target=root/"research-local"/"link.json"
                try:
                    target.symlink_to(allowed)
                except (OSError,NotImplementedError):
                    pass
                else:
                    with self.assertRaises(cap.CaptureHold):cap.save_private(target,transcript)


if __name__=="__main__":
    unittest.main()
