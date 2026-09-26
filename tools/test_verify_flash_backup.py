import hashlib
import tempfile
import unittest
from pathlib import Path

from verify_flash_backup import BackupError, verify_pair


def sample(size=1024):
    return bytes([0xE9, 2, 2, 0x40, 0x80, 0xF4, 0x10, 0x40]) + bytes(range(256)) * ((size - 8) // 256) + bytes(range((size - 8) % 256))


class BackupVerificationTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.a = Path(self.temp.name) / "A.bin"
        self.b = Path(self.temp.name) / "B.bin"
        self.data = sample()
        self.a.write_bytes(self.data)
        self.b.write_bytes(self.data)

    def tearDown(self):
        self.temp.cleanup()

    def test_valid_independent_matching_files(self):
        result = verify_pair(self.a, self.b, 1024)
        self.assertEqual(result["bytes"], 1024)
        self.assertEqual(result["sha256"], hashlib.sha256(self.data).hexdigest())

    def test_same_file_is_rejected(self):
        with self.assertRaisesRegex(BackupError, "different files"):
            verify_pair(self.a, self.a, 1024)

    def test_wrong_size_is_rejected(self):
        self.b.write_bytes(self.data[:-1])
        with self.assertRaisesRegex(BackupError, "Wrong readback sizes"):
            verify_pair(self.a, self.b, 1024)

    def test_mismatch_reports_exact_offset(self):
        bad = bytearray(self.data)
        bad[700] ^= 1
        self.b.write_bytes(bad)
        with self.assertRaisesRegex(BackupError, "0x2BC"):
            verify_pair(self.a, self.b, 1024)

    def test_invalid_header_and_homogeneous_dump_rejected(self):
        bad = b"\xff" * 1024
        self.a.write_bytes(bad)
        self.b.write_bytes(bad)
        with self.assertRaisesRegex(BackupError, "homogeneous"):
            verify_pair(self.a, self.b, 1024)
        bad = b"NOHEADER" + self.data[8:]
        self.a.write_bytes(bad)
        self.b.write_bytes(bad)
        with self.assertRaisesRegex(BackupError, "boot image header"):
            verify_pair(self.a, self.b, 1024)

    def test_expected_size_must_be_positive(self):
        with self.assertRaises(BackupError):
            verify_pair(self.a, self.b, 0)


if __name__ == "__main__":
    unittest.main()
