#!/usr/bin/env python3
"""Offline geometry comparison, not an OTA-slot measurement or flash permission.

The 4-MB linker values are copied from esp8266/Arduino at pinned commit
1475ed7d49fef5c5167061ac76abb6eced9abda5.
Released BIN sizes are release asset byte counts, not old CI link flash usage.
"""
from __future__ import annotations
import argparse
import json
from pathlib import Path

SECTOR = 4096
FLASH_BYTES = 0x400000
FS_END = 0x3FA000
LAYOUTS = {"4m3m": 0x100000, "4m2m": 0x200000, "4m1m": 0x300000}
IMAGE_BYTES = {
    "official_Ultra_V9_0_44": 494144,
    "Times_Z_v1_5_0": 445696,
    "smalltv_mod_v2_16_0": 780352,
    "smalltv_mod_lean_v2_16_0": 654464,
    "smalltv_mod_loader_v2_16_0": 315920,
    "SHINO_loader_CI_36267887773": 312256,
    "SHINO_experimental_CI_36267887773": 456960,
    "SHINO_default_CI_36267887778": 453296,
}
OEM_IMAGE = "official_Ultra_V9_0_44"


def rounded(length: int) -> int:
    return ((length + SECTOR - 1) // SECTOR) * SECTOR


def compare(observed_storage_total: int, images: dict[str, int] | None = None) -> dict:
    if type(observed_storage_total) is not int or observed_storage_total <= 0:
        raise ValueError("observed_storage_total must be a positive integer")
    sizes = images if images is not None else IMAGE_BYTES
    if not sizes or OEM_IMAGE not in sizes or any(type(n) is not int or n <= 0 for n in sizes.values()):
        raise ValueError("Invalid image-size snapshot")
    candidates = []
    for name, first_sector in LAYOUTS.items():
        fs_size = FS_END - first_sector
        candidates.append({
            "name": name,
            "filesystem_start": f"0x{first_sector:06x}",
            "filesystem_end": f"0x{FS_END:06x}",
            "filesystem_bytes": fs_size,
            "matches_observed_total_exactly": fs_size == observed_storage_total,
        })
    hypothesized_oem = sizes[OEM_IMAGE]
    modeled_free = LAYOUTS["4m3m"] - rounded(hypothesized_oem)
    if modeled_free <= 0:
        raise ValueError("Invalid hypothetical stock application geometry")
    return {
        "physical_flash_bytes_assumed": FLASH_BYTES,
        "observed_photo_gif_storage_bytes": observed_storage_total,
        "matching_linker_layouts": [x["name"] for x in candidates if x["matches_observed_total_exactly"]],
        "source_linker_layouts": candidates,
        "assumptions_not_measurements": [
            "The manufacturer uses the observed-identical Arduino 4m3m FS boundaries.",
            "Stock update follows ESP8266 Arduino getFreeSketchSpace() and the running sketch length approximates the OEM OTA BIN byte count.",
            "Actual stock updater code, flash operations and acceptance were not exercised.",
        ],
        "modeled_stock_free_sketch_bytes_NOT_measured": modeled_free,
        "image_comparison": [{
            "image": label,
            "bytes": length,
            "rounded_to_sector": rounded(length),
            "difference_to_nominal_512_KiB_slot": 524288 - length,
            "modeled_4m3m_free_sketch_fit": rounded(length) <= modeled_free,
            "device_upload_tested": False,
        } for label, length in sizes.items()],
        "stock_OTA_capacity_proven": False,
        "manufacturer_full_flash_backup_available": False,
        "OEM_FS_preserved_after_layout_switch_proven": False,
        "permission_to_flash": False,
    }


def report_total(report: dict) -> int:
    if report.get("tool") != "SHINO-TV_stock_V9.0.44_readonly_audit":
        raise ValueError("Unexpected report type")
    try:
        data = report["observations"]["/space.json"]
        if data["status"] != "observed":
            raise ValueError("No valid /space.json observation")
        if data["data"].get("storage_kind") != "images_and_gifs_filesystem_NOT_OTA_slot":
            raise ValueError("Reported storage type not recognized")
        total = data["data"]["total_bytes"]
    except (KeyError, TypeError):
        raise ValueError("Missing safe /space.json projection") from None
    if type(total) is not int or total <= 0:
        raise ValueError("Invalid filesystem size in report")
    return total


def main() -> int:
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--stock-report", type=Path,
                   help="Optional locally sanitized read-only report; no raw device response required")
    args = p.parse_args()
    observed_total = 3121152  # Owner's sanitized snapshot as of 2026-09-26; not a firmware parameter.
    if args.stock_report:
        observed_total = report_total(json.loads(args.stock_report.read_text(encoding="utf-8")))
    print(json.dumps(compare(observed_total), indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
