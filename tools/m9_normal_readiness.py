#!/usr/bin/env python3
"""Offline source/readiness receipt. Reads public source/local reports; no executor."""
import argparse
import hashlib
import json
from pathlib import Path
import re
from m9_mount_stack import ROOT, source_audit
from m9_fsless_gate import inspect_source, inspect_build
from m9_first_migration import inspect_candidate
from m9_mount_probe_resources import section_sizes, stack_frames

# Evidence anchors, not a claim that scanning words proves runtime safety.
HAZARDS = {
    'profile1_blocked': ('firmware/include/boot/ShinoBootProfile.h', '#if SHINO_BOOT_PROFILE == 1'),
    'startup_mount': ('firmware/src/main.cpp', 'const bool littleFsMounted = LittleFS.begin();'),
    'load_remount': ('firmware/src/config/ConfigManager.cpp', 'if (!LittleFS.begin())'),
    'migration_save': ('firmware/src/config/ConfigManager.cpp', 'ConfigManager::save();'),
    'unbounded_config_allocation': ('firmware/src/config/ConfigManager.cpp', 'new char[size + 1]'),
    'eeprom_initialization': ('firmware/src/config/SecureStorage.cpp', 'if (!flushToEEPROM())'),
    'eeprom_commit': ('firmware/src/config/SecureStorage.cpp', 'if (!EEPROM.commit())'),
    'token_provision': ('firmware/src/main.cpp', 'configManager.secure.put("api_token", SHINO_BOOTSTRAP_API_TOKEN);'),
    'rescue_persistent_counter': ('firmware/src/boot/RescueMode.cpp', 'configManager.secure.put("rescue_persistent_crash_count"'),
    'rescue_rtc_write': ('firmware/src/boot/RescueMode.cpp', 'ESP.rtcUserMemoryWrite('),
    'wifi_volatile_start': ('firmware/src/main.cpp', 'WiFi.persistent(false);'),
    'wifi_unconditional_station': ('firmware/src/wireless/WiFiManager.cpp', 'WiFi.begin(_staSsid, _staPass);'),
    'normal_bearer_auth': ('firmware/src/web/Api.cpp', 'if (!authHeader.startsWith("Bearer "))'),
    'runtime_status_remount': ('firmware/src/web/Api.cpp', 'if (LittleFS.begin())'),
    'runtime_fs_write': ('firmware/src/web/Api.cpp', 'LittleFS.open(currentFilename, "w")'),
    'runtime_config_save': ('firmware/src/web/Api.cpp', 'configManager.save();'),
    'gif_remount': ('firmware/src/display/Gif.cpp', 'if (!LittleFS.begin())'),
    'gif_unmount': ('firmware/src/display/Gif.cpp', 'LittleFS.end();'),
    'legacy_scene_freshness': ('firmware/src/scenes/SceneManager.cpp', 'STALE_AFTER_MS = 60000'),
    'bridge_profile_consumer': ('firmware/src/boot/FirstBootBridge.cpp', 'SHINO_BOOT_PROFILE == 0 || SHINO_BOOT_PROFILE == 2'),
}


def audit(root=ROOT):
    # Exact frozen firmware/policy/runner pins reject drift before a readiness
    # conclusion. Historical source_gate physical labels are not current facts.
    source_audit(root)
    inspect_source(root)
    evidence = {}
    for name, (path, anchor) in HAZARDS.items():
        body = (root / path).read_text(encoding='utf-8')
        lines = [i for i, line in enumerate(body.splitlines(), 1) if anchor in line]
        if not lines:
            raise ValueError('Readiness evidence missing: ' + name)
        evidence[name] = {'file': path, 'lines': lines, 'anchor': anchor,
                          'sha256_lf': hashlib.sha256(body.replace('\r\n', '\n').encode()).hexdigest()}
    return {
        'readiness_audit': 'PASS_OFFLINE_SOURCE_AND_DESIGN_RECEIPT',
        'implementation_decision': 'DESIGN_ONLY_NORMAL_CANDIDATE_HOLD',
        'firmware_files_checked': 103, 'firmware_files_changed_this_pass': 0,
        'hazards': evidence,
        'proposed_environment': 'esp12e_m9_4m2m_normal_qualification',
        'proposed_environment_implemented': False,
        'normal_profile_build': 'NOT_BUILT_COMPILE_PROHIBITED',
        'normal_candidate_frozen': False,
        'NORMAL_PROFILE_LITTLEFS_MOUNT_GATE': 'NOT_RUN',
        'NORMAL_PROFILE_RUNTIME_GATE': 'NOT_RUN',
        'physical_authorization': False,
        'device_contacts': 0, 'serial_io': 0, 'flash_writes': 0,
        'rtc_writes': 0, 'reboots': 0, 'device_filesystem_writes': 0,
    }


def reference_build(policy, symbols, sections, stack, candidate):
    """Explicitly profile-0 reference only; cannot qualify a normal candidate."""
    fsless = inspect_build(policy, symbols)
    text = symbols.read_text(encoding='utf-8-sig')
    # nm -C (without -S) report used by historical inspect_build.
    for symbol, address in (('_FS_start', 0x40400000), ('_FS_end', 0x405FA000),
                            ('_EEPROM_start', 0x405FB000)):
        if not re.search(rf'(?mi)^{address:08x}\s+A\s+{symbol}$', text):
            raise ValueError('4m2m linker proof missing: ' + symbol)
    image = inspect_candidate(candidate)
    return {'role': 'PUBLIC_PROFILE0_4M2M_REFERENCE_ONLY_NOT_NORMAL_CANDIDATE',
            'fsless_gate': fsless, 'image': image, 'sections': section_sizes(sections),
            'major_compiler_frames_bytes': stack_frames(stack),
            'physical_stack_margin_proven': False}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    for name in ('policy', 'symbols', 'sections', 'stack', 'candidate'):
        parser.add_argument('--' + name, type=Path)
    args = parser.parse_args()
    report = audit()
    inputs = (args.policy, args.symbols, args.sections, args.stack, args.candidate)
    if any(inputs) and not all(inputs):
        parser.error('All five reference-build inputs are required together')
    if all(inputs):
        report['reference_build'] = reference_build(*inputs)
    print(json.dumps(report, indent=2, sort_keys=True))


if __name__ == '__main__':
    main()
