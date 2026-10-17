"""Real tracked-file guards in isolation: no SDK, build or owner input."""
import ast
from pathlib import Path
import subprocess
import unittest
from unittest.mock import patch

import m9_signed_ota_runner as signed
import m9_stagea_source_gate as stagea
from b52_source_compat import NEW_FILE_BLOBS, SCENE, predecessor

ROOT = Path(__file__).resolve().parents[1]
TOOLS = ("companion/shino_b5_get_diagnostic.py",
         "companion/test_shino_b5_get_diagnostic.py",
         "companion/shino_b5_partial_preflight.py",
         "companion/test_shino_b5_partial_preflight.py")


def tracked_gate(module):
    """Execute the actual pin assignment/loop, excluding the separate SDK gate."""
    tree = ast.parse(Path(module.__file__).read_text(encoding="utf-8"))
    function = next(node for node in tree.body if isinstance(node, ast.FunctionDef)
                    and node.name == ("source_gate" if module is signed else "run"))
    assignment = next(node for node in function.body if isinstance(node, ast.Assign)
                      and any(isinstance(t, ast.Name) and t.id == "new_offline_script_pins"
                              for t in node.targets))
    loop = next(node for node in function.body if isinstance(node, ast.For)
                and isinstance(node.target, ast.Name) and node.target.id == "name")
    # Include the actual reviewed-overlay import and pin-map update, while
    # continuing to exclude core_root/signing/SDK work before the assignment.
    imports = [node for node in function.body if isinstance(node, ast.ImportFrom)
               and node.module in ('b52_source_compat', 'link_m2_source_identity')]
    start, end = function.body.index(assignment), function.body.index(loop)
    block = ast.Module(body=imports + function.body[start:end+1], type_ignores=[])
    exec(compile(block, module.__file__, "exec"), {"ROOT": ROOT, "subprocess": subprocess})


class OfflineSourcePinsTests(unittest.TestCase):
    def setUp(self):
        for name in ("socket.socket", "socket.create_connection", "socket.getaddrinfo"):
            guard = self.enterContext(patch(name, side_effect=AssertionError("NO NETWORK")))
            self.addCleanup(guard.assert_not_called)
        # The general CI job has a shallow clone. Use immutable HEAD blobs as
        # this unit's baseline snapshot; specialized gates check real history.
        original = subprocess.check_output
        def snapshot(command, *args, **kwargs):
            if command[:2] == ["git", "show"]:
                ref, path = command[2].split(":", 1)
                if ref in ("7455f6b353f1733a78f2a6d25503edb063f7befb",
                           "b59964af43b555b75d415e6d063580945e6d99f7"):
                    command = ["git", "show", "HEAD:"+path]
                    if path == SCENE:
                        # The independent compatibility tests prove this
                        # reconstruction against the immutable old SHA-256.
                        data = original(command, *args, **kwargs)
                        return predecessor(path, data.decode('utf-8')).encode('utf-8')
            return original(command, *args, **kwargs)
        self.enterContext(patch.object(subprocess, "check_output", side_effect=snapshot))

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
                    ["git", "rev-parse", "HEAD:"+name], cwd=ROOT, text=True).strip()
                self.assertEqual(pins.get(name), expected, (module.__name__, name))

    def test_actual_tracked_closure_does_not_require_sdk(self):
        for module in (signed, stagea):
            with self.subTest(gate=module.__name__), \
                 patch.object(module, "core_root", side_effect=AssertionError("NO SDK REQUIRED")):
                tracked_gate(module)

    def test_each_tampered_new_tool_is_rejected(self):
        original = subprocess.check_output
        for name in TOOLS:
            def changed(command, *args, **kwargs):
                if command == ["git", "hash-object", "--", name]:
                    return "0"*40+"\n"
                return original(command, *args, **kwargs)
            with self.subTest(tool=name), patch.object(subprocess, "check_output", side_effect=changed):
                with self.assertRaisesRegex(AssertionError, "offline launcher changed"):
                    tracked_gate(signed)

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
                tracked_gate(signed)

    def test_each_reviewed_clock_file_is_pinned_before_sdk(self):
        original = subprocess.check_output
        for name in NEW_FILE_BLOBS:
            def changed(command, *args, **kwargs):
                if command == ["git", "hash-object", "--", name]:
                    return "0"*40+"\n"
                return original(command, *args, **kwargs)
            with self.subTest(clock_file=name), patch.object(subprocess, "check_output", side_effect=changed):
                with self.assertRaisesRegex(AssertionError, "offline launcher changed"):
                    tracked_gate(signed)

    def test_each_new_m1_m2_source_requires_exact_reviewed_git_blob(self):
        from link_m2_source_identity import LINK_M2_FILE_BLOBS
        original = subprocess.check_output
        for name in LINK_M2_FILE_BLOBS:
            def changed(command, *args, **kwargs):
                if command == ["git", "hash-object", "--", name]:
                    return "0"*40 + "\\n"
                return original(command, *args, **kwargs)
            with self.subTest(file=name), patch.object(subprocess, "check_output", side_effect=changed):
                with self.assertRaises(AssertionError):
                    tracked_gate(signed)
                with self.assertRaises(AssertionError):
                    tracked_gate(stagea)

    def test_preexisting_companion_remains_frozen(self):
        original = Path.read_bytes
        protected = ROOT/"companion/media_sessions.py"
        def changed(path):
            result = original(path)
            return result+b"\n# synthetic drift\n" if path == protected else result
        with patch.object(Path, "read_bytes", changed):
            with self.assertRaisesRegex(AssertionError, "companion/media_sessions.py"):
                tracked_gate(signed)


if __name__ == "__main__":
    unittest.main()
