#!/usr/bin/env python3
"""Build ONE private Windows owner review kit. Never access the actual TV.

Requires local checkout with clean tracked source, a locally obtained official
pinned OEM ZIP, preinstalled PlatformIO and esptool. PlatformIO may download
compiler dependencies from its own registries. This script itself does NOT
fetch the OEM ZIP, access any TV IP, invoke esptool serial mode, flash firmware,
publish build artifacts or reuse credentials from another compilation.

Private output folder MUST be outside git, not pre-existing and locally
controlled. Each invocation creates new random device credentials. This build
is a review artifact, NOT a deployment permission or proof of stock OTA fit.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile
import zipfile

from owner_install_packet_gate import PacketError, assess
from verify_factory_ota import FactoryOtaError, verify_archive, inspect_archive
from wifi_flash_preflight import PreflightError

ROOT = Path(__file__).resolve().parent.parent
POLICY = ROOT / "firmware/include/shino_private_policy.h"
CREDENTIALS = ROOT / "firmware/private/credentials.txt"
APP = ROOT / "firmware/.pio/build/esp12e/firmware.bin"
OEM_MEMBER = "FW-Smalltv-Ultra-V9.0.44.bin"
APP_NAME = "SHINO-TV-V2-PRIVATE-NOT-A-FLASH-APPROVAL.bin"
OEM_NAME = "OEM-V9.0.44-APPLICATION-ONLY.bin"
MAX_OEM_ZIP = 2_000_000

class OwnerKitError(ValueError):
    pass

def sha256(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as file:
        for block in iter(lambda: file.read(262144), b""):
            h.update(block)
    return h.hexdigest()

def run(args: list[str], *, cwd: Path=ROOT, output: bool=True) -> str:
    completed = subprocess.run(args, cwd=cwd, text=True, capture_output=True,
                               check=False, timeout=900)
    if completed.returncode:
        # PlatformIO error output can include paths/config. No secret-file body
        # or command tokens are intentionally included in published output.
        raise OwnerKitError("Local prerequisite/build/check failed: " +
                            args[0] + " exited with " + str(completed.returncode) +
                            ". Inspect LOCAL process logs; do not publish secrets.")
    return completed.stdout.strip() if output else ""

def require_clean_frozen_checkout() -> str:
    if not (ROOT / ".git").exists():
        raise OwnerKitError("Use a Git checkout, not a branch ZIP; exact source commit is mandatory")
    sha = run(["git", "rev-parse", "--verify", "HEAD"])
    if len(sha) != 40 or any(c not in "0123456789abcdef" for c in sha):
        raise OwnerKitError("Invalid source commit SHA")
    if run(["git", "status", "--porcelain", "--untracked-files=normal"]):
        raise OwnerKitError("Tracked/untracked source tree is not clean; freeze an exact reviewed commit")
    if run(["git", "diff", "--name-only", "HEAD"]):
        raise OwnerKitError("Uncommitted code changes; refuse ambiguous source provenance")
    return sha

def output_policy(zip_path: Path, out_dir: Path) -> tuple[Path, Path]:
    original = zip_path.resolve(strict=True)
    root = ROOT.resolve(strict=True)
    out = out_dir.resolve(strict=False)
    if original.is_symlink() or not original.is_file():
        raise OwnerKitError("OEM ZIP must be a regular local file, no symlink")
    if original.stat().st_size > MAX_OEM_ZIP:
        raise OwnerKitError("Unexpected OEM ZIP size")
    if out == root or root in out.parents:
        raise OwnerKitError("Private output must be OUTSIDE Git checkout and .gitignore is not a backup")
    if out.exists():
        raise OwnerKitError("Private output directory exists; never overwrite another build or secrets")
    if not out.parent.is_dir() or out.parent.is_symlink():
        raise OwnerKitError("Create a private LOCAL parent directory before building")
    if out == original or out in original.parents:
        raise OwnerKitError("Output and OEM source directories must not overlap")
    if POLICY.exists() or CREDENTIALS.exists():
        raise OwnerKitError("Old generated private policy/credentials exist; do NOT silently reuse/overwrite")
    if (ROOT / "firmware/data/config.json").exists():
        raise OwnerKitError("Old config.json exists; FS-less build must not embed another config")
    if APP.exists():
        raise OwnerKitError("Old candidate BIN exists; clean build folder first, never reuse unknown bytes")
    return original, out

def write_private_kit(zip_path: Path, out_dir: Path, expected_source_sha: str, *, python=sys.executable) -> dict:
    source_sha = require_clean_frozen_checkout()
    if source_sha != expected_source_sha:
        raise OwnerKitError("Current checkout commit does NOT match the explicitly reviewed source SHA")
    original, final = output_policy(zip_path, out_dir)
    oem = verify_archive(original, ROOT / "recovery/factory_ota_v9_0_44.json")
    parent = final.parent
    # Work in private parent. Publish only after exact source/image/secret
    # pairing, independent image checks and zero-FS envelope verification.
    temporary = Path(tempfile.mkdtemp(prefix=".shino-review-incomplete-", dir=parent))
    generated = False
    try:
        # policy generator never replaces existing private secrets.
        run([python, "tools/generate_shino_device_policy.py",
             "--oem-zip", str(original), "--enable-restore"])
        generated = True
        run([python, "-m", "platformio", "run", "--project-dir", "firmware", "-e", "esp12e"],
            output=False)
        if not APP.is_file() or APP.is_symlink():
            raise OwnerKitError("No regular fresh candidate application BIN compiled")
        private_app = temporary / APP_NAME
        shutil.copyfile(APP, private_app)

        # This is extraction to owner-controlled local folder only, NOT full 4MiB
        # flash backup, never an update request.
        private_oem = temporary / OEM_NAME
        with zipfile.ZipFile(original) as archive:
            with private_oem.open("xb") as dest:
                dest.write(archive.read(oem["firmware_member"]))
        if sha256(private_oem) != oem["firmware_sha256"]:
            raise OwnerKitError("Extracted original BIN has wrong SHA-256")
        shutil.copyfile(POLICY, temporary / "shino_private_policy.h")
        shutil.copyfile(CREDENTIALS, temporary / "credentials.txt")
        report = assess(
            original, ROOT / "recovery/factory_ota_v9_0_44.json",
            private_app, temporary / "shino_private_policy.h",
            temporary / "credentials.txt", ROOT / "firmware/platformio.ini",
        )
        for item in (private_app, private_oem):
            # Exact esptool image-info is a FILE-ONLY command; no serial port,
            # baud, target address, upload/flash/erase or device connection.
            run([python, "-m", "esptool", "image-info", str(item)], output=False)
        if report["status"] != "PRIVATE_OFFLINE_PACKET_CHECKED__OWNER_FLASH_NOT_AUTHORIZED":
            raise OwnerKitError("Safe review status missing")
        if report["permission_to_flash"] or report["files_uploaded"]:
            raise OwnerKitError("Review kit MUST NOT authorize or perform device operation")
        if report["direct_install_model"]["overlaps_inferred_stock_file_sectors_bytes"] != 0:
            raise OwnerKitError("Direct OTA would intersect inferred stock filesystem")
        if report["running_shino_to_oem_application_model"]["overlaps_inferred_stock_file_sectors_bytes"] != 0:
            raise OwnerKitError("OEM return would intersect inferred stock filesystem")
        result = {
            "status": "PRIVATE_KIT_READY_FOR_REVIEW__OWNER_FLASH_NOT_AUTHORIZED",
            "source_commit": source_sha,
            "files": {
                APP_NAME: {"bytes": private_app.stat().st_size, "sha256": sha256(private_app)},
                OEM_NAME: {"bytes": private_oem.stat().st_size, "sha256": sha256(private_oem),
                           "scope": "original application OTA only; not whole owner flash"},
                "credentials.txt": {"private": True, "never_share": True},
                "shino_private_policy.h": {"private": True, "never_share": True},
            },
            "review": report,
            "owner_ready_to_flash": False,
            "physical_device_contacted": False,
            "usb_uart_or_second_device_required_for_software_preparation": False,
            "warning": ("DO NOT upload any of these images based on this kit. "
                        "Owner stock OTA acceptance and nonbooting recovery remain UNKNOWN."),
        }
        (temporary / "REVIEW-ONLY-MANIFEST.json").write_text(json.dumps(result, indent=2) + "\n",
                                                               encoding="utf-8")
        # Check that report has no literal AP/HTTP/token secrets.
        public = (temporary / "REVIEW-ONLY-MANIFEST.json").read_bytes()
        private_text = (temporary / "shino_private_policy.h").read_text(encoding="utf-8")
        import re
        for name in ("SHINO_SETUP_AP_PSK", "SHINO_RESCUE_HTTP_PASSWORD", "SHINO_BOOTSTRAP_API_TOKEN"):
            match = re.search(r'^#define ' + name + r' "([^"]+)"$', private_text, flags=re.M)
            if not match or match.group(1).encode("utf-8") in public:
                raise OwnerKitError("Sanitized manifest includes credentials or private policy incomplete")
        if (ROOT / "firmware/.pio/build/esp12e/littlefs.bin").exists():
            raise OwnerKitError("An unexpected filesystem image was created")
        temporary.rename(final)
        return {"folder": str(final), "source_commit": source_sha,
                "candidate_bytes": result["files"][APP_NAME]["bytes"],
                "candidate_sha256": result["files"][APP_NAME]["sha256"],
                "factory_app_sha256": result["files"][OEM_NAME]["sha256"],
                "status": result["status"], "device_contacted": False}
    finally:
        # Remove only newly generated, ignored build secrets. Private KIT
        # contains the exact pair. Failed temporary report has no use.
        if generated:
            POLICY.unlink(missing_ok=True)
            CREDENTIALS.unlink(missing_ok=True)
        if temporary.exists():
            shutil.rmtree(temporary)
        # PlatformIO output is ignored and stays local; do not auto-delete it
        # before the user can inspect an unexpected failure. Next invocation
        # must explicitly clear that previous .pio build before starting.

def main() -> int:
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--expected-source-sha", required=True,
                        help="Full 40-char reviewed Git source SHA; never use a floating branch silently")
    parser.add_argument("--official-zip", type=Path, required=True,
                        help="Verified OEM Ultra V9.0.44 original ZIP already on user's PC")
    parser.add_argument("--out-dir", type=Path, required=True,
                        help="New PRIVATE local directory OUTSIDE Git checkout, no overwrite")
    args=parser.parse_args()
    try:
        result=write_private_kit(args.official_zip,args.out_dir,args.expected_source_sha)
    except (OwnerKitError, PacketError, PreflightError, FactoryOtaError,
            OSError, ValueError, subprocess.TimeoutExpired) as exc:
        parser.exit(1, f"PRIVATE BUILD CLOSED: {exc}\n")
    print("Private owner-review kit prepared locally. NO TV contacted; NOT approved for flash.")
    print(json.dumps(result, indent=2))
    return 0

if __name__=="__main__":
    raise SystemExit(main())
