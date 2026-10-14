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
        self.assertNotIn("MediaReceiver",new)
        self.assertNotIn("FirstBootBridge",new)
        for start,end in (("bool auth(){","enum class Route"),("__attribute__((noinline)) void upload(","__attribute__((noinline)) bool beforeBody"),("__attribute__((noinline)) void telemetry(){","__attribute__((noinline)) void metrics(){")):
            self.assertEqual(src[src.index(start):src.index(end)],new[new.index(start):new.index(end)])
    def test_anchor_drift_fails_closed(self):
        with self.assertRaises(ValueError):b52.patch_clock("different graph")
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

