#!/usr/bin/env python3
"""Read-only, PRIVATE owner build pairing + direct OTA geometry report.

This script NEVER contacts the SmallTV, performs no POST, writes no firmware,
extracts no OEM BIN, and does not generate/upload a flashable artifact.
The report deliberately omits ALL private AP, HTTP and bearer credentials.
No success result grants permission to flash this one-device installation.
"""
from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
import re
import zipfile

from verify_factory_ota import FactoryOtaError, verify_archive
from wifi_flash_preflight import (
    PreflightError, inspect_image, platformio_layout, staging_model,
    inferred_stock_fs_staging_overlap,
)

OEM_STOCK_CEILING_ASSUMED = 0x100000
EXPECTED_FACTORY_IMAGE_BYTES = 494144
MARKERS = (
    b"FIRST_BOOT_BRIDGE", b"FSLESS_PC_TELEMETRY_RAM_ONLY",
    b"READ_ONLY_FS_MIGRATION_PLAN", b"RAM_SAMPLE_ACCEPTED",
)
EXPERIMENTAL_OEM_RETURN_MARKER = b"Verified OEM application image"


class PacketError(ValueError):
    pass


def private_regular(path: Path, label: str) -> Path:
    p = Path(path)
    if not p.is_file() or p.is_symlink():
        raise PacketError(f"{label}: expected a regular existing LOCAL file, no symlinks")
    return p


def macros(path: Path) -> dict[str, str]:
    data = private_regular(path, "private device policy").read_text(encoding="utf-8")
    out = {}
    for name, value in re.findall(r'^#define (SHINO_[A-Z0-9_]+) (\d+|"[^"\n]*")$', data, re.M):
        if name in out:
            raise PacketError("Duplicate policy macro; refuse ambiguous credentials or image pins")
        out[name] = value[1:-1] if value.startswith('"') else value
    return out


def private_pair(policy: Path, credentials: Path, official: dict, candidate_bytes: bytes) -> dict:
    m = macros(policy)
    required = {
        "SHINO_BOOT_PROFILE": "0",
        "SHINO_FS_IMAGE_PRESENT": "0",
        "SHINO_ENABLE_FS_MIGRATION": "0",
        "SHINO_ENABLE_FACTORY_RESTORE": "1",  # An owner restore receiver is needed for review.
        "SHINO_FACTORY_BYTES": str(EXPECTED_FACTORY_IMAGE_BYTES),
        "SHINO_FACTORY_SHA256": official["firmware_sha256"],
    }
    for field, expected in required.items():
        if m.get(field) != expected:
            raise PacketError(f"Unsafe or mismatched private build policy: {field}")
    digest = official["firmware_md5_for_updater"]
    if m.get("SHINO_FACTORY_MD5") != digest:
        raise PacketError("Private OEM updater digest does not match the pinned original")
    if digest.encode("ascii") not in candidate_bytes:
        raise PacketError("Compiled candidate lacks the exact manufacturer application MD5 pin")
    if EXPERIMENTAL_OEM_RETURN_MARKER not in candidate_bytes:
        raise PacketError("Compiled candidate does not contain its experimental pinned OEM return receiver")
    for marker in MARKERS:
        if marker not in candidate_bytes:
            raise PacketError("Compiled candidate lacks mandatory FS-less first-boot functionality")

    creds = private_regular(credentials, "private build credentials")
    if creds.stat().st_size > 4096:
        raise PacketError("Credential file unexpectedly large")
    values = {}
    for line in creds.read_text(encoding="utf-8").splitlines():
        name, separator, value = line.partition(": ")
        if separator:
            if name in values:
                raise PacketError("Duplicate private credential line")
            values[name] = value
    comparisons = {
        "Setup/rescue Wi-Fi password": "SHINO_SETUP_AP_PSK",
        "Initial API bearer token": "SHINO_BOOTSTRAP_API_TOKEN",
        "Rescue HTTP Digest user": "SHINO_RESCUE_HTTP_USER",
        "Rescue HTTP Digest password": "SHINO_RESCUE_HTTP_PASSWORD",
    }
    for line, macro in comparisons.items():
        if not m.get(macro) or values.get(line) != m[macro]:
            raise PacketError("Credentials do not correspond to generated private policy")
    if values.get("First-boot Wi-Fi SSID") != "SHINO-FirstBoot-<chip-id>":
        raise PacketError("Wrong first-boot AP identity in the paired private credentials")
    ap = m["SHINO_SETUP_AP_PSK"]
    digest_secret = m["SHINO_RESCUE_HTTP_PASSWORD"]
    token = m["SHINO_BOOTSTRAP_API_TOKEN"]
    if min(len(ap), len(digest_secret), len(token)) < 20 or len({ap,digest_secret,token}) != 3:
        raise PacketError("Weak or shared generated credential secrets")
    # The active bridge consumes both secrets. This also catches pairing a
    # genuine policy/credential file with a DIFFERENT candidate build.
    for secret in (ap, digest_secret):
        if secret.encode("ascii") not in candidate_bytes:
            raise PacketError("A compiled active first-boot AP/Digest secret differs from supplied private policy")
    return {
        "policy_matches_oem_archive": True,
        "private_policy_matches_private_credentials": True,
        "compiled_app_has_correct_active_ap_and_digest_secrets": True,
        "experimental_exact_oem_return_present": True,
        "fs_migration_compiled": False,
        "credential_values_in_public_report": False,
    }


def assess(official_zip: Path, manifest: Path, candidate_bin: Path,
           policy: Path, credentials: Path, candidate_ini: Path,
           loader_bin: Path | None = None, loader_ini: Path | None = None) -> dict:
    metadata = verify_archive(private_regular(official_zip, "official archive"), manifest)
    with zipfile.ZipFile(official_zip) as z:
        original = z.read(metadata["firmware_member"])
    original_info = inspect_image(original, "pinned_manufacturer_V9_0_44")
    official = dict(metadata, firmware_md5_for_updater=original_info["md5_for_arduino_updater"])
    if original_info["size_bytes"] != EXPECTED_FACTORY_IMAGE_BYTES:
        raise PacketError("Original factory image changed")
    candidate_bytes = private_regular(candidate_bin, "private SHINO application").read_bytes()
    candidate = inspect_image(candidate_bytes, "paired_shino_v2")
    for item in (candidate, original_info):
        if item["flash_mode"] != "DIO" or item["flash_size_bytes_from_header"] != 0x400000 or item["flash_frequency"] != "40MHz":
            raise PacketError("Unexpected ESP8266 image flash mode/capacity/frequency")
    if candidate["size_bytes"] >= original_info["size_bytes"]:
        raise PacketError("Reviewed FS-less application exceeds conservative original OEM image budget")
    linked_map, stage_end = platformio_layout(candidate_ini, "env:esp12e")
    if linked_map != "eagle.flash.4m3m.ld" or stage_end != OEM_STOCK_CEILING_ASSUMED:
        raise PacketError("FS-less application must use the stock-like 4m3m OTA ceiling")
    security = private_pair(policy, credentials, official, candidate_bytes)
    direct = staging_model(original_info["size_bytes"], candidate["size_bytes"], OEM_STOCK_CEILING_ASSUMED)
    return_oem = staging_model(candidate["size_bytes"], original_info["size_bytes"], stage_end)
    if not (direct["nominal_no_overlap"] and return_oem["nominal_no_overlap"]):
        raise PacketError("Application and OTA staging geometrically overlap under modeled 4m3m")
    for transition in (direct, return_oem):
        transition["overlaps_inferred_stock_file_sectors_bytes"] = inferred_stock_fs_staging_overlap(transition)
        if transition["overlaps_inferred_stock_file_sectors_bytes"] != 0:
            raise PacketError("Direct/recovery staging would overwrite inferred manufacturer file sectors")
    alternative = {"provided": False, "not_a_stock_data_preserving_fallback": True}
    if loader_bin is not None or loader_ini is not None:
        if loader_bin is None or loader_ini is None:
            raise PacketError("Loader BIN and reviewed loader source map must be provided together")
        loader = inspect_image(private_regular(loader_bin, "private loader").read_bytes(), "optional_loader")
        if loader["flash_mode"] != "DIO" or loader["flash_size_bytes_from_header"] != 0x400000:
            raise PacketError("Loader has incompatible chip flash parameters")
        loader_map, loader_end = platformio_layout(loader_ini, "env:esp12e_recovery")
        if loader_map != "eagle.flash.4m1m.ld":
            raise PacketError("Unexpected transient-loader flash map")
        hop = staging_model(loader["size_bytes"], candidate["size_bytes"], loader_end)
        affected = inferred_stock_fs_staging_overlap(hop)
        if affected <= 0:
            raise PacketError("Loader stage's inferred manufacturer file damage must not be hidden")
        alternative = {
            "provided": True, "loader_bytes": loader["size_bytes"],
            "loader_sha256": loader["sha256"], "second_hop": hop,
            "inferred_original_file_sectors_affected_bytes": affected,
            "not_a_stock_data_preserving_fallback": True,
        }
    return {
        "status": "PRIVATE_OFFLINE_PACKET_CHECKED__OWNER_FLASH_NOT_AUTHORIZED",
        "official_application": {
            "bytes": original_info["size_bytes"],
            "sha256": metadata["firmware_sha256"],
            "official_zip_sha256": metadata["zip_sha256"],
            "full_owner_flash_backup": False,
        },
        "reviewed_candidate": {
            "bytes": candidate["size_bytes"],
            "sha256": candidate["sha256"],
            "header": {k: candidate[k] for k in ("flash_mode","flash_size_flag","flash_frequency","segments")},
            "source_map": linked_map,
            "expected_first_boot": "FSLESS_NATIVE_UI_V2",
        },
        "private_pair_checks": security,
        "direct_install_model": direct,
        "running_shino_to_oem_application_model": return_oem,
        "optional_two_hop_model": alternative,
        "unproven": [
            "Actual owner stock V9.0.44 updater/slot acceptance and physical flash ID",
            "The owner's exact factory filesystem sector map and whether the OEM updater writes other areas",
            "Hardware boot, LCD/WPA2/Digest routes, PC telemetry and OEM return on physical unit",
            "No working Wi-Fi recovery if application does not boot",
            "This factory package is NOT a full owner-specific 4-MiB backup",
            "Arduino updater model/geometry does not prove power-cut safety or preservation of original assets",
        ],
        "independent_esptool_checksum_required_before_real_install": True,
        "physical_device_contacted": False,
        "files_uploaded": False,
        "permission_to_flash": False,
    }


def main() -> int:
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--official-zip", type=Path, required=True)
    p.add_argument("--manifest", type=Path, default=Path(__file__).resolve().parent.parent /
                   "recovery/factory_ota_v9_0_44.json")
    p.add_argument("--candidate-bin", type=Path, required=True)
    p.add_argument("--policy", type=Path, required=True)
    p.add_argument("--credentials", type=Path, required=True)
    p.add_argument("--candidate-ini", type=Path, default=Path(__file__).resolve().parent.parent /
                   "firmware/platformio.ini")
    p.add_argument("--loader-bin", type=Path, help="Optional comparison only, NOT a fallback upload instruction")
    p.add_argument("--loader-ini", type=Path)
    p.add_argument("--out", type=Path, help="Create NEW sanitized JSON; refuse to overwrite existing report")
    args = p.parse_args()
    try:
        result = assess(args.official_zip, args.manifest, args.candidate_bin,
                        args.policy, args.credentials, args.candidate_ini,
                        args.loader_bin, args.loader_ini)
        output = json.dumps(result, indent=2) + "\n"
        if args.out:
            with args.out.open("x", encoding="utf-8") as stream:
                stream.write(output)
            print(f"Sanitized offline packet assessment written: {args.out}")
        else:
            print(output, end="")
    except (PacketError, FactoryOtaError, PreflightError, OSError, ValueError, KeyError) as exc:
        p.exit(1, f"PRIVATE FIRST-INSTALL GATE CLOSED: {exc}\n")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
