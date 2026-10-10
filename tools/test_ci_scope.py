"""Unit tests of CI scope, especially required-check fail-open behavior."""
import importlib.util
from pathlib import Path
import unittest
from unittest.mock import patch

script=Path(__file__).with_name("ci_scope.py")
spec=importlib.util.spec_from_file_location("shino_ci_scope",script)
scope=importlib.util.module_from_spec(spec)
spec.loader.exec_module(scope)


class TestCiScope(unittest.TestCase):
    def test_docs_only_skips_optional_jobs(self):
        for group in scope.SCOPE:
            with self.subTest(group=group):
                if group == "ci-core":
                    # Mandatory core check is intentionally present on every PR.
                    self.assertTrue(scope.in_scope(group,["docs/README.md"]))
                else:
                    self.assertFalse(scope.in_scope(group,["docs/README.md"]))

    def test_corresponding_workflow_always_runs(self):
        for group,file in (("signed","m9-signed-ota.yml"),
                           ("stagea","m9-stagea-ota.yml"),
                           ("http","shino-http-ota.yml"),
                           ("wifi","shino-wifi-install.yml")):
            self.assertTrue(scope.in_scope(group,[".github/workflows/"+file]))

    def test_ota_fix_runs_ota_but_not_historical_unwired(self):
        paths=["ota/firmware/ShinoHttpOta.h",
               "tools/shino_http_ota_exact_image_replay.py"]
        self.assertTrue(scope.in_scope("http",paths))
        self.assertFalse(scope.in_scope("signed",paths))
        self.assertFalse(scope.in_scope("stagea",paths))
        self.assertFalse(scope.in_scope("wifi",paths))

    def test_wifi_receiver_changes_trigger_wifi_gate(self):
        self.assertTrue(scope.in_scope("wifi", [
            "tools/shino_maintenance_native.py"]))
        self.assertTrue(scope.in_scope("wifi", [
            "experiments/shino_wifi_install/include/ShinoWifiUpdate.h"]))

    def test_ci_archival_only_runs_when_dispatched(self):
        self.assertFalse(scope.in_scope("ci-legacy", ["firmware/src/Normal.cpp"]))
        self.assertFalse(scope.in_scope("ci-legacy", [".github/workflows/ci.yml"]))

    def test_ota_change_does_not_rebuild_old_missions(self):
        for group in ("ci-legacy", "ci-home", "ci-artwork", "ci-v07", "ci-crypto",
                      "ci-preparse", "ci-bridge", "ci-windows"):
            with self.subTest(group=group):
                self.assertFalse(scope.in_scope(group, ["ota/firmware/ShinoHttpOta.h"]))

    def test_windows_changes_scoped(self):
        self.assertTrue(scope.in_scope("ci-windows", ["companion/shino_link.py"]))
        self.assertFalse(scope.in_scope("ci-windows", ["docs/README.md"]))

    def test_non_push_events_not_duplicate(self):
        self.assertFalse(scope.duplicate_open_pr_push("pull_request"))
        self.assertFalse(scope.duplicate_open_pr_push("workflow_dispatch"))

    def test_missing_token_fails_open(self):
        with patch.dict(scope.os.environ, {"GITHUB_REPOSITORY": "shinobione/SHINO-TV",
                         "GITHUB_REF_NAME": "feature/test", "GITHUB_TOKEN": ""}):
            self.assertFalse(scope.duplicate_open_pr_push("push"))

    def test_unavailable_github_api_fails_open(self):
        with patch.dict(scope.os.environ, {"GITHUB_REPOSITORY": "shinobione/SHINO-TV",
                         "GITHUB_REF_NAME": "feature/test", "GITHUB_TOKEN": "token"}):
            with patch.object(scope, "urlopen", side_effect=OSError("offline")):
                self.assertFalse(scope.duplicate_open_pr_push("push"))

    def test_missing_ref_fails_open(self):
        self.assertIsNone(scope.changed_files("push","0"*40,"a"*40))
        self.assertIsNone(scope.changed_files("pull_request",None,"a"*40))
        self.assertIsNone(scope.changed_files("workflow_dispatch",None,None))

    def test_git_failure_fails_open(self):
        with patch.object(scope.subprocess,"run",side_effect=OSError("offline")):
            self.assertIsNone(scope.changed_files("pull_request","a"*40,"b"*40))

    def test_no_changes_is_not_implicitly_relevant(self):
        self.assertFalse(scope.in_scope("http",[]))


if __name__ == "__main__":
    unittest.main()
