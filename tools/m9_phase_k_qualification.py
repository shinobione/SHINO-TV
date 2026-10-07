#!/usr/bin/env python3
"""Phase K source/version qualification only; no candidate build or device operation."""
import argparse
import json
from pathlib import Path
from m9_mount_probe_resources import ROOT, source_gate
from m9_resource_policy import policy
from m9_single_attempt_app_write import load_pinned_esptool, candidate, FROZEN_BYTES, FROZEN_SHA256, ROUNDED_END


def qualify(stub_audit_root: Path, image: Path | None = None, expected: str | None = None) -> dict:
    source_gate()  # Original probe/J scope and instrumentation are still intact.
    manifest=json.loads((ROOT/'tools/m9_phase_k_sources.json').read_text(encoding='utf-8'))
    from m9_mount_stack import source_audit
    firmware=source_audit()  # Only two separately pinned workspace successors;
    # historical K firmware/candidate manifest remains unchanged on disk.
    _,sources=load_pinned_esptool(stub_audit_root)
    report={'PHASE_K_RESOURCE_POLICY_GATE':'PASS/OFFLINE',
            'qualification_report_scope':'HISTORICAL_K_PROBE_POLICY_PLUS_CURRENT_BINDING_METADATA; NOT_NORMAL_PHYSICAL_ACCEPTANCE',
            'PHASE_K_SINGLE_ATTEMPT_EXECUTOR_GATE':'PASS/OFFLINE',
            'policy':policy(), 'source_audit':sources,
            **firmware,
            'candidate':{'bytes':FROZEN_BYTES, 'sha256':FROZEN_SHA256,
                         'rounded_end':ROUNDED_END, 'physical_authorization':False},
            'candidate_role':'FROZEN_PROFILE1_STAGE_A_NORMAL_OFFLINE_ONLY',
            'historical_successor_candidate':json.loads((ROOT/'tools/m9_phase_o_sources.json').read_text(encoding='utf-8'))['historical_successor_candidate'],
            'historical_j_candidate':manifest['candidate'],
            'PHASE_K_FROZEN_CANDIDATE_IDENTITY_GATE':'NOT_READ_BY_THIS_RUN',
            'MOUNT_PROBE_RESOURCE_PHYSICAL_GATE':'HOLD / NOT_RUN',
            'MOUNT_PROBE_PHYSICAL_GATE':'PARTIAL / HOLD',
            'NORMAL_PROFILE_LITTLEFS_MOUNT_GATE':'NOT_RUN', 'NORMAL_PROFILE_RUNTIME_GATE':'NOT_RUN',
            'physical_authorization':False, 'device_contacts':0, 'serial_io':0, 'flash_writes':0,
            'rtc_writes':0, 'reboots':0, 'device_filesystem_writes':0}
    if image is not None:
        _,checked=candidate(image,expected)
        report['PHASE_K_FROZEN_CANDIDATE_IDENTITY_GATE']=checked['PHASE_K_FROZEN_CANDIDATE_IDENTITY_GATE']
    return report


def main() -> int:
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--stub-audit-root',type=Path,required=True)
    p.add_argument('--candidate',type=Path)
    p.add_argument('--expected-sha256')
    args=p.parse_args()
    if bool(args.candidate)!=bool(args.expected_sha256):p.error('Candidate and external hash required together')
    try:print(json.dumps(qualify(args.stub_audit_root,args.candidate,args.expected_sha256),indent=2,sort_keys=True))
    except (ValueError,OSError,ImportError,TypeError) as exc:p.exit(1,'PHASE K GATE CLOSED: '+str(exc)+'\n')
    return 0


if __name__=='__main__':raise SystemExit(main())
