"""Host-only source identity for reviewed M1/M2 LINK and its old predecessor."""

from pathlib import Path
import subprocess
import unittest
from unittest.mock import patch

from link_m2_source_identity import (
    LINK_PATH, LINK_B52_PREDECESSOR_BLOB, LINK_M2_FILE_BLOBS,
    LINK_M2_REVIEWED_BLOB, LinkSourceIdentityError,
    git_blob_sha1, reviewed_link_predecessor,
)

ROOT = Path(__file__).resolve().parents[1]


class LinkM2ExactIdentityTests(unittest.TestCase):
    def test_exact_current_and_immutable_predecessor_reconstruction(self):
        current = (ROOT / LINK_PATH).read_bytes().replace(b"\r\n", b"\n")
        self.assertEqual(git_blob_sha1(current), LINK_M2_REVIEWED_BLOB)
        old = reviewed_link_predecessor(current)
        self.assertEqual(git_blob_sha1(old), LINK_B52_PREDECESSOR_BLOB)
        self.assertNotEqual(current, old)
        self.assertNotIn(b"from link_mode_tray import", old)
        self.assertNotIn(b"mode_controller", old)
        self.assertIn(b"pystray.Menu(", old)

    def test_every_new_file_has_exact_reviewed_git_blob(self):
        self.assertEqual(len(LINK_M2_FILE_BLOBS), 5)
        self.assertEqual(LINK_M2_FILE_BLOBS[LINK_PATH],
                         LINK_M2_REVIEWED_BLOB)
        for name, sha in LINK_M2_FILE_BLOBS.items():
            with self.subTest(path=name):
                self.assertTrue(name.startswith("companion/"))
                self.assertEqual(
                    subprocess.check_output(
                        ["git", "rev-parse", "HEAD:" + name],
                        cwd=ROOT, text=True,
                    ).strip(), sha,
                )
                current = (ROOT / name).read_bytes()
                self.assertEqual(git_blob_sha1(current), sha)

    def test_any_extra_change_in_link_or_foreign_source_rejected(self):
        current = (ROOT / LINK_PATH).read_bytes()
        prior = reviewed_link_predecessor(current)
        for variant in (
            current + b"\n# accidental extra change\n",
            current.replace(b"mode_controller", b"mode_controllerX", 1),
            prior,  # even the historical version is not the approved M2 input
            b"",
        ):
            with self.subTest(variant=variant[:24]), \
                 self.assertRaises(LinkSourceIdentityError):
                reviewed_link_predecessor(variant)

    def test_no_network_or_device_required(self):
        import socket
        current = (ROOT / LINK_PATH).read_bytes()
        with patch.object(socket, "socket", side_effect=AssertionError("NO NETWORK")):
            self.assertEqual(git_blob_sha1(reviewed_link_predecessor(current)),
                             LINK_B52_PREDECESSOR_BLOB)

    def test_garbage_input_type_rejected(self):
        for bad in ("bytes", None, bytearray(b"abc")):
            with self.subTest(type=type(bad).__name__):
                with self.assertRaises(TypeError):
                    git_blob_sha1(bad)
                with self.assertRaises(TypeError):
                    reviewed_link_predecessor(bad)


if __name__ == "__main__":
    unittest.main()
