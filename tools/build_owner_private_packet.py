#!/usr/bin/env python3
"""Make a PRIVATE, one-run SHINO V2 + OEM application package on the owner's PC.

OFFLINE WITH RESPECT TO THE DEVICE: only downloads the exact pinned official
ZIP from raw.githubusercontent.com, builds local source with PlatformIO, and
checks existing local bytes. It has NO LAN access, device URL, updater upload,
serial COM command, LittleFS build, flash/erase command or release publishing.

This script MUST be launched manually from a clean, reviewed Git checkout with
an explicitly supplied *full source commit SHA*. It never authorizes a flash.
"""
from __future__ import annotations

import argparse
from datetime import datetime, timezone
import hashlib
import json
import os
from pathlib import Path
import re
import shutil
import subprocess
import sys
import urllib.parse
import urllib.request

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "tools"))
from owner_install_packet_gate import assess
from prepare_factory_rollback import prepare_factory_bin
from verify_factory_ota import verify_archive

MANIFEST = ROOT / "recovery/factory_ota_v9_0_44.json"
PLATFORMIO = ROOT / "firmware/platformio.ini"
POLICY = ROOT / "firmware/include/shino_private_policy.h"
CREDS = ROOT / "firmware/private/credentials.txt"
BUILD_DIR = ROOT / "firmware/.pio"
BUILT_APP = BUILD_DIR / "build/esp12e/firmware.bin"
PR16_REVIEWED_ANCESTOR = "22ace473000ec447c6f1d0e595ba14d5e81e4e84"
SOURCE_REMOTE_ALLOWED = {
    "https://github.com/shinobione/SHINO-TV.git",
    "https://github.com/shinobione/SHINO-TV",
    "git@github.com:shinobione/SHINO-TV.git",
}
OEM_URL = (
    "https://raw.githubusercontent.com/GeekMagicClock/smalltv-ultra/"
    "55d7877fcba8b1cb7a66a0830d35d5b374bc8540/"
    "Ultra-V9.0.44/FW-Smalltv-Ultra-V9.0.44.zip"
)
APP_NAME = "SHINO-TV-V2-4m3m-private-experimental-OEM-return.bin"
ZIP_NAME = "original-GeekMagic-Ultra-V9.0.44.zip"
BIN_NAME = "FW-Smalltv-Ultra-V9.0.44.bin"


class PrivateBuildError(ValueError):
    pass


def run(args: list[str], *, cwd: Path = ROOT, log: Path | None = None) -> str:
    result = subprocess.run(args, cwd=cwd, text=True, errors="replace",
                            stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
                            timeout=1200, check=False)
    if log is not None:
        with log.open("x", encoding="utf-8") as target:
            target.write(result.stdout)
    if result.returncode != 0:
        raise PrivateBuildError(
            "A local verification/compile step failed. Review the PRIVATE build log "
            "in the new output folder; do not use any incomplete images."
        )
    return result.stdout


def verify_reviewed_checkout(expected_source_sha: str) -> str:
    if not re.fullmatch(r"[0-9a-f]{40}", expected_source_sha):
        raise PrivateBuildError("Enter the complete lowercase 40-hex reviewed source commit SHA.")
    if not (ROOT / ".git").exists():
        raise PrivateBuildError("A fresh Git checkout is required; a GitHub source ZIP has no verifiable source commit.")
    sha = run(["git", "rev-parse", "HEAD"]).strip()
    if sha != expected_source_sha:
        raise PrivateBuildError("The current Git checkout SHA differs from the explicitly reviewed commit; stop.")
    if run(["git", "remote", "get-url", "origin"]).strip() not in SOURCE_REMOTE_ALLOWED:
        raise PrivateBuildError("Clone the official shinobione/SHINO-TV repository, not an unreviewed source copy.")
    if run(["git", "status", "--porcelain", "--untracked-files=normal"]).strip():
        raise PrivateBuildError("Source checkout has tracked/untracked changes. Use a clean, reviewed clone.")
    run(["git", "merge-base", "--is-ancestor", PR16_REVIEWED_ANCESTOR, "HEAD"])
    source_ini = PLATFORMIO.read_text(encoding="utf-8")
    if not re.search(r"^board_build\.ldscript\s*=\s*eagle\.flash\.4m3m\.ld\s*$", source_ini, re.M):
        raise PrivateBuildError("The exact FS-less 4m3m linker configuration is missing.")
    if not (ROOT / "firmware/src/boot/DashboardV2.h").exists() and not (
        ROOT / "firmware/include/boot/DashboardV2.h"
    ).is_file():
        raise PrivateBuildError("Four-card native V2 source missing.")
    for file in (POLICY, CREDS):
        if file.exists() or file.is_symlink():
            raise PrivateBuildError("A previous private policy or credentials file exists. Never overwrite/mix builds.")
    if BUILD_DIR.exists() or BUILD_DIR.is_symlink():
        raise PrivateBuildError("Existing PlatformIO build directory: use a clean clone, never reuse stale objects.")
    return sha


def git_blob_sha(content: bytes) -> str:
    header = f"blob {len(content)}\0".encode("ascii")
    return hashlib.sha1(header + content).hexdigest()  # Git's immutable blob object format.


def download_exact_oem(destination: Path) -> dict:
    manifest = json.loads(MANIFEST.read_text(encoding="utf-8"))
    if (manifest.get("source_repository") != "GeekMagicClock/smalltv-ultra" or
        manifest.get("source_commit") != "55d7877fcba8b1cb7a66a0830d35d5b374bc8540" or
        manifest.get("source_path") != "Ultra-V9.0.44/FW-Smalltv-Ultra-V9.0.44.zip"):
        raise PrivateBuildError("Unreviewed manufacturer source metadata: stop.")
    request = urllib.request.Request(OEM_URL, headers={"User-Agent": "SHINO-TV-offline-owner-package/1"})
    with urllib.request.urlopen(request, timeout=40) as response:
        final_url = urllib.parse.urlsplit(response.geturl())
        if (final_url.scheme != "https" or
            final_url.hostname != "raw.githubusercontent.com" or
            final_url.path != urllib.parse.urlsplit(OEM_URL).path):
            raise PrivateBuildError("Manufacturer download redirected to an unexpected host/path.")
        archive = response.read(2_000_001)
    if len(archive) != manifest["zip_bytes"]:
        raise PrivateBuildError("Manufacturer ZIP size differs from the immutable source record.")
    if hashlib.sha256(archive).hexdigest() != manifest["zip_sha256"]:
        raise PrivateBuildError("Manufacturer ZIP SHA-256 mismatch.")
    if git_blob_sha(archive) != manifest["source_git_blob_sha"]:
        raise PrivateBuildError("Manufacturer Git blob identity mismatch.")
    with destination.open("xb") as handle:
        handle.write(archive)
    info = verify_archive(destination, MANIFEST)
    return {
        "official_source_commit": manifest["source_commit"],
        "official_git_blob": manifest["source_git_blob_sha"],
        "archive_size_bytes": info["zip_bytes"],
        "archive_sha256": info["zip_sha256"],
        "application_size_bytes": info["firmware_bytes"],
        "application_sha256": info["firmware_sha256"],
    }


def independent_esptool_image_check(image: Path, private_log: Path) -> None:
    result = run([sys.executable, "-m", "esptool", "image-info", str(image)], log=private_log)
    if not re.search(r"Checksum:\s*0x[0-9a-f]+\s*\(valid\)", result, re.I):
        raise PrivateBuildError("Espressif image checksum not explicitly reported valid; stop.")


def build(expected_source_sha: str, output_root: Path) -> dict:
    # Fail-before-any-work review. No physical/remote device API is present.
    sha = verify_reviewed_checkout(expected_source_sha)
    root = Path(output_root).expanduser().resolve()
    if root == ROOT or ROOT in root.parents:
        raise PrivateBuildError("Private output folder must be OUTSIDE the Git working tree.")
    if root.is_symlink():
        raise PrivateBuildError("Refusing a symlinked private output root.")
    root.mkdir(parents=True, exist_ok=True)
    stamp = datetime.now(timezone.utc).strftime("%Y%m%d-%H%M%S-%f")
    packet = root / f"SHINO-V2-PRIVATE-{sha[:12]}-{stamp}"
    packet.mkdir(exist_ok=False)
    image_dir = packet / "images"
    secret_dir = packet / "private"
    report_dir = packet / "reports"
    for directory in (image_dir, secret_dir, report_dir):
        directory.mkdir()

    # A failed build is never a candidate for deployment. Preserve evidence
    # privately and move any generated ignored credentials out of checkout.
    marker = packet / "INCOMPLETE__DO_NOT_FLASH.txt"
    marker.write_text("INCOMPLETE. Not inspected or authorized. No device was contacted.\n", encoding="utf-8")
    zip_path = image_dir / ZIP_NAME
    oem_path = image_dir / BIN_NAME
    app_path = image_dir / APP_NAME
    final_policy = secret_dir / "shino_private_policy.h"
    final_creds = secret_dir / "credentials.txt"
    try:
        original = download_exact_oem(zip_path)
        print("Pinned official OEM ZIP checked (commit, Git blob, size and SHA-256).")
        prepared = prepare_factory_bin(zip_path, MANIFEST, oem_path)
        if prepared["bytes"] != original["application_size_bytes"]:
            raise PrivateBuildError("Extracted original application has unexpected size.")

        from generate_shino_device_policy import generate
        generated = generate(zip_path, MANIFEST, POLICY, CREDS, enable_restore=True)
        if (generated["boot_profile"] != "FIRST_BOOT_BRIDGE_ONLY" or
            generated["restore_mode"] != "EXPERIMENTAL_OEM_ONLY" or
            generated["fs_image_present"] or generated["fs_migration_writer_compiled"]):
            raise PrivateBuildError("Generated security policy not conservative FS-less/OEM-only.")
        print("Unique private AP/Digest secrets generated locally; experimental pinned OEM receiver selected.")
        run([sys.executable, "-m", "platformio", "run", "-e", "esp12e"],
            cwd=ROOT / "firmware", log=report_dir / "platformio-build-PRIVATE.log")
        if not BUILT_APP.is_file() or BUILT_APP.is_symlink():
            raise PrivateBuildError("Expected actual firmware.bin was not generated.")
        shutil.copyfile(BUILT_APP, app_path)

        # Preserve EXACT header+credentials of THIS app before cleaning the
        # generated source. Move them, do not silently rotate/regenerate.
        shutil.move(str(POLICY), str(final_policy))
        shutil.move(str(CREDS), str(final_creds))
        print("Private exact-build policy and credentials archived outside Git.")

        independent_esptool_image_check(app_path, report_dir / "esptool-shino-PRIVATE.log")
        independent_esptool_image_check(oem_path, report_dir / "esptool-original-PRIVATE.log")
        reviewed = assess(zip_path, MANIFEST, app_path, final_policy, final_creds, PLATFORMIO)
        if (reviewed["permission_to_flash"] is not False or
            reviewed["direct_install_model"]["overlaps_inferred_stock_file_sectors_bytes"] != 0 or
            reviewed["running_shino_to_oem_application_model"]["overlaps_inferred_stock_file_sectors_bytes"] != 0 or
            reviewed["private_pair_checks"]["experimental_exact_oem_return_present"] is not True):
            raise PrivateBuildError("Final private pairing or inferred stock-FS staging checks failed.")
        for key in ("SHINO_SETUP_AP_PSK", "SHINO_RESCUE_HTTP_PASSWORD", "SHINO_BOOTSTRAP_API_TOKEN"):
            # Reject accidental embedding of actual credential values into
            # the sanitized report. Only the private file contains them.
            import re as _re
            raw = final_policy.read_text(encoding="utf-8")
            match = _re.search(r'^#define ' + key + r' "([^"]+)"$', raw, _re.M)
            if match and match.group(1) in json.dumps(reviewed):
                raise PrivateBuildError("Credential secret leaked into summary; refusing to finalize.")
        (report_dir / "sanitized-offline-review.json").write_text(
            json.dumps(reviewed, indent=2) + "\n", encoding="utf-8")
        manifest = {
            "status": "OWNER_PRIVATE_LOCAL_FILES_VERIFIED__FLASH_NOT_AUTHORIZED",
            "source_sha40": sha,
            "private_files_are_one_exact_build": True,
            "experimental_OEM_application_only_return_enabled": True,
            "filesystem_image_compiled_or_migrated": False,
            "original": original,
            "actual_candidate": {
                "filename": APP_NAME,
                "bytes": app_path.stat().st_size,
                "sha256": hashlib.sha256(app_path.read_bytes()).hexdigest(),
                "linker_map": "eagle.flash.4m3m.ld",
                "esptool_checksum_valid": True,
            },
            "verified_original_app": {
                "filename": BIN_NAME,
                "bytes": oem_path.stat().st_size,
                "sha256": hashlib.sha256(oem_path.read_bytes()).hexdigest(),
                "esptool_checksum_valid": True,
                "full_original_owner_flash_backup": False,
            },
            "secret_files": {
                "location": "private/ (NEVER SHARE)",
                "policy_filename": final_policy.name,
                "credential_filename": final_creds.name,
                "matching_binary_checked": True,
                "values_printed_or_uploaded": False,
            },
            "inferred_stock_ota_slot_acceptance": "UNKNOWN",
            "owner_original_FS_preservation_guaranteed": False,
            "owner_nonbooting_wifi_recovery_guaranteed": False,
            "physical_device_accessed": False,
            "device_upload_or_flash": False,
            "permission_to_flash": False,
        }
        (report_dir / "owner-private-build-manifest.json").write_text(
            json.dumps(manifest, indent=2) + "\n", encoding="utf-8")
        (packet / "READ_ME_FIRST.txt").write_text(
            "SHINO // TV — PRIVATE V2 software build only.\n"
            "No device contacted; no upload performed or authorized.\n\n"
            "images/: exact checked original application-only OEM ZIP/BIN and one paired\n"
            "         custom 4m3m SHINO V2 application BIN (NOT a public release).\n"
            "private/: per-build policy and credentials. KEEP PRIVATE and OFF CLOUD.\n"
            "reports/: sanitized review+manifest; private platformio and esptool logs.\n\n"
            "DO NOT upload any .bin to the manufacturer's /update page on the basis\n"
            "of this packet alone. Stock OTA acceptance is unknown; a nonbooting\n"
            "application has no guaranteed Wi-Fi rescue. The original OEM BIN is\n"
            "NOT a full 4-MiB owner flash/filesystem backup. A separate explicit\n"
            "owner decision on the named actual BIN SHA-256/action is required.\n",
            encoding="utf-8")
        marker.unlink()
        print("PRIVATE LOCAL PACKET VERIFIED. No device/OTA/flash operation performed.")
        print("Private directory:", packet)
        print("Candidate bytes:", manifest["actual_candidate"]["bytes"])
        print("Candidate SHA-256:", manifest["actual_candidate"]["sha256"])
        print("Original official application SHA-256:", original["application_sha256"])
        print("DO NOT share private/ or upload any BIN without a separate owner decision.")
        return manifest
    except BaseException:
        if not marker.exists():
            marker.write_text("INCOMPLETE: later verification failed. DO NOT FLASH.\n", encoding="utf-8")
        raise
    finally:
        # No ignored secrets and no sensitive compiled objects remain in the
        # working checkout, whether verification passed or failed.
        for original_file, final_file in ((POLICY, final_policy), (CREDS, final_creds)):
            if original_file.exists() and not final_file.exists():
                shutil.move(str(original_file), str(final_file))
        if BUILD_DIR.is_dir() and not BUILD_DIR.is_symlink():
            shutil.rmtree(BUILD_DIR)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--expected-source-sha", required=True,
                        help="Reviewed EXACT 40-hex Git source SHA; never silently build a moving branch")
    parser.add_argument("--output-root", type=Path,
                        default=Path.home() / "SHINO-TV-private-builds",
                        help="Private local folder OUTSIDE Git/OneDrive/cloud sync; default is user home")
    args = parser.parse_args()
    try:
        build(args.expected_source_sha, args.output_root)
    except (PrivateBuildError, OSError, ValueError, subprocess.TimeoutExpired,
            urllib.error.URLError, urllib.error.HTTPError) as error:
        parser.exit(1, f"OWNER PRIVATE BUILD STOPPED: {error}\n"
                       "An incomplete private folder may remain; never use it for a TV upload.\n")
    except KeyboardInterrupt:
        parser.exit(1, "Owner stopped local build. Any incomplete packet is NOT flashable.\n")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
