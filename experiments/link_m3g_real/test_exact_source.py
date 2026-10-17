"""Pin original metrics source and parity laboratory, not a flashed firmware."""
import subprocess
import unittest
from pathlib import Path
ROOT = Path(__file__).resolve().parents[2]
EXPECTED = {
    "firmware/src/boot/FslessMetrics.cpp": "c4b178fd0ce807e56a5cb88ddb4ccdead7547bca",
    "firmware/src/boot/FirstBootBridge.cpp": "705028430a854537924ef30a83a1761d0670387e",
    "firmware/src/boot/HomeLan.cpp": "70f9922829dfb27be39955c1583648c32d05ceeb",
}
class ExactSource(unittest.TestCase):
    def test_original_unchanged_exact_git_blobs(self):
        for path, expected in EXPECTED.items():
            with self.subTest(path=path):
                self.assertEqual(subprocess.check_output(
                    ["git", "hash-object", path], cwd=ROOT, text=True, timeout=5
                ).strip(), expected)

    def test_real_compiled_metrics_is_not_synthetic_preview(self):
        code=(ROOT/"experiments/link_m3g_real/native_integrated_real_metrics.cpp").read_text()
        assert_in=self.assertIn
        assert_in("FslessMetrics::apply(payload.as<JsonVariantConst>()",code)
        assert_in("FslessMetrics::describe(liveMetrics)",code)
        assert_in("isLegacyProof(authorization,authorizationLength,",code)
        assert_in('host_fixture_only',code)
        self.assertNotIn("body==GOOD_JSON",code)
        self.assertNotIn("body==BAD_JSON",code)
        self.assertNotIn("WiFiServer",code)
        self.assertNotIn("Update.begin(",code)

    def test_original_six_second_lease_and_previous_good_retention(self):
        src=(ROOT/"firmware/src/boot/FslessMetrics.cpp").read_text()
        self.assertIn("METRICS_STALE_MS = 6000",src)
        self.assertIn("state = next; // Invalid payload never replaces",src)
        self.assertIn("std::isfinite(numeric)",src)
        self.assertIn("memory_used_gb",src)
        self.assertIn("gpu_temp_c",src)
        self.assertIn("memory_total_gb",src)

if __name__=="__main__":
    unittest.main()
