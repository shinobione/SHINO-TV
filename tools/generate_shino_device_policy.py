#!/usr/bin/env python3
"""Create an ignored, per-build SHINO firmware security policy using pinned OEM bytes.

Local/CI only: does not connect to or write the device. Never publish generated
header or credential file (they contain per-build AP and HTTP secrets).
"""
from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
import secrets
import sys
import zipfile

sys.path.insert(0, str(Path(__file__).resolve().parent))
from verify_factory_ota import FactoryOtaError, verify_archive  # noqa: E402

ROOT = Path(__file__).resolve().parent.parent
DEFAULT_MANIFEST = ROOT / "recovery" / "factory_ota_v9_0_44.json"
DEFAULT_HEADER = ROOT / "firmware" / "include" / "shino_private_policy.h"
DEFAULT_SECRETS = ROOT / "firmware" / "private" / "credentials.txt"


def generate(oem_zip: Path, manifest: Path, output: Path, secrets_file: Path,
             enable_restore: bool = False) -> dict:
    reference = verify_archive(Path(oem_zip), Path(manifest))
    with zipfile.ZipFile(oem_zip) as archive:
        original = archive.read(reference["firmware_member"])
    if hashlib.sha256(original).hexdigest() != reference["firmware_sha256"]:
        raise FactoryOtaError("OEM inner SHA-256 mismatch after extraction")
    if output.exists() or secrets_file.exists():
        raise FactoryOtaError("Output already exists; refusing credential overwrite")
    if output.resolve() == secrets_file.resolve():
        raise FactoryOtaError("Header and credential file must be distinct")

    # Separate values so an HTTP token cannot double as the Wi-Fi AP password.
    ap_psk = secrets.token_urlsafe(19)
    token = secrets.token_urlsafe(29)
    rescue_password = secrets.token_urlsafe(25)
    pin = (
        "// Generated locally from pinned V9.0.44; NEVER commit or redistribute.\n"
        "#pragma once\n"
        f"#define SHINO_FACTORY_BYTES {len(original)}\n"
        f'#define SHINO_FACTORY_MD5 "{hashlib.md5(original, usedforsecurity=False).hexdigest()}"\n'
        f'#define SHINO_FACTORY_SHA256 "{reference["firmware_sha256"]}"\n'
        f'#define SHINO_ENABLE_FACTORY_RESTORE {1 if enable_restore else 0}\n'
        '#define SHINO_BOOT_PROFILE 0\n'

        f'#define SHINO_SETUP_AP_PSK "{ap_psk}"\n'
        f'#define SHINO_BOOTSTRAP_API_TOKEN "{token}"\n'
        '#define SHINO_RESCUE_HTTP_USER "shino"\n'
        f'#define SHINO_RESCUE_HTTP_PASSWORD "{rescue_password}"\n'
    )
    credentials = (
        "PRIVATE SHINO // TV SOURCE BUILD CREDENTIALS — never publish or upload.\n"
        "Setup/rescue Wi-Fi SSID: SHINO-TV-<chip-id>\n"
        f"Setup/rescue Wi-Fi password: {ap_psk}\n"
        f"Initial API bearer token: {token}\n"
        "Rescue HTTP Digest user: shino\n"
        f"Rescue HTTP Digest password: {rescue_password}\n"
        "If a firmware was built with different secrets, use that build's own private file.\n"
        f"Experimental factory restore endpoint compiled: {enable_restore}\n"
        "First boot mode: isolated WPA2/Digest diagnostics, no filesystem/EEPROM setup.\n"
        "This credential file is not a full flash recovery mechanism.\n"
    )
    output.parent.mkdir(parents=True, exist_ok=True)
    secrets_file.parent.mkdir(parents=True, exist_ok=True)
    try:
        with output.open("x", encoding="utf-8") as file:
            file.write(pin)
        with secrets_file.open("x", encoding="utf-8") as file:
            file.write(credentials)
    except BaseException:
        # Only clean up a new header when writing the companion file failed.
        if output.exists() and not secrets_file.exists():
            output.unlink()
        raise
    return {
        "oem_sha256": reference["firmware_sha256"],
        "oem_size": len(original),
        "restore_mode": "EXPERIMENTAL_OEM_ONLY" if enable_restore else "DISABLED",
        "boot_profile": "FIRST_BOOT_BRIDGE_ONLY",
        "header": str(output),
        "credential_file": str(secrets_file),
        "device_operation": "none",
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--oem-zip", type=Path, required=True)
    parser.add_argument("--manifest", type=Path, default=DEFAULT_MANIFEST)
    parser.add_argument("--enable-restore", action="store_true",
                        help="Compile experimental OEM-only restore; NOT permission for any actual upload")
    parser.add_argument("--out", type=Path, default=DEFAULT_HEADER)
    parser.add_argument("--credentials-out", type=Path, default=DEFAULT_SECRETS)
    args = parser.parse_args()
    try:
        report = generate(args.oem_zip, args.manifest, args.out, args.credentials_out, args.enable_restore)
    except (FactoryOtaError, OSError, ValueError, KeyError) as error:
        parser.exit(1, f"SECURE FIRMWARE BUILD GATE CLOSED: {error}\n")
    print(json.dumps(report, indent=2))
    print("Generated credentials are local/private; no OEM binary or device writes occurred.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
