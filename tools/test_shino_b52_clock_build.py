"""Narrow B5.2 generation guards; public synthetic sources only."""
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch
import shino_b52_clock_build as b52
import shino_b5_lan_build as b51

class BuildTests(unittest.TestCase):
    def test_normal_routes_and_old_contracts(self):
        src=b51.add_b5_routes(b51.patch_normal((b52.ROOT/"ota/firmware/Normal.cpp").read_text()))
        new=b52.patch_clock(src)
        for marker in ('"/api/v1/clock/sync"','"/api/v1/clock/status"',"ClockSync","B52Clock::step(now)"):
            self.assertIn(marker,new)
        self.assertIn('if(!auth())return false;',new)
        self.assertIn('if(!B5Lan::permitted(server))',new)
        self.assertIn('bytes!=B52Clock::FRAME_BYTES',new)
        self.assertIn('CLOCK_FRAME_BOUND',new)
        self.assertIn('B52ClockHttp.inc',new)
        self.assertIn('B5.2',new)
        self.assertNotIn('B5.1',new)
        self.assertNotIn("MediaReceiver",new)
        self.assertNotIn("FirstBootBridge",new)
        for start,end in (("bool auth(){","enum class Route"),("__attribute__((noinline)) void upload(","__attribute__((noinline)) bool beforeBody"),("__attribute__((noinline)) void telemetry(){","__attribute__((noinline)) void metrics(){")):
            self.assertEqual(src[src.index(start):src.index(end)],new[new.index(start):new.index(end)])
    def test_anchor_drift_fails_closed(self):
        with self.assertRaises(ValueError):b52.patch_clock("different graph")
    def test_private_source_gate_fails_on_dirty_tree(self):
        with patch.object(b52.subprocess,"check_output",return_value=" M tools/unreviewed.py\\n"):
            with self.assertRaisesRegex(ValueError,"not clean"):
                b52.private_source_gate()

    def test_private_source_gate_records_exact_clean_head(self):
        sha="a"*40
        def git(command,**kwargs):
            return "" if command[1]=="status" else sha+"\\n"
        with patch.object(b52.subprocess,"check_output",side_effect=git):
            self.assertEqual(b52.private_source_gate(),sha)

    def test_private_preparation_refuses_non_owner_path_before_secret_access(self):
        with tempfile.TemporaryDirectory(prefix="b52-private-guard-") as td:
            out=Path(td)/"candidate"
            with patch.object(b52,"prepare_b51",side_effect=AssertionError("SECRET LOAD")):
                with self.assertRaisesRegex(ValueError,"owner-local"):
                    b52.prepare(out,private=True)
            self.assertFalse(out.exists())

    def test_private_preparation_preserves_owner_identity(self):
        with tempfile.TemporaryDirectory(prefix="b52-private-fixture-") as td:
            owner=Path(td)/"m9-owner";owner.mkdir()
            out=owner/"candidate"
            def fake_prepare(folder,private=False):
                self.assertTrue(private)
                new,device,identity=b51.prepare(folder,private=False)
                release=new/"include/ShinoRelease.h"
                release.write_text(release.read_text(encoding="utf-8").replace(
                    "#define SHINO_OTA_PRIVATE 0","#define SHINO_OTA_PRIVATE 1"),encoding="utf-8")
                return new,device,identity
            with patch.object(b52,"OWNER",owner),patch.object(b52,"prepare_b51",side_effect=fake_prepare):
                _,device,identity=b52.prepare(out,private=True)
            release=(out/"include/ShinoRelease.h").read_text(encoding="utf-8")
            self.assertIn("#define SHINO_OTA_PRIVATE 1",release)
            self.assertIn(f'#define SHINO_OTA_BUILD "{identity}"',release)
            self.assertNotEqual(identity,"c"*64)
            self.assertIn("B52Clock::step(now)",(out/"src/boot/M9NormalStageA.cpp").read_text())
            self.assertIn("clockPermitted=SHINO_OTA_PRIVATE",(out/"include/B52ClockHttp.inc").read_text())

    def test_public_only_new_output_and_inert_authority(self):
        parent=b52.ROOT/"research-local"
        parent.mkdir(exist_ok=True)
        with tempfile.TemporaryDirectory(prefix="clock-prepare-",dir=parent) as td:
            out=Path(td)/"public"
            b52.prepare(out)
            release=(out/"include/ShinoRelease.h").read_text()
            self.assertIn("#define SHINO_OTA_PRIVATE 0",release)
            self.assertIn("B52Clock.cpp",(out/"src/boot/B52Clock.cpp").name)
            self.assertIn("-<boot/M9NormalDashboard.cpp>",(out/"platformio.ini").read_text())
            self.assertEqual((out/"include/boot/FslessMetrics.h").read_bytes(),(b52.ROOT/"firmware/include/boot/FslessMetrics.h").read_bytes())
            self.assertIn("METRICS_STALE_MS = 6000",(out/"src/boot/FslessMetrics.cpp").read_text())
            with self.assertRaises(ValueError):b52.prepare(out)

if __name__=="__main__":unittest.main()

