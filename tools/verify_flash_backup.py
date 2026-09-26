#!/usr/bin/env python3
"""Compare two PRIVATE, independently acquired full-flash readbacks. Local files only.

No serial connection, requests, flashing, erase, image rewriting or automatic uploads.
Never commit either flash image: full-chip dumps may contain Wi-Fi/API credentials.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import os
from pathlib import Path


DEFAULT_EXPECTED_BYTES = 0x400000  # hypothesis: owner's chip is 4 MiB; confirm with flash-id first
CHUNK = 1024 * 256


class BackupError(ValueError):
    """A readback pair has not passed the recovery backup gate."""


def verify_pair(path_a: Path, path_b: Path, expected_bytes: int = DEFAULT_EXPECTED_BYTES) -> dict:
    path_a = Path(path_a)
    path_b = Path(path_b)
    if expected_bytes <= 0:
        raise BackupError("Expected flash size must be positive")
    if path_a.resolve() == path_b.resolve() or os.path.samefile(path_a, path_b):
        raise BackupError("Two different files are required; independent reads must be documented")
    size_a, size_b = path_a.stat().st_size, path_b.stat().st_size
    if size_a != expected_bytes or size_b != expected_bytes:
        raise BackupError(
            f"Wrong readback sizes: A={size_a}, B={size_b}, detected flash must be {expected_bytes} bytes"
        )

    hash_a, hash_b = hashlib.sha256(), hashlib.sha256()
    first = None
    all_same = True
    offset = 0
    with path_a.open("rb") as a, path_b.open("rb") as b:
        while offset < expected_bytes:
            left = a.read(min(CHUNK, expected_bytes - offset))
            right = b.read(min(CHUNK, expected_bytes - offset))
            if not left or len(left) != len(right):
                raise BackupError(f"Truncated/inconsistent readback at byte {offset}")
            if left != right:
                first_difference = next(i for i, pair in enumerate(zip(left, right)) if pair[0] != pair[1])
                raise BackupError(f"Readbacks differ at offset 0x{offset + first_difference:X}")
            if first is None:
                first = left[0]
            if left.count(first) != len(left):
                all_same = False
            hash_a.update(left)
            hash_b.update(right)
            offset += len(left)

    if all_same:
        raise BackupError("Dump is homogeneous (all one byte); reject as implausible")
    # ESP8266 boot images normally have 0xE9 magic and segment count 1..16 at address 0.
    # This is a plausibility check, not a complete firmware validation or restoration test.
    with path_a.open("rb") as source:
        header = source.read(8)
    if len(header) != 8 or header[0] != 0xE9 or not 1 <= header[1] <= 16:
        raise BackupError("No plausible ESP8266 boot image header at offset zero (0xE9 + segment count)")

    a_digest, b_digest = hash_a.hexdigest(), hash_b.hexdigest()
    if a_digest != b_digest:
        raise BackupError("Readbacks have different SHA-256 digests")
    return {
        "status": "matching_readbacks",
        "bytes": expected_bytes,
        "sha256": a_digest,
        "esp8266_header_magic": "0xE9",
        "segment_count_from_header": header[1],
        "reminder": "Not proof of restored bootability. Keep both dumps private/off Git.",
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("first", type=Path, help="First private full-flash readback")
    parser.add_argument("second", type=Path, help="Independent second private full-flash readback")
    parser.add_argument("--expected-bytes", type=int, default=DEFAULT_EXPECTED_BYTES,
                        help="Use confirmed chip size from flash-id; default hypothesis: 4194304")
    args = parser.parse_args()
    try:
        report = verify_pair(args.first, args.second, args.expected_bytes)
    except (BackupError, OSError) as error:
        parser.exit(status=1, message=f"BACKUP GATE CLOSED: {error}\n")
    print(json.dumps(report, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
