"""Host-only interoperability checks against the unchanged V0.7 wire-v2 reference."""

import base64
import hashlib
import json
from pathlib import Path
import sys
import unittest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "companion"))
from media_wire_v2_host import BEGIN, COMMIT, TILE, encode, parse_metadata  # noqa: E402


class V08VectorCompatibility(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.fixture = json.loads((ROOT / "tools" / "v08_crypto_vectors.json").read_text("utf-8"))

    def test_valid_binary_records_match_frozen_v07_reference(self):
        tx = bytes.fromhex(self.fixture["tx"])
        for name, operation in (("begin", BEGIN), ("tile", TILE), ("commit", COMMIT)):
            entry = self.fixture["entries"][name]
            body = bytes.fromhex(entry["body_hex"])
            with self.subTest(name=name):
                self.assertEqual(body, b"".join(encode(operation, tx, body[40:])))
                expected_digest = base64.b64encode(hashlib.sha256(body).digest()).decode("ascii")
                self.assertIn(f"Content-Digest: sha-256=:{expected_digest}:", entry["header"])

    def test_begin_metadata_is_canonical_and_bound_to_target_tx(self):
        entry = self.fixture["entries"]["begin"]
        document = parse_metadata(bytes.fromhex(entry["body_hex"])[40:])
        self.assertEqual(document["tx"], self.fixture["tx"])
        self.assertEqual((document["width"], document["height"], document["cover_len"]), (0, 0, 0))


if __name__ == "__main__":
    unittest.main()
