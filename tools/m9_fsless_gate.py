#!/usr/bin/env python3
"""Offline source/policy/link-symbol regressions; never physical boot proof.

Consumes existing files only. LittleFS virtual methods may be linked by global
construction; their presence does not mean begin/format is called at startup.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import re
from pathlib import Path


ROOT = Path(__file__).resolve().parent.parent
FORBIDDEN = re.compile(
    r"LittleFS\s*\.|SPIFFS\s*\.|EEPROM\s*\.|SecureStorage\s*::|"
    r"configManager\s*\.|Update\s*\.\s*(begin|write|end)|U_FS|"
    r"flashEraseSector|flashWrite|rtcUserMemoryWrite|WiFi\s*\.\s*persistent\s*\(\s*true"
)


class FslessGateError(ValueError):
    pass


def code_only(source: str) -> str:
    pattern = r'"(?:\\.|[^"\\])*"|\'(?:\\.|[^\'\\])*\'|//[^\n]*|/\*[\s\S]*?\*/'
    return re.sub(pattern, lambda m: '""' if m[0][0] in '\"\'' else '', source)


def require(condition: bool, detail: str) -> None:
    if not condition:
        raise FslessGateError(detail)


def inspect_source(root: Path = ROOT) -> dict:
    paths = ["firmware/src/main.cpp", "firmware/src/boot/FirstBootBridge.cpp",
             "firmware/src/boot/FslessMetrics.cpp", "firmware/src/boot/FslessWebUI.cpp",
             "firmware/src/config/ConfigManager.cpp", "firmware/src/config/SecureStorage.cpp",
             "firmware/include/boot/HomeLan.h", "firmware/src/display/DisplayManager.cpp",
             "firmware/src/recovery/FactoryRollback.cpp", "firmware/include/boot/ShinoBootProfile.h"]
    sources = {p: (root / p).read_text(encoding="utf-8") for p in paths}
    main = code_only(sources[paths[0]])
    branches = re.findall(r"#if SHINO_BOOT_PROFILE == 0\s*(.*?)#(?:elif|else)", main, re.S)
    require(len(branches) == 2, "Expected separate profile-0 setup and loop branches")
    # Fail closed if startup gains an unreviewed function call.
    require(re.sub(r"\s+", "", branches[0]) ==
            "FirstBootBridge::run();EspClass::wdtEnable(WDTO_2S);return;",
            "Unreviewed profile-0 setup path")
    require(re.sub(r"\s+", "", branches[1]) == "FirstBootBridge::loop();return;",
            "Unreviewed profile-0 loop path")
    profile_gate = code_only(sources[paths[-1]])
    require('#if SHINO_BOOT_PROFILE != 0' in profile_gate and
            '#if SHINO_BOOT_PROFILE == 1' in profile_gate and '#error' in profile_gate,
            "Normal boot compile-time prohibition missing")
    bridge = code_only(sources[paths[1]])
    for p in paths[1:4]:
        require(FORBIDDEN.search(code_only(sources[p])) is None,
                f"Storage call in FS-less module: {p}")
    for flag in ("SHINO_ENABLE_NATIVE_SIGNED_OTA", "SHINO_ENABLE_FS_MIGRATION"):
        require(f"static_assert({flag} == 0," in bridge, f"Disabled writer gate missing: {flag}")
    require("#if SHINO_ENABLE_FACTORY_RESTORE" in bridge,
            "Optional OEM writer must remain compile gated")
    require("WiFi.persistent(false)" in bridge, "Wi-Fi persistence prohibition missing")
    require("server.send_P(200, PSTR" in sources[paths[1]] and
            "FslessWebUI::PAGE" in sources[paths[1]] and
            "FslessWebUI::SCRIPT" in sources[paths[1]], "Program-flash asset serving changed")
    require("const char PAGE[] PROGMEM" in sources[paths[3]] and
            "const char SCRIPT[] PROGMEM" in sources[paths[3]], "Flash assets changed")
    require("FslessMetrics::Snapshot state;" in sources[paths[2]] and
            "state = next;" in sources[paths[2]] and
            "METRICS_STALE_MS = 6000" in sources[paths[2]], "RAM-only metrics/TTL changed")
    require(re.search(r"ConfigManager::ConfigManager\([^\n]+:\s*filename\(filename\),\s*secure\(\)\s*\{\s*\}",
                      code_only(sources[paths[4]])) is not None, "Config constructor changed")
    require(re.search(r"SecureStorage::SecureStorage\([^\n]+:\s*_eepromSize\(eepromSize\),\s*_doc\(\)\s*\{\s*\}",
                      code_only(sources[paths[5]])) is not None, "SecureStorage constructor changed")
    require("#define SHINO_ENABLE_HOME_LAN 0" in sources[paths[6]], "Default Home LAN gate changed")
    return {"status": "PASS_FSLESS_SOURCE_REGRESSIONS", "physical_boot_proven": False,
            "source_sha256": {p: hashlib.sha256((root / p).read_bytes()).hexdigest() for p in paths}}


def inspect_build(policy: Path, symbols: Path) -> dict:
    policy_text = policy.read_text(encoding="utf-8")
    for name in ("SHINO_BOOT_PROFILE", "SHINO_ENABLE_FS_MIGRATION",
                 "SHINO_ENABLE_NATIVE_SIGNED_OTA", "SHINO_ENABLE_FACTORY_RESTORE",
                 "SHINO_FS_IMAGE_PRESENT"):
        require(re.search(rf"(?m)^#define {name} 0\s*$", policy_text) is not None,
                f"Candidate policy requires {name}=0")
    text = symbols.read_text(encoding="utf-8-sig")
    for name, address in (("_FS_start", 0x40400000), ("_FS_end", 0x405FA000),
                          ("_EEPROM_start", 0x405FB000)):
        require(re.search(rf"(?mi)^{address:08x}\s+A\s+{name}$", text) is not None,
                f"Wrong/missing linked {name}")
    for prefix in ("EEPROMClass::begin(", "EEPROMClass::commit(", "SecureStorage::begin(",
                   "SecureStorage::flushToEEPROM(", "ConfigManager::load(", "ConfigManager::save(",
                   "FactoryRollback::upload(", "FactoryRollback::complete(",
                   "UpdaterClass::begin(", "UpdaterClass::write(", "UpdaterClass::end(",
                   "HomeLan::begin("):
        require(prefix not in text, f"Unreviewed active storage/writer symbol: {prefix}")
    for required in ("FirstBootBridge::run()", "FirstBootBridge::loop()",
                     "FslessWebUI::PAGE", "FslessWebUI::SCRIPT", "FslessMetrics::apply("):
        require(required in text, f"Missing linked FS-less path: {required}")
    return {"status": "PASS_FSLESS_POLICY_AND_LINKED_SYMBOLS",
            "littlefs_virtual_methods_linked_but_not_called_by_boot": True,
            "native_and_fs_writers_enabled": False, "physical_boot_proven": False,
            "physical_authorization": False}


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--policy", type=Path)
    parser.add_argument("--symbols", type=Path, help="Existing nm -C output; no command is executed")
    args = parser.parse_args()
    if bool(args.policy) != bool(args.symbols):
        parser.error("Supply --policy and --symbols together")
    try:
        report = inspect_source()
        if args.policy:
            report["build"] = inspect_build(args.policy, args.symbols)
    except (FslessGateError, OSError) as exc:
        print(json.dumps({"status": "HOLD", "error": str(exc)}))
        return 1
    print(json.dumps(report, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
