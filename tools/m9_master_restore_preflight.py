#!/usr/bin/env python3
"""Mission 9 private 4 MiB UART MASTER preflight — local files only.

This tool validates a private owner-unit full-flash image before a separately
authorized recovery operation. It performs no serial I/O and never writes,
erases, mounts, or uploads anything.

The expected SHA-256 must be supplied from the owner's private custody record;
the owner-unit digest is intentionally not embedded in this repository.
"""
from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path


EXPECTED_BYTES = 0x400000
CHUNK = 256 * 1024


class MasterPreflightError(ValueError):
    """Private MASTER failed a recovery preflight invariant."""


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as source:
        while True:
            chunk = source.read(CHUNK)
            if not chunk:
                break
            digest.update(chunk)
    return digest.hexdigest()


def inspect_master(path: Path, expected_sha256: str) -> dict:
    path = Path(path)
    expected = expected_sha256.strip().lower()

    if not path.is_file() or path.is_symlink():
        raise MasterPreflightError("MASTER must be a regular local file")
    if len(expected) != 64 or any(c not in "0123456789abcdef" for c in expected):
        raise MasterPreflightError("Expected SHA-256 must be exactly 64 hexadecimal characters")
    if path.stat().st_size != EXPECTED_BYTES:
        raise MasterPreflightError(
            f"Wrong MASTER length: {path.stat().st_size}; expected {EXPECTED_BYTES}"
        )

    with path.open("rb") as source:
        header = source.read(8)
        source.seek(0)
        first = source.read(1)
        all_same = bool(first)
        if first:
            while True:
                chunk = source.read(CHUNK)
                if not chunk:
                    break
                if chunk.count(first[0]) != len(chunk):
                    all_same = False
                    break

    if len(header) != 8 or header[0] != 0xE9 or not 1 <= header[1] <= 16:
        raise MasterPreflightError(
            "No plausible ESP8266 boot image header at flash offset 0"
        )
    if all_same:
        raise MasterPreflightError("MASTER is homogeneous and implausible")

    actual = _sha256(path)
    if actual != expected:
        raise MasterPreflightError(
            f"SHA-256 mismatch: actual {actual}, expected {expected}"
        )

    return {
        "status": "PRIVATE_MASTER_PREFLIGHT_PASS",
        "bytes": EXPECTED_BYTES,
        "sha256": actual,
        "esp8266_header_magic": "0xE9",
        "segment_count_from_header": header[1],
        "serial_io_performed": False,
        "flash_write_performed": False,
        "erase_performed": False,
        "authorization_to_restore": False,
        "next_gate": (
            "Verify same physical ESP8266/4MiB target and obtain separate explicit "
            "authorization before any write-flash command."
        ),
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("master", type=Path, help="Private owner-unit 4 MiB MASTER")
    parser.add_argument(
        "--expected-sha256",
        required=True,
        help="Digest copied from the owner's private custody record",
    )
    args = parser.parse_args()
    try:
        report = inspect_master(args.master, args.expected_sha256)
    except (MasterPreflightError, OSError) as exc:
        parser.exit(1, f"MASTER RESTORE GATE CLOSED: {exc}\n")
    print(json.dumps(report, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
