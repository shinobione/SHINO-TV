#!/usr/bin/env python3
"""Generate throwaway private build policy for SHINO recovery loader, OFFLINE.

No device contact; no firmware write. Build secrets are never committed.
The current official factory archive is read only after exact pinned verification.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import os
from pathlib import Path
import secrets
import sys
import zipfile

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
from verify_factory_ota import FactoryOtaError, verify_archive  # noqa: E402

REPO = HERE.parent
MANIFEST = REPO / "recovery" / "factory_ota_v9_0_44.json"
POLICY = REPO / "recovery_loader" / "include" / "local_policy.h"
PRIVATE = REPO / "recovery_loader" / "private" / "credentials.txt"
MAX_CANDIDATE_BYTES = 1_044_464  # Source candidate size guard; not OTA-fit proof.


def inspect_candidate(path: Path) -> tuple[int, str]:
    data = path.read_bytes()
    if not 64_000 <= len(data) <= MAX_CANDIDATE_BYTES:
        raise FactoryOtaError("SHINO candidate image size outside ESP8266 supported guard")
    if data[0] != 0xE9 or not 1 <= data[1] <= 16:
        raise FactoryOtaError("SHINO candidate is not a plausible uncompressed ESP8266 application")
    return len(data), hashlib.md5(data, usedforsecurity=False).hexdigest()


def generate(official_zip: Path, manifest: Path, output: Path, secrets_out: Path,
             candidate: Path | None = None, writes: bool = False) -> dict:
    if writes and candidate is None:
        raise FactoryOtaError("Experimental write-enabled builds REQUIRE a pinned candidate binary")
    metadata = verify_archive(official_zip, manifest)
    with zipfile.ZipFile(official_zip) as z:
        factory = z.read(metadata["firmware_member"])
    if hashlib.sha256(factory).hexdigest() != metadata["firmware_sha256"]:
        raise FactoryOtaError("OEM application digest changed after archive verification")
    official_md5 = hashlib.md5(factory, usedforsecurity=False).hexdigest()
    candidate_size, candidate_md5 = inspect_candidate(candidate) if candidate else (0, "0" * 32)

    if output.exists() or secrets_out.exists():
        raise FactoryOtaError("Output exists; never overwrite provisioned credentials/policy")
    if output.resolve() == secrets_out.resolve():
        raise FactoryOtaError("Policy and credentials must be different files")

    wifi_pass = secrets.token_urlsafe(19)
    http_pass = secrets.token_urlsafe(25)
    user = "shino"
    config = (
        "// GENERATED LOCALLY; NOT FOR SOURCE CONTROL. Never publish this image or credentials.\n"
        "#pragma once\n"
        f'#define SHINO_RECOVERY_AP_PSK "{wifi_pass}"\n'
        f'#define SHINO_RECOVERY_HTTP_USER "{user}"\n'
        f'#define SHINO_RECOVERY_HTTP_PASSWORD "{http_pass}"\n'
        f'#define SHINO_ENABLE_LOADER_WRITES {1 if writes else 0}\n'
        f'#define SHINO_FACTORY_BYTES {len(factory)}\n'
        f'#define SHINO_FACTORY_MD5 "{official_md5}"\n'
        f'#define SHINO_CANDIDATE_BYTES {candidate_size}\n'
        f'#define SHINO_CANDIDATE_MD5 "{candidate_md5}"\n'
    )
    credential_text = (
        "PRIVATE, PER-BUILD SHINO RECOVERY CREDENTIALS. Do not share or commit.\n"
        f"Recovery Wi-Fi AP: SHINO-Recovery-<chip-id>\n"
        f"Wi-Fi password: {wifi_pass}\n"
        f"HTTP user: {user}\n"
        f"HTTP password: {http_pass}\n"
        f"Write handlers enabled: {writes}\n"
        "This file cannot recover a nonbooting loader. Keep it offline.\n"
    )
    output.parent.mkdir(parents=True, exist_ok=True)
    secrets_out.parent.mkdir(parents=True, exist_ok=True)
    try:
        with output.open("x", encoding="utf-8") as destination:
            destination.write(config)
        os.chmod(output, 0o600)
        with secrets_out.open("x", encoding="utf-8") as destination:
            destination.write(credential_text)
        os.chmod(secrets_out, 0o600)
    except BaseException:
        # Only delete files from this fresh invocation; caller pre-existing files
        # were explicitly refused before any write.
        if output.exists() and not secrets_out.exists():
            output.unlink()
        raise
    return {
        "mode": "experimental_write" if writes else "read_only",
        "factory_image_size": len(factory),
        "factory_sha256": metadata["firmware_sha256"],
        "candidate_size": candidate_size,
        "private_policy_file": str(output),
        "private_credentials_file": str(secrets_out),
        "device_action": "none",
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--official-zip", type=Path, required=True)
    parser.add_argument("--manifest", type=Path, default=MANIFEST)
    parser.add_argument("--candidate-bin", type=Path)
    parser.add_argument("--enable-writes", action="store_true",
                        help="EXPERIMENTAL, compile-only. Not an authorization to flash hardware.")
    parser.add_argument("--out", type=Path, default=POLICY)
    parser.add_argument("--credentials-out", type=Path, default=PRIVATE)
    args = parser.parse_args()
    try:
        report = generate(args.official_zip, args.manifest, args.out,
                          args.credentials_out, args.candidate_bin, args.enable_writes)
    except (FactoryOtaError, OSError, ValueError, KeyError) as exc:
        parser.exit(1, f"RECOVERY LOADER BUILD GATE CLOSED: {exc}\n")
    # No passwords/digests printed to shared GitHub Actions logs.
    print(json.dumps(report, indent=2))
    print("NO DEVICE ACTION. Credentials remain in ignored private local files.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
