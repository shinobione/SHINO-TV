"""Pure/mocked regressions; never download, build, contact device or create files on owner PC."""
from __future__ import annotations

import hashlib
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from build_owner_private_packet import (
    APP_NAME, BIN_NAME, OEM_URL, PR16_REVIEWED_ANCESTOR,
    PrivateBuildError, build, git_blob_sha, independent_esptool_image_check,
    verify_reviewed_checkout,
)


class PrivateWindowsBuildTests(unittest.TestCase):
    def test_git_blob_exact_object_format(self):
        content = b"owner stock package bytes"
        expected = hashlib.sha1(b"blob 25\0" + content).hexdigest()
        self.assertEqual(git_blob_sha(content), expected)

    def test_requires_exact_reviewed_git_sha_before_work(self):
        for invalid in ("", "abc", "0" * 39, "A" * 40,
                        "0" * 40 + "anything", "../../wrong"):
            with self.subTest(source_sha=invalid), self.assertRaisesRegex(
                    PrivateBuildError, "complete lowercase 40"):
                verify_reviewed_checkout(invalid)

    def test_private_output_in_repo_denied_before_download_or_compile(self):
        from build_owner_private_packet import ROOT
        with patch("build_owner_private_packet.verify_reviewed_checkout", return_value="a" * 40):
            with self.assertRaisesRegex(PrivateBuildError, "OUTSIDE"):
                build("a" * 40, ROOT / "research-local" / "will-not-create")
        self.assertFalse((ROOT / "research-local" / "will-not-create").exists())

    def test_esptool_requires_explicit_valid_checksum(self):
        with tempfile.TemporaryDirectory() as tmp:
            with patch("build_owner_private_packet.run",
                       return_value="Checksum: 0x2b (valid)\n") as runner:
                independent_esptool_image_check(Path(tmp) / APP_NAME, Path(tmp) / "inspection.log")
                self.assertIn("image-info", runner.call_args.args[0])
            with patch("build_owner_private_packet.run",
                       return_value="Checksum: 0x2b (invalid)\n"):
                with self.assertRaisesRegex(PrivateBuildError, "not explicitly reported valid"):
                    independent_esptool_image_check(Path(tmp) / APP_NAME,
                                                    Path(tmp) / "inspection.log")

    def test_no_generic_install_paths_in_owner_python_or_windows_launcher(self):
        from build_owner_private_packet import ROOT
        source = (ROOT / "tools/build_owner_private_packet.py").read_text(encoding="utf-8")
        bat = (ROOT / "start-owner-private-build.cmd").read_text(encoding="utf-8")
        for forbidden in (
            "esptool write-flash", "esptool erase-flash", "/update\", method=\"POST",
            "serial.Serial(", "upload_port =", "requests.post(", "ssh ",
            "curl -F", "upload-artifact@", "pio run -t upload",
        ):
            with self.subTest(forbidden=forbidden):
                self.assertNotIn(forbidden, source)
                self.assertNotIn(forbidden, bat)
        self.assertIn("git", bat.lower())
        self.assertIn("--expected-source-sha", bat)
        self.assertIn("OWNER_PRIVATE_LOCAL_FILES_VERIFIED__FLASH_NOT_AUTHORIZED", source)
        self.assertIn("permission_to_flash", source)
        self.assertIn("False", source)
        self.assertIn("PRIVATE", APP_NAME)
        self.assertTrue(OEM_URL.startswith("https://raw.githubusercontent.com/GeekMagicClock/"))
        self.assertEqual(len(PR16_REVIEWED_ANCESTOR), 40)
        self.assertTrue(BIN_NAME.endswith(".bin"))

    def test_no_secret_values_or_firmware_in_public_ci_workflow(self):
        from build_owner_private_packet import ROOT
        flow = (ROOT / ".github/workflows/owner-private-build-smoke.yml").read_text(encoding="utf-8")
        self.assertNotIn("upload-artifact", flow)
        self.assertNotIn("upload-release", flow)
        self.assertNotIn("write-flash", flow)
        self.assertNotIn("erase-flash", flow)
        self.assertIn("fetch-depth: 0", flow)
        self.assertIn("rm -rf", flow)
        self.assertIn("build_owner_private_packet.py", flow)


if __name__ == "__main__":
    unittest.main()
