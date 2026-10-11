"""Prepare ONE minimal owner-private B4 release from the qualified installed B3.

This is a LOCAL BUILD ONLY. No AP/HTTP, UART, serial, OTA, RTC, reboot, Wi-Fi
switch or flash access. No updater command is executed. B4 uses the frozen B3
firmware sources; its generated private build identity makes a distinct image.
Any physical OTA requires a separate owner decision on that exact SHA.
"""
from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
import subprocess

B3_BYTES = 407552
B3_SHA256 = "e1d03b44ab3bd0b3693285ba6c4033de8a2925c55f2e86a3924185d779eb0042"
B3_BUILD_ID = "6c2d07928b341ad0097f3ffb68f14bd6bde010000c9ee9c7dd794af2814ac096"
B3_SOURCE_COMMIT = "26e1ace98dcd4713c4a227c3847bc4b5cf74dee5"
BRANCH = "feature/shino-tv-b3-telemetry-scratch-experiment"
FROZEN_SOURCES = ("ota/firmware/Normal.cpp", "ota/firmware/ShinoHttpOta.h")
ENV = "esp12e_m9_4m2m_normal_qualification"


class B4Hold(ValueError):
    pass


def verify_checkout(root: Path) -> str:
    def git(*args):
        return subprocess.check_output(
            ["git", *args], cwd=root, text=False, stderr=subprocess.DEVNULL,
            timeout=20,
        ).strip()
    try:
        if git("branch", "--show-current").decode() != BRANCH:
            raise B4Hold("Wrong review branch")
        if git("status", "--porcelain"):
            raise B4Hold("Uncommitted changes: stop before private build")
        head = git("rev-parse", "HEAD").decode()
        if len(head) != 40 or any(c not in "0123456789abcdef" for c in head):
            raise B4Hold("Source HEAD unavailable")
        # This first OTA experiment deliberately excludes new firmware logic.
        # Different B4 bytes come only from the new private release identity.
        for name in FROZEN_SOURCES:
            frozen = subprocess.check_output(
                ["git", "show", B3_SOURCE_COMMIT + ":" + name],
                cwd=root, stderr=subprocess.DEVNULL, timeout=20,
            )
            if (root / name).read_bytes().replace(b"\r\n", b"\n") != frozen.replace(b"\r\n", b"\n"):
                raise B4Hold("B3 firmware source changed: " + name)
        return head
    except (OSError, subprocess.CalledProcessError, subprocess.TimeoutExpired) as exc:
        raise B4Hold("Cannot verify clean pinned source checkout") from None


def check_b3(m: dict, raw: bytes, device: str) -> None:
    if (m.get("bytes") != B3_BYTES or len(raw) != B3_BYTES
            or m.get("sha256") != B3_SHA256
            or hashlib.sha256(raw).hexdigest() != B3_SHA256
            or m.get("build_id") != B3_BUILD_ID
            or m.get("device") != device):
        raise B4Hold("Installed B3 packet mismatch: stop")


def check_b4(m: dict, raw: bytes, report: dict, old: dict, head: str) -> None:
    if (report.get("private") is not True
            or report.get("source_dirty") is not False
            or report.get("source_commit") != head
            or m.get("device") != old["device"]
            or m.get("sha256") == B3_SHA256
            or m.get("build_id") == B3_BUILD_ID
            or not 64000 <= len(raw) <= 0xFEFF0
            or not report.get("layout_symbols") == {
                "_FS_start": 0x40400000, "_FS_end": 0x405FA000,
                "_EEPROM_start": 0x405FB000,
            }
            or report.get("json_arena_bytes") != 768
            or report.get("json_document_heap_fallback") is not False
            or report.get("physical") != "NOT_RUN"
            or report.get("native_heap_peak_measured") is not False):
        raise B4Hold("B4 private build identity, layout or provenance invalid")
    stage = 0x200000 - ((len(raw) + 4095) & ~4095)
    running_end = (B3_BYTES + 4095) & ~4095
    if stage < running_end + 4096:
        raise B4Hold("B4 staging overlaps installed B3 or safety sector")


def prepare(root: Path, owner: Path, output: Path, *,
            inspect=None, load=None, build=None, checker=verify_checkout):
    """Prepare new private packet, never upload. Injection is offline-test only."""
    root = root.resolve()
    owner = owner.resolve()
    if output.is_symlink() or output.exists() or output.parent.resolve() != owner:
        raise B4Hold("Fresh direct owner-private output directory required")
    if not owner.is_dir() or owner.is_symlink():
        raise B4Hold("Owner-private directory unavailable")
    # No side effects (including directory creation) before preflight.
    head = checker(root)
    if inspect is None:
        from sys import path as sys_path
        sys_path.insert(0, str(root / "companion"))
        from shino_update import inspect as inspect
    if load is None:
        from sys import path as sys_path
        sys_path.insert(0, str(root / "tools"))
        from shino_owner_transition import load as load
    if build is None:
        from sys import path as sys_path
        sys_path.insert(0, str(root / "tools"))
        from shino_http_ota_build import build as build
    old_dir = owner / "b3-owner-20261011-120209" / "B3"
    old_bin = old_dir / ".pio" / "build" / ENV / "firmware.bin"
    old_manifest = old_dir / "release.json"
    old, old_raw = inspect(old_bin, old_manifest)
    identity = load()
    check_b3(old, old_raw, identity["device"])
    # The existing builder accepts only a fresh directory and does not
    # contain serial/network/update installation code. No OTA runner here.
    output.mkdir(mode=0o700)
    target = output / "B4"
    result = build(target, True)
    m, raw = inspect(target / ".pio" / "build" / ENV / "firmware.bin",
                     target / "release.json")
    check_b4(m, raw, result, old, head)
    if hashlib.sha256(identity["maintenance_password"].encode()).digest() not in raw:
        raise B4Hold("B4 does not retain owner HMAC key")
    for name in ("ap_psk", "api_token", "digest_password"):
        if identity[name].encode() not in raw:
            raise B4Hold("B4 does not retain owner communication credentials")
    # Only two newly created, ignored local files. No private JSON to Git.
    summary = {
        "status": "B4_OWNER_PRIVATE_CANDIDATE_OFFLINE_ONLY",
        "ota_offline_gate": "HOLD",
        "physical_install_authorized": False,
        "source_commit": head,
        "installed_B3_sha256": B3_SHA256,
        "installed_B3_bytes": B3_BYTES,
        "candidate_B4_sha256": m["sha256"],
        "candidate_B4_bytes": m["bytes"],
        "staging_start": 0x200000 - ((len(raw) + 4095) & ~4095),
        "fs_start": 0x200000,
        "native_ota_memory_measured": False,
        "device_contacts": 0,
        "ota_posts": 0,
        "flash_writes": 0,
    }
    (output / "B4-OFFLINE-REVIEW.json").write_text(
        json.dumps(summary, indent=2) + "\n", encoding="utf-8"
    )
    (output / "NEXT-OWNER-DECISION.md").write_text(
        "# SHINO // TV B3 → B4 — not yet authorized\n\n"
        "Installed B3 SHA256: `" + B3_SHA256 + "`\n\n"
        "Prepared B4 SHA256: `" + m["sha256"] + "`\n\n"
        "Review release.json, BIN, static memory/stack-paths.json and the "
        "B3 OTA offline HOLD before approving a one-shot upload.\n\n"
        "**No physical OTA is authorized by this package.** The installed "
        "B3 receiver must execute the first upload, so B4 improvements alone "
        "cannot correct B3's unmeasured native upload stack/heap. eboot "
        "copy is destructive and has no atomic rollback.\n\n"
        "After a separate exact-SHA owner approval, use the existing "
        "`companion/shino_update.py` with an exact current SHA256 pin, "
        "fresh attempt marker and fresh receipt; no automatic retry. "
        "Keep the 4MiB backup and physical UART recovery plan accessible.\n",
        encoding="utf-8",
    )
    return summary


def main(argv=None):
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--output", type=Path, required=True,
                   help="NEW git-ignored directory directly under research-local/m9-owner")
    args = p.parse_args(argv)
    root = Path(__file__).resolve().parents[1]
    owner = root / "research-local" / "m9-owner"
    try:
        result = prepare(root, owner, args.output.resolve())
    except (B4Hold, ValueError, OSError, RuntimeError) as exc:
        # No credentials, paths or raw exception data in failure messages.
        print("B4_OFFLINE_HOLD:", str(exc) if isinstance(exc, B4Hold) else "Build/preflight failed")
        return 2
    print("B4_PRIVATE_CANDIDATE_PREPARED_OFFLINE — OTA_HOLD")
    print("Installed B3:", result["installed_B3_sha256"])
    print("Candidate B4:", result["candidate_B4_sha256"])
    print("Review:", args.output / "B4-OFFLINE-REVIEW.json")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
