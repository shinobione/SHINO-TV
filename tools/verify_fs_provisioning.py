#!/usr/bin/env python3
"""Offline-only LittleFS package inspection for SHINO 4m2m; never uploads.

ESP8266 Arduino Updater U_FS without ATOMIC_FS_UPDATE erases and writes the
*active* FS from the first sector. SHA-256 is independently checked on the PC
before any separately authorized real-world provisioning. An app-only OEM
rollback CANNOT recover overwritten stock assets or the original filesystem.
"""
from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
import re
from configparser import ConfigParser

FLASH_BYTES = 0x400000
SHINO_FS_START = 0x200000
SHINO_FS_END = 0x3FA000
OEM_INFERRED_FS_START = 0x100000
SHINO_FS_BYTES = SHINO_FS_END - SHINO_FS_START
SECTOR_BYTES = 4096
DISALLOWED_ASSET_SNIPPETS = (
    b"/api/v1/ota/fw", b"/api/v1/ota/fs", b"/legacyupdate",
    b"otaUploadHandler(", b"firmware/data/config.json",
)
EXPECTED_BLANK_CONFIG = {
    "wifi_ssid": "", "wifi_password": "", "api_token": "", "lcd_rotation": 0,
}


class FsInspectionError(ValueError):
    pass


def validate_source(root: Path) -> dict:
    root = Path(root)
    if not root.is_dir() or root.is_symlink():
        raise FsInspectionError("LittleFS source root is absent or is a symlink")
    files = []
    for path in sorted(root.rglob("*")):
        if path.is_symlink():
            raise FsInspectionError("Symlinks in LittleFS source tree are not accepted")
        if not path.is_file():
            continue
        relative = path.relative_to(root).as_posix()
        if relative == "config.json":
            try:
                config = json.loads(path.read_text(encoding="utf-8"))
            except (UnicodeError, json.JSONDecodeError) as exc:
                raise FsInspectionError("Invalid blank build-only config.json") from exc
            if type(config) is not dict or config != EXPECTED_BLANK_CONFIG:
                raise FsInspectionError("Build-only config.json must contain no credentials or other settings")
        elif not re.fullmatch(r"web/(?:[a-zA-Z0-9_-]+\.html|css/[a-zA-Z0-9_-]+\.css|js/[a-zA-Z0-9_-]+\.js)", relative):
            raise FsInspectionError("Unreviewed or private file in LittleFS source tree")
        if relative == "web/js/otaUploadHandler.js":
            raise FsInspectionError("Legacy arbitrary-OTA JavaScript must not be packaged")
        body = path.read_bytes()
        if len(body) > 200_000:
            raise FsInspectionError("Unexpected oversized web asset")
        if any(fragment in body for fragment in DISALLOWED_ASSET_SNIPPETS):
            raise FsInspectionError("A legacy arbitrary-update reference remains in LittleFS assets")
        files.append({
            "path": relative,
            "bytes": len(body),
            "sha256": hashlib.sha256(body).hexdigest(),
        })
    if not files or not any(f["path"] == "web/index.html" for f in files):
        raise FsInspectionError("Missing essential first-party web asset")
    return {"source_files": files, "source_file_count": len(files)}


def check_platformio(path: Path) -> None:
    cfg = ConfigParser(interpolation=None)
    with Path(path).open(encoding="utf-8") as source:
        cfg.read_file(source)
    section = cfg["env:esp12e"] if "env:esp12e" in cfg else {}
    required = {
        "board": "esp12e",
        "board_build.flash_size": "4MB",
        "board_build.flash_mode": "dio",
        "board_build.filesystem": "littlefs",
        "board_build.ldscript": "eagle.flash.4m2m.ld",
    }
    for key, expected in required.items():
        if section.get(key) != expected:
            raise FsInspectionError(f"Unreviewed PlatformIO filesystem geometry: {key}")


def inspect(image_path: Path, source_root: Path, ini_path: Path) -> dict:
    check_platformio(ini_path)
    source = validate_source(source_root)
    image = Path(image_path)
    if not image.is_file() or image.is_symlink():
        raise FsInspectionError("Expected regular local LittleFS image file")
    if image.stat().st_size != SHINO_FS_BYTES:
        raise FsInspectionError(f"Wrong LittleFS image length; expected exactly {SHINO_FS_BYTES} bytes")
    body = image.read_bytes()
    # The raw filesystem image is not an ESP8266 0xE9 application image.
    sha = hashlib.sha256(body).hexdigest()
    md5 = hashlib.md5(body, usedforsecurity=False).hexdigest()
    stage_address_atomic = SHINO_FS_START - SHINO_FS_BYTES
    assert stage_address_atomic == 0x6000
    return {
        "status": "OFFLINE_IMAGE_INTEGRITY_ONLY__FS_WRITER_NOT_AUTHORIZED",
        "image_bytes": len(body),
        "image_sha256": sha,
        "image_md5_for_esp8266_updater": md5,
        "flash_total_bytes_assumed": FLASH_BYTES,
        "new_shino_littlefs_start": f"0x{SHINO_FS_START:06x}",
        "new_shino_littlefs_end_exclusive": f"0x{SHINO_FS_END:06x}",
        "old_stock_filesystem_start_inferred_NOT_PROVEN": f"0x{OEM_INFERRED_FS_START:06x}",
        "old_stock_filesystem_end_inferred_NOT_PROVEN": f"0x{SHINO_FS_END:06x}",
        "shino_fs_overlaps_inferred_stock_bytes": SHINO_FS_BYTES,
        "shino_fs_occupies_stock_suffix": True,
        "non_atomic_esp8266_U_FS_writes_active_FS_in_place": True,
        "full_fs_atomic_staging_candidate_start": f"0x{stage_address_atomic:06x}",
        "full_fs_atomic_staging_can_coexist_with_running_bridge": False,
        "incorrect_or_interrupted_stream_can_erase_original_data_BEFORE_MD5_check": True,
        "OEM_application_OTA_zip_cannot_restore_stock_filesystem": True,
        "first_boot_migration_writer_compiled": False,
        "device_read_or_upload_performed": False,
        "owner_FS_migration_permission": False,
        **source,
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--image", required=True, type=Path)
    parser.add_argument("--source-root", default=Path("firmware/data"), type=Path)
    parser.add_argument("--platformio", default=Path("firmware/platformio.ini"), type=Path)
    parser.add_argument("--out", type=Path, help="New local JSON report; existing files are not overwritten")
    args = parser.parse_args()
    try:
        result = inspect(args.image, args.source_root, args.platformio)
        message = json.dumps(result, indent=2) + "\n"
        if args.out:
            with args.out.open("x", encoding="utf-8") as dest:
                dest.write(message)
            print(f"OFFLINE-only inspection saved: {args.out}")
        else:
            print(message, end="")
    except (FsInspectionError, OSError, ValueError, KeyError) as exc:
        parser.exit(1, f"LITTLEFS PROVISIONING GATE CLOSED: {exc}\n")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
