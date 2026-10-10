#!/usr/bin/env python3
"""Phase C: static installed-source identity and PRINT-ONLY command packet.

Never imports esptool/serial or executes a command. Source PASS is not permission.
"""
from __future__ import annotations

import argparse
import configparser
import hashlib
import importlib.metadata
import json
import os
import platform
import struct
import sys
from pathlib import Path

from m9_first_migration import application_extent
from m9_first_migration import arduino_crc
from m9_stage1_readback_verify import candidate_bytes, regular_file

MANIFEST = Path(__file__).with_name("m9_executor_sources.json")
FROZEN_SHA = "cd99139121fa47fedd6286a185fb16e8fb9e120280ecd75f1c6b41b905e31011"
FROZEN_BYTES = 399168


class ExecutorError(ValueError):
    """Re-review required; never proceed to physical execution."""


def canonical_hash(path: Path) -> str:
    return hashlib.sha256(regular_file(path).read_bytes().replace(b"\r\n", b"\n")).hexdigest()


def check_hashes(root: Path, expected: dict) -> dict:
    actual = {}
    for name, digest in expected.items():
        path = Path(name)
        if path.is_absolute() or ".." in path.parts:
            raise ExecutorError("Unsafe source manifest path")
        actual[name] = canonical_hash(root / path)
        if actual[name] != digest:
            raise ExecutorError(f"Pinned source changed: {name}")
    return actual


def aggregate(files: dict) -> str:
    blob = "".join(f"{name}\0{files[name]}\n" for name in sorted(files))
    return hashlib.sha256(blob.encode("utf-8")).hexdigest()


def inspect_sources(module_root: Path, core_root: Path | None = None) -> dict:
    manifest = json.loads(MANIFEST.read_text(encoding="utf-8"))
    files = check_hashes(module_root, manifest["esptool_files"])
    observed = {p.relative_to(module_root).as_posix() for p in module_root.rglob("*")
                if p.is_file() and p.suffix in (".py", ".json", ".md")}
    if observed != set(files):
        raise ExecutorError("Installed esptool source inventory differs from pinned package")
    # Digest pins the complete package; these checks make the reviewed assumptions explicit.
    loader = (module_root / "loader.py").read_text(encoding="utf-8")
    cmds = (module_root / "cmds.py").read_text(encoding="utf-8")
    required_loader = ('WRITE_FLASH_ATTEMPTS = 2',
                       'cfg.getint("write_block_attempts", 3)',
                       'cfg.getint("connect_attempts", 7)', 'mode="default-reset"')
    required_cmds = ('except SerialException:', 'original_image = image',
                     'image = original_image', 'esp.connect()',
                     'esp.flash_begin(uncsize, address, encrypted_write=encrypted)',
                     'if (flash_mode, flash_freq, flash_size) == ("keep",) * 3:',
                     'esp.flash_md5sum(base_address, base_size)')
    if any(token not in loader for token in required_loader) or any(
            token not in cmds for token in required_cmds):
        raise ExecutorError("Reviewed retry/header/verification assumptions missing")
    if manifest["eboot_cold_start_gate"] != "HOLD":
        raise ExecutorError("RTC conclusion cannot be promoted without a new reviewed gate")
    core_checked = False
    if core_root is not None:
        check_hashes(core_root, manifest["arduino_files"])
        package = json.loads((core_root / "package.json").read_text(encoding="utf-8"))
        if package["version"] != "3.30102.0":
            raise ExecutorError("Expected pinned PlatformIO Core 3.1.2 package")
        core_checked = True
    return {"status": "PASS_PINNED_OFFLINE_SOURCE_IDENTITY",
            "esptool_package_digest": aggregate(files), "source_files_checked": len(files),
            "stub_version": "2", "stub_release": manifest["stub_release"],
            "arduino_sources_checked": core_checked,
            "eboot_cold_start_gate": "HOLD", "esptool_executor_gate": "PASS",
            "esptool_pass_scope": "bounded official command source model; physical assumptions unresolved",
            "physical_authorization": False, "serial_io_performed": False}


def check_configuration() -> list[str]:
    # Mirror audited esp-pylib 1.1.5 default search; reject any esptool section.
    if os.environ.get("ESPTOOL_CFGFILE") or os.environ.get("ESPTOOL_STUB_VERSION"):
        raise ExecutorError("Clear esptool configuration/stub environment overrides")
    home = Path.home()
    user = home / "AppData/Local/esptool" if os.name == "nt" else home / ".config/esptool"
    inspected = []
    for directory in (Path.cwd(), user, home):
        for name in ("esptool.cfg", "setup.cfg", "tox.ini"):
            path = directory / name
            if path.exists():
                regular_file(path)
                parser = configparser.ConfigParser()
                with path.open(encoding="utf-8") as handle:
                    parser.read_file(handle)
                if parser.has_section("esptool"):
                    raise ExecutorError(f"Custom esptool configuration is not qualified: {path}")
                inspected.append(str(path.resolve()))
    return inspected


def installed_identity(core_root: Path | None = None) -> dict:
    manifest = json.loads(MANIFEST.read_text(encoding="utf-8"))
    dist = importlib.metadata.distribution("esptool")
    if dist.version != "5.4.0":
        raise ExecutorError("Exactly esptool 5.4.0 required")
    for name, version in (("esp-pylib", manifest["esp_pylib_version"]),
                          ("pyserial", manifest["pyserial_version"])):
        if importlib.metadata.version(name) != version:
            raise ExecutorError(f"Unreviewed dependency version: {name}")
    root = Path(dist.locate_file("esptool")).resolve()
    support = Path(importlib.metadata.distribution("esp-pylib").locate_file("esp_pylib/config.py"))
    if canonical_hash(support) != manifest["esp_pylib_config_sha256"]:
        raise ExecutorError("Config loader source differs from pinned audit")
    report = inspect_sources(root, core_root)
    # setup-python/POSIX may invoke a symlink; hash the real executable bytes.
    executable = regular_file(Path(sys.executable).resolve())
    report.update({"python_invoked_path": sys.executable,
                   "python_executable": str(executable),
                   "python_version": platform.python_version(),
                   "python_executable_sha256": hashlib.sha256(executable.read_bytes()).hexdigest(),
                   "esptool_version": dist.version, "esptool_module_path": str(root),
                   "config_files_without_esptool_section": check_configuration(),
                   "python_isolated_mode_required_for_physical_commands": True})
    return report


def preflight(candidate: Path, expected_sha256: str, expected_python_sha256: str,
              expected_python_version: str, expected_module_root: Path,
              core_root: Path) -> dict:
    report = installed_identity(core_root)
    if (report["python_executable_sha256"] != expected_python_sha256.lower()
            or report["python_version"] != expected_python_version
            or Path(report["esptool_module_path"]) != expected_module_root.resolve()):
        raise ExecutorError("External interpreter/module identity does not match")
    data, inspected = candidate_bytes(candidate, expected_sha256)
    if expected_sha256.lower() != FROZEN_SHA or len(data) != FROZEN_BYTES:
        raise ExecutorError("Only the unchanged Phase B LOCAL frozen candidate is proposed")
    report.update({"status": "PASS_OFFLINE_EXECUTOR_IDENTITY_PHYSICAL_HOLD",
                   "candidate_path": str(candidate.resolve()), "candidate_bytes": len(data),
                   "candidate_sha256": inspected["sha256"], "stage1_target_address": 0,
                   "rounded_extent": inspected["sector_rounded_write_extent"],
                   "expected_physical_flash_bytes": 0x400000,
                   "command_policy": render_packet()["policy"],
                   "physical_runtime_gate": "NOT_RUN", "physical_write": "HOLD"})
    return report


def retry_extent_model(size: int, deliveries: list[int]) -> dict:
    """Model clamped sequential stub writes, including duplicated packets.

    Does not assert packet idempotence: lost ACK replay can corrupt payload.
    No C code or protocol is executed. Hash/readback still mandatory.
    """
    rounded = application_extent(size)
    if size % 4 or any(type(value) is not int or not 0 < value <= 0x4000 for value in deliveries):
        raise ExecutorError("Only aligned reviewed packet lengths are modeled")
    attempts = []
    for _ in range(2):
        cursor = 0
        writes = []
        for length in deliveries:
            consumed = min(length, size - cursor)
            if consumed:
                writes.append([cursor, cursor + consumed])
                cursor += consumed
        # Erases are either aligned 64KiB blocks or 4KiB sectors, bounded by R.
        erases, cursor = [], 0
        while cursor < rounded:
            length = 0x10000 if cursor % 0x10000 == 0 and rounded - cursor >= 0x10000 else 0x1000
            erases.append([cursor, cursor + length])
            cursor += length
        attempts.append({"begin_address": 0, "begin_size": size, "writes": writes,
                         "possible_erase_ranges": erases})
    return {"attempts": attempts, "destructive_end_exclusive": rounded,
            "payload_correctness_proven": False, "physical_authorization": False}


def rtc_command_model(data: bytes) -> dict:
    """Synthetic 128-byte RTC parser model, not a hardware read/clear operation."""
    if len(data) != 128:
        raise ExecutorError("Exactly one synthetic 128-byte RTC command required")
    magic, action = struct.unpack_from("<II", data)
    valid = magic & 0xFFFFF000 == 0xEB001000 and arduino_crc(data[:124]) == struct.unpack_from("<I", data, 124)[0]
    return {"valid_command": valid, "pending_copy": valid and action == 1,
            "default_load_app_zero": not valid, "reset_reason_checked": False,
            "power_on_guarantees_invalid_command": False, "eboot_cold_start_gate": "HOLD"}


def render_packet() -> dict:
    python = '& "<PYTHON_EXE>"'  # PowerShell call operator; strings are never executed here.
    base = (python + ' -I -m esptool --chip esp8266 --port "<PORT>" --baud 115200 '
            '--stub-version 2 --before no-reset --after no-reset-stub --connect-attempts 1 ')
    keep = '--flash-mode keep --flash-freq keep --flash-size keep --no-compress '
    local = python + ' '
    digest = '--expected-sha256 "<EXPECTED_CANDIDATE_SHA256>"'
    entries = [
        ("A", "LOCAL identity", local + 'tools/m9_executor_preflight.py --candidate "<CANDIDATE_BIN>" '
         + digest + ' --expected-python-sha256 "<EXPECTED_PYTHON_SHA256>" '
         '--expected-python-version "<EXPECTED_PYTHON_VERSION>" --expected-module-root "<ESPTOOL_MODULE_ROOT>" '
         '--core-root "<PINNED_CORE_ROOT>"'),
        ("B", "PHYSICAL chip", base + 'chip-id'),
        ("C", "PHYSICAL flash", base + 'flash-id'),
        ("D", "PHYSICAL fresh PRE", base + 'read-flash 0x000000 0x400000 "<PREWRITE_4MB_BIN>"'),
        ("E", "LOCAL immediate candidate preflight", local + 'tools/m9_first_migration.py "<CANDIDATE_BIN>"'),
        ("F", "PHYSICAL Stage1", base + 'write-flash ' + keep + '0x000000 "<CANDIDATE_BIN>"'),
        ("G", "PHYSICAL POST before normal boot", base + 'read-flash 0x000000 0x400000 "<POSTWRITE_4MB_BIN>"'),
        ("H", "LOCAL preservation", local + 'tools/m9_stage1_readback_verify.py "<CANDIDATE_BIN>" '
         '"<PREWRITE_4MB_BIN>" "<POSTWRITE_4MB_BIN>" ' + digest),
        ("I", "PHYSICAL manual", "FULL POWER OFF; remove GPIO0 strap while unpowered; cold first boot only after EBOOT gate closes"),
        ("J", "PHYSICAL separate MASTER authority", local + 'tools/m9_master_restore_preflight.py "<PRIVATE_MASTER_BIN>" '
         '--expected-sha256 "<PRIVATE_CUSTODY_SHA256>" --check-restore-gate --confirmed-chip esp8266 '
         '--confirmed-flash-bytes 4194304 --owner-authorized\n'
         + base + 'write-flash ' + keep + '0x000000 "<PRIVATE_MASTER_BIN>"'),
        ("K", "PHYSICAL rollback read / LOCAL comparison", base + 'read-flash 0x000000 0x400000 "<ROLLBACK_READBACK_BIN>"\n'
         + local + 'tools/m9_master_restore_preflight.py "<PRIVATE_MASTER_BIN>" --expected-sha256 "<PRIVATE_CUSTODY_SHA256>" '
         '--readback "<ROLLBACK_READBACK_BIN>"'),
    ]
    # E repeats A, which rehashes and checks external SHA immediately before F.
    entries[4] = ("E", "LOCAL immediate candidate rehash / identity", entries[0][2])
    return {"print_only": True, "physical_authorization": False,
            "policy": {"chip": "esp8266", "baud": 115200, "stub_version": "2",
                       "before": "no-reset", "after": "no-reset-stub", "connect_attempts": 1,
                       "whole_write_attempts": 2, "packet_attempts_default": 3,
                       "internal_reconnect_uses_default_reset": True,
                       "flash_mode": "keep", "flash_freq": "keep", "flash_size": "keep",
                       "compress": False, "erase_all": False, "stage2": False},
            "steps": [{"step": key, "purpose": purpose, "template": command,
                       "authorization": "NOT AUTHORIZED BY PHASE C" if "PHYSICAL" in purpose
                       else "LOCAL FILES ONLY"} for key, purpose, command in entries]}


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--print-commands", action="store_true")
    parser.add_argument("--source-only", action="store_true")
    parser.add_argument("--core-root", type=Path)
    parser.add_argument("--candidate", type=Path)
    parser.add_argument("--expected-sha256")
    parser.add_argument("--expected-python-sha256")
    parser.add_argument("--expected-python-version")
    parser.add_argument("--expected-module-root", type=Path)
    args = parser.parse_args()
    try:
        if args.print_commands:
            if args.source_only or args.candidate:
                parser.error("Command rendering is a separate print-only operation")
            report = render_packet()
        elif args.source_only:
            report = installed_identity(args.core_root)
        else:
            names = ("candidate", "expected_sha256", "expected_python_sha256",
                     "expected_python_version", "expected_module_root", "core_root")
            if any(getattr(args, name) is None for name in names):
                parser.error("Candidate, external SHA/interpreter identity, module and Core roots required")
            report = preflight(*(getattr(args, name) for name in names))
    except (ValueError, OSError, KeyError, importlib.metadata.PackageNotFoundError) as exc:
        parser.exit(1, f"EXECUTOR IDENTITY GATE CLOSED: {exc}\n")
    print(json.dumps(report, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
