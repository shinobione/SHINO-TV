"""Regression checks for real 240x240 four-card LCD, never simulated full-width bars."""
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
BRIDGE = (ROOT/"firmware/src/boot/FirstBootBridge.cpp").read_text(encoding="utf-8")
MATH = (ROOT/"firmware/include/boot/DashboardV2.h").read_text(encoding="utf-8")
WEB = (ROOT/"firmware/src/boot/FslessWebUI.cpp").read_text(encoding="utf-8")
METRICS = (ROOT/"firmware/src/boot/FslessMetrics.cpp").read_text(encoding="utf-8")


class NativeV2SourceTests(unittest.TestCase):
    def test_four_exact_rectangles_and_native_per_card_gauges(self):
        for coordinate in ("{8, 124, 8, 124}", "{8, 8, 124, 124}"):
            self.assertIn(coordinate, MATH)
        self.assertIn("CARD_SIZE = 108", MATH)
        self.assertIn("TRACK_WIDTH = 90", MATH)
        self.assertIn("gfx->fillRoundRect(trackX, trackY, 90, 6, 3", BRIDGE)
        self.assertIn("DashboardV2::stableBand", BRIDGE)
        self.assertIn("DashboardV2::ramPercent(m.memoryGb, m.memoryTotalGb)", BRIDGE)
        self.assertIn("DashboardV2::tempPercent(m.gpuTempC)", BRIDGE)
        self.assertIn("const int16_t trackY = y + 91", BRIDGE)
        self.assertNotIn("DisplayManager::drawLoadingBar(", BRIDGE)

    def test_four_cards_remain_when_stale_or_gpu_unavailable(self):
        self.assertIn("Card cards[4]{}", BRIDGE)
        self.assertIn("if (!old)", BRIDGE)
        self.assertIn("if (m.gpuAvailable)", BRIDGE)
        self.assertIn("for (uint8_t i = 0; i < 4; ++i) paintCard(i, cards[i]);", BRIDGE)
        self.assertIn("card.number[0] == '\\0'", BRIDGE)
        self.assertIn("firstFrame = false", BRIDGE)
        self.assertIn("lastPixels[index] == pixels", BRIDGE)
        self.assertIn("priorBand[index] = band", BRIDGE)

    def test_native_degree_glyph_and_fit_without_240px_framebuffer(self):
        self.assertIn("gfx->drawCircle(degreeX, valueY + 4, 2", BRIDGE)
        self.assertIn("gfx->print('C')", BRIDGE)
        self.assertIn("strlen(card.number) * 12 <= 90 ? 2 : 1", BRIDGE)
        self.assertIn("gfx->fillScreen(DashboardV2::BACKGROUND)", BRIDGE)
        self.assertNotIn("new uint16_t[240", BRIDGE)

    def test_flash_browser_mirrors_native_layout_and_safe_ram_contract(self):
        self.assertIn("grid-template-columns:108px 108px", WEB)
        self.assertIn("grid-template-rows:108px 108px", WEB)
        self.assertEqual(WEB.count('<article class="card">'), 4)
        self.assertIn("const thresholds=[20,50,80]", WEB)
        self.assertIn("const colors=['#66D39A','#D8C35E','#D9894A','#8E394B']", WEB)
        self.assertIn("memory_total_gb", WEB)
        self.assertIn('"memory_total_gb"', METRICS)
        for forbidden in ("LittleFS.begin(", "EEPROM.begin(", "Update.begin(", "WiFi.persistent(true)"):
            self.assertNotIn(forbidden, BRIDGE)
            self.assertNotIn(forbidden, WEB)


if __name__ == "__main__":
    unittest.main()
