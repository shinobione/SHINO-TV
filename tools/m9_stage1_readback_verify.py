#!/usr/bin/env python3
"""Local-only Phase C comparison of existing files; never device authority."""
from __future__ import annotations

import argparse
import hashlib
import json
import re
import stat
from pathlib import Path

from m9_first_migration import inspect_candidate
from m9_flash_layout import FLASH_BYTES


class ReadbackError(ValueError):
    """The local evidence gate is closed."""


def regular_file(path: Path) -> Path:
    path = Path(path)
    if not stat.S_ISREG(path.lstat().st_mode) or path.is_symlink():
        raise ReadbackError("Regular non-symlink file required")
    # Reject symlinked directory components, too.
    if any(parent.is_symlink() for parent in path.absolute().parents):
        raise ReadbackError("Symlinked file ancestry is not accepted")
    return path


def distinct_files(*paths: Path) -> None:
    for index, left in enumerate(paths):
        for right in paths[index + 1:]:
            if left.resolve() == right.resolve() or left.samefile(right):
                raise ReadbackError("Candidate, PRE and POST must be independent files")


def candidate_bytes(path: Path, expected_sha256: str) -> tuple[bytes, dict]:
    if not re.fullmatch(r"[0-9a-fA-F]{64}", expected_sha256):
        raise ReadbackError("External SHA-256 must be exactly 64 hexadecimal characters")
    path = regular_file(path)
    report = inspect_candidate(path)
    data = path.read_bytes()
    digest = hashlib.sha256(data).hexdigest()
    if digest != expected_sha256.lower() or digest != report["sha256"]:
        raise ReadbackError("Candidate SHA-256 mismatch or changed during inspection")
    return data, report


def verify_stage1(candidate: Path, pre: Path, post: Path, expected_sha256: str) -> dict:
    paths = tuple(regular_file(path) for path in (candidate, pre, post))
    distinct_files(*paths)
    data, inspected = candidate_bytes(paths[0], expected_sha256)
    before, after = paths[1].read_bytes(), paths[2].read_bytes()
    if len(before) != FLASH_BYTES or len(after) != FLASH_BYTES:
        raise ReadbackError("PRE and POST must each be exactly 4,194,304 bytes")
    size, rounded = len(data), inspected["sector_rounded_write_extent"]
    if after[:size] != data:
        raise ReadbackError("POST payload differs from candidate")
    if after[rounded:] != before[rounded:]:
        raise ReadbackError("Protected region differs byte-for-byte")
    return {
        "status": "PASS_LOCAL_STAGE1_READBACK_MODEL", "candidate_bytes": size,
        "candidate_sha256": inspected["sha256"], "readback_bytes_each": FLASH_BYTES,
        "pre_sha256": hashlib.sha256(before).hexdigest(),
        "post_sha256": hashlib.sha256(after).hexdigest(),
        "payload_range_inclusive": f"0x000000..0x{size - 1:06X}",
        "touched_sector_range_inclusive": f"0x000000..0x{rounded - 1:06X}",
        "slack_range_half_open": [size, rounded], "slack_equality_required": False,
        "protected_range_inclusive": f"0x{rounded:06X}..0x3FFFFF",
        "protected_bytes_compared": FLASH_BYTES - rounded, "protected_byte_exact": True,
        "physical_capture_freshness_proven": False, "device_claims": False,
        "serial_io_performed": False, "physical_authorization": False,
        "device_contacts": 0, "device_writes": 0, "physical_write": "HOLD",
        "physical_runtime_gate": "NOT_RUN",
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("candidate", type=Path)
    parser.add_argument("pre", type=Path)
    parser.add_argument("post", type=Path)
    parser.add_argument("--expected-sha256", required=True)
    args = parser.parse_args()
    try:
        report = verify_stage1(args.candidate, args.pre, args.post, args.expected_sha256)
    except (ValueError, OSError) as exc:
        parser.exit(1, f"STAGE1 READBACK GATE CLOSED: {exc}\n")
    print(json.dumps(report, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
