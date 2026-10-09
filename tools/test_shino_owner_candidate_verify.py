"""Offline fail-closed verification of owner-private candidate source lineage."""
import json
import sys
import unittest
from pathlib import Path
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parent))
import shino_owner_candidate_verify as verify


class SourceIdentityReview(unittest.TestCase):
    def test_offline_gate_changes_do_not_mutate_an_existing_candidate(self):
        with patch.object(verify, "git", return_value=(
                "tools/m9_stagea_source_gate.py\n"
                "tools/m9_signed_ota_runner.py\n"
                "tools/shino_owner_candidate_verify.py")):
            self.assertEqual(verify.firmware_source_drift("base", "head"), [])

    def test_any_firmware_producer_change_requires_new_candidate(self):
        cases = (
            "firmware/src/boot/M9NormalStageA.cpp",
            "experiments/shino_wifi_install/include/ShinoWifiUpdate.h",
            "tools/shino_owner_transition.py",
            "tools/shino_transition_build.py",
            "tools/shino_wifi_core.py",
            "tools/m9_stagea_build.py",
        )
        for case in cases:
            with self.subTest(path=case), patch.object(verify, "git", return_value=case):
                self.assertEqual(verify.firmware_source_drift("base", "head"), [case])

    def test_verify_missing_owner_artifacts_is_no_go(self):
        with patch.object(verify, "OWNER", Path("C:/unavailable-owner-artifacts")):
            with self.assertRaises((ValueError, OSError)):
                verify.audit()


if __name__ == "__main__":
    unittest.main()
