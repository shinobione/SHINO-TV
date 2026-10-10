"""Cross-process HTTP Digest lock tests. No network/device/OTA requests."""
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import threading
import time
import unittest
from unittest.mock import patch

from shino_digest_coord import (
    CoordinationBusy, CoordinatedReader, _safe_host, digest_exchange
)

HOST = "192.168.4.1"


class TestDigestCoord(unittest.TestCase):
    def test_only_rfc1918_targets(self):
        self.assertEqual(_safe_host(HOST), HOST)
        for host in ("127.0.0.1", "8.8.8.8", "example.org", "192.168.4.1:80", "::1"):
            with self.subTest(host=host), self.assertRaises(ValueError):
                _safe_host(host)

    def test_no_temporary_directory_until_acquire(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp) / "missing"
            self.assertFalse(root.exists())
            with digest_exchange(HOST, directory=root):
                self.assertTrue(root.is_dir())
                self.assertEqual(len(list(root.glob("*.lock"))), 1)
            self.assertEqual(len(list(root.glob("*.lock"))), 1)

    def test_two_windows_processes_cannot_overlap(self):
        # subprocess is essential: a thread-only test does not verify OS
        # inter-process locking or Windows msvcrt byte-lock behavior.
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            script = (
                "import sys;from pathlib import Path;"
                "from shino_digest_coord import digest_exchange,CoordinationBusy;"
                "try:\n"
                " with digest_exchange('192.168.4.1',wait_seconds=float(sys.argv[2]),directory=Path(sys.argv[1])):print('ACQUIRED')\n"
                "except CoordinationBusy: print('BUSY')\n"
            )
            env = dict(os.environ, PYTHONPATH=str(Path(__file__).resolve().parent))
            with digest_exchange(HOST, directory=root):
                done = subprocess.run([sys.executable, "-c", script, str(root), "0.15"],
                                      env=env, capture_output=True, text=True, timeout=6)
                self.assertEqual(done.returncode, 0, done.stderr)
                self.assertEqual(done.stdout.strip(), "BUSY")
            done = subprocess.run([sys.executable, "-c", script, str(root), "0.15"],
                                  env=env, capture_output=True, text=True, timeout=6)
            self.assertEqual(done.returncode, 0, done.stderr)
            self.assertEqual(done.stdout.strip(), "ACQUIRED")

    def test_coordinated_reader_holds_lock_through_body_and_release(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            class Response:
                def __enter__(self): return self
                def __exit__(self, *args): return False
                def read(self):
                    # Another local logical request must not acquire while
                    # this full read+Digest operation is active.
                    with self.assert_busy(): pass
                    return b"OK"
            class Raw:
                def __init__(self): self.called = []
                def open(self, req, timeout):
                    self.called.append((req, timeout))
                    return response
            class Harness:
                def assert_busy(self):
                    return digest_exchange(HOST, directory=root, wait_seconds=0)
            harness = Harness()
            response = Response()
            response.assert_busy = harness.assert_busy
            raw = Raw()
            with patch("shino_digest_coord._lock_directory", return_value=root):
                with CoordinatedReader(raw, HOST).open("GET", timeout=4) as got:
                    with self.assertRaises(CoordinationBusy):
                        with digest_exchange(HOST, directory=root, wait_seconds=0):
                            pass
                    self.assertIs(got, response)
                with digest_exchange(HOST, directory=root, wait_seconds=0):
                    pass
            self.assertEqual(raw.called, [("GET", 4)])

    def test_busy_does_not_open_underlying_http(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            class Forbidden:
                def open(self, request, timeout):
                    raise AssertionError("HTTP attempted without lock")
            with patch("shino_digest_coord._lock_directory", return_value=root):
                with digest_exchange(HOST, directory=root):
                    reader = CoordinatedReader(Forbidden(), HOST)
                    with self.assertRaises(CoordinationBusy):
                        with reader.open("GET", timeout=1):
                            pass

    def test_symlink_rejected_if_available(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            actual = root / "real"
            actual.mkdir()
            alias = root / "alias"
            try:
                alias.symlink_to(actual, target_is_directory=True)
            except (OSError, NotImplementedError):
                return
            with self.assertRaises(CoordinationBusy):
                with digest_exchange(HOST, directory=alias): pass

    def test_invalid_deadline_is_rejected(self):
        with tempfile.TemporaryDirectory() as temp:
            for value in (-1, 3.01, True, "4"):
                with self.subTest(value=value), self.assertRaises(ValueError):
                    with digest_exchange(HOST, wait_seconds=value, directory=Path(temp)): pass


if __name__ == "__main__":
    unittest.main()
