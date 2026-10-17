#!/usr/bin/env python3
"""Phase O source/binding audit and optional retained local BIN inspection only.

No serial object, transport factory, build, readback capture or physical authority.
CI omits the private candidate argument and reports NOT_READ_BY_THIS_RUN.
"""
import argparse
import ast
import hashlib
import json
from pathlib import Path
from m9_single_attempt_app_write import candidate, future_packet
import m9_single_attempt_app_write as app

ROOT = Path(__file__).resolve().parent.parent
PINS = ROOT / 'tools/m9_phase_o_sources.json'
COUNTERS = dict(device_contacts=0, serial_io=0, flash_writes=0, rtc_writes=0,
                reboots=0, device_filesystem_writes=0)


def digest(raw):
    return hashlib.sha256(raw.replace(b'\r\n', b'\n')).hexdigest()


def runner_equivalent(text, expected):
    # The sole reviewed runner edit is a numeric success receipt. Restore that
    # literal to prove the ENTIRE prior module, not just selected functions.
    current = "rounded_extent='0x000000..0x061FFF'"
    prior = "rounded_extent='0x000000..0x064FFF'"
    if text.count(current) != 1 or digest(text.replace(current, prior).encode()) != expected:
        raise ValueError('Unreviewed Phase M runner/acquisition change')


def transaction_equivalent(text, expected):
    # Exact class text is stronger than a version-dependent debug AST dump.
    classes = {node.name: digest(ast.get_source_segment(text, node).encode())
               for node in ast.parse(text).body if isinstance(node, ast.ClassDef)
               and node.name in ('SingleAttempt', 'PinnedStubTransport')}
    if classes != expected:
        raise ValueError('Single-attempt transaction class changed')


def source_gate(root=ROOT):
    pins = json.loads(PINS.read_text(encoding='utf-8'))
    for group in ('firmware_sha256_lf', 'unchanged_sha256_lf', 'current_binding_tool_sha256_lf'):
        for name, expected in pins[group].items():
            if digest((root/name).read_bytes()) != expected:
                raise ValueError('Phase O source drift: ' + name)
    runner_equivalent((root/'tools/m9_single_attempt_physical_runner.py').read_text(encoding='utf-8'),
                      pins['runner_predecessor_sha256_lf'])
    transaction_equivalent((root/'tools/m9_single_attempt_app_write.py').read_text(encoding='utf-8'),
                           pins['transaction_class_sha256_lf'])
    binding = pins['normal_candidate']
    if (app.FROZEN_BYTES, app.FROZEN_SHA256, app.ROUNDED_END, app.BLOCK_COUNT) != (
            binding['bytes'], binding['sha256'], binding['rounded_end'], binding['block_count']):
        raise ValueError('Active candidate binding differs from owner identity')
    assert app.BLOCK_BYTES == 4096 and app.FLASH_BYTES == 0x400000
    assert binding['payload_end'] == binding['bytes'] == 0x0617A0
    assert binding['rounded_end'] == app.BLOCK_COUNT*4096 == 0x062000 < 0x100000
    assert binding['final_sequence'] == app.BLOCK_COUNT-1 == 97
    assert binding['final_block_start'] == 97*4096 == 0x061000
    assert binding['final_payload_bytes'] == app.FROZEN_BYTES-97*4096 == 1952
    assert binding['final_ff_padding_bytes'] == 4096-1952 == 2144
    from m9_phase_n_qualification import source_gate as stage_a_source_gate
    stage_a_source_gate(root)  # Current N source pins + explicit historical projection.
    return dict(PHASE_O_BINDING_SOURCE_GATE='PASS/OFFLINE',
                firmware_identity='RAW_PHASE_N_HEAD_EQUALITY',
                firmware_files_checked=len(pins['firmware_sha256_lf']),
                phase_n_source_checkpoint=pins['phase_n_source_checkpoint'],
                phase_o_start_head=pins['start_head'],
                candidate=binding, historical_successor_candidate=pins['historical_successor_candidate'],
                transaction_classes_source_equivalent=True,
                runner_source_equivalent_except_numeric_receipt=True,
                PHASE_O_RETAINED_CANDIDATE_IDENTITY_GATE='NOT_READ_BY_THIS_RUN',
                NORMAL_PROFILE_LITTLEFS_MOUNT_GATE='NOT_RUN',
                NORMAL_PROFILE_RUNTIME_GATE='NOT_RUN',
                installed_profile2_probe_gates='HISTORICAL_OWNER_SUPPLIED_PASS_ONLY',
                future_packet=future_packet('PASS/OFFLINE', 'PASS/OFFLINE'),
                physical_authorization=False, **COUNTERS)


def qualify(image=None, expected=None):
    if bool(image) != bool(expected):
        raise ValueError('Retained candidate and external SHA required together')
    result = source_gate()
    if image is not None:
        data, inspected = candidate(image, expected)
        binding = result['candidate']
        if len(data) != binding['bytes'] or inspected['sector_rounded_write_extent'] != binding['rounded_end']:
            raise ValueError('Retained image geometry differs from binding')
        result['PHASE_O_RETAINED_CANDIDATE_IDENTITY_GATE'] = 'PASS/OFFLINE'
        result['image_geometry_checksums_crc'] = inspected['status']
    return result


def main():
    parser = argparse.ArgumentParser(description=__doc__, allow_abbrev=False)
    parser.add_argument('--candidate', type=Path)
    parser.add_argument('--expected-sha256')
    args = parser.parse_args()
    try:
        print(json.dumps(qualify(args.candidate, args.expected_sha256), indent=2, sort_keys=True))
    except (ValueError, OSError, TypeError, AssertionError) as exc:
        parser.exit(1, 'PHASE O OFFLINE GATE CLOSED: ' + str(exc) + '\n')
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
