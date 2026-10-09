"""Local-only M9 owner identity and private transition firmware preflight.

No network/device/COM. Never uploads firmware and never authorizes physical flash.
All secrets stay under git-ignored research-local/m9-owner/.
"""
import argparse
import configparser
import hashlib
import json
import os
import re
import secrets
import shutil
import subprocess
import sys
from pathlib import Path

from m9_stagea_build import ROOT, ENV
from m9_signed_release import validate_image
from shino_transition_build import prepare as prepare_public, replace_once

OWNER = ROOT / "research-local" / "m9-owner"
SECRETS = OWNER / "owner-credentials.json"
FIELDS = ("device", "build", "ap_psk", "api_token", "digest_password", "maintenance_password")
PUBLIC = {
    "device": "0123456789abcdef",
    "build": "a" * 64,
    "maintenance_key": "1" * 64,
    "ap_psk": "PUBLIC-INERT-AP-FIXTURE",
    "api_token": "PUBLIC-INERT-TOKEN-FIXTURE-00000000",
    "digest_password": "PUBLIC-INERT-LAB-HTTP-FIXTURE",
}


def under_private(path):
    path = Path(path).resolve()
    assert OWNER.resolve() in path.parents, "Private files must remain in ignored research-local/m9-owner"
    assert not path.is_symlink()
    return path


def validate_owner(config):
    if not isinstance(config, dict) or set(config) != set(FIELDS):
        raise ValueError("Owner identity schema mismatch")
    if not re.fullmatch(r"[0-9a-f]{16}", config["device"]):
        raise ValueError("Invalid device ID")
    if not re.fullmatch(r"[0-9a-f]{64}", config["build"]):
        raise ValueError("Invalid build ID")
    for field in ("ap_psk", "api_token", "digest_password", "maintenance_password"):
        text = config[field]
        if not isinstance(text, str) or not re.fullmatch(r"[A-Za-z0-9_-]{32,120}", text):
            raise ValueError("Invalid credential: " + field)
        if text in PUBLIC.values():
            raise ValueError("Public fixture credential rejected")
    if len(set(config[f] for f in FIELDS)) != len(FIELDS):
        raise ValueError("Duplicate owner values")
    return config


def initialize():
    OWNER.mkdir(parents=True, exist_ok=True)
    if SECRETS.exists() or SECRETS.is_symlink():
        raise ValueError("Owner secrets already exist: refuse overwrite/rotation")
    data = validate_owner({
        "device": secrets.token_hex(8),
        "build": secrets.token_hex(32),
        "ap_psk": secrets.token_urlsafe(24),
        "api_token": secrets.token_urlsafe(36),
        "digest_password": secrets.token_urlsafe(36),
        "maintenance_password": secrets.token_urlsafe(48),
    })
    # O_EXCL prevents existing credential loss. Path is ignored by Git.
    fd = os.open(SECRETS, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as out:
            json.dump(data, out, indent=2)
            out.write("\n")
    except BaseException:
        SECRETS.unlink(missing_ok=True)
        raise
    print("OWNER_IDENTITY_CREATED_LOCAL_ONLY")
    print("Secrets: research-local/m9-owner/owner-credentials.json")
    print("Keep the password file private and backed up. Newly generated AP/Digest credentials")
    print("will require a corresponding Windows LINK reconnection after eventual installation.")


def load():
    if SECRETS.is_symlink() or not SECRETS.is_file() or SECRETS.stat().st_size > 4096:
        raise ValueError("Expected private owner credential file not found")
    return validate_owner(json.loads(SECRETS.read_text(encoding="utf-8")))


def private_source(directory, config):
    """Make one owner-specific graph; only in ignored local staging directory."""
    directory = under_private(directory)
    directory = prepare_public(directory)
    src = directory / "src/boot/M9NormalStageA.cpp"
    body = src.read_text(encoding="utf-8")
    key = hashlib.sha256(config["maintenance_password"].encode("utf-8")).hexdigest()
    for before, after in (
        (f'ReviewDevice[]="{PUBLIC["device"]}"', f'ReviewDevice[]="{config["device"]}"'),
        ('"a" * 64', 'never-used'),
        ('"aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa"',
         f'"{config["build"]}"'),
        ('"1111111111111111111111111111111111111111111111111111111111111111"',
         f'"{key}"'),
        ("if(!armGate.consume(p) || !p.dryRun)return false;",
         "if(!armGate.consume(p))return false;"),
        ("c={p.device,p.build,p.key,true,true};return true;",
         "c={p.device,p.build,p.key,true,p.dryRun};return true;"),
        ('    if(!dryRun){respond(403,"{\\\"error\\\":\\\"PUBLIC_REVIEW_DRY_RUN_ONLY\\\"}");return;}',
         '    // Private HMAC, one-use challenge and a prior qualified probe gate INSTALL.'),
    ):
        if before == '"a" * 64':
            continue
        body = replace_once(body, before, after)
    src.write_text(body, encoding="utf-8")
    policy = directory / "include/shino_private_policy.h"
    policy_text = policy.read_text(encoding="utf-8")
    for field, macro in (
        ("ap_psk", "SHINO_SETUP_AP_PSK"),
        ("api_token", "SHINO_BOOTSTRAP_API_TOKEN"),
        ("digest_password", "SHINO_RESCUE_HTTP_PASSWORD"),
    ):
        policy_text = replace_once(policy_text, f'#define {macro} "{PUBLIC[field]}"',
                                   f'#define {macro} "{config[field]}"')
    policy.write_text(policy_text, encoding="utf-8")
    version = directory / "include/project_version.h"
    version.write_text('#pragma once\n#define PROJECT_VER "SHINO-M9-OWNER"\n'
                       'static const char PROJECT_VER_STR[]="SHINO-M9-OWNER";\n',
                       encoding="utf-8")
    ini = directory / "platformio.ini"
    ini_text = ini.read_text(encoding="utf-8")
    ini_text = replace_once(ini_text, "-DSHINO_PUBLIC_INERT_REVIEW=1",
                            "-DSHINO_OWNER_PRIVATE_TRANSITION=1")
    ini.write_text(ini_text, encoding="utf-8")
    meta = directory / "public-inputs.json"
    info = json.loads(meta.read_text(encoding="utf-8"))
    info["public_inert_hmac_credential_only"] = False
    info["public_install_denied"] = False
    info["owner_private_identity"] = True
    info["not_flashable_or_owner_qualified"] = True
    # Never leave credential material or owner secrets in JSON/reports.
    meta.write_text(json.dumps(info, indent=2) + "\n", encoding="utf-8")
    forbidden = [PUBLIC["device"], PUBLIC["build"], PUBLIC["maintenance_key"],
                 PUBLIC["ap_psk"], PUBLIC["api_token"], PUBLIC["digest_password"]]
    assert all(v not in body for v in forbidden)
    assert all(v not in policy_text for v in forbidden)
    assert "-DSHINO_PUBLIC_INERT_REVIEW=1" not in ini_text
    assert "PUBLIC_REVIEW_DRY_RUN_ONLY" not in body
    assert (directory / "include/shino_private_policy.h").is_file()
    return directory


def build():
    config = load()
    OWNER.mkdir(parents=True, exist_ok=True)
    directory = OWNER / "transition-build"
    if directory.exists() or directory.is_symlink():
        raise ValueError("Existing private transition build: refuse overwrite (archive offline first)")
    directory = private_source(directory, config)
    pio = shutil.which("pio") or shutil.which("platformio")
    if not pio:
        raise RuntimeError("PlatformIO not installed; source generated only")
    log_path = OWNER / "transition-build.log"
    with log_path.open("x", encoding="utf-8") as log:
        run = subprocess.run([pio, "run", "-d", str(directory), "-e", ENV],
                             cwd=ROOT, stdin=subprocess.DEVNULL,
                             stdout=log, stderr=subprocess.STDOUT, check=False)
    if run.returncode:
        raise RuntimeError("Private build FAILED; inspect local log, DO NOT FLASH")
    binpath = directory / ".pio/build" / ENV / "firmware.bin"
    raw = binpath.read_bytes()
    validate_image(raw)
    result = {
        "status": "PRIVATE_BUILD_OFFLINE_PHYSICAL_NO_GO",
        "git_head": subprocess.check_output(["git", "rev-parse", "HEAD"], cwd=ROOT,
                                             text=True).strip(),
        "firmware_sha256": hashlib.sha256(raw).hexdigest(),
        "bytes": len(raw),
        "build_id": config["build"],
        "layout": "4m2m",
        "public_fixture": False,
        "device_contacts": 0, "serial_io": 0, "flash_writes": 0,
        "physical_flash_authorized": False,
        "network_ota_install_authorized": False,
        "native_memory": "NOT_MEASURED",
        "private_credentials_not_in_report": True,
    }
    report = OWNER / "transition-report.json"
    report.write_text(json.dumps(result, indent=2) + "\n", encoding="utf-8")
    manifest = { "schema": 1, "family": "SHINO-StageA", "layout": "4m2m",
                 "protocol": "shino-install-1", "bytes": len(raw),
                 "sha256": result["firmware_sha256"], "build_id": config["build"] }
    (OWNER / "transition-manifest.json").write_text(json.dumps(manifest, indent=2)+"\n",
                                                    encoding="utf-8")
    print("PRIVATE_TRANSITION_BUILD_OK — PHYSICAL_FLASH_NO_GO")
    print("Firmware bytes:", len(raw), "SHA256:", result["firmware_sha256"])
    print("Report: research-local/m9-owner/transition-report.json")
    print("No device access. Do not upload this candidate.")


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("operation", choices=("init", "build"))
    args = ap.parse_args()
    if args.operation == "init":
        initialize()
    else:
        build()


if __name__ == "__main__":
    try:
        main()
    except (OSError, ValueError, AssertionError, RuntimeError) as exc:
        print("OWNER TRANSITION HOLD:", exc, file=sys.stderr)
        sys.exit(2)
