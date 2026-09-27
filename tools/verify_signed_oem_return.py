#!/usr/bin/env python3
"""OFFLINE signed-and-exact-OEM return verifier; not a device uploader.

Required trust sources are independent:
(1) original manufacturer's ZIP checked against repo-pinned metadata, and
(2) owner's separately pinned RSA-2048 signing public PEM SHA-256.
The signed transport must contain BYTE-FOR-BYTE the exact OEM application.
A passing result never grants permission to flash. No private signing key is
read/generated here. No device/IP/network access exists.
"""
from __future__ import annotations

import argparse
import hashlib
import hmac
import json
from pathlib import Path
import struct
import subprocess
import tempfile
import zipfile

from verify_factory_ota import FactoryOtaError, verify_archive
from verify_signed_ota_package import (
    SIGNATURE_BYTES, SignedPackageError, _checked_file, _digest_argument,
    _digest_file,
)
from wifi_flash_preflight import (
    FOUR_MB, PreflightError, inspect_image, platformio_layout, round_sector,
    staging_model, inferred_stock_fs_staging_overlap,
)

OEM_BYTES = 494144
SIGNATURE_TRAILER_BYTES = SIGNATURE_BYTES + 4
SIGNED_OEM_BYTES = OEM_BYTES + SIGNATURE_TRAILER_BYTES
OTA_END = 0x100000
SECTOR = 4096


class SignedOemReturnError(ValueError):
    pass


def assess_signed_oem(
    package: Path, owner_public_key: Path, manufacturer_zip: Path, pinned_manifest: Path,
    *, expected_owner_public_key_sha256: str,
    current_sketch_bytes: int, reported_free_sketch_bytes: int,
    observed_physical_flash_bytes: int, platformio_ini: Path,
    openssl: str = "openssl",
) -> dict:
    """Verify both independent trust conditions, never contact any device."""
    try:
        expected_key = _digest_argument(
            expected_owner_public_key_sha256, "owner public signing key")
        pub = _checked_file(owner_public_key, max_bytes=8192, label="Owner public PEM")
        signed = _checked_file(package, max_bytes=SIGNED_OEM_BYTES,
                               label="Signed exact-OEM return")
    except SignedPackageError as exc:
        raise SignedOemReturnError(str(exc)) from exc
    if not hmac.compare_digest(_digest_file(pub), expected_key):
        raise SignedOemReturnError("Owner public PEM does not match independent trust pin")
    if observed_physical_flash_bytes != FOUR_MB:
        raise SignedOemReturnError("Owner-reported physical flash is not 4 MiB")
    if not 64000 <= current_sketch_bytes <= OEM_BYTES:
        raise SignedOemReturnError("Unreviewed currently running application size")
    if not 0 < reported_free_sketch_bytes <= OTA_END:
        raise SignedOemReturnError("Invalid operator-reported free sketch bytes")

    try:
        original_metadata = verify_archive(manufacturer_zip, pinned_manifest)
        with zipfile.ZipFile(manufacturer_zip) as z:
            original = z.read(original_metadata["firmware_member"])
    except (FactoryOtaError, OSError, RuntimeError, ValueError, KeyError,
            zipfile.BadZipFile) as exc:
        raise SignedOemReturnError("Manufacturer original does not match independently pinned ZIP") from exc
    if len(original) != OEM_BYTES:
        raise SignedOemReturnError("Manufacturer original application size changed")

    data = signed.read_bytes()
    if len(data) != SIGNED_OEM_BYTES:
        raise SignedOemReturnError("Signed transport must be exactly 494404 bytes")
    siglen = struct.unpack("<I", data[-4:])[0]
    if siglen != SIGNATURE_BYTES:
        raise SignedOemReturnError("Signed OEM trailer must contain exactly 256-byte signature")
    raw = data[:OEM_BYTES]
    signature = data[OEM_BYTES:-4]
    raw_sha = hashlib.sha256(raw).hexdigest()
    pinned_sha = original_metadata["firmware_sha256"]
    if not hmac.compare_digest(raw_sha, pinned_sha) or not hmac.compare_digest(raw, original):
        raise SignedOemReturnError("Signed package raw payload is NOT exact pinned OEM application")
    try:
        header = inspect_image(raw, "pinned_OEM_unsigned_application")
        layout, app_end = platformio_layout(platformio_ini, "env:esp12e")
    except PreflightError as exc:
        raise SignedOemReturnError(str(exc)) from exc
    if (header["flash_mode"] != "DIO" or
        header["flash_size_bytes_from_header"] != FOUR_MB or
        header["flash_frequency"] != "40MHz"):
        raise SignedOemReturnError("OEM image header mismatches reviewed DIO/4MB/40MHz")
    if layout != "eagle.flash.4m3m.ld" or app_end != OTA_END:
        raise SignedOemReturnError("Current source image is not linked for reviewed 4m3m boundary")
    geometry = staging_model(current_sketch_bytes, len(data), OTA_END)
    if (not geometry["nominal_no_overlap"] or
        geometry["free_gap_bytes"] < SECTOR or
        inferred_stock_fs_staging_overlap(geometry) != 0 or
        round_sector(len(data)) + SECTOR > reported_free_sketch_bytes):
        raise SignedOemReturnError("Signed OEM transport does not safely fit modeled staging")
    with tempfile.TemporaryDirectory(prefix="shino-oem-signed-research-") as tmp:
        raw_path, signature_path = Path(tmp) / "oem.bin", Path(tmp) / "oem.sig"
        raw_path.write_bytes(raw)
        signature_path.write_bytes(signature)
        try:
            run = subprocess.run(
                [openssl, "dgst", "-sha256", "-verify", str(pub),
                 "-signature", str(signature_path), str(raw_path)],
                capture_output=True, text=True, timeout=20, check=False)
        except (OSError, subprocess.TimeoutExpired) as exc:
            raise SignedOemReturnError("Offline OpenSSL check unavailable or timed out") from exc
        if run.returncode != 0 or "Verified OK" not in run.stdout:
            raise SignedOemReturnError("Owner RSA-2048/SHA-256 signature did not verify")
    return {
        "status": "SIGNED_EXACT_OEM_OFFLINE_VERIFIED__NO_INSTALL_PERMISSION",
        "model": "SmallTV-Ultra",
        "manufacturer_application_bytes": OEM_BYTES,
        "manufacturer_application_sha256": pinned_sha,
        "signed_transport_bytes": SIGNED_OEM_BYTES,
        "signature_bytes": SIGNATURE_BYTES,
        "signing_public_pem_sha256": expected_key,
        "manufacturer_original_byte_for_byte_equal": True,
        "owner_signature_verified": True,
        "source_linker": layout,
        "staging_uses_entire_signed_transport": True,
        "staging_model": geometry,
        "OEM_application_ONLY_not_full_flash_or_filesystem": True,
        "on_device_signed_oem_writer_compiled": False,
        "hardware_or_network_access": False,
        "permission_to_flash": False,
        "caveat": ("Offline verification only; inputs for running sketch and free space are "
                   "operator supplied, and signature/image match cannot prove boot or rescue."),
    }


def main() -> int:
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--signed-package", type=Path, required=True)
    p.add_argument("--owner-public-key", type=Path, required=True)
    p.add_argument("--expected-owner-public-key-sha256", required=True)
    p.add_argument("--manufacturer-zip", type=Path, required=True)
    p.add_argument("--pinned-manifest", type=Path, default=Path(__file__).resolve().parent.parent /
                   "recovery/factory_ota_v9_0_44.json")
    p.add_argument("--current-sketch-bytes", type=int, required=True)
    p.add_argument("--reported-free-sketch-bytes", type=int, required=True)
    p.add_argument("--observed-physical-flash-bytes", type=int, required=True)
    p.add_argument("--platformio", type=Path, default=Path(__file__).resolve().parent.parent /
                   "firmware/platformio.ini")
    args = p.parse_args()
    try:
        result = assess_signed_oem(
            args.signed_package, args.owner_public_key, args.manufacturer_zip,
            args.pinned_manifest,
            expected_owner_public_key_sha256=args.expected_owner_public_key_sha256,
            current_sketch_bytes=args.current_sketch_bytes,
            reported_free_sketch_bytes=args.reported_free_sketch_bytes,
            observed_physical_flash_bytes=args.observed_physical_flash_bytes,
            platformio_ini=args.platformio)
    except (SignedOemReturnError, OSError, ValueError) as exc:
        p.exit(1, f"SIGNED OEM RETURN RESEARCH GATE CLOSED: {exc}\n")
    print(json.dumps(result, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
