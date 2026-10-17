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

    if (len(header) != 8 or header[0] != 0xE9 or not 1 <= header[1] <= 16 or
            header[2] not in range(4) or header[3] >> 4 != 4 or
            (header[3] & 15) not in (0, 1, 2, 15)):
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


def restore_gate(path: Path, expected_sha256: str, *, confirmed_chip: str | None,
                 confirmed_flash_bytes: int | None, owner_authorized: bool) -> dict:
    """Offline validation of externally supplied evidence, never an executor.

    An assertion here is not live target verification or new owner permission.
    Physical restore stays HOLD until the separate exact-operation review.
    """
    report = inspect_master(path, expected_sha256)
    if confirmed_chip != "esp8266":
        raise MasterPreflightError("Confirmed same owner-unit ESP8266 target required")
    if confirmed_flash_bytes != EXPECTED_BYTES:
        raise MasterPreflightError("Confirmed 4 MiB physical flash required")
    if owner_authorized is not True:
        raise MasterPreflightError("Separate explicit exact-MASTER owner authorization required")
    report.update({
        "status": "OFFLINE_RESTORE_PREREQUISITES_PASS",
        "confirmed_chip_externally_supplied": confirmed_chip,
        "confirmed_flash_bytes_externally_supplied": confirmed_flash_bytes,
        "owner_authorization_externally_asserted": True,
        "authorization_to_restore": False,
        "post_restore_full_readback_bytes_required": EXPECTED_BYTES,
        "factory_recovery_successful": False,
        "next_gate": "Exact-operation review, then full MASTER restore and byte/hash readback verification.",
    })
    return report


def verify_readback(master: Path, readback: Path, expected_sha256: str) -> dict:
    """Compare existing local files after a future separately authorized read."""
    master_report = inspect_master(master, expected_sha256)
    if master.resolve() == readback.resolve() or master.samefile(readback):
        raise MasterPreflightError("Readback must be an independent file")
    readback_report = inspect_master(readback, expected_sha256)
    with master.open("rb") as original, readback.open("rb") as observed:
        while True:
            left, right = original.read(CHUNK), observed.read(CHUNK)
            if left != right:
                raise MasterPreflightError("Readback differs byte-for-byte from MASTER")
            if not left:
                break
    return {
        "status": "LOCAL_FULL_READBACK_VERIFICATION_PASS",
        "bytes": EXPECTED_BYTES, "master_sha256": master_report["sha256"],
        "readback_sha256": readback_report["sha256"], "byte_exact": True,
        "serial_io_performed": False, "flash_write_performed": False,
        "factory_runtime_recovery_proven": False,
        "next_gate": "Owner verifies OEM boot identity/display after separate reboot authorization.",
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("master", type=Path, help="Private owner-unit 4 MiB MASTER")
    parser.add_argument(
        "--expected-sha256",
        required=True,
        help="Digest copied from the owner's private custody record",
    )
    parser.add_argument("--check-restore-gate", action="store_true")
    parser.add_argument("--confirmed-chip", choices=["esp8266"])
    parser.add_argument("--confirmed-flash-bytes", type=int)
    parser.add_argument("--owner-authorized", action="store_true",
                        help="External exact-operation consent assertion; does not grant permission")
    parser.add_argument("--readback", type=Path,
                        help="Independent existing full readback for local byte/hash verification")
    args = parser.parse_args()
    try:
        if args.check_restore_gate and args.readback:
            parser.error("Restore preflight and post-restore verification are separate gates")
        if args.check_restore_gate:
            report = restore_gate(args.master, args.expected_sha256,
                                  confirmed_chip=args.confirmed_chip,
                                  confirmed_flash_bytes=args.confirmed_flash_bytes,
                                  owner_authorized=args.owner_authorized)
        elif args.readback:
            report = verify_readback(args.master, args.readback, args.expected_sha256)
        else:
            if args.confirmed_chip or args.confirmed_flash_bytes or args.owner_authorized:
                parser.error("Target/consent assertions require --check-restore-gate")
            report = inspect_master(args.master, args.expected_sha256)
    except (MasterPreflightError, OSError) as exc:
        parser.exit(1, f"MASTER RESTORE GATE CLOSED: {exc}\n")
    print(json.dumps(report, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
