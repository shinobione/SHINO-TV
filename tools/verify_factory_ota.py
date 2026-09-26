#!/usr/bin/env python3
"""Offline verify a pinned OEM application OTA ZIP. This never flashes or uploads.

Manufacturer image is fetched only transiently in CI from its pinned original
Git commit. Commit hashes/metadata only, never third-party binary payloads.
"""
from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path, PurePosixPath
import zipfile


class FactoryOtaError(ValueError):
    pass


def inspect_archive(path: Path) -> dict:
    path = Path(path)
    archive_size = path.stat().st_size
    if not 10_000 <= archive_size <= 2_000_000:
        raise FactoryOtaError(f"Unexpected ZIP size: {archive_size} bytes")
    archive_digest = hashlib.sha256(path.read_bytes()).hexdigest()
    try:
        with zipfile.ZipFile(path) as z:
            members = z.infolist()
            if not 1 <= len(members) <= 50:
                raise FactoryOtaError("Unexpected ZIP member count")
            names = set()
            bins = []
            total_uncompressed = 0
            for entry in members:
                name = entry.filename
                normalized = PurePosixPath(name)
                if (name.startswith("/") or "\\" in name or
                        normalized.is_absolute() or ".." in normalized.parts or
                        not name or name in names):
                    raise FactoryOtaError("Unsafe or duplicate ZIP member path")
                names.add(name)
                if entry.flag_bits & 1:
                    raise FactoryOtaError("Encrypted ZIP members not accepted")
                if (entry.external_attr >> 16) & 0o170000 == 0o120000:
                    raise FactoryOtaError("Symlink ZIP member not accepted")
                total_uncompressed += entry.file_size
                if total_uncompressed > 8_000_000:
                    raise FactoryOtaError("ZIP expanded content too large")
                if not entry.is_dir() and normalized.suffix.lower() == ".bin":
                    bins.append(entry)
            if len(bins) != 1:
                raise FactoryOtaError(f"Expected exactly one firmware BIN, found {len(bins)}")
            firmware = bins[0]
            if not 64_000 <= firmware.file_size <= 1_200_000:
                raise FactoryOtaError("Unexpected OEM application BIN size")
            image = z.read(firmware)
    except (zipfile.BadZipFile, RuntimeError, EOFError, OSError) as exc:
        raise FactoryOtaError(f"Invalid archive: {exc}") from exc

    if len(image) != firmware.file_size:
        raise FactoryOtaError("Truncated firmware member")
    if len(image) < 8 or image[0] != 0xE9 or not 1 <= image[1] <= 16:
        raise FactoryOtaError("Not a plausible ESP8266 0xE9 application image")
    return {
        "zip_bytes": archive_size,
        "zip_sha256": archive_digest,
        "firmware_member": firmware.filename,
        "firmware_bytes": len(image),
        "firmware_sha256": hashlib.sha256(image).hexdigest(),
        "firmware_magic": "0xE9",
        "firmware_segments": image[1],
        "recovery_scope": "OEM application OTA only: NOT a complete flash backup or guaranteed brick recovery",
    }


def verify_archive(path: Path, manifest_path: Path) -> dict:
    actual = inspect_archive(path)
    manifest = json.loads(Path(manifest_path).read_text(encoding="utf-8"))
    fields = (
        "zip_bytes", "zip_sha256", "firmware_member", "firmware_bytes",
        "firmware_sha256", "firmware_magic", "firmware_segments",
    )
    for key in fields:
        if key not in manifest or manifest[key] != actual[key]:
            raise FactoryOtaError(f"PIN MISMATCH for {key}: OEM OTA reference must not change silently")
    return actual


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--inspect", action="store_true", help="Print nonbinary metadata for an initial pin")
    parser.add_argument("--manifest", type=Path, help="Require exact known checksum and member metadata")
    parser.add_argument("archive", type=Path, help="Local OEM ZIP; never writes or uploads it")
    args = parser.parse_args()
    if not (args.inspect or args.manifest) or (args.inspect and args.manifest):
        parser.error("Choose --inspect for initial audit OR --manifest for strict verification")
    try:
        result = inspect_archive(args.archive) if args.inspect else verify_archive(args.archive, args.manifest)
    except (FactoryOtaError, OSError, ValueError, KeyError) as exc:
        parser.exit(1, f"OEM OTA GATE CLOSED: {exc}\n")
    print(json.dumps(result, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
