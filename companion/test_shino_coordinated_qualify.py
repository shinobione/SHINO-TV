"""Offline coordinated qualification wrapper tests: no device or OTA."""
import contextlib
import io
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

import shino_coordinated_qualify as module


class TestCoordinatedQualifier(unittest.TestCase):
    def test_print_only_does_not_create_transport(self):
        with tempfile.TemporaryDirectory() as tmp:
            receipt = Path(tmp) / "new.json"
            with patch.object(module.shino_qualify, "main", return_value=0) as run, \
                 patch.object(module, "Transport", side_effect=AssertionError("Device transport")):
                self.assertEqual(module.main(["--bin", "b", "--manifest", "m",
                                              "--receipt", str(receipt)]), 0)
                self.assertNotIn("--authorize-read", run.call_args.args[0])
                self.assertFalse(receipt.exists())

    def test_historical_receipt_cannot_be_written(self):
        for historical in ("A2-readonly-receipt.json", "B2-readonly-receipt.json"):
            with self.subTest(historical=historical), patch.object(module.shino_qualify, "main", side_effect=AssertionError("Touched prior receipt")):
                with self.assertRaises(SystemExit):
                    module.main(["--bin", "b", "--manifest", "m",
                                 "--receipt", historical, "--authorize-read"])

    def test_real_mode_passes_exact_args_and_restores_transport(self):
        original = module.shino_qualify.Transport
        with patch.object(module.shino_qualify, "main", return_value=2) as run:
            self.assertEqual(module.main(["--bin", "b", "--manifest", "m",
                                          "--receipt", "new-receipt.json",
                                          "--authorize-read"]), 2)
            self.assertIn("--authorize-read", run.call_args.args[0])
        self.assertIs(module.shino_qualify.Transport, original)


if __name__ == "__main__":
    unittest.main()
