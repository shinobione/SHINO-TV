"""Reviewed B5.2 overlay versus immutable historical source pins; no device I/O."""
import hashlib
import unittest
from pathlib import Path
from unittest.mock import patch

from m9_phase_n_compat import predecessor

ROOT = Path(__file__).resolve().parents[1]
SCENE = "firmware/include/display/SceneEngine.h"
OLD_SCENE_SHA256_LF = "d22e09b31225bf15ccce69e3753610864d04056a93baadc055f8c60ad8c8d413"


class B52SourceCompatibilityTests(unittest.TestCase):
    def test_reviewed_scene_projects_to_exact_frozen_predecessor(self):
        current = (ROOT / SCENE).read_text(encoding="utf-8")
        restored = predecessor(SCENE, current)
        self.assertEqual(hashlib.sha256(restored.encode()).hexdigest(), OLD_SCENE_SHA256_LF)
        self.assertNotEqual(restored, current)
        self.assertEqual(predecessor(SCENE, restored), restored)

    def test_any_unreviewed_scene_mutation_fails_closed(self):
        current = (ROOT / SCENE).read_text(encoding="utf-8")
        for changed in (current + "// unreviewed\n", current.replace("ClockSource", "OtherSource")):
            with self.subTest(changed=changed[-32:]), self.assertRaises(ValueError):
                predecessor(SCENE, changed)

    def test_other_sources_are_not_exempted(self):
        self.assertEqual(predecessor("firmware/include/unreviewed.h", "unreviewed"), "unreviewed")

    def test_added_clock_header_mutation_fails_closed(self):
        from m9_phase_o_qualification import source_gate

        read = Path.read_bytes
        name = "firmware/include/display/ClockFoundation.h"
        def changed(path):
            data = read(path)
            return data + b"// unreviewed\n" if path == ROOT / name else data
        with patch.object(Path, "read_bytes", changed), self.assertRaises(ValueError):
            source_gate()

    def test_mount_and_phase_o_keep_historical_counts_and_physical_hold(self):
        from m9_mount_stack import source_audit
        from m9_phase_o_qualification import source_gate

        self.assertEqual(source_audit()["firmware_files_checked"], 103)
        report = source_gate()
        self.assertEqual(report["firmware_files_checked"], 113)
        self.assertEqual(report["firmware_identity"], "PINNED_B52_PREDECESSOR_PROJECTION")
        self.assertEqual(set(report["reviewed_new_firmware_sha256_lf"]),
                         {"firmware/include/display/ClockFoundation.h"})
        self.assertFalse(report["physical_authorization"])
        self.assertEqual(report["PHASE_O_RETAINED_CANDIDATE_IDENTITY_GATE"], "NOT_READ_BY_THIS_RUN")

    def test_wifi_historical_set_and_added_header_both_pinned(self):
        from b52_source_compat import wifi_firmware_predecessor

        import subprocess
        original = subprocess.check_output
        def shallow(command, *args, **kwargs):
            if command[:2] == ["git", "show"]:
                raise AssertionError("NO DEEP HISTORY AVAILABLE")
            return original(command, *args, **kwargs)
        with patch.object(subprocess, "check_output", side_effect=shallow):
            report = wifi_firmware_predecessor(ROOT)
        self.assertEqual(report["historical_firmware_files_checked"], 113)
        self.assertEqual(set(report["reviewed_new_firmware_sha256_lf"]),
                         {"firmware/include/display/ClockFoundation.h"})
        self.assertEqual(report["source_scope"],
                         "PINNED_PREDECESSOR_PROJECTION_NOT_RAW_CURRENT_EQUALITY")

    def test_historical_pin_manifest_tampering_fails_closed(self):
        from b52_source_compat import wifi_firmware_predecessor

        read = Path.read_bytes
        manifest = ROOT / "tools/m9_phase_o_sources.json"
        def changed(path):
            data = read(path)
            return data + b" " if path == manifest else data
        with patch.object(Path, "read_bytes", changed), self.assertRaises(ValueError):
            wifi_firmware_predecessor(ROOT)


if __name__ == "__main__":
    unittest.main()
