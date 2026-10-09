"""Create new local M9 owner-private review binaries, NEVER a device operation.

uart-repair: identical owner AP/Digest/maintenance credentials, corrected graph.
wifi-smoke: new build identity, same private credentials, a *future* OTA target.
All outputs are fresh git-ignored dirs, no original build/backup is touched.
"""
import argparse
import hashlib
import json
import secrets
import shutil
import subprocess
import sys
from pathlib import Path

from m9_stagea_build import ROOT, ENV
from m9_signed_release import validate_image
from shino_owner_transition import OWNER, load, check_checkout, private_source, validate_owner
from shino_wifi_resources import one

OLD_INSTALLED_SHA = "9de1ffe3abbe039bc3ed0f8eb78d1336137a5d1caae74383443fa736d1b9764d"
TARGETS = {
    "uart-repair": "m9-uart-repair-build",
    "wifi-smoke": "m9-wifi-smoke-build",
}


def build(kind):
    if kind not in TARGETS:
        raise ValueError("Unknown offline output mode")
    check_checkout()
    config = dict(load())
    if kind == "wifi-smoke":
        # A future authenticated OTA transfer MUST not reuse the running build
        # ID. Never rotate the Wi-Fi AP/Digest/maintenance secrets.
        config["build"] = secrets.token_hex(32)
        if config["build"] == load()["build"]:
            raise ValueError("Unique future OTA build ID required")
        validate_owner(config)
    target = OWNER / TARGETS[kind]
    report = OWNER / (TARGETS[kind] + "-report.json")
    manifest = OWNER / (TARGETS[kind] + "-manifest.json")
    log = OWNER / (TARGETS[kind] + ".log")
    # No unattended re-build, no accidental delete of old receipts/binaries.
    for item in (target, report, manifest, log):
        if item.exists() or item.is_symlink():
            raise ValueError("Refusing to overwrite existing private output: " + item.name)
    OWNER.mkdir(parents=True, exist_ok=True)
    pio = shutil.which("pio") or shutil.which("platformio")
    if not pio:
        raise RuntimeError("PlatformIO unavailable; no candidate produced")
    private_source(target, config)
    with log.open("x", encoding="utf-8") as output:
        proc = subprocess.run([pio, "run", "-d", str(target), "-e", ENV],
                              cwd=ROOT, stdin=subprocess.DEVNULL, stdout=output,
                              stderr=subprocess.STDOUT, timeout=1200, check=False)
    if proc.returncode:
        raise RuntimeError("Private M9 build failed; no candidate or device permission")
    path = target / ".pio/build" / ENV / "firmware.bin"
    raw = path.read_bytes()
    validate_image(raw)
    resources = one(target)
    sha = hashlib.sha256(raw).hexdigest()
    if sha == OLD_INSTALLED_SHA:
        raise ValueError("Old, uncorrected owner image unexpectedly reproduced")
    if resources["bin_bytes"] != len(raw) or resources["noinit"] != 56:
        raise ValueError("Unexpected actual native resource measurements")
    if not 64000 <= len(raw) <= 0xFEFF0:
        raise ValueError("Image exceeds strict OTA application bounds")
    head = subprocess.check_output(["git", "rev-parse", "HEAD"], cwd=ROOT,
                                   text=True).strip()
    metadata = {
        "status": "NEW_PRIVATE_IMAGE_VERIFIED_OFFLINE_PHYSICAL_NO_GO",
        "kind": kind,
        "source_commit": head,
        "firmware_sha256": sha,
        "firmware_bytes": len(raw),
        "linked_flash": resources["linked_flash"],
        "static_ram": resources["static_ram"],
        "noinit": resources["noinit"],
        "build_id": config["build"],
        "same_wifi_and_digest_credentials": True,
        "same_maintenance_secret": True,
        "different_firmware_from_installed": True,
        "runtime_heap_tcp_stack": "NOT_MEASURED",
        "physical_flash_authorized": False,
        "live_ota_authorized": False,
        "network_contacts": 0,
        "serial_io": 0,
        "flash_writes": 0,
        "private_credentials_in_report": False,
    }
    summary = {
        "schema": 1,
        "family": "SHINO-StageA",
        "layout": "4m2m",
        "protocol": "shino-install-1",
        "bytes": len(raw),
        "sha256": sha,
        "build_id": config["build"],
    }
    report.write_text(json.dumps(metadata, indent=2) + "\n", encoding="utf-8")
    manifest.write_text(json.dumps(summary, indent=2) + "\n", encoding="utf-8")
    print("PASS_OFFLINE_PHYSICAL_NO_GO", kind, len(raw), sha)
    print("Report (safe to share):", report.relative_to(ROOT))
    print("Private BIN/credentials MUST NOT be uploaded to GitHub or chat")


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("kind", choices=tuple(TARGETS))
    opts = ap.parse_args()
    try:
        build(opts.kind)
        return 0
    except (OSError, ValueError, RuntimeError, subprocess.SubprocessError) as exc:
        print("SHINO M9 OWNER PRIVATE BUILD HOLD:", exc, file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
