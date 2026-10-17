#!/usr/bin/env python3
"""Compare existing Stage-2 local files; no capture, executor or device claim."""
from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path

from m9_stage2_fs_candidate import exact_image, local_path, FS_START, FS_END, FLASH_END
from m9_stage1_readback_verify import distinct_files


def verify_stage2(image: Path, pre: Path, post: Path, expected_sha256: str) -> dict:
    paths = tuple(local_path(p) for p in (image, pre, post))
    distinct_files(*paths)
    data = exact_image(paths[0], expected_sha256)
    if any(p.stat().st_size != FLASH_END for p in paths[1:]):
        raise ValueError("PRE-STAGE2 and POST-STAGE2 must each be exactly 4194304 bytes")
    before, after = paths[1].read_bytes(), paths[2].read_bytes()
    if len(before) != FLASH_END or len(after) != FLASH_END:
        raise ValueError("Readback changed during inspection")
    if after[FS_START:FS_END] != data:
        raise ValueError("POST filesystem payload differs from exact frozen image")
    if after[:FS_START] != before[:FS_START]:
        raise ValueError("Lower protected region differs byte-for-byte")
    if after[FS_END:] != before[FS_END:]:
        raise ValueError("Reserved tail protected region differs byte-for-byte")
    # Do not print owner PRE/POST hashes, contents or absolute backup paths.
    return {"status": "PASS_LOCAL_STAGE2_READBACK_MODEL", "readback_bytes_each": FLASH_END,
            "image_bytes": len(data), "image_sha256": hashlib.sha256(data).hexdigest(),
            "filesystem_range_inclusive": "0x200000..0x3F9FFF", "filesystem_exact": True,
            "lower_protected_range_inclusive": "0x000000..0x1FFFFF",
            "lower_protected_bytes_compared": FS_START, "lower_protected_exact": True,
            "tail_protected_range_inclusive": "0x3FA000..0x3FFFFF",
            "tail_protected_bytes_compared": FLASH_END - FS_END, "tail_protected_exact": True,
            "pre_fs_equality_required": False, "physical_capture_freshness_proven": False,
            "filesystem_package_qualification_proven_by_this_comparison": False,
            "device_claims": False, "physical_authorization": False,
            "device_contacts": 0, "serial_io": 0, "flash_writes": 0,
            "device_filesystem_writes": 0, "reboots": 0,
            "stage2_physical_write": "HOLD", "stage2_runtime": "NOT_RUN"}


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("image", type=Path)
    parser.add_argument("pre", type=Path)
    parser.add_argument("post", type=Path)
    parser.add_argument("--expected-sha256", required=True)
    args = parser.parse_args()
    try:
        result = verify_stage2(args.image, args.pre, args.post, args.expected_sha256)
    except (ValueError, OSError) as exc:
        parser.exit(1, f"STAGE2 READBACK GATE CLOSED: {exc}\n")
    print(json.dumps(result, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
