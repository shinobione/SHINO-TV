#!/usr/bin/env python3
"""Phase K local evidence evaluator; never contacts hardware or grants write authority."""
from __future__ import annotations
import argparse
import json
from pathlib import Path

RESOURCE_POLICY_SCOPE = 'M9_PROFILE2_INSTRUMENTED_MOUNT_PROBE_ONLY'
M9_PROBE_MIN_FREE_HEAP_BYTES = 20480
M9_PROBE_MIN_LARGEST_BLOCK_BYTES = 16384
M9_PROBE_MAX_FRAGMENTATION_PERCENT = 25
M9_PROBE_MIN_CONT_STACK_FREE_BYTES = 2048


class PolicyError(ValueError):
    """Missing, inconsistent or failing supplied evidence: gate stays closed."""


def require(condition: bool, message: str) -> None:
    if not condition:
        raise PolicyError(message)


def number(status: dict, key: str, maximum: int = 0xFFFFFFFF) -> int:
    value = status.get(key)
    require(type(value) is int and 0 <= value <= maximum, 'Invalid integer: ' + key)
    return value


def heap(status: dict, free: str, block: str, frag: str) -> None:
    f, b, g = number(status, free, 81920), number(status, block, 81920), number(status, frag, 100)
    require(0 < b <= f, 'Impossible heap snapshot')
    require(f >= M9_PROBE_MIN_FREE_HEAP_BYTES, 'Free heap policy failed')
    require(b >= M9_PROBE_MIN_LARGEST_BLOCK_BYTES, 'Largest block policy failed')
    require(g <= M9_PROBE_MAX_FRAGMENTATION_PERCENT, 'Fragmentation policy failed')


MOUNT_FIXED = ('mount_phase_cont_stack_start', 'mount_phase_cont_stack_min_free',
               'heap_after_probe_free', 'heap_after_probe_largest_block', 'heap_after_probe_fragmentation',
               'runtime_cont_stack_start')


def validate_status(status: dict) -> None:
    require(type(status) is dict, 'Status object required')
    for field in ('resource_diagnostics_enabled', 'resource_measurements_valid', 'attempted',
                  'autoformat_disabled', 'mounted', 'inventory_checked', 'inventory_exact', 'config_seed_exact'):
        require(status.get(field) is True, 'Required true field: ' + field)
    require(status.get('write_paths_compiled') is False, 'Writer exclusion missing')
    for field, expected in {'blocked_write_attempts': 0, 'resource_rejected_sample_count': 0,
                            'checked_file_count': 24, 'checked_payload_bytes': 181402,
                            'filesystem_start': 0x200000, 'filesystem_end_exclusive': 0x3FA000,
                            'filesystem_bytes': 2072576}.items():
        require(number(status, field) == expected, 'Required exact value: ' + field)
    require(number(status, 'resource_sample_count') > 0, 'No valid runtime sample')
    for field in ('mount_phase_cont_stack_start', 'mount_phase_cont_stack_min_free',
                  'runtime_cont_stack_start', 'runtime_min_cont_stack_free'):
        value = number(status, field, 4096)
        require(value % 4 == 0 and value >= M9_PROBE_MIN_CONT_STACK_FREE_BYTES,
                'Continuation policy/validity failed: ' + field)
    require(status['mount_phase_cont_stack_min_free'] <= status['mount_phase_cont_stack_start'],
            'Mount watermark increased')
    require(status['runtime_min_cont_stack_free'] <= status['runtime_cont_stack_start'],
            'Runtime watermark increased')
    heap(status, 'heap_after_probe_free', 'heap_after_probe_largest_block', 'heap_after_probe_fragmentation')
    heap(status, 'latest_free_heap', 'latest_largest_free_block', 'latest_fragmentation_percent')
    heap(status, 'lowest_observed_free_heap', 'lowest_observed_largest_free_block',
         'highest_observed_fragmentation_percent')
    for low, latest in (('lowest_observed_free_heap', 'latest_free_heap'),
                        ('lowest_observed_largest_free_block', 'latest_largest_free_block')):
        require(status[low] <= status[latest], 'Cached minimum exceeds latest')
    require(status['highest_observed_fragmentation_percent'] >= status['latest_fragmentation_percent'],
            'Cached maximum below latest')
    # The old loop/mount observer is denser than the once-per-second heap sampler.
    for field in ('available_heap_after_mount', 'available_heap_after_inventory', 'minimum_observed_free_heap'):
        require(number(status, field, 81920) >= M9_PROBE_MIN_FREE_HEAP_BYTES, 'Base heap policy failed')
    require(status['minimum_observed_free_heap'] <= min(status['available_heap_after_mount'],
            status['available_heap_after_inventory']), 'Base minimum inconsistent')


def evaluate(before: dict, after: dict, observations: dict) -> dict:
    """Evaluate supplied observations, never assert their authenticity or provenance."""
    validate_status(before)
    validate_status(after)
    require(type(observations) is dict, 'Owner observation object required')
    for key in ('same_boot', 'digest_status_observed', 'stable_link_pass', 'telemetry_stale_recovery_pass'):
        require(observations.get(key) is True, 'Missing successful observation: ' + key)
    for key in ('reboot_observed', 'display_corruption_observed'):
        require(observations.get(key) is False, 'Unsafe/unknown observation: ' + key)
    require(number(observations, 'link_seconds') >= 180, 'LINK window shorter than 180 s')
    require(after['resource_sample_count'] > before['resource_sample_count'], 'Sample count did not advance')
    require(all(before[k] == after[k] for k in MOUNT_FIXED), 'Mount/window identity changed')
    for field in ('runtime_min_cont_stack_free', 'lowest_observed_free_heap',
                  'lowest_observed_largest_free_block', 'minimum_observed_free_heap'):
        require(after[field] <= before[field], 'Minimum increased across window: ' + field)
    require(after['highest_observed_fragmentation_percent'] >= before['highest_observed_fragmentation_percent'],
            'Maximum decreased across window')
    return {'status': 'PASS_SUPPLIED_RESOURCE_EVIDENCE_ONLY', 'scope': RESOURCE_POLICY_SCOPE,
            'physical_authenticity_verified': False, 'physical_authorization': False,
            'normal_profile_authorized': False, 'device_contacts': 0, 'device_writes': 0}


def policy() -> dict:
    return {'PHASE_K_RESOURCE_POLICY_GATE': 'PASS/OFFLINE', 'RESOURCE_POLICY_SCOPE': RESOURCE_POLICY_SCOPE,
            'PHYSICAL_RESOURCE_THRESHOLD': 'DEFINED_SCOPED_ACCEPTANCE_POLICY',
            'M9_PROBE_MIN_FREE_HEAP_BYTES': M9_PROBE_MIN_FREE_HEAP_BYTES,
            'M9_PROBE_MIN_LARGEST_BLOCK_BYTES': M9_PROBE_MIN_LARGEST_BLOCK_BYTES,
            'M9_PROBE_MAX_FRAGMENTATION_PERCENT': M9_PROBE_MAX_FRAGMENTATION_PERCENT,
            'M9_PROBE_MIN_CONT_STACK_FREE_BYTES': M9_PROBE_MIN_CONT_STACK_FREE_BYTES,
            'universal_esp8266_floor': False, 'physical_authorization': False,
            'physical_gate': 'HOLD / NOT_RUN', 'normal_profile_gate': 'NOT_RUN'}


def main() -> int:
    p = argparse.ArgumentParser(description=__doc__)
    for key in ('before', 'after', 'observations'):
        p.add_argument('--' + key, type=Path)
    args = p.parse_args()
    inputs = (args.before, args.after, args.observations)
    if any(inputs) and not all(inputs):
        p.error('All three local evidence files are required')
    try:
        report = policy()
        if all(inputs):
            report['supplied_evidence'] = evaluate(*(json.loads(x.read_text(encoding='utf-8')) for x in inputs))
        print(json.dumps(report, indent=2, sort_keys=True))
    except (ValueError, OSError, TypeError) as exc:
        p.exit(1, 'RESOURCE GATE CLOSED: ' + str(exc) + '\n')
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
