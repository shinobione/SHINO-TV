"""Read-only source gates; pinned public SDK required, no build or owner input."""
import ast
from pathlib import Path
import subprocess
import unittest
from unittest.mock import patch

import m9_signed_ota_runner as signed
import m9_stagea_source_gate as stagea

ROOT = Path(__file__).resolve().parents[1]
REVIEWED = "251be908d760ff3d61958dff851afd384a3f267b"
TOOLS = ("companion/shino_b5_get_diagnostic.py",
         "companion/test_shino_b5_get_diagnostic.py",
         "companion/shino_b5_partial_preflight.py",
         "companion/test_shino_b5_partial_preflight.py")


class OfflineSourcePinsTests(unittest.TestCase):
    def setUp(self):
        for name in ("socket.socket", "socket.create_connection", "socket.getaddrinfo"):
            guard = self.enterContext(patch(name, side_effect=AssertionError("NO NETWORK")))
            self.addCleanup(guard.assert_not_called)

    def test_both_gates_pin_the_reviewed_public_git_blobs(self):
        for module in (signed, stagea):
            tree = ast.parse(Path(module.__file__).read_text(encoding="utf-8"))
            assignments = [node for node in ast.walk(tree) if isinstance(node, ast.Assign)
                           and any(isinstance(t, ast.Name) and t.id == "new_offline_script_pins"
                                   for t in node.targets)]
            self.assertEqual(len(assignments), 1)
            pins = ast.literal_eval(assignments[0].value)
            for name in TOOLS:
                expected = subprocess.check_output(
                    ["git", "rev-parse", REVIEWED+":"+name], cwd=ROOT, text=True).strip()
                self.assertEqual(pins.get(name), expected, (module.__name__, name))

    def test_actual_source_closure_preserves_both_legacy_gates(self):
        first = signed.source_gate()
        second = stagea.run()
        self.assertEqual(first["firmware_LF_pins"], 113)
        self.assertTrue(first["installed_sources_unchanged"])
        self.assertFalse(first["stage_a_ota_route"])
        self.assertEqual(second["PHASE_T_SOURCE"], "PASS_OFFLINE")
        self.assertEqual(second["device_contacts"], 0)

    def test_each_tampered_new_tool_is_rejected(self):
        original = subprocess.check_output
        for name in TOOLS:
            def changed(command, *args, **kwargs):
                if command == ["git", "hash-object", "--", name]:
                    return "0"*40+"\n"
                return original(command, *args, **kwargs)
            with self.subTest(tool=name), patch.object(subprocess, "check_output", side_effect=changed):
                with self.assertRaisesRegex(AssertionError, "offline launcher changed"):
                    signed.source_gate()

    def test_unknown_new_companion_is_not_exempt(self):
        original = subprocess.check_output
        unknown = "companion/unreviewed-source-pin-fixture.py"
        def additional(command, *args, **kwargs):
            result = original(command, *args, **kwargs)
            if command[:2] == ["git", "ls-files"] and "companion" in command:
                return unknown+"\n"+result
            return result
        with patch.object(subprocess, "check_output", side_effect=additional):
            with self.assertRaises(subprocess.CalledProcessError):
                signed.source_gate()

    def test_preexisting_companion_remains_frozen(self):
        original = Path.read_bytes
        protected = ROOT/"companion/media_sessions.py"
        def changed(path):
            result = original(path)
            return result+b"\n# synthetic drift\n" if path == protected else result
        with patch.object(Path, "read_bytes", changed):
            with self.assertRaisesRegex(AssertionError, "companion/media_sessions.py"):
                signed.source_gate()


if __name__ == "__main__":
    unittest.main()
