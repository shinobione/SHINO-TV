#!/usr/bin/env python3
"""Offline, conservative single-device Wi-Fi installation preflight.

This script NEVER sends requests to a device or prepares an upload. It checks
three local application images, their manufacturer reference, and known source
flash layouts. Its result is NOT a physical installation authorization.
"""
from __future__ import annotations

import argparse
import configparser
import hashlib
import json
from pathlib import Path
import sys
import zipfile

from verify_factory_ota import FactoryOtaError, verify_archive


SIZE_FLAGS = {
    0: ("512KB", 512 * 1024), 1: ("256KB", 256 * 1024),
    2: ("1MB", 1024 * 1024), 3: ("2MB", 2 * 1024 * 1024),
    4: ("4MB", 4 * 1024 * 1024), 5: ("2MB-c1", 2 * 1024 * 1024),
    6: ("4MB-c1", 4 * 1024 * 1024), 8: ("8MB", 8 * 1024 * 1024),
    9: ("16MB", 16 * 1024 * 1024),
}
SPI_MODES = {0: "QIO", 1: "QOUT", 2: "DIO", 3: "DOUT"}
FREQUENCY = {0: "40MHz", 1: "26MHz", 2: "20MHz", 15: "80MHz"}
FOUR_MB = 4 * 1024 * 1024
SINGLE_SECTOR = 4096
COMMUNITY_LOADER_COMPARISON = 315920  # Research comparison; NOT measured stock OTA capacity.
OEM_SIZE = 494144
# Preflight only models layouts selected in our exact committed PlatformIO configs:
# eagle.flash.4m1m.ld -> 3 MiB until FS; eagle.flash.4m2m.ld -> 2 MiB.
LAYOUT_END = {"eagle.flash.4m1m.ld": 3 * 1024 * 1024,
              "eagle.flash.4m2m.ld": 2 * 1024 * 1024}


class PreflightError(ValueError):
    pass


def round_sector(length: int) -> int:
    return (length + SINGLE_SECTOR - 1) & ~(SINGLE_SECTOR - 1)


def inspect_image(image: bytes, name: str) -> dict:
    if len(image) < 8 or image[0] != 0xE9 or not 1 <= image[1] <= 16:
        raise PreflightError(f"{name}: invalid ESP8266 application magic/segment count")
    mode = SPI_MODES.get(image[2])
    flash_flag = image[3] >> 4
    flash_data = SIZE_FLAGS.get(flash_flag)
    clock = FREQUENCY.get(image[3] & 15)
    if mode is None or flash_data is None or clock is None:
        raise PreflightError(f"{name}: unsupported ESP8266 header mode/flash size/frequency")
    if len(image) < 64_000 or len(image) > 1_044_464:
        raise PreflightError(f"{name}: unexpected application file size {len(image)}")
    return {
        "name": name,
        "size_bytes": len(image),
        "sha256": hashlib.sha256(image).hexdigest(),
        "md5_for_arduino_updater": hashlib.md5(image, usedforsecurity=False).hexdigest(),
        "segments": image[1],
        "flash_mode": mode,
        "flash_size_flag": flash_data[0],
        "flash_size_bytes_from_header": flash_data[1],
        "flash_frequency": clock,
        "entry_address": f"0x{int.from_bytes(image[4:8], 'little'):08X}",
    }


def platformio_layout(path: Path, environment: str) -> tuple[str, int]:
    parser = configparser.ConfigParser(interpolation=None)
    with Path(path).open(encoding="utf-8") as source:
        parser.read_file(source)
    if environment not in parser:
        raise PreflightError(f"PlatformIO env missing: {environment}")
    section = parser[environment]
    if section.get("board") != "esp12e" or section.get("board_build.flash_size") != "4MB":
        raise PreflightError(f"{environment}: unexpected board or physical size setting")
    if section.get("board_build.flash_mode") != "dio":
        raise PreflightError(f"{environment}: expected DIO flash mode")
    ld = section.get("board_build.ldscript", "")
    if ld not in LAYOUT_END:
        raise PreflightError(f"{environment}: unreviewed flash map {ld}")
    return ld, LAYOUT_END[ld]


def staging_model(current_bytes: int, incoming_bytes: int, flash_end: int) -> dict:
    current_rounded = round_sector(current_bytes)
    incoming_rounded = round_sector(incoming_bytes)
    stage_start = flash_end - incoming_rounded
    return {
        "current_rounded": current_rounded,
        "incoming_rounded": incoming_rounded,
        "OTA_staging_end": f"0x{flash_end:06X}",
        "OTA_staging_start": f"0x{stage_start:06X}",
        "nominal_no_overlap": stage_start >= current_rounded and stage_start >= 0,
        "free_gap_bytes": stage_start - current_rounded,
        "caveat": "Arithmetic only; live ESP.getFreeSketchSpace(), Update.begin(), flash ID and actual stock layout not measured",
    }


def evaluate(official_zip: Path, manifest: Path, loader: Path, candidate: Path,
             loader_ini: Path, candidate_ini: Path) -> dict:
    metadata = verify_archive(official_zip, manifest)
    with zipfile.ZipFile(official_zip) as archive:
        oem_image = archive.read(metadata["firmware_member"])
    oem = inspect_image(oem_image, "official_Ultra_V9.0.44")
    loader_bytes = Path(loader).read_bytes()
    candidate_bytes = Path(candidate).read_bytes()
    first = inspect_image(loader_bytes, "experimental_shino_loader")
    second = inspect_image(candidate_bytes, "shino_candidate")
    if oem["md5_for_arduino_updater"].encode("ascii") not in candidate_bytes:
        raise PreflightError("SHINO application lacks its own exact compiled OEM factory-return digest")
    # A smaller BIN alone must never authorize the old full-app startup:
    # require the actual application to embed the conservatively linked mode.
    if b"FIRST_BOOT_BRIDGE" not in candidate_bytes:
        raise PreflightError("SHINO application is not the approved conservative first-boot bridge image")
    if oem["size_bytes"] != OEM_SIZE:
        raise PreflightError("OEM V9.0.44 image size changed")
    if first["size_bytes"] > COMMUNITY_LOADER_COMPARISON:
        raise PreflightError("Loader larger than independently documented comparison loader")
    if first["flash_mode"] != "DIO" or second["flash_mode"] != "DIO":
        raise PreflightError("Our loader and candidate must be compiled for DIO")
    if first["flash_size_bytes_from_header"] != FOUR_MB or second["flash_size_bytes_from_header"] != FOUR_MB:
        raise PreflightError("Our images must announce a 4-MiB ESP8266 flash")
    # Critical: the read-only loader cannot do the second hop. Its binary
    # must actually contain the pinned OEM image MD5 in compiled upload logic.
    if oem["md5_for_arduino_updater"].encode("ascii") not in Path(loader).read_bytes():
        raise PreflightError("Experimental loader lacks the pinned OEM image digest (read-only/wrong build?)")
    if second["md5_for_arduino_updater"].encode("ascii") not in Path(loader).read_bytes():
        raise PreflightError("Experimental loader lacks exact compiled candidate digest")
    loader_layout, loader_end = platformio_layout(loader_ini, "env:esp12e_recovery")
    shino_layout, shino_end = platformio_layout(candidate_ini, "env:esp12e")
    if loader_layout != "eagle.flash.4m1m.ld" or shino_layout != "eagle.flash.4m2m.ld":
        raise PreflightError("Unexpected source layout for staged SHINO update")
    into_shino = staging_model(first["size_bytes"], second["size_bytes"], loader_end)
    into_oem = staging_model(second["size_bytes"], oem["size_bytes"], shino_end)
    if not into_shino["nominal_no_overlap"] or not into_oem["nominal_no_overlap"]:
        raise PreflightError("Modeled OTA sketch space overlaps; do not prepare a physical install")

    return {
        "status": "OFFLINE_PREFLIGHT_ONLY__OWNER_FLASH_NOT_AUTHORIZED",
        "manufacturer_package_sha256_verified": metadata["zip_sha256"],
        "images": [oem, first, second],
        "source_layouts": {
            "loader": loader_layout, "candidate": shino_layout,
            "OEM_internal_FS_layout": "UNKNOWN_FROM_APPLICATION_IMAGE_ALONE",
        },
        "transitions": {
            "factory_to_loader": {
                "loader_bytes": first["size_bytes"],
                "below_public_community_loader_benchmark": first["size_bytes"] <= COMMUNITY_LOADER_COMPARISON,
                "actual_owner_factory_OTA_available_bytes": "NOT MEASURED",
                "acceptance_by_owner_V9_0_44": "UNKNOWN__DO_NOT_ASSUME",
            },
            "loader_to_shino": into_shino,
            "shino_to_factory": into_oem,
        },
        "still_unproven": [
            "Owner actual physical flash ID/capacity and OEM free OTA slot size",
            "Conservative first-boot bridge runtime boot/display/AP/auth not physically verified",
            "Current owner's OTA handler accepting custom loader application",
            "Loader booting, WPA2 AP, authentication and tested upload on owner board",
            "OEM filesystem/data layout after changing from SHINO 4m2m map",
            "First-boot bridge does not mount or migrate stock FS or initialize EEPROM; no full dashboard in this build",
            "A nonbooting SHINO/loader cannot be recovered via this transient Wi-Fi trampoline",
            "End-to-end restore and power-interruption behavior cannot be proven via CI",
        ],
        "device_access_performed": False,
        "permission_to_flash": False,
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--official-zip", required=True, type=Path)
    parser.add_argument("--manifest", required=True, type=Path)
    parser.add_argument("--loader", required=True, type=Path)
    parser.add_argument("--candidate", required=True, type=Path)
    parser.add_argument("--loader-ini", required=True, type=Path)
    parser.add_argument("--candidate-ini", required=True, type=Path)
    args = parser.parse_args()
    try:
        report = evaluate(args.official_zip, args.manifest, args.loader, args.candidate,
                          args.loader_ini, args.candidate_ini)
    except (FactoryOtaError, PreflightError, OSError, ValueError, KeyError, configparser.Error) as err:
        parser.exit(1, f"OFFLINE PREFLIGHT FAILED: {err}\n")
    print(json.dumps(report, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
