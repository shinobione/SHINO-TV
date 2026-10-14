"""B5.2 owner-local orchestrator: run without secrets or network/device."""
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch
import shino_b52_owner_candidate as target


class OwnerBuildTests(unittest.TestCase):
    def test_pinned_libraries_exact_version(self):
        with tempfile.TemporaryDirectory() as td:
            base = Path(td)
            for name, version in target.PINNED:
                folder = base / name
                folder.mkdir()
                (folder / "library.properties").write_text("version=" + version + "\n")
            self.assertTrue(target.pinned_libraries(base))
            (base / "ArduinoJson" / "library.properties").write_text("version=0\n")
            self.assertFalse(target.pinned_libraries(base))

    def test_wrong_branch_before_private_credential_check(self):
        with patch.object(target.subprocess, "check_output", return_value="main\n"), \
             patch.object(target, "private_source_gate", side_effect=AssertionError("NO")):
            with self.assertRaisesRegex(ValueError, "wrong branch"):
                target.preflight()

    def test_missing_credentials_fails_closed(self):
        with patch.object(target.subprocess, "check_output",
                          return_value=target.BRANCH + "\n"), \
             patch.object(target, "private_source_gate", return_value="a" * 40), \
             patch.object(target, "SECRETS", Path("__missing_shino_owner_credentials__")):
            with self.assertRaisesRegex(ValueError, "credentials missing"):
                target.preflight()

    def test_no_libraries_never_bootstraps_or_reads_private(self):
        with patch.object(target, "preflight", return_value="a" * 40), \
             patch.object(target, "available_libraries", return_value=iter(())), \
             patch.object(target, "build_b52", side_effect=AssertionError("NO")), \
             patch.object(target, "build_public_b51", side_effect=AssertionError("NO")):
            with self.assertRaisesRegex(ValueError, "no pinned local libraries"):
                target.run()


if __name__ == "__main__":
    unittest.main()
