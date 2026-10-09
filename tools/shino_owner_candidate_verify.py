"""Review an EXISTING owner-private Mission 9 BIN: local, read-only, no device.

Reads the private BIN, not private credentials. Hash / manifest / ELF / layout
must agree; verifies that source changes since original build were not firmware-
producing changes. Outputs a safe summary; NEVER grants physical flashing.
"""
import hashlib
import json
import subprocess
import sys
from pathlib import Path

from m9_signed_release import geometry, validate_image
from m9_stagea_build import ROOT, ENV
from shino_owner_transition import OWNER
from shino_wifi_resources import one

COMPANION = ROOT / "companion"
sys.path.insert(0, str(COMPANION))
from shino_install import inspect

CURRENT_STAGEA_BYTES = 399264
PINNED_LAYOUT = "4m2m"
SOURCE_GUARDS = ("firmware/", "experiments/", "tools/")
# These were added strictly for offline review after the known owner build.
# They are not firmware inputs. All other tooling changes require a new review.
REVIEW_ONLY = frozenset({
    "tools/m9_stagea_source_gate.py",
    "tools/m9_signed_ota_runner.py",
    "tools/shino_owner_candidate_verify.py",
    "tools/test_shino_owner_candidate_verify.py",
})


def git(*args):
    return subprocess.check_output(["git", *args], cwd=ROOT, text=True, stderr=subprocess.DEVNULL).strip()


def firmware_source_drift(built_from, head):
    modified = git("diff", "--name-only", built_from, head).splitlines()
    return [name for name in modified
            if name not in REVIEW_ONLY
            and any(name == prefix or name.startswith(prefix)
                    for prefix in SOURCE_GUARDS)]


def audit(owner=OWNER):
    owner = Path(owner).resolve()
    if owner != OWNER.resolve() or owner.is_symlink():
        raise ValueError("Only the ignored local owner workspace is permitted")
    root = owner / "transition-build"
    report = owner / "transition-report.json"
    manifest = owner / "transition-manifest.json"
    binary = root / ".pio/build" / ENV / "firmware.bin"
    if any(p.is_symlink() for p in (root, report, manifest, binary)):
        raise ValueError("Symlink input refused")
    if not report.is_file() or report.stat().st_size > 4096:
        raise ValueError("Owner report missing or oversized")
    data = json.loads(report.read_text(encoding="utf-8"))
    if data.get("status") != "PRIVATE_BUILD_OFFLINE_PHYSICAL_NO_GO":
        raise ValueError("Not an offline owner-private build")
    if data.get("public_fixture") is not False or data.get("layout") != PINNED_LAYOUT:
        raise ValueError("Invalid private firmware profile")
    if data.get("physical_flash_authorized") is not False or data.get("network_ota_install_authorized") is not False:
        raise ValueError("Physical permission unexpectedly present")
    if data.get("native_memory") != "NOT_MEASURED":
        raise ValueError("Runtime memory is falsely qualified")
    if type(data.get("bytes")) is not int or not 64000 <= data["bytes"] <= 0xFEFF0:
        raise ValueError("Application-only bounds failure")
    if data.get("device_contacts") != 0 or data.get("serial_io") != 0 or data.get("flash_writes") != 0:
        raise ValueError("Review must originate from no-contact build")
    selected, raw = inspect(binary, manifest)
    if data.get("firmware_sha256") != selected["sha256"] or data.get("bytes") != len(raw):
        raise ValueError("Existing private BIN differs from approved candidate receipt")
    if data.get("build_id") != selected["build_id"]:
        raise ValueError("Firmware build ID differs from receipt")
    validate_image(raw)
    delta = geometry(CURRENT_STAGEA_BYTES, len(raw))
    if delta["stage_end"] != 0x200000 or delta["filesystem_end"] != 0x3FA000:
        raise ValueError("Unexpected filesystem boundary")
    linked = one(root)
    for result, field in (("bin_bytes", "bytes"), ("linked_flash", "linked_flash"),
                          ("static_ram", "static_ram"), ("noinit", "noinit")):
        if linked[result] != data[field]:
            raise ValueError("Actual ELF/BIN memory mismatch: " + result)
    built_from = data.get("git_head")
    if not isinstance(built_from, str) or len(built_from) != 40:
        raise ValueError("Missing build source commit")
    head = git("rev-parse", "HEAD")
    if git("merge-base", built_from, head) != built_from:
        raise ValueError("Source commit not an ancestor of HEAD")
    build_related = firmware_source_drift(built_from, head)
    if build_related:
        raise ValueError("Private firmware-producing sources changed: " + ", ".join(build_related))
    return {
        "status": "EXISTING_PRIVATE_BIN_VERIFIED_OFFLINE_PHYSICAL_NO_GO",
        "firmware_sha256": hashlib.sha256(raw).hexdigest(),
        "firmware_bytes": len(raw),
        "source_commit": built_from,
        "review_head": head,
        "size_guard_bytes": delta["guard_bytes"],
        "staging_start": delta["stage_start"],
        "fs_start": delta["stage_end"],
        "fs_end": delta["filesystem_end"],
        "static_ram": data["static_ram"],
        "linked_flash": data["linked_flash"],
        "native_memory_high_water": "NOT_MEASURED",
        "physical_flash_authorized": False,
        "live_ota_authorized": False,
        "device_contacts": 0,
        "serial_io": 0,
        "flash_writes": 0,
        "credentials_read": False,
    }


def main():
    try:
        result = audit()
        out = OWNER / "candidate-verify.json"
        out.write_text(json.dumps(result, indent=2) + "\n", encoding="utf-8")
        print(json.dumps(result, indent=2))
        return 0
    except (OSError, ValueError, TypeError, subprocess.CalledProcessError) as exc:
        print("EXISTING PRIVATE BIN REVIEW: NO_GO — " + str(exc), file=sys.stderr)
        return 2


if __name__ == "__main__":
    sys.exit(main())
