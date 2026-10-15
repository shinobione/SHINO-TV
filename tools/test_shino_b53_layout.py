"""B5.3 Paint layout and metric/clock behavior source contract."""
import unittest
from shino_b53_layout import patch_design
from shino_b53_clock_build import patch_scene,ROOT

class OwnerLayoutTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.original=(ROOT/"firmware/include/display/SceneEngine.h").read_text()
        cls.generated=patch_design(patch_scene(cls.original))

    def test_exact_owner_240_canvas(self):
        s=self.generated
        self.assertIn('#include "B53Layout.h"',s)
        self.assertIn("const auto r=B53Layout::CARDS[i];",s)
        self.assertIn('c.text(87,10,"SHINO // TV",LABEL);',s)
        self.assertIn('c.text(60,32,hhmm,WHITE,4);',s)
        self.assertIn('c.text(219,10,"NT",LABEL);',s)
        self.assertIn('c.fill(0,headerTask*8,240,8,BG);',s)
        self.assertIn('headerTask<13',s)

    def test_four_labels_values_and_dynamic_color_bars(self):
        s=self.generated
        self.assertIn('"CPU","GPU","RAM","GPU temp"',s)
        self.assertIn('c.text(r.x+7,r.y+5,names[i],LABEL,2);',s)
        self.assertIn('const uint8_t fontSize=strlen(value)*18U<=97U?3:2;',s)
        self.assertIn('BARS[cards[i].band]',s)
        self.assertIn('DashboardV2::tempPercent(m.gpuTempC)',s)
        self.assertIn('DashboardV2::ramPercent(m.ramGb,m.ramTotalGb)',s)
        self.assertIn('snprintf(next.number,sizeof next.number,"%.0f%%",value);',s)

    def test_offline_clock_weather_but_no_fake_metrics(self):
        s=self.generated
        self.assertIn('if(stale) {\n            c.fill(r.x,r.y,r.w,r.h,BG);',s)
        self.assertIn('c.text(60,148,"PC OFFLINE",LABEL,2);',s)
        self.assertIn('offlineRendered = false; dirty = 15;',s)
        self.assertIn('if(weatherFresh(now))',s)
        self.assertIn('"WEATHER --"',s)
        self.assertIn("memset(static_cast<void*>(&caption),0,sizeof caption)",s)

    def test_change_is_generated_only_and_fail_closed(self):
        self.assertNotIn('PC OFFLINE",LABEL,2',self.original)
        with self.assertRaises(ValueError):
            patch_design(self.generated)
        with self.assertRaises(ValueError):
            patch_design("renderer was refactored elsewhere")

if __name__=="__main__":
    unittest.main()
