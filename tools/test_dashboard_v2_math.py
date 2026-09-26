"""Compile and exercise EXACT firmware DashboardV2.h with host g++, without a TV."""
import shutil
import subprocess
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
HEADER = ROOT / "firmware/include/boot/DashboardV2.h"


@unittest.skipUnless(shutil.which("g++"), "Host g++ is not installed")
class DashboardV2MathTests(unittest.TestCase):
    def test_geometry_palette_bands_hysteresis_and_bar_pixels(self):
        source = r'''
#include "boot/DashboardV2.h"
#include <cassert>
#include <cmath>
#include <limits>
int main() {
    using namespace DashboardV2;
    static_assert(CANVAS == 240 && CARD_SIZE == 108 && TRACK_WIDTH == 90);
    static_assert(X[0] == 8 && Y[0] == 8 && X[1] == 124 && Y[1] == 8);
    static_assert(X[2] == 8 && Y[2] == 124 && X[3] == 124 && Y[3] == 124);
    static_assert(PALETTE[0] == rgb565(0x66, 0xd3, 0x9a));
    static_assert(PALETTE[3] == rgb565(0x8e, 0x39, 0x4b));
    assert(rawBand(0) == 0 && rawBand(19.9f) == 0);
    assert(rawBand(20.0f) == 1 && rawBand(49.9f) == 1);
    assert(rawBand(50.0f) == 2 && rawBand(79.9f) == 2);
    assert(rawBand(80.0f) == 3 && rawBand(100.0f) == 3);
    assert(stableBand(-1, 50.1f) == 2);
    assert(stableBand(1, 50.1f) == 1); // no yellow/orange flicker
    assert(stableBand(1, 52.0f) == 2);
    assert(stableBand(2, 48.0f) == 2);
    assert(stableBand(2, 47.9f) == 1);
    assert(stableBand(0, 90.0f) == 3); // skip multiple boundaries
    assert(stableBand(3, 0.0f) == 0);
    assert(stableBand(2, -1.0f) == -1); // stale clears old band
    assert(fillPixels(0) == 0 && fillPixels(-1) == 0);
    assert(fillPixels(0.01f) == 1);
    assert(fillPixels(5) == 5 && fillPixels(70) == 63);
    assert(fillPixels(100) == 90);
    assert(std::fabs(ramPercent(11.2f, 16.0f) - 70.0f) < 0.01f);
    assert(ramPercent(11.2f, 0.0f) == -1);
    assert(ramPercent(17.0f, 16.0f) == -1);
    assert(ramPercent(0.0f, 16.0f) == 0.0f);
    assert(std::fabs(tempPercent(50.0f) - 33.3333f) < 0.01f);
    assert(tempPercent(30.0f) == 0 && tempPercent(42.0f) == 20);
    assert(tempPercent(60.0f) == 50 && tempPercent(78.0f) == 80);
    assert(tempPercent(90.0f) == 100 && tempPercent(120.0f) == 100);
    assert(tempPercent(std::numeric_limits<float>::quiet_NaN()) == -1);
    return 0;
}
'''
        with tempfile.TemporaryDirectory() as tmp:
            src = Path(tmp) / "test.cpp"
            program = Path(tmp) / "test"
            src.write_text(source)
            compile_result = subprocess.run([
                "g++", "-std=c++17", "-Wall", "-Wextra", "-Werror",
                "-I", str(HEADER.parent.parent), str(src), "-o", str(program),
            ], capture_output=True, text=True, check=False, timeout=30)
            self.assertEqual(compile_result.returncode, 0, compile_result.stderr)
            run_result = subprocess.run([str(program)], capture_output=True,
                                        text=True, check=False, timeout=5)
            self.assertEqual(run_result.returncode, 0, run_result.stderr)


if __name__ == "__main__":
    unittest.main()
