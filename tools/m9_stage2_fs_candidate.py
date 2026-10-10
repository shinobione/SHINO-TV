#!/usr/bin/env python3
"""Phase F local LittleFS inventory/image inspection; no device executor."""
from __future__ import annotations

import argparse
import hashlib
import importlib.metadata
import json
import os
import re
import stat
from configparser import ConfigParser
from pathlib import Path

from verify_fs_provisioning import check_platformio, EXPECTED_BLANK_CONFIG

FS_START, FS_END, FLASH_END = 0x200000, 0x3FA000, 0x400000
FS_BYTES = FS_END - FS_START
SECTOR, FS_BLOCK, FS_PAGE = 4096, 8192, 256
ENVIRONMENT = "env:esp12e_m9_4m2m"
MANIFEST = Path(__file__).with_name("m9_stage2_sources.json")
SOURCE_EPOCH = 1704067200  # build-source metadata only, never device time
FORBIDDEN = (b"/api/v1/ota/fw", b"/api/v1/ota/fs", b"/legacyupdate",
             b"otaUploadHandler(", b"firmware/data/config.json")


class Stage2Error(ValueError):
    """Offline gate closed; physical authorization is never granted."""


def local_path(path: Path, *, directory: bool = False) -> Path:
    path = Path(path)
    if str(path).startswith(("\\\\", "//")):
        raise Stage2Error("Network/device paths are not accepted")
    for part in (path.absolute(), *path.absolute().parents):
        info = part.lstat()
        if part.is_symlink() or getattr(info, "st_file_attributes", 0) & 0x400:
            raise Stage2Error("Symlink/reparse paths are not accepted")
    mode = path.lstat().st_mode
    if not (stat.S_ISDIR(mode) if directory else stat.S_ISREG(mode)):
        raise Stage2Error("Regular local file/directory required")
    return path


def exact_image(path: Path, expected_sha256: str) -> bytes:
    if not re.fullmatch(r"[0-9a-fA-F]{64}", expected_sha256):
        raise Stage2Error("External SHA-256 must be 64 hexadecimal characters")
    path = local_path(path)
    if path.stat().st_size != FS_BYTES:
        raise Stage2Error("FS image must be exactly 2072576 bytes")
    data = path.read_bytes()
    if len(data) != FS_BYTES or hashlib.sha256(data).hexdigest() != expected_sha256.lower():
        raise Stage2Error("Frozen FS SHA-256 mismatch or file changed")
    return data


def geometry(ini: Path) -> dict:
    check_platformio(local_path(ini), ENVIRONMENT)
    config = ConfigParser(interpolation=None)
    config.read(ini, encoding="utf-8")
    base, selected = config["env:esp12e"], config[ENVIRONMENT]
    if (config["platformio"].get("default_envs") != "esp12e"
            or selected.get("extends") != "env:esp12e"
            or selected.get("platform", base.get("platform")) != "espressif8266@4.2.1"
            or selected.get("platform_packages", base.get("platform_packages", "")).strip()
            != "platformio/framework-arduinoespressif8266@3.30102.0"):
        raise Stage2Error("Pinned platform/Core or reviewed inheritance changed")
    return {"environment": ENVIRONMENT, "target": FS_START,
            "end_exclusive": FS_END, "image_bytes": FS_BYTES,
            "erase_start": FS_START, "erase_end_inclusive": FS_END - 1,
            "sector_bytes": SECTOR, "sector_count": FS_BYTES // SECTOR,
            "fs_block_bytes": FS_BLOCK, "fs_page_bytes": FS_PAGE,
            "lower_protected_bytes": FS_START, "tail_protected_bytes": FLASH_END - FS_END,
            "flash_end_exclusive": FLASH_END}


def reviewed_source(root: Path) -> dict[str, bytes]:
    root = local_path(root, directory=True)
    manifest = json.loads(local_path(MANIFEST).read_text(encoding="utf-8"))
    if manifest["schema"] != 1 or manifest["blank_config"] != EXPECTED_BLANK_CONFIG:
        raise Stage2Error("Reviewed source manifest changed")
    expected = manifest["assets"]
    files: dict[str, bytes] = {}
    allowed_dirs = {"web", "web/css", "web/js"}
    for path in sorted(root.rglob("*")):
        relative = path.relative_to(root).as_posix()
        if path.is_dir():
            local_path(path, directory=True)
            if relative not in allowed_dirs:
                raise Stage2Error("Unreviewed source directory")
            continue
        local_path(path)
        if relative != "config.json" and relative not in expected:
            raise Stage2Error("Unreviewed/private asset")
        if path.stat().st_size > (4096 if relative == "config.json" else 200_000):
            raise Stage2Error("Unreviewed oversized asset")
        body = path.read_bytes().replace(b"\r\n", b"\n")
        if relative == "config.json":
            config = json.loads(body)
            if (type(config) is not dict or config != EXPECTED_BLANK_CONFIG
                    or any(type(config[k]) is not type(v) for k, v in EXPECTED_BLANK_CONFIG.items())):
                raise Stage2Error("Seed config must contain only blank non-secret defaults")
            continue
        if relative not in expected or len(body) > 200_000:
            raise Stage2Error("Unreviewed/private/oversized asset")
        body.decode("utf-8")
        pin = expected[relative]
        if len(body) != pin["bytes_lf"] or hashlib.sha256(body).hexdigest() != pin["sha256_lf"]:
            raise Stage2Error("Reviewed asset changed; secrets/routes require re-review")
        if any(token in body for token in FORBIDDEN):
            raise Stage2Error("Generic updater artifact is forbidden")
        files[relative] = body
    if set(files) != set(expected) or "web/index.html" not in files:
        raise Stage2Error("Reviewed source inventory is incomplete")
    files["config.json"] = (json.dumps(EXPECTED_BLANK_CONFIG, sort_keys=True, indent=2) + "\n").encode()
    return files


def prepare_source(root: Path, output: Path, ini: Path) -> dict:
    """Create a new LOCAL build tree; never changes firmware/data or an image."""
    layout, files = geometry(ini), reviewed_source(root)
    output = Path(output)
    local_path(output.parent, directory=True)
    output.mkdir()  # fail on existing tree; never overwrite a prior package
    for name, body in sorted(files.items()):
        target = output / name
        target.parent.mkdir(parents=True, exist_ok=True)
        with target.open("xb") as handle:
            handle.write(body)
        os.utime(target, (SOURCE_EPOCH, SOURCE_EPOCH))
    for directory in sorted((p for p in output.rglob("*") if p.is_dir()), reverse=True):
        os.utime(directory, (SOURCE_EPOCH, SOURCE_EPOCH))
    os.utime(output, (SOURCE_EPOCH, SOURCE_EPOCH))
    return {"status": "PASS_LOCAL_REVIEWED_BUILD_SOURCE", "files": len(files),
            "source_bytes": sum(map(len, files.values())), "geometry": layout,
            "physical_authorization": False, "device_contacts": 0}


def inspect_contents(data: bytes, expected: dict[str, bytes]) -> dict:
    # The library's default mount=True autoformats on failure. NEVER use it.
    if importlib.metadata.version("littlefs-python") != "0.15.0":
        raise Stage2Error("Pinned littlefs-python 0.15.0 parser required")
    from littlefs import LittleFS

    class ReadOnlyMemory:
        def __init__(self):
            self.write_attempted = False

        def read(self, cfg, block, off, size):
            start = block * cfg.block_size + off
            if start < 0 or start + size > len(data):
                raise Stage2Error("Parser read outside image")
            return bytearray(data[start:start + size])

        def prog(self, *args):
            self.write_attempted = True
            return -5

        erase = prog

        def sync(self, *args):
            return 0

    context = ReadOnlyMemory()
    fs = LittleFS(context=context, mount=False, block_size=FS_BLOCK,
                  block_count=FS_BYTES // FS_BLOCK, read_size=FS_PAGE,
                  prog_size=FS_PAGE, cache_size=FS_PAGE, lookahead_size=32)
    mounted = False
    try:
        fs.mount()
        mounted = True
        if fs.block_count != FS_BYTES // FS_BLOCK:
            raise Stage2Error("LittleFS superblock geometry differs")
        dirs = {"/", "/web", "/web/css", "/web/js"}
        found = {}
        seen_dirs = {"/"}
        for directory in sorted(dirs):
            count = 0
            for entry in fs.scandir(directory):
                count += 1
                if count > len(expected) + len(dirs):
                    raise Stage2Error("Unexpected image inventory")
                name = directory.rstrip("/") + "/" + entry.name
                if entry.type == 2 and name in dirs:
                    seen_dirs.add(name)
                elif entry.type == 1 and name.lstrip("/") in expected:
                    key = name.lstrip("/")
                    if entry.size != len(expected[key]):
                        raise Stage2Error("Packaged file size differs")
                    with fs.open(name, "rb") as handle:
                        content = handle.read(len(expected[key]) + 1)
                    if content != expected[key]:
                        raise Stage2Error("Packaged file differs from reviewed source")
                    found[key] = hashlib.sha256(content).hexdigest()
                else:
                    raise Stage2Error("Unreviewed/private entry in image")
        if set(found) != set(expected) or seen_dirs != dirs or context.write_attempted:
            raise Stage2Error("Image inventory incomplete or parser attempted a write")
        return {"image_inventory_exact": True, "image_file_count": len(found),
                "parser": "littlefs-python==0.15.0", "parser_autoformat": False,
                "parser_backing": "READ_ONLY_MEMORY", "parser_writes": 0,
                "reviewed_file_sha256": found}
    except Stage2Error:
        raise
    except Exception as exc:
        raise Stage2Error("Independent LittleFS parsing failed") from exc
    finally:
        if mounted:
            fs.unmount()


def inspect(image: Path, expected_sha256: str, source_root: Path, ini: Path) -> dict:
    layout = geometry(ini)
    files = reviewed_source(source_root)
    data = exact_image(image, expected_sha256)
    contents = inspect_contents(data, files)
    return {"status": "PASS_OFFLINE_STAGE2_PACKAGE_PHYSICAL_HOLD",
            "STAGE2_IMAGE_FREEZE_GATE": "PASS_OFFLINE_EXACT_FILE_ONLY",
            "geometry": layout, "image_sha256": hashlib.sha256(data).hexdigest(),
            "image_md5": hashlib.md5(data, usedforsecurity=False).hexdigest(),
            **contents, "device_contacts": 0, "serial_io": 0, "flash_writes": 0,
            "device_filesystem_writes": 0, "reboots": 0, "physical_authorization": False,
            "stage2_physical_write": "HOLD", "stage2_runtime": "NOT_RUN"}


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    group = parser.add_mutually_exclusive_group(required=True)
    group.add_argument("--image", type=Path)
    group.add_argument("--prepare-source", type=Path)
    parser.add_argument("--expected-sha256")
    parser.add_argument("--source-root", type=Path, default=Path("firmware/data"))
    parser.add_argument("--platformio", type=Path, default=Path("firmware/platformio.ini"))
    args = parser.parse_args()
    try:
        if args.prepare_source:
            result = prepare_source(args.source_root, args.prepare_source, args.platformio)
        else:
            if not args.expected_sha256:
                raise Stage2Error("External frozen SHA-256 required")
            result = inspect(args.image, args.expected_sha256, args.source_root, args.platformio)
    except (ValueError, OSError, KeyError, importlib.metadata.PackageNotFoundError) as exc:
        parser.exit(1, f"STAGE2 PACKAGE GATE CLOSED: {exc}\n")
    print(json.dumps(result, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
