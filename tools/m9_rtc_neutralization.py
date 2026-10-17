#!/usr/bin/env python3
"""Phase D: deterministic synthetic RTC/transition models and PRINT ONLY text.

No device executor. A model receipt is never a physical observation/permission.
"""
from __future__ import annotations

import argparse
import importlib.metadata
import json
import os
import struct
from pathlib import Path

from m9_executor_preflight import (
    MANIFEST, ExecutorError, canonical_hash, check_hashes, installed_identity,
    rtc_command_model,
)

MAGIC_ADDRESS = 0x60001200
CRC_ADDRESS = 0x6000127C
COMMAND_BYTES = 128
LOCAL_PYTHON = r"C:\Users\jerry\AppData\Local\Programs\Python\Python312\python.exe"
LOCAL_PYTHON_SHA = "4d6f5f81a4bca11191c4c7c6b43632694d0a4ce74e068619d8fdc161d469859a"
LOCAL_PYTHON_VERSION = "3.12.10"
RESET_SOURCE = "https://www.espressif.com/sites/default/files/2c-esp8266_non_os_sdk_api_guide_en_v1.5.4.pdf"
BOOT_SOURCE = "https://docs.espressif.com/projects/esptool/en/latest/esp8266/advanced-topics/boot-mode-selection.html"


class NeutralizationError(ValueError):
    """HOLD; no retry or physical operation is implied."""


def command_state(data: bytes) -> dict:
    result = rtc_command_model(data)
    magic, crc = struct.unpack_from("<I", data)[0], struct.unpack_from("<I", data, 124)[0]
    result.update(neutral_words=magic == crc == 0, deliberately_verified_neutral=False,
                  other_rtc_words_known_zero=False, physical_observation=False)
    return result


def neutralize_model(data: bytes) -> bytes:
    """Pure byte transformation mirroring Core clear; preserves other 120 bytes."""
    command_state(data)  # Exact size required.
    out = bytearray(data)
    struct.pack_into("<I", out, 0, 0)
    struct.pack_into("<I", out, 124, 0)
    return bytes(out)


def reset_retention_matrix() -> dict:
    # SDK documents retention, not a callable stock-ROM system_restart API.
    return {
        "EXT_RST": {"rtc": "retained", "normal_boot_qualified": True,
                    "strap_sampling": "external reset with normal boot straps", "source": BOOT_SOURCE,
                    "retention_source": RESET_SOURCE},
        "watchdog": {"rtc": "retained", "normal_boot_qualified": False,
                     "reason": "No qualified stock ROM/stub trigger; esptool falls back to EN", "source": RESET_SOURCE},
        "system_restart": {"rtc": "retained", "normal_boot_qualified": False,
                           "reason": "SDK application API; stock ROM/stub trigger and strap path unqualified", "source": RESET_SOURCE},
        "CHIP_EN": {"rtc": "random", "normal_boot_qualified": False, "source": RESET_SOURCE},
        "power_on": {"rtc": "random", "normal_boot_qualified": False, "source": RESET_SOURCE},
        "esptool_run": {"rtc": "unqualified", "normal_boot_qualified": False,
                        "reason": "v2 FLASH_END reboot TODO; no qualified reset/eboot path"},
        "esptool_soft_reset": {"rtc": "unqualified", "normal_boot_qualified": False,
                               "reason": "v2 RUN_USER_CODE TODO; no reset implementation"},
    }


def required_events() -> list[dict]:
    return [
        {"step": "magic_clear", "address": MAGIC_ADDRESS, "value": 0, "success": True},
        {"step": "crc_clear", "address": CRC_ADDRESS, "value": 0, "success": True},
        {"step": "magic_readback", "address": MAGIC_ADDRESS, "value": 0, "success": True},
        {"step": "crc_readback", "address": CRC_ADDRESS, "value": 0, "success": True},
        {"step": "gpio0_release_while_powered", "success": True},
        {"step": "EXT_RST", "success": True},
        {"step": "first_normal_boot", "success": True},
    ]


REQUIRED_CONDITIONS = (
    "postwrite_verified", "continuous_power", "no_chip_en_reset",
    "dtr_rts_isolated", "existing_rst_used_as_ext_rst", "normal_other_straps",
    "no_intervening_reset", "no_application_before_ext_rst",
)


def verify_sequence(events: list[dict], conditions: dict, reset_class: str = "EXT_RST") -> dict:
    """Validate supplied SYNTHETIC trace. No hardware receipt is produced.

    No intervening reset means between S7 and the sole modeled S7D EXT_RST.
    Conditions cover the full interval, including command open/close boundaries.
    """
    if reset_class != "EXT_RST" or not reset_retention_matrix()[reset_class]["normal_boot_qualified"]:
        raise NeutralizationError("Reset does not qualify deterministic first normal boot")
    if set(conditions) != set(REQUIRED_CONDITIONS) or any(
            conditions[name] is not True for name in REQUIRED_CONDITIONS):
        raise NeutralizationError("Missing verified sequence conditions (synthetic model only)")
    expected = required_events()
    if len(events) != len(expected):
        raise NeutralizationError("Incomplete/extra operation or intervening reset")
    for actual, wanted in zip(events, expected):
        if actual != wanted or any(type(actual.get(key)) is not type(value) for key, value in wanted.items()):
            raise NeutralizationError("Operation order, exact word readback, or success differs")
    return {"status": "PASS_SYNTHETIC_SEQUENCE", "model_neutralization_verified": True,
            "pending_copy": False, "default_load_app_zero": True,
            "reset_class": "EXT_RST", "other_rtc_words_known_zero": False,
            "physical_observation": False, "physical_authorization": False,
            "physical_runtime_gate": "NOT_RUN", "physical_write": "HOLD"}


def audit_sources(core_root: Path, stub_root: Path, library_root: Path) -> dict:
    """Read pinned public sources only; never import their executable modules."""
    identity = installed_identity(core_root)
    if os.environ.get("ESPTOOL_OPEN_PORT_ATTEMPTS") is not None:
        raise ExecutorError("Clear ESPTOOL_OPEN_PORT_ATTEMPTS; one default open only")
    manifest = json.loads(MANIFEST.read_text(encoding="utf-8"))
    pins = manifest["rtc_neutralization_sources"]
    support = Path(importlib.metadata.distribution("esp-pylib").locate_file("esp_pylib/serial_reset.py"))
    if canonical_hash(support) != pins["esp_pylib_serial_reset_sha256"]:
        raise ExecutorError("Reset primitive source changed")
    check_hashes(stub_root, pins["stub_files"])
    check_hashes(library_root, pins["library_files"])
    # Complete hashes are primary. Explicit tokens document the reviewed contract.
    header = (core_root / "bootloaders/eboot/eboot_command.h").read_text(encoding="utf-8")
    clear = (core_root / "bootloaders/eboot/eboot_command.c").read_text(encoding="utf-8")
    macros = (library_root / "include/esp-stub-lib/soc_utils.h").read_text(encoding="utf-8")
    handler = (stub_root / "src/command_handler.c").read_text(encoding="utf-8")
    for body, tokens in (
        (header, ("((volatile uint32_t*)0x60001200)", "uint32_t args[29];", "0xeb001000", "0xfffff000")),
        (clear, ("cmd->crc32 != crc32", "offsetof(struct eboot_command, magic) / sizeof(uint32_t)] = 0;",
                 "offsetof(struct eboot_command, crc32) / sizeof(uint32_t)] = 0;")),
        (macros, ("(*(volatile uint32_t *)(_r))",)),
        (handler, ("REG_WRITE(addr, write_value);", "*reg_value = REG_READ(addr);",
                   "write_value |= REG_READ(addr) & ~mask;", "case ESP_RUN_USER_CODE:",
                   "TODO: Try to implement WDT reset")),
    ):
        if any(token not in body for token in tokens):
            raise ExecutorError("RTC source contract differs")
    sequence = verify_sequence(required_events(), dict.fromkeys(REQUIRED_CONDITIONS, True))
    neutral = command_state(neutralize_model(bytes(range(COMMAND_BYTES))))
    if neutral["pending_copy"] or not neutral["default_load_app_zero"] or not neutral["neutral_words"]:
        raise ExecutorError("Deterministic neutral-state model failed")
    return {"phase_d_rtc_eboot_neutralization": "PASS",
            "rtc_memory_access_gate": "PASS", "rtc_neutral_state_gate": "PASS",
            "rtc_to_normal_boot_transition_gate": "PASS",
            "gate_scope": "pinned source and synthetic models; conditional EXT_RST hardware path",
            "identity": identity, "reset_matrix": reset_retention_matrix(),
            "synthetic_sequence": sequence,
            "magic_address": MAGIC_ADDRESS, "crc_address": CRC_ADDRESS,
            "physical_runtime_gate": "NOT_RUN", "physical_write": "HOLD",
            "physical_authorization": False, "serial_io_performed": False}


def render_packet() -> dict:
    """Exact audited CLI text. No runner and no live port substitution."""
    base = (f'& "{LOCAL_PYTHON}" -I -m esptool --chip esp8266 --port "<PORT>" '
            '--baud 115200 --stub-version 2 --before no-reset --after no-reset-stub --connect-attempts 1 ')
    commands = [
        ("RTC MAGIC CLEAR", "write-mem 0x60001200 0x00000000 0xFFFFFFFF"),
        ("RTC CRC CLEAR", "write-mem 0x6000127C 0x00000000 0xFFFFFFFF"),
        ("RTC MAGIC READBACK", "read-mem 0x60001200"),
        ("RTC CRC READBACK", "read-mem 0x6000127C"),
    ]
    return {"mode": "PRINT_ONLY", "python_version": LOCAL_PYTHON_VERSION,
            "python_sha256": LOCAL_PYTHON_SHA, "esptool_version": "5.4.0",
            "steps": [{"label": label + " — NOT AUTHORIZED BY PHASE D", "command": base + args}
                      for label, args in commands],
            "physical_authorization": False, "serial_io_performed": False}


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--core-root", type=Path, required=True)
    parser.add_argument("--stub-root", type=Path, required=True)
    parser.add_argument("--stub-lib-root", type=Path, required=True)
    parser.add_argument("--render-commands", action="store_true")
    args = parser.parse_args()
    try:
        report = audit_sources(args.core_root, args.stub_root, args.stub_lib_root)
        if args.render_commands:
            identity = report["identity"]
            if (identity["python_executable_sha256"] != LOCAL_PYTHON_SHA
                    or identity["python_version"] != LOCAL_PYTHON_VERSION
                    or identity["python_executable"] != LOCAL_PYTHON):
                raise ExecutorError("PRINT packet requires frozen LOCAL interpreter identity")
            report["print_only_packet"] = render_packet()
        print(json.dumps(report, indent=2, sort_keys=True))
        return 0
    except (ExecutorError, NeutralizationError, OSError, ValueError, KeyError) as error:
        print(json.dumps({"status": "HOLD", "reason": str(error), "physical_authorization": False}))
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
