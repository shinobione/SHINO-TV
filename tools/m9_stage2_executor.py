#!/usr/bin/env python3
"""Pinned Phase F source audit and PRINT ONLY packet; never imports esptool."""
from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path

from m9_executor_preflight import installed_identity, check_hashes
from m9_stage2_fs_candidate import (
    MANIFEST, FS_START, FS_END, FS_BYTES, FLASH_END, SECTOR, FS_BLOCK, FS_PAGE,
    geometry, local_path, Stage2Error,
)


def raw_write_bounds(address: int = FS_START, size: int = FS_BYTES,
                     deliveries: list[int] | None = None) -> dict:
    """Model pinned stub clamping, not a device/protocol execution or atomicity proof."""
    if type(address) is not int or type(size) is not int or (address, size) != (FS_START, FS_BYTES):
        raise Stage2Error("Only the exact Stage-2 FS address and length are qualified")
    erase_start = address // SECTOR * SECTOR
    erase_end = (address + size + SECTOR - 1) // SECTOR * SECTOR
    if deliveries is None:
        deliveries = [0x4000] * ((size + 0x3FFF) // 0x4000)
    if any(type(n) is not int or not 0 < n <= 0x4000 for n in deliveries):
        raise Stage2Error("Invalid modeled wire block")
    attempts = []
    for _ in range(2):  # pinned WRITE_FLASH_ATTEMPTS; same address/original image
        offset, remaining = address, size
        writes = []
        for delivered in deliveries:
            length = min(delivered, remaining)
            writes.append([offset, offset + length])
            offset += length
            remaining -= length
        if remaining:
            raise Stage2Error("Synthetic delivery is incomplete")
        attempts.append({"writes": writes, "end_exclusive": offset})
    erases, cursor = [], erase_start
    while cursor < erase_end:
        step = 0x10000 if cursor % 0x10000 == 0 and erase_end - cursor >= 0x10000 else SECTOR
        erases.append([cursor, cursor + step])
        cursor += step
    return {"erase_start": erase_start, "erase_end_inclusive": erase_end - 1,
            "erase_operations_max": erases, "attempts": attempts,
            "last_wire_block_bytes": deliveries[-1],
            "last_payload_bytes_default": FS_BYTES % 0x4000,
            "whole_write_attempts_max": 2, "packet_attempts_default": 3,
            "header_rewrite": False, "compression": False,
            "retry_payload_idempotence_proven": False, "atomicity_proven": False,
            "device_claims": False, "physical_authorization": False}


def audit(core_root: Path, builder: Path, stub_audit_root: Path,
          mklittlefs_source: Path, ini: Path) -> dict:
    manifest = json.loads(MANIFEST.read_text(encoding="utf-8"))
    pins = manifest["pinned_source_sha256_lf"]
    identity = installed_identity(local_path(core_root, directory=True))
    paths = {"eagle.flash.4m2m.ld": core_root / "tools/sdk/ld/eagle.flash.4m2m.ld",
             "platformio-builder-main.py": builder, "mklittlefs-main.cpp": mklittlefs_source}
    for name, path in paths.items():
        data = local_path(path).read_bytes().replace(b"\r\n", b"\n")
        if hashlib.sha256(data).hexdigest() != pins[name]:
            raise Stage2Error("Pinned geometry/builder source differs: " + name)
    platform = json.loads(local_path(builder.parent.parent / "platform.json").read_text(encoding="utf-8"))
    if platform["version"] != "4.2.1":
        raise Stage2Error("Pinned espressif8266 platform 4.2.1 required")
    old_manifest = json.loads(Path(__file__).with_name("m9_executor_sources.json").read_text(encoding="utf-8"))
    check_hashes(local_path(stub_audit_root, directory=True), old_manifest["upstream_stub_source_sha256"])
    stub = (stub_audit_root / "src-command_handler.c").read_text(encoding="utf-8")
    required = ("ALIGN_DOWN(s_flash_state.offset, config.sector_size)",
                "ALIGN_UP(s_flash_state.offset + s_flash_state.total_remaining, config.sector_size)",
                "MIN(actual_data_size, s_flash_state.total_remaining)")
    if any(token not in stub for token in required):
        raise Stage2Error("Pinned nonzero-address stub bounds are missing")
    layout = geometry(ini)
    model = raw_write_bounds()
    if model["erase_start"] != FS_START or model["erase_end_inclusive"] != FS_END - 1:
        raise Stage2Error("Raw write exceeds filesystem bounds")
    return {"status": "PASS_OFFLINE_STAGE2_EXECUTOR_SOURCE_MODEL",
            "STAGE2_EXECUTOR_MODEL_GATE": "PASS", "STAGE2_RAW_WRITE_BOUNDS_GATE": "PASS",
            "selected_executor": "DIRECT_UART_RAW_LITTLEFS_WRITE_PRINT_ONLY",
            "esptool_version": identity["esptool_version"],
            "esptool_package_digest": identity["esptool_package_digest"],
            "python_executable_sha256": identity["python_executable_sha256"],
            "python_version": identity["python_version"],
            "esptool_module_path": identity["esptool_module_path"],
            "external_interpreter_pin_checked": False,
            "stub_version": "2", "stub_release": old_manifest["stub_release"],
            "core_version": "3.1.2", "platform_version": "4.2.1",
            "source_pins_checked": True, "geometry": layout,
            "atomic_U_FS_stage_start": FS_START - FS_BYTES,
            "atomic_U_FS_overlaps_installed_application": True,
            "non_atomic_U_FS_MD5_after_active_FS_write": True,
            "alternative_full_FS_atomic_staging_available": False,
            "mklittlefs_root_wall_clock_metadata": True,
            "raw_write_model": model, "internal_reconnect_may_use_default_reset": True,
            "GPIO0_LOW_required_through_PRE_write_POST": True,
            "device_contacts": 0, "serial_io": 0, "flash_writes": 0,
            "device_filesystem_writes": 0, "reboots": 0, "physical_authorization": False,
            "stage2_physical_write": "HOLD", "stage2_runtime": "NOT_RUN"}


def render_packet() -> dict:
    python = '& "<PYTHON_EXE>" '
    physical = (python + '-I -m esptool --chip esp8266 --port "<PORT>" --baud 115200 '
                '--stub-version 2 --before no-reset --after no-reset-stub --connect-attempts 1 ')
    keep = '--flash-mode keep --flash-freq keep --flash-size keep --no-compress '
    steps = []

    def add(key, purpose, command, is_physical=False, rollback=False):
        steps.append({"step": key, "purpose": purpose,
                      "authorization": "NOT AUTHORIZED BY PHASE F" if is_physical else "LOCAL FILES ONLY",
                      "rollback_separate_authority": rollback,
                      "template": ("# NOT AUTHORIZED BY PHASE F\n" if is_physical else "# LOCAL FILES ONLY\n") + command})

    add("A0", "ROM entry", "MANUAL: continuous USB-C power; GPIO0 LOW; existing RST pulse; require ROM (1,7). EN not assumed.", True)
    add("A1", "same-unit ROM/stub chip qualification", physical + 'chip-id', True)
    add("A2", "4 MiB physical flash qualification", physical + 'flash-id', True)
    add("B", "fresh distinct PRE-STAGE2 in ROM/stub", physical + 'read-flash 0x000000 0x400000 "<PRE_STAGE2_4MB>"', True)
    add("C0", "pinned local source/interpreter gate", python + 'tools/m9_stage2_executor.py --core-root "<PINNED_CORE_ROOT>" --platformio-builder "<PINNED_PIO_BUILDER>" --stub-audit-root "<PINNED_STUB_AUDIT_ROOT>" --mklittlefs-source "<PINNED_MKLITTLEFS_SOURCE>" --expected-python-sha256 "<EXPECTED_PYTHON_SHA256>" --expected-python-version "<EXPECTED_PYTHON_VERSION>" --expected-module-root "<ESPTOOL_MODULE_ROOT>"')
    add("C1", "immediate exact FS rehash/inventory gate", python + 'tools/m9_stage2_fs_candidate.py --image "<FS_IMAGE>" --expected-sha256 "<EXPECTED_FS_SHA256>"')
    add("D", "STAGE2 FS WRITE ONLY", physical + 'write-flash ' + keep + '0x200000 "<FS_IMAGE>"', True)
    add("E", "independent full POST-STAGE2 BEFORE normal boot", physical + 'read-flash 0x000000 0x400000 "<POST_STAGE2_4MB>"', True)
    add("F", "local FS/lower/tail exact preservation", python + 'tools/m9_stage2_readback_verify.py "<FS_IMAGE>" "<PRE_STAGE2_4MB>" "<POST_STAGE2_4MB>" --expected-sha256 "<EXPECTED_FS_SHA256>"')
    for key, args in (("G1", "write-mem 0x60001200 0x00000000 0xFFFFFFFF"),
                      ("G2", "write-mem 0x6000127C 0x00000000 0xFFFFFFFF"),
                      ("G3", "read-mem 0x60001200"), ("G4", "read-mem 0x6000127C")):
        add(key, "RTC neutralization; require exact 0/0 readbacks", physical + args, True)
    add("H", "still-FS-less Stage-1 normal boot", "MANUAL: only after all gates PASS and separately approved boot: release GPIO0 while powered, existing RST pulse, continuous power; require (3,7), ~ld, no cp:, Stage-1 LCD/AP/telemetry. No mount/format or normal-profile activation.", True)
    for key, placeholder, digest in (("I", "<PRE_STAGE2_ROLLBACK>", "<PRIVATE_PRE_STAGE2_SHA256>"),
                                     ("J", "<PRIVATE_MASTER>", "<PRIVATE_MASTER_SHA256>")):
        add(key + "0", "separate exact full-chip rollback preflight", python + f'tools/m9_master_restore_preflight.py "{placeholder}" --expected-sha256 "{digest}"')
        add(key + "1", "separately authorized FULL CHIP ROLLBACK, not Stage-2 bounds", physical + 'write-flash ' + keep + f'0x000000 "{placeholder}"', True, True)
        add(key + "2", "rollback full readback before normal boot", physical + 'read-flash 0x000000 0x400000 "<ROLLBACK_READBACK>"', True, True)
        add(key + "3", "local rollback exact comparison, private report only", python + f'tools/m9_master_restore_preflight.py "{placeholder}" --expected-sha256 "{digest}" --readback "<ROLLBACK_READBACK>"')
    return {"mode": "PRINT_ONLY", "physical_authorization": False,
            "stage2_write_step": "D", "stage2_target": FS_START, "stage2_end_exclusive": FS_END,
            "fs_bytes": FS_BYTES, "selected_executor": "DIRECT_UART_RAW_LITTLEFS_WRITE",
            "internal_whole_write_attempts_max": 2, "packet_attempts_default": 3,
            "internal_reconnect_may_reset": True, "manual_retry_authorized": False,
            "automatic_rollback": False, "GPIO0_LOW_through_POST_required": True,
            "steps": steps, "device_contacts": 0, "serial_io": 0,
            "flash_writes": 0, "device_filesystem_writes": 0, "reboots": 0}


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--render-commands", action="store_true")
    parser.add_argument("--core-root", type=Path)
    parser.add_argument("--platformio-builder", type=Path)
    parser.add_argument("--stub-audit-root", type=Path)
    parser.add_argument("--mklittlefs-source", type=Path)
    parser.add_argument("--expected-python-sha256")
    parser.add_argument("--expected-python-version")
    parser.add_argument("--expected-module-root", type=Path)
    parser.add_argument("--platformio", type=Path, default=Path("firmware/platformio.ini"))
    args = parser.parse_args()
    try:
        if args.render_commands:
            result = render_packet()
        else:
            if not all((args.core_root, args.platformio_builder, args.stub_audit_root, args.mklittlefs_source)):
                raise Stage2Error("All pinned local source roots required for audit")
            result = audit(args.core_root, args.platformio_builder, args.stub_audit_root,
                           args.mklittlefs_source, args.platformio)
            expected = (args.expected_python_sha256, args.expected_python_version, args.expected_module_root)
            if any(expected):
                if (not all(expected)
                        or result["python_executable_sha256"] != args.expected_python_sha256.lower()
                        or result["python_version"] != args.expected_python_version
                        or Path(result["esptool_module_path"]) != args.expected_module_root.resolve()):
                    raise Stage2Error("External interpreter/module pin differs")
                result["external_interpreter_pin_checked"] = True
    except (ValueError, OSError, KeyError) as exc:
        parser.exit(1, f"STAGE2 EXECUTOR GATE CLOSED: {exc}\n")
    print(json.dumps(result, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
