"""Source-only B5.3 lean tests, no HTTP network or device."""
import tempfile
import unittest
from pathlib import Path
import shino_b53_lean_build as lean
import shino_b53_clock_build as full

class LeanGraph(unittest.TestCase):
    def test_inert_lean_preserves_link_and_lcd(self):
        root=lean.ROOT/"research-local"
        root.mkdir(exist_ok=True)
        with tempfile.TemporaryDirectory(dir=root,prefix="b53-lean-source-") as td:
            out=Path(td)/"public"
            lean.prepare(out)
            normal=(out/"src/boot/M9NormalStageA.cpp").read_text()
            clock=(out/"src/boot/B52Clock.cpp").read_text()
            screen=(out/"include/display/SceneEngine.h").read_text()
            self.assertIn("B53Sntp::begin();",normal)
            self.assertIn("B52Clock::step(now)",normal)
            self.assertIn('"/api/v1/clock/sync"',normal)
            self.assertIn('"/api/v1/update"',normal)
            self.assertIn("B52ClockHttp.inc",normal)
            self.assertIn("B53Sntp::current(now,ntpUtc)",clock)
            self.assertIn("clockState.snapshot(now)",clock)
            self.assertIn("B53Layout::CARDS[i]",screen)
            self.assertIn('"CPU","GPU","RAM","GPU temp"',screen)
            self.assertIn("SHINO_OTA_PRIVATE 0",
                          (out/"include/ShinoRelease.h").read_text())
            self.assertIn("4m2m",(out/"platformio.ini").read_text())
            for path in ("src/boot/B53WeatherHttps.cpp","include/B53WeatherHttps.h",
                         "include/B53WeatherCA.h","include/B53WeatherFrame.h",
                         "include/B53WeatherGate.h","include/B53WeatherChunked.h"):
                self.assertFalse((out/path).exists(),path)
            for content in (normal,clock,(out/"include/B52Clock.h").read_text()):
                self.assertNotIn("B53WeatherHttps",content)
                self.assertNotIn("WiFiClientSecure",content)
            with self.assertRaises(ValueError):lean.prepare(out)

    def test_platformio_exact_version_gate(self):
        from unittest.mock import patch
        from types import SimpleNamespace
        with patch.object(lean.shutil,"which",return_value="C:/pinned/pio.exe"), \
             patch.object(lean.subprocess,"run",return_value=SimpleNamespace(
                 returncode=0,stdout="PlatformIO Core, version 6.1.18\n")):
            self.assertEqual(lean.pinned_platformio(),"C:/pinned/pio.exe")
        with patch.object(lean.shutil,"which",return_value="C:/global/pio.exe"), \
             patch.object(lean.subprocess,"run",return_value=SimpleNamespace(
                 returncode=0,stdout="PlatformIO Core, version 6.2.0\n")):
            with self.assertRaisesRegex(ValueError,"6.1.18"):
                lean.pinned_platformio()

    def test_private_build_forwards_private_to_inspect_build(self):
        from unittest.mock import patch
        from types import SimpleNamespace
        with tempfile.TemporaryDirectory() as td:
            root=Path(td)
            libs=root/"deps"
            for name,version in lean.PINNED:
                entry=libs/name
                entry.mkdir(parents=True)
                (entry/"library.properties").write_text("version="+version+"\n")
            def fake_prepare(output,private=False):
                out=Path(output)
                out.mkdir()
                (out/"platformio.ini").write_text(
                    "[env:esp12e]\nlib_deps =\n[env:"+lean.ENV+"]\nlib_extra_dirs =\n")
                return out,"device","build"
            observed=[]
            def fake_inspect(directory,device,build_id,private=False):
                observed.append(private)
                return {"private":private,"bytes":123,
                        "sha256":"a"*64,"static_ram":47000}
            with patch.object(lean,"private_source_gate"), \
                 patch.object(lean,"pinned_platformio",return_value="pio"), \
                 patch.object(lean,"prepare",side_effect=fake_prepare), \
                 patch.object(lean,"inspect_build",side_effect=fake_inspect), \
                 patch.object(lean.subprocess,"run",return_value=SimpleNamespace(returncode=0)):
                result=lean.build(root/"out",libs,private=True)
            self.assertEqual(observed,[True])
            self.assertIs(result["private"],True)
            self.assertIs(result["private_build"],True)
            self.assertIs(result["clock_authority"],True)

    def test_weather_build_kept_separately(self):
        root=lean.ROOT/"research-local"
        root.mkdir(exist_ok=True)
        with tempfile.TemporaryDirectory(dir=root,prefix="b53-compare-") as td:
            out=Path(td)/"public"
            full.prepare(out)
            self.assertIn('B53WeatherHttps::begin("","");',
                          (out/"src/boot/M9NormalStageA.cpp").read_text())
            self.assertTrue((out/"src/boot/B53WeatherHttps.cpp").is_file())

if __name__=="__main__":unittest.main()
