"""Differential against unchanged wire-v2; no sockets or signed forgery claims."""
import itertools
import json
import os
from pathlib import Path
import subprocess
import sys
import unittest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "companion"))
from media_wire_v2_host import Authority, HostReceiver, WireError, BEGIN


def differential():
    fixture = json.loads((ROOT / "tools/v08_crypto_vectors.json").read_text("utf-8"))
    original = bytes.fromhex(fixture["entries"]["begin"]["body_hex"])
    records = [original]
    # Every alternative octet in each fixed-header position, including all
    # 1020 single-byte magic negatives. Cartesian high-bit combinations follow.
    for position in range(40):
        for value in range(256):
            if value != original[position]:
                changed = bytearray(original)
                changed[position] = value
                records.append(bytes(changed))
    for bits in itertools.product((0, 128), repeat=4):
        if any(bits):
            records.append(bytes(original[i] | bits[i] for i in range(4)) + original[4:])
    for length in (0, 1, 39, 40, len(original)-1):
        records.append(original[:length])
    records.append(original + b"X")
    epoch = int(fixture["epoch_hex"], 16)
    authority = Authority("media-test", epoch, BEGIN, bytes.fromhex(fixture["tx"]))
    expected = []
    for record in records:
        try:
            HostReceiver(epoch).receive(record[:40], record[40:], authority, now=100)
            expected.append(True)
        except WireError:
            expected.append(False)
    proc = subprocess.run([os.environ.get("SHINO_NODE", "node"), str(ROOT / "tools/v08_m6b_wire_probe.js")],
                          input=json.dumps([r.hex() for r in records]), text=True,
                          capture_output=True, check=True, timeout=60, cwd=ROOT)
    actual = json.loads(proc.stdout)
    assert actual == expected, [(i, records[i][:40].hex()) for i, (a, b) in enumerate(zip(actual, expected)) if a != b][:10]
    assert sum(actual) == 1
    return {"cases": len(records), "admitted": sum(actual), "rejected": len(records)-sum(actual),
            "magic_octet_negatives": 1020, "high_bit_permutations": 15,
            "header_octet_negatives": 10200, "reference_unchanged": True,
            "scope": "function-level matching-digest record admissibility; no signature forgery; no transfer state equivalence"}


class Mission6BWire(unittest.TestCase):
    def test_byte_exact_fixed_header_and_body_differential(self):
        self.assertEqual(differential()["cases"], 10222)


if __name__ == "__main__":
    print(json.dumps(differential(), indent=2))
