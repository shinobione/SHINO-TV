"""Readiness cannot promote probe evidence or silently accept changed firmware."""
from pathlib import Path
import json
import shutil
import tempfile
import unittest
from m9_normal_readiness import ROOT, audit, reference_build


class ReadinessTests(unittest.TestCase):
    def test_current_hazards_do_not_grant_normal_candidate_or_physical_authority(self):
        receipt = audit()
        self.assertEqual(receipt['firmware_files_checked'], 103)
        self.assertEqual(len(receipt['hazards']), 20)
        self.assertFalse(receipt['normal_candidate_frozen'])
        self.assertFalse(receipt['proposed_environment_implemented'])
        self.assertFalse(receipt['physical_authorization'])
        self.assertEqual(receipt['NORMAL_PROFILE_RUNTIME_GATE'], 'NOT_RUN')

    def test_firmware_drift_closes_readiness_before_evidence(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            pins = json.loads((ROOT/'tools/m9_phase_k_sources.json').read_text())
            for name in pins['firmware_sha256_lf']:
                target = root/name
                target.parent.mkdir(parents=True, exist_ok=True)
                shutil.copyfile(ROOT/name, target)
            target = root / 'firmware/include/boot/ShinoBootProfile.h'
            target.write_text(target.read_text().replace('#error', '// removed #error'), encoding='utf-8')
            with self.assertRaises(ValueError):
                audit(root)

    def test_probe_policy_cannot_be_reported_as_profile0_reference_or_normal_build(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            policy = root / 'policy.h'
            policy.write_text('#define SHINO_BOOT_PROFILE 2\n')
            from m9_fsless_gate import FslessGateError
            with self.assertRaises(FslessGateError):
                reference_build(policy, root/'absent', root/'absent', root, root/'absent')


if __name__ == '__main__':
    unittest.main()
