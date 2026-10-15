"""Pure source/graph B5.3 qualification. No sockets, secrets or device."""
import tempfile,unittest
from pathlib import Path
import shino_b53_clock_build as b53
class B53GraphTests(unittest.TestCase):
    def test_anchors_keep_real_pc_clock(self):
        old=(b53.ROOT/"experiments/b52_clock/native/B52Clock.cpp").read_text()
        result=b53.patch_clock(old)
        self.assertIn("B53Sntp::poll(now)",result)
        self.assertIn("freshness.accept(clockState",result)
        with self.assertRaises(ValueError):b53.patch_clock(result)
    def test_scene_sntp(self):
        old=(b53.ROOT/"firmware/include/display/SceneEngine.h").read_text()
        result=b53.patch_scene(old)
        self.assertIn("ClockSource::Sntp",result)
        self.assertIn('"CPU", "GPU", "RAM", "GPU TEMP"',result)
    def test_public_only_generated_graph(self):
        base=b53.ROOT/"research-local";base.mkdir(exist_ok=True)
        with tempfile.TemporaryDirectory(dir=base,prefix="b53-graph-") as td:
            out=Path(td)/"public"
            b53.prepare(out)
            firmware=(out/"src/boot/M9NormalStageA.cpp").read_text()
            self.assertIn("B53Sntp::begin();",firmware)
            self.assertIn('#include "B53Sntp.h"',firmware)
            self.assertIn("B52ClockHttp.inc",firmware)
            self.assertIn("B52Clock::step(now)",firmware)
            self.assertIn("SHINO_OTA_PRIVATE 0",(out/"include/ShinoRelease.h").read_text())
            self.assertTrue((out/"src/boot/B53Sntp.cpp").is_file())
            with self.assertRaises(ValueError):b53.prepare(out)
if __name__=="__main__":unittest.main()
