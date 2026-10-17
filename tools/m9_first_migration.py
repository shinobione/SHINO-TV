#!/usr/bin/env python3
"""Mission 9 Phase B: local image inspection and PRINT-ONLY future commands.

No subprocess, serial, network, filesystem mount or device writer exists here.
Image plausibility and write geometry do not authenticate firmware or prove its
linker/boot profile. Pair this report with exact-source/ELF/build evidence.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import struct
from pathlib import Path

from m9_flash_layout import (
    FLASH_BYTES, FS_START, FS_END, LINKER_MAX_APP_BYTES, align_sector,
)

OLD_FS_START = 0x100000
ESPTOOL_VERSION = "5.4.0"  # .github/workflows/m9-flash-layout.yml


class MigrationError(ValueError):
    """The offline candidate gate is closed."""


def application_extent(size: int) -> int:
    if size <= 0:
        raise MigrationError("Application size must be positive")
    rounded = align_sector(size)
    if rounded >= OLD_FS_START:
        raise MigrationError("Rounded application extent reaches/exceeds 0x100000")
    if size > LINKER_MAX_APP_BYTES:
        raise MigrationError("Candidate exceeds the pinned 4m2m linker ceiling")
    return rounded


def esp8266_v1_image(data: bytes, offset: int = 0) -> dict:
    """Bounded ESP8266 v1 segment/checksum parser; does not import esptool."""
    if len(data) < offset + 8:
        raise MigrationError("Truncated ESP8266 header")
    magic, count, mode, size_freq, entry = struct.unpack_from("<BBBBI", data, offset)
    if magic != 0xE9 or not 1 <= count <= 16 or mode not in range(4):
        raise MigrationError("Implausible ESP8266 v1 header")
    # This mission targets exactly 4 MiB / 40 MHz / DIO; keep those header
    # parameters unchanged in all rendered future writes.
    if mode != 2 or size_freq != 0x40 or not 0x40100000 <= entry < 0x40300000:
        raise MigrationError("Expected ESP8266 4 MiB / 40 MHz / DIO executable image")
    cursor = offset + 8
    checksum = 0xEF
    for _ in range(count):
        if cursor + 8 > len(data):
            raise MigrationError("Truncated segment header")
        address, size = struct.unpack_from("<II", data, cursor)
        cursor += 8
        if size == 0 or cursor + size > len(data):
            raise MigrationError("Invalid/truncated segment length")
        if not (0x3FFE8000 <= address < 0x40000000 or
                0x40100000 <= address < 0x40300000):
            raise MigrationError("Implausible ESP8266 segment address")
        for index in range(cursor, cursor + size):
            # elf2bin adds size/CRC after calculating the application XOR.
            byte = 0 if offset == 0x1000 and 0x1010 <= index < 0x1018 else data[index]
            checksum ^= byte
        cursor += size
    footer = ((cursor - offset) // 16) * 16 + 15 + offset
    if footer >= len(data) or data[footer] != checksum:
        raise MigrationError("Missing/invalid ESP8266 XOR checksum")
    return {"offset": offset, "segments": count, "checksum_valid": True,
            "end_exclusive": footer + 1}


def arduino_crc(data: bytes) -> int:
    """Core 3.1.2 elf2bin.py/eboot polynomial, with CRC fields zeroed."""
    crc = 0xFFFFFFFF
    for index, byte in enumerate(data):
        if 0x1010 <= index < 0x1018:
            byte = 0
        for mask in (128, 64, 32, 16, 8, 4, 2, 1):
            bit = bool(crc & 0x80000000) ^ bool(byte & mask)
            crc = (crc << 1) & 0xFFFFFFFF
            if bit:
                crc ^= 0x04C11DB7
    return crc


def inspect_candidate(path: Path) -> dict:
    path = Path(path)
    if not path.is_file() or path.is_symlink():
        raise MigrationError("Candidate must be a regular local BIN")
    size = path.stat().st_size
    rounded = application_extent(size)
    data = path.read_bytes()
    if len(data) != size:
        raise MigrationError("Candidate changed while being inspected")
    boot = esp8266_v1_image(data)
    if boot["end_exclusive"] > 0x1000 or len(data) < 0x1018:
        raise MigrationError("Expected Core 3.1.2 eboot + application BIN")
    application = esp8266_v1_image(data, 0x1000)
    if application["end_exclusive"] != size:
        raise MigrationError("Unexpected trailing bytes beyond the Arduino application")
    stored_size, stored_crc = struct.unpack_from("<II", data, 0x1010)
    if stored_size != size or stored_crc != arduino_crc(data):
        raise MigrationError("Invalid Arduino image length/CRC")
    return {
        "status": "PASS_OFFLINE_CANDIDATE_GEOMETRY",
        "candidate_size": size,
        "sha256": hashlib.sha256(data).hexdigest(),
        "esp8266_image_plausible": True,
        "image_evidence": {"boot": boot, "application": application,
                           "arduino_crc_valid": True},
        "flash_target_address": 0, "flash_target_address_hex": "0x000000",
        "sector_rounded_write_extent": rounded,
        "write_end_exclusive": rounded,
        "touched_sector_range_inclusive": f"0x000000..0x{rounded - 1:06X}",
        "untouched_by_stage1_command_inclusive": f"0x{rounded:06X}..0x3FFFFF",
        "application_write_overlaps_0x100000": False,
        "expected_physical_flash_bytes": FLASH_BYTES,
        "expected_linker_profile": "4m2m",
        "linker_profile_proven_by_bin_alone": False,
        "filesystem_start": FS_START, "filesystem_end_exclusive": FS_END,
        "filesystem_write_performed": False, "erase_all_performed": False,
        "serial_io_performed": False, "physical_authorization": False,
        "device_contacts": 0, "device_writes": 0,
        "physical_write": "HOLD",
    }


def render_commands() -> dict:
    # Placeholders only: never accept a port or concatenate user paths into
    # executable shell text. v5.4.0 hyphenated syntax, NOT PlatformIO's v3.0.
    base = ('python -m esptool --chip esp8266 --port "<PORT>" --baud 115200 '
            '--before no-reset --after no-reset-stub --connect-attempts 1 ')
    keep = '--flash-mode keep --flash-freq keep --flash-size keep --no-compress '
    return {
        "esptool_version_required": ESPTOOL_VERSION,
        "print_only": True, "all_device_operations_authorized": False,
        "identification": {"authorization": "NOT AUTHORIZED BY PHASE B",
                           "commands": [base + "chip-id", base + "flash-id"]},
        "stage1": {"authorization": "NOT AUTHORIZED BY PHASE B",
                   "command": base + 'write-flash ' + keep + '0x000000 "<CANDIDATE_BIN>"'},
        "master_restore": {"authorization": "NOT AUTHORIZED BY PHASE B",
                           "command": base + 'write-flash ' + keep + '0x000000 "<PRIVATE_MASTER_BIN>"'},
        "post_restore_readback": {"authorization": "NOT AUTHORIZED BY PHASE B",
                                  "command": base + 'read-flash 0x000000 0x400000 "<PRIVATE_READBACK_BIN>"'},
        "warning": ("Default RAM stub required; do not substitute --no-stub. "
                    "No erase-all, no header rewriting, no auto reboot. "
                    "esptool 5.4.0 internally permits two whole-write attempts; "
                    "a future one-attempt execution gate must resolve this before authorization."),
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("candidate", type=Path, nargs="?")
    parser.add_argument("--render-commands", action="store_true")
    args = parser.parse_args()
    if args.candidate is None and not args.render_commands:
        parser.error("Supply a local candidate and/or --render-commands")
    try:
        report = inspect_candidate(args.candidate) if args.candidate else {}
        if args.render_commands:
            report["future_commands"] = render_commands()
    except (MigrationError, OSError, struct.error) as exc:
        print(json.dumps({"status": "HOLD", "error": str(exc),
                          "physical_authorization": False, "device_contacts": 0,
                          "device_writes": 0}))
        return 1
    print(json.dumps(report, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
