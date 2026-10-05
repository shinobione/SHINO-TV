#!/usr/bin/env python3
"""Mission 9 offline ESP8266 4m2m flash/OTA geometry audit.

This tool performs arithmetic and source-configuration checks only.
It never opens a serial port, contacts a device, erases flash, writes flash,
mounts LittleFS, or handles the owner's private 4 MiB backup.
"""
from __future__ import annotations

import argparse
import json
import re
from pathlib import Path


FLASH_BYTES = 0x400000
SECTOR_BYTES = 0x1000

# Pinned Arduino ESP8266 Core 3.1.2 / eagle.flash.4m2m.ld.
FS_START = 0x200000
FS_END = 0x3FA000
EEPROM_START = 0x3FB000
RFCAL_START = 0x3FC000
WIFI_START = 0x3FD000
LINKER_MAX_APP_BYTES = 1_044_464  # 0xFEFF0, linker comment: ~1019 KiB

# Exact owner-approved/installed P1 application length retained in project docs.
P1_APP_BYTES = 464_544

DEFAULT_PLATFORMIO = Path("firmware/platformio.ini")
M9_ENV = "env:esp12e_m9_4m2m"


class LayoutError(ValueError):
    """Mission 9 layout gate failure."""


def align_sector(value: int) -> int:
    if value < 0:
        raise LayoutError("byte count must be non-negative")
    return (value + SECTOR_BYTES - 1) & ~(SECTOR_BYTES - 1)


def ota_geometry(current_bytes: int, target_bytes: int) -> dict:
    if current_bytes <= 0 or target_bytes <= 0:
        raise LayoutError("current and target application sizes must be positive")

    current_rounded = align_sector(current_bytes)
    target_rounded = align_sector(target_bytes)
    stage_start = FS_START - target_rounded if target_rounded <= FS_START else -1
    ota_geometry_fits = stage_start >= current_rounded
    linker_target_fits = target_bytes <= LINKER_MAX_APP_BYTES

    return {
        "current_bytes": current_bytes,
        "current_rounded_bytes": current_rounded,
        "target_bytes": target_bytes,
        "target_rounded_bytes": target_rounded,
        "stage_start": stage_start,
        "stage_start_hex": None if stage_start < 0 else f"0x{stage_start:06X}",
        "gap_between_current_and_staging_bytes": (
            stage_start - current_rounded if stage_start >= 0 else -1
        ),
        "ota_geometry_fits": ota_geometry_fits,
        "linker_target_fits": linker_target_fits,
        "candidate_passes": ota_geometry_fits and linker_target_fits,
    }


def _env_block(text: str, env_name: str) -> str:
    pattern = re.compile(
        rf"(?ms)^\[{re.escape(env_name)}\]\s*$"
        rf"(.*?)(?=^\[|\Z)"
    )
    match = pattern.search(text)
    if not match:
        raise LayoutError(f"missing [{env_name}] in platformio.ini")
    return match.group(1)


def inspect_platformio(path: Path = DEFAULT_PLATFORMIO) -> dict:
    text = path.read_text(encoding="utf-8")
    default_match = re.search(r"(?m)^default_envs\s*=\s*(\S+)\s*$", text)
    if not default_match:
        raise LayoutError("default_envs is missing")

    baseline = _env_block(text, "env:esp12e")
    mission = _env_block(text, M9_ENV)

    baseline_layout = re.search(
        r"(?m)^board_build\.ldscript\s*=\s*(\S+)\s*$", baseline
    )
    mission_layout = re.search(
        r"(?m)^board_build\.ldscript\s*=\s*(\S+)\s*$", mission
    )
    extends = re.search(r"(?m)^extends\s*=\s*(\S+)\s*$", mission)

    if not baseline_layout or baseline_layout.group(1) != "eagle.flash.4m3m.ld":
        raise LayoutError("baseline esp12e must remain on eagle.flash.4m3m.ld")
    if not mission_layout or mission_layout.group(1) != "eagle.flash.4m2m.ld":
        raise LayoutError("Mission 9 env must select eagle.flash.4m2m.ld")
    if not extends or extends.group(1) != "env:esp12e":
        raise LayoutError("Mission 9 env must extend env:esp12e")
    if default_match.group(1) != "esp12e":
        raise LayoutError("Mission 9 must not become the default environment")

    return {
        "default_env": default_match.group(1),
        "baseline_ldscript": baseline_layout.group(1),
        "mission9_env": M9_ENV,
        "mission9_ldscript": mission_layout.group(1),
        "mission9_is_default": False,
    }


def build_report(platformio_path: Path = DEFAULT_PLATFORMIO) -> dict:
    max_rounded = align_sector(LINKER_MAX_APP_BYTES)
    symmetric_gap = FS_START - (2 * max_rounded)

    cases = {
        "installed_p1_to_linker_max": ota_geometry(
            P1_APP_BYTES, LINKER_MAX_APP_BYTES
        ),
        "linker_max_to_linker_max": ota_geometry(
            LINKER_MAX_APP_BYTES, LINKER_MAX_APP_BYTES
        ),
        "600KiB_to_600KiB": ota_geometry(600 * 1024, 600 * 1024),
        "750KiB_to_750KiB": ota_geometry(750 * 1024, 750 * 1024),
        "900KiB_to_900KiB": ota_geometry(900 * 1024, 900 * 1024),
    }

    return {
        "status": "MISSION9_OFFLINE_LAYOUT_CANDIDATE",
        "device_contacts": 0,
        "device_writes": 0,
        "layout": {
            "physical_flash_bytes": FLASH_BYTES,
            "application_and_ota_region_start": 0,
            "application_and_ota_region_end": FS_START,
            "application_and_ota_region_bytes": FS_START,
            "filesystem_start": FS_START,
            "filesystem_end": FS_END,
            "filesystem_bytes": FS_END - FS_START,
            "post_filesystem_reserved_bytes": FLASH_BYTES - FS_END,
            "eeprom_start": EEPROM_START,
            "rfcal_start": RFCAL_START,
            "wifi_start": WIFI_START,
            "linker_max_application_bytes": LINKER_MAX_APP_BYTES,
            "linker_max_application_sector_rounded_bytes": max_rounded,
            "symmetric_max_to_max_gap_bytes": symmetric_gap,
        },
        "platformio": inspect_platformio(platformio_path),
        "ota_cases": cases,
        "gate": (
            "PASS_OFFLINE_GEOMETRY"
            if symmetric_gap >= 2 * SECTOR_BYTES
            and all(case["candidate_passes"] for case in cases.values())
            else "HOLD"
        ),
        "warnings": [
            "No physical migration is authorized by this report.",
            "Changing 4m3m to 4m2m intentionally overlaps the stock filesystem range 0x100000..0x1FFFFF.",
            "A stock application-only BIN is not a full factory restore after layout migration.",
            "Keep the owner-unit 4 MiB MASTER private and off Git.",
        ],
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--platformio",
        type=Path,
        default=DEFAULT_PLATFORMIO,
        help="Path to firmware/platformio.ini",
    )
    parser.add_argument(
        "--current-bytes",
        type=int,
        help="Optional current application size for an extra OTA geometry calculation",
    )
    parser.add_argument(
        "--target-bytes",
        type=int,
        help="Optional target application size for an extra OTA geometry calculation",
    )
    args = parser.parse_args()

    report = build_report(args.platformio)
    if args.current_bytes is not None or args.target_bytes is not None:
        if args.current_bytes is None or args.target_bytes is None:
            parser.error("--current-bytes and --target-bytes must be supplied together")
        report["custom_ota_case"] = ota_geometry(args.current_bytes, args.target_bytes)

    print(json.dumps(report, indent=2, sort_keys=True))
    return 0 if report["gate"] == "PASS_OFFLINE_GEOMETRY" else 1


if __name__ == "__main__":
    raise SystemExit(main())
