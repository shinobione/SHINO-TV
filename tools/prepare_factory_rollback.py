#!/usr/bin/env python3
"""Prepare an offline, verified factory rollback BIN from the OEM V9.0.44 ZIP.

This is a LOCAL extraction only. It never communicates with any SmallTV.
The output is NOT a full-flash backup, nor a brick-proof restore image.
"""
from __future__ import annotations

import argparse
import hashlib
from pathlib import Path
import zipfile

from verify_factory_ota import FactoryOtaError, verify_archive


def prepare_factory_bin(archive: Path, manifest: Path, destination: Path) -> dict:
    metadata = verify_archive(Path(archive), Path(manifest))
    target = Path(destination)
    if target.suffix.lower() != ".bin":
        raise FactoryOtaError("Destination must end with .bin")
    if target.exists():
        raise FactoryOtaError("Refusing to overwrite an existing recovery file")
    if not target.parent.is_dir():
        raise FactoryOtaError("Destination directory must already exist")
    with zipfile.ZipFile(archive) as z:
        image = z.read(metadata["firmware_member"])
    if hashlib.sha256(image).hexdigest() != metadata["firmware_sha256"]:
        raise FactoryOtaError("Inner image SHA-256 changed before extraction")
    try:
        with target.open("xb") as out:
            out.write(image)
    except BaseException:
        if target.exists():
            target.unlink()
        raise
    return {
        "file": str(target),
        "bytes": len(image),
        "sha256": hashlib.sha256(image).hexdigest(),
        "scope": "Verified GeekMagic application OTA BIN, not full factory flash",
        "device_communication": "none",
    }


def main() -> int:
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("archive", type=Path, help="Original V9.0.44 ZIP downloaded from pinned OEM commit")
    p.add_argument("--manifest", type=Path, default=Path(__file__).resolve().parent.parent /
                   "recovery" / "factory_ota_v9_0_44.json")
    p.add_argument("--out", type=Path, required=True, help="Write verified .bin to a local folder outside Git")
    args = p.parse_args()
    try:
        report = prepare_factory_bin(args.archive, args.manifest, args.out)
    except (FactoryOtaError, OSError, ValueError, KeyError) as exc:
        p.exit(1, f"RECOVERY PREPARATION FAILED: {exc}\n")
    print(f"Verified local application image: {report['file']}")
    print(f"Bytes: {report['bytes']}; SHA-256: {report['sha256']}")
    print("NO DEVICE ACTION TAKEN. This is not a full flash backup or bootloader recovery.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
