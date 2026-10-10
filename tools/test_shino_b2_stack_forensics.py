"""Offline B2 stack forensics tests; no SDK/firmware compile required."""
import tempfile
import unittest
import shutil
import subprocess
from pathlib import Path
from unittest.mock import patch

import shino_b2_stack_forensics as f


class TestForensics(unittest.TestCase):
    def test_su_parses_function_name_and_disallows_unknown_zero(self):
        rows = f.rows_of_su(
            "/tmp/M9NormalStageA.cpp:111:9:void M9NormalStageA::identity()\t160\tstatic\n"
            "/tmp/M9NormalStageA.cpp:112:9:void M9NormalStageA::telemetry()\t80\tdynamic\n"
            "incorrect-data\n")
        self.assertEqual(len(rows), 2)
        self.assertEqual(rows[0]["frame_bytes"], 160)
        self.assertIn("identity()", rows[0]["signature"])
        self.assertEqual(rows[1]["kind"], "dynamic")

    def test_original_frame_caps_enforced(self):
        data = "\n".join([
            f"Normal.cpp:1:1:void Foo{marker}\t{f.RETAINED_FRAME_CAPS.get(key, 80)}\tstatic"
            for key,marker in f.TARGETS.items()])
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp)
            build = path / ".pio/build" / f.ENV
            root = build / "src/boot"
            root.mkdir(parents=True)
            (build / "firmware.elf").write_bytes(b"PUBLIC-ONLY")
            (root / "M9NormalStageA.cpp.su").write_text(data)
            handlers, _ = f.collect_frames(path)
            self.assertEqual(handlers["identity_get"]["frame_bytes"], 160)
            self.assertEqual(handlers["normal_status_get"]["frame_bytes"], 256)
            (root / "M9NormalStageA.cpp.su").write_text(data.replace("::identity()\t160", "::identity()\t164"))
            with self.assertRaisesRegex(ValueError, "identity_get"):
                f.collect_frames(path)

    def test_missing_or_dynamic_handler_is_not_zero_stack(self):
        only = "\n".join([
            "Normal.cpp:1:1:void Foo::identity()\t160\tstatic",
            "Normal.cpp:2:1:void Foo::status()\t96\tstatic",
            "Normal.cpp:3:1:void Foo::metrics()\t112\tstatic",
            "Normal.cpp:4:1:void Foo::telemetry()\t32\tdynamic",
        ])
        with tempfile.TemporaryDirectory() as tmp:
            path=Path(tmp); root=path/".pio/build"/f.ENV
            (root/"src/boot").mkdir(parents=True)
            (root/"firmware.elf").write_bytes(b"public")
            (root/"src/boot/M9NormalStageA.cpp.su").write_text(only)
            result,_=f.collect_frames(path)
            self.assertIsNone(result["telemetry_post"]["frame_bytes"])
            self.assertEqual(result["telemetry_post"]["state"], "DYNAMIC_UNKNOWN")
            self.assertIsNone(result["digest_gate"]["frame_bytes"])
            self.assertEqual(result["digest_gate"]["state"], "INLINED_OR_AMBIGUOUS")

    def test_resource_observer_poll_never_repaints(self):
        normal=f.TRACKED_NORMAL.read_text(encoding="utf-8")
        source=f.TRACKED_RESOURCES.read_text(encoding="utf-8")
        self.assertTrue(f.highwater_source_guard(normal,source))
        marker="void poll()"
        self.assertIn(marker,source)
        changed=source.replace("last_ = now;", "reset();last_ = now;")
        with self.assertRaisesRegex(ValueError,"repaint"):
            f.highwater_source_guard(normal,changed)

    def test_b3_telemetry_scratch_is_leased_and_destructed(self):
        normal = f.TRACKED_NORMAL.read_text(encoding="utf-8")
        resources = f.TRACKED_RESOURCES.read_text(encoding="utf-8")
        self.assertIn("TelemetryScratchLease scratch;", normal)
        self.assertIn("ResponseLease responseLease_;", normal)
        self.assertIn("scratch_->~TelemetryScratch();", normal)
        self.assertTrue(f.highwater_source_guard(normal, resources))
        with self.assertRaises(AssertionError):
            f.highwater_source_guard(
                normal.replace("ResponseLease responseLease_;", "bool unguarded_;"),
                resources)
        with self.assertRaises(AssertionError):
            f.highwater_source_guard(
                normal.replace("scratch_->~TelemetryScratch();", "/* lost destructor */"),
                resources)

    def test_b3_live_handler_heap_snapshot_has_no_stack_reset(self):
        compiler = shutil.which("g++") or shutil.which("clang++")
        if not compiler:
            self.skipTest("C++ compiler unavailable in source-only environment")
        code = r'''
#include "boot/M9NormalResources.h"
#include <cassert>
using namespace M9NormalResources;
struct Fake {
  unsigned resets=0, stacks=0, heaps=0;
  uint32_t tick=0, freeStack=3800;
  Heap current{36000,34000,3};
  void resetStack(){++resets;}
  uint32_t stack(){++stacks;return freeStack;}
  void heap(Heap& h){++heaps;h=current;}
  uint32_t now(){return tick;}
};
int main(){
  Fake f; Observer<Fake> o(f);
  o.sampleHandlerHeap(); assert(f.heaps==0);
  o.beforeSetup(); o.beforeFs(); o.afterFs(); o.afterSetup();
  assert(f.resets==4);
  const unsigned resets=f.resets, stackReads=f.stacks;
  f.current={24576,17000,22}; o.sampleHandlerHeap();
  assert(f.resets==resets && f.stacks==stackReads);
  assert(o.status().min_heap==24576 && o.status().min_block==17000);
  assert(o.status().max_frag==22 && o.status().samples==0);
  assert(o.status().valid);
  f.current={20100,16000,26}; o.sampleHandlerHeap();
  assert(!floors(o.status()));
  f.tick=1000; f.current={33000,31000,2}; o.poll();
  assert(o.status().samples==1);
  assert(o.status().min_heap==20100 && o.status().min_block==16000);
  assert(o.status().max_frag==26 && f.resets==resets);
  f.current={0,0,0}; o.sampleHandlerHeap();
  assert(o.status().rejected==1 && !o.status().valid);
  f.current={32000,30000,1}; o.sampleHandlerHeap();
  assert(!o.status().valid && f.resets==resets);
}
'''
        with tempfile.TemporaryDirectory() as tmp:
            src=Path(tmp)/"sample.cpp"
            exe=Path(tmp)/"sample"
            src.write_text(code, encoding="utf-8")
            root=Path(__file__).resolve().parents[1]
            cp=subprocess.run([compiler,"-std=c++17","-Wall","-Wextra","-Werror",
                               "-I"+str(root/"firmware/include"),
                               str(src),"-o",str(exe)],capture_output=True,text=True)
            self.assertEqual(cp.returncode,0,cp.stdout+cp.stderr)
            run=subprocess.run([str(exe)],capture_output=True,text=True)
            self.assertEqual(run.returncode,0,run.stdout+run.stderr)

    def test_audit_has_no_device_or_firmware_side_effect(self):
        framed={key:{"state":"MEASURED_STATIC","frame_bytes":64} for key in f.TARGETS}
        with patch.object(f,"collect_frames",return_value=(framed,[])), \
             patch.object(f,"ota_audit",return_value={"whole_native_upper_bound":False,"paths":{"a":{"compiled_bytes":1400}}}):
            report=f.audit(Path("nonexistent"))
        self.assertEqual(report["status"],"COMPILED_NORMAL_HANDLER_FRAMES_NOT_NATIVE_STACK_BOUND")
        self.assertEqual(report["stack_free_floor"],2048)
        self.assertFalse(report["complete_normal_native_upper_bound"])
        self.assertFalse(report["firmware_changed"])
        self.assertEqual(report["device_contacts"],0)
        self.assertEqual(report["ota_posts"],0)


if __name__=="__main__":
    unittest.main()
