#!/usr/bin/env python3
"""Read-only SHINO 4m3m native OTA geometry/integrity feasibility research.

NEVER contacts the device. NEVER writes or uploads firmware. SHA-256 here
compares an image against a SEPARATELY reviewed owner-provided digest; it is
NOT a digital signature or proof of the author. A passing result does NOT
authorize an OTA. The on-device writer is deliberately not implemented.
"""
from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
import re

from wifi_flash_preflight import (
    FOUR_MB, PreflightError, inspect_image, platformio_layout,
    round_sector, staging_model, inferred_stock_fs_staging_overlap,
)

OTA_END = 0x100000  # 4m3m linked application ceiling, not physical 4-MB end
SECTOR = 4096
MAX_RESEARCH_BYTES = 494144  # bounded by reviewed OEM app size, not a guarantee
REQUIRED_BINARY_MARKERS = (
    b"FIRST_BOOT_BRIDGE",
    b"FSLESS_PC_TELEMETRY_RAM_ONLY",
    b"RAM_SAMPLE_ACCEPTED",
)


class NativeOtaGateError(ValueError):
    pass


def assess(candidate: Path, expected_sha256: str, *, current_sketch_bytes: int,
           reported_free_sketch_bytes: int, observed_physical_flash_bytes: int,
           platformio_ini: Path) -> dict:
    """File-only sanity model; returns explicit NO-GO even on a passing image."""
    if not re.fullmatch(r"[0-9a-fA-F]{64}", expected_sha256):
        raise NativeOtaGateError("Expected SHA-256 must be an independent 64-hex reference")
    if not candidate.is_file() or candidate.is_symlink():
        raise NativeOtaGateError("Candidate must be a regular local application file")
    size = candidate.stat().st_size
    if not 64000 <= size <= MAX_RESEARCH_BYTES:
        raise NativeOtaGateError("Candidate exceeds the conservative reviewed research window")
    if observed_physical_flash_bytes != FOUR_MB:
        raise NativeOtaGateError("Real runtime flash size is not the exact 4-MiB model")
    if not 64000 <= current_sketch_bytes <= MAX_RESEARCH_BYTES:
        raise NativeOtaGateError("Unexpected running sketch size")
    if not 0 < reported_free_sketch_bytes <= OTA_END:
        raise NativeOtaGateError("Missing or invalid runtime free-sketch report")

    image = candidate.read_bytes()
    actual_hash = hashlib.sha256(image).hexdigest()
    if actual_hash != expected_sha256.lower():
        raise NativeOtaGateError("Candidate does not match independently reviewed SHA-256")
    try:
        header = inspect_image(image, "SHINO_OTA_RESEARCH_CANDIDATE")
        layout, application_end = platformio_layout(platformio_ini, "env:esp12e")
    except PreflightError as exc:
        raise NativeOtaGateError(str(exc)) from exc
    if header["flash_mode"] != "DIO" or header["flash_size_bytes_from_header"] != FOUR_MB or (
            header["flash_frequency"] != "40MHz"):
        raise NativeOtaGateError("Unexpected ESP8266 flash mode/size/frequency header")
    if layout != "eagle.flash.4m3m.ld" or application_end != OTA_END:
        raise NativeOtaGateError("Source is not linked for the reviewed 4m3m OTA ceiling")
    if any(marker not in image for marker in REQUIRED_BINARY_MARKERS):
        raise NativeOtaGateError("Required conservative FS-less runtime marker absent")
    model = staging_model(current_sketch_bytes, size, OTA_END)
    if (not model["nominal_no_overlap"] or model["free_gap_bytes"] < SECTOR or
            inferred_stock_fs_staging_overlap(model) != 0):
        raise NativeOtaGateError("Staging model overlaps sketch/guard or inferred FS")
    if round_sector(size) + SECTOR > reported_free_sketch_bytes:
        raise NativeOtaGateError("Runtime free-sketch report lacks image + 4-KiB margin")

    return {
        "status": "OFFLINE_NATIVE_OTA_FEASIBILITY_ONLY__NO_INSTALL_PERMISSION",
        "image_bytes": size,
        "candidate_sha256": actual_hash,
        "header": {
            "flash_mode": header["flash_mode"],
            "flash_size_flag": header["flash_size_flag"],
            "flash_frequency": header["flash_frequency"],
            "segments": header["segments"],
        },
        "source_layout": layout,
        "OTA_staging_model": model,
        "estimated_inferred_stock_fs_sector_overlap_bytes":
            inferred_stock_fs_staging_overlap(model),
        "runtime_free_sketch_report_supplied_by_operator_not_queried": reported_free_sketch_bytes,
        "trust_model": "Local SHA-256 integrity against independently reviewed owner digest; NO signature verification",
        "signature_verification_implemented": False,
        "native_device_writer_compiled": False,
        "hardware_or_network_contact": False,
        "firmware_or_filesystem_write": False,
        "permission_to_flash": False,
        "warning": ("Arithmetic and header checks cannot establish runtime OTA power-cut safety, "
                    "package authenticity, recovery from a nonbooting app or installer permission."),
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--candidate", type=Path, required=True)
    parser.add_argument("--expected-sha256", required=True)
    parser.add_argument("--current-sketch-bytes", type=int, required=True)
    parser.add_argument("--reported-free-sketch-bytes", type=int, required=True)
    parser.add_argument("--observed-physical-flash-bytes", type=int, required=True)
    parser.add_argument("--platformio", type=Path,
                        default=Path(__file__).resolve().parent.parent / "firmware/platformio.ini")
    args = parser.parse_args()
    try:
        result = assess(args.candidate, args.expected_sha256,
                        current_sketch_bytes=args.current_sketch_bytes,
                        reported_free_sketch_bytes=args.reported_free_sketch_bytes,
                        observed_physical_flash_bytes=args.observed_physical_flash_bytes,
                        platformio_ini=args.platformio)
    except (NativeOtaGateError, OSError, ValueError) as exc:
        parser.exit(1, f"NATIVE OTA OFFLINE GATE CLOSED: {exc}\n")
    print(json.dumps(result, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
