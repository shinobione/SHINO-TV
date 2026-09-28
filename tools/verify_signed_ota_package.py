#!/usr/bin/env python3
"""OFFLINE research verifier for the ESP8266 Arduino Core 3.1.2 signed-OTA format.

This tool NEVER accesses any device, flashes firmware, signs a release, or
reads a signing PRIVATE key. Two independently reviewed SHA-256 values are
mandatory: the RAW (unsigned) application and the public PEM trust anchor.
Passing does not authorize installation, prove recovery or validate full boot.
"""

from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
import re
import struct
import subprocess
import tempfile

from native_ota_preflight import (
    NativeOtaGateError, REQUIRED_BINARY_MARKERS, OTA_END, SECTOR,
)
from wifi_flash_preflight import (
    FOUR_MB, PreflightError, inspect_image, platformio_layout, round_sector,
    staging_model, inferred_stock_fs_staging_overlap,
)

SIGNATURE_BYTES = 256  # Deliberate RSA-2048-only initial trust policy
MAX_UNSIGNED_BYTES = 494144
MIN_UNSIGNED_BYTES = 64000


class SignedPackageError(ValueError):
    pass


def _digest_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as inp:
        for block in iter(lambda: inp.read(131072), b""):
            digest.update(block)
    return digest.hexdigest()


def _checked_file(path: Path, *, max_bytes: int, label: str) -> Path:
    if not path.is_file() or path.is_symlink():
        raise SignedPackageError(f"{label}: regular local file required; no symlinks")
    if path.stat().st_size <= 0 or path.stat().st_size > max_bytes:
        raise SignedPackageError(f"{label}: invalid or oversized local file")
    return path


def _digest_argument(value: str, label: str) -> str:
    if not re.fullmatch(r"[0-9a-fA-F]{64}", value):
        raise SignedPackageError(f"{label}: an independently reviewed 64-hex SHA-256 is required")
    return value.lower()


def assess_signed(package: Path, public_key: Path, *,
                  expected_unsigned_sha256: str, expected_public_key_sha256: str,
                  current_sketch_bytes: int, reported_free_sketch_bytes: int,
                  observed_physical_flash_bytes: int, platformio_ini: Path,
                  openssl: str = "openssl") -> dict:
    """Check one file against an independently pinned public key and unsigned hash.

    The reported runtime fields are operator-provided; this function never
    queries the device. It always returns permission_to_flash=False.
    """
    expected_raw = _digest_argument(expected_unsigned_sha256, "unsigned application")
    expected_key = _digest_argument(expected_public_key_sha256, "public signing key")
    pkg = _checked_file(package, max_bytes=MAX_UNSIGNED_BYTES + SIGNATURE_BYTES + 4,
                        label="Signed firmware package")
    pub = _checked_file(public_key, max_bytes=8192, label="Public signing PEM")
    if _digest_file(pub) != expected_key:
        raise SignedPackageError("Public-key PEM does not match the independent owner trust anchor")
    if observed_physical_flash_bytes != FOUR_MB:
        raise SignedPackageError("Reported physical flash is not 4 MiB")
    if not MIN_UNSIGNED_BYTES <= current_sketch_bytes <= MAX_UNSIGNED_BYTES:
        raise SignedPackageError("Invalid current application size")
    if not 0 < reported_free_sketch_bytes <= OTA_END:
        raise SignedPackageError("Invalid runtime free-sketch report")

    data = pkg.read_bytes()
    if len(data) < MIN_UNSIGNED_BYTES + SIGNATURE_BYTES + 4:
        raise SignedPackageError("Package too small to contain a complete signed application")
    signature_length = struct.unpack("<I", data[-4:])[0]
    if signature_length != SIGNATURE_BYTES:
        raise SignedPackageError("Expected precisely 256-byte RSA-2048 signature trailer")
    unsigned = data[:-(SIGNATURE_BYTES + 4)]
    signature = data[-(SIGNATURE_BYTES + 4):-4]
    if not MIN_UNSIGNED_BYTES <= len(unsigned) <= MAX_UNSIGNED_BYTES:
        raise SignedPackageError("Invalid unsigned firmware image size")
    unsigned_sha256 = hashlib.sha256(unsigned).hexdigest()
    if unsigned_sha256 != expected_raw:
        raise SignedPackageError("Unsigned image does not match independently reviewed SHA-256")
    try:
        header = inspect_image(unsigned, "SHINO_signed_OTA_unsigned_payload")
        layout, end = platformio_layout(platformio_ini, "env:esp12e")
    except PreflightError as exc:
        raise SignedPackageError(str(exc)) from exc
    if (header["flash_mode"] != "DIO" or
        header["flash_size_bytes_from_header"] != FOUR_MB or
        header["flash_frequency"] != "40MHz"):
        raise SignedPackageError("Invalid hardware flash header")
    if layout != "eagle.flash.4m3m.ld" or end != OTA_END:
        raise SignedPackageError("Unreviewed source linker/OTA geometry")
    if any(marker not in unsigned for marker in REQUIRED_BINARY_MARKERS):
        raise SignedPackageError("Missing conservative FS-less runtime marker")

    # The upstream Update.begin(size) gets the whole SIGNED transfer byte count.
    # Only Update.end(false) verifies its signature and removes trailer length
    # before scheduling eboot copy of the raw image.
    model = staging_model(current_sketch_bytes, len(data), OTA_END)
    if (not model["nominal_no_overlap"] or model["free_gap_bytes"] < SECTOR or
        inferred_stock_fs_staging_overlap(model) != 0 or
        round_sector(len(data)) + SECTOR > reported_free_sketch_bytes):
        raise SignedPackageError("Signed transport does not fit the conservative staging model")

    # Verify actual RSA/SHA-256 signature; no local private key is opened.
    # Separate temporary raw/signature files are deleted regardless of result.
    with tempfile.TemporaryDirectory(prefix="shino-ota-offline-") as directory:
        raw_path = Path(directory) / "unsigned.bin"
        sig_path = Path(directory) / "signature.bin"
        raw_path.write_bytes(unsigned)
        sig_path.write_bytes(signature)
        try:
            proc = subprocess.run(
                [openssl, "dgst", "-sha256", "-verify", str(pub),
                 "-signature", str(sig_path), str(raw_path)],
                capture_output=True, text=True, timeout=20, check=False,
            )
        except (OSError, subprocess.TimeoutExpired) as exc:
            raise SignedPackageError("OpenSSL verification unavailable or timed out") from exc
        if proc.returncode != 0 or "Verified OK" not in proc.stdout:
            raise SignedPackageError("RSA-2048/SHA-256 signing verification FAILED")

    return {
        "status": "CORE_SIGNED_PACKAGE_OFFLINE_VERIFIED__NO_INSTALL_PERMISSION",
        "signed_transport_bytes": len(data),
        "unsigned_application_bytes": len(unsigned),
        "unsigned_sha256": unsigned_sha256,
        "public_key_sha256": expected_key,
        "signature_bytes": signature_length,
        "format": "ESP8266_CORE_3_1_2__BIN_RSA2048_SIG_UINT32_LE",
        "staging_model_uses_signed_transport_bytes": True,
        "staging": model,
        "signature_verified_by_openssl": True,
        "unsigned_app_header": {
            "flash_mode": header["flash_mode"],
            "flash_size_flag": header["flash_size_flag"],
            "flash_frequency": header["flash_frequency"],
        },
        "signature_verification_compiled_on_device": False,
        "native_ota_writer_compiled": False,
        "hardware_or_network_contact": False,
        "permission_to_flash": False,
        "warning": ("Trust applies only to the independently pinned public key. "
                    "Runtime values are operator-supplied. Successful signature, "
                    "headers and geometry do not prove boot or recovery."),
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--signed-package", type=Path, required=True)
    parser.add_argument("--public-key", type=Path, required=True)
    parser.add_argument("--expected-unsigned-sha256", required=True)
    parser.add_argument("--expected-public-key-sha256", required=True)
    parser.add_argument("--current-sketch-bytes", type=int, required=True)
    parser.add_argument("--reported-free-sketch-bytes", type=int, required=True)
    parser.add_argument("--observed-physical-flash-bytes", type=int, required=True)
    parser.add_argument("--platformio", type=Path,
                        default=Path(__file__).resolve().parent.parent / "firmware/platformio.ini")
    args = parser.parse_args()
    try:
        result = assess_signed(
            args.signed_package, args.public_key,
            expected_unsigned_sha256=args.expected_unsigned_sha256,
            expected_public_key_sha256=args.expected_public_key_sha256,
            current_sketch_bytes=args.current_sketch_bytes,
            reported_free_sketch_bytes=args.reported_free_sketch_bytes,
            observed_physical_flash_bytes=args.observed_physical_flash_bytes,
            platformio_ini=args.platformio,
        )
    except (SignedPackageError, OSError, ValueError) as exc:
        parser.exit(1, f"SIGNED OTA RESEARCH CLOSED: {exc}\n")
    print(json.dumps(result, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
