"""Offline source execution and separate candidate C++ assertions."""
import unittest
from pathlib import Path

from v07_cpp_lab_runner import build_and_run, ROOT
from v07_full_parser_probe import harness
from v07_pinned_core_probe import core_root, pinned_sources, run_host_probe


class SourceExecutedIngressLab(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        if not (core_root() / "package.json").is_file():
            raise unittest.SkipTest("pinned PlatformIO core absent; dedicated CI job installs it")

    def test_exact_pinned_source_primitives(self):
        status, detail = run_host_probe(pinned_sources())
        self.assertEqual(status, "PASS", detail)

    def test_exact_pinned_parser_with_simulated_dependencies(self):
        result = build_and_run(Path("v07_exact_parser.cpp"), generated=harness())
        observed = result["result"]
        self.assertEqual(observed["exact_parser_checks"], 11)
        self.assertEqual(observed["failed"], 0)
        self.assertGreaterEqual(observed["max_read_string_bytes"], 5008)

    def test_independent_bounded_candidate(self):
        result = build_and_run(ROOT / "v07_bounded_ingress_lab.cpp")["result"]
        self.assertEqual(result["candidate_tests"], 67)
        self.assertEqual(result["max_payload"], 512)
        self.assertEqual(result["max_live_payload_allocations"], 0)
        self.assertEqual(result["body_bytes_before_auth"], 0)
        self.assertEqual(result["max_metric_interval_ms_simulated"], 100)

    def test_synthetic_single_owner_handoff_contract(self):
        result = build_and_run(ROOT / "v07_single_owner_handoff_lab.cpp")["result"]
        self.assertEqual(result["handoff_assertions"], 36)
        self.assertLessEqual(result["max_step_bytes"], 64)
        self.assertLessEqual(result["max_prefix_bytes"], 130)
        self.assertEqual(result["metric_updates"], 2)
        self.assertEqual(result["owned_cleanups"], 2)


if __name__ == "__main__":
    unittest.main()
