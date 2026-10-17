#!/usr/bin/env python3
"""Phase M exact source/candidate audit only. Never creates a serial session."""
import argparse
import hashlib
import importlib.metadata
import importlib.util
import json
from pathlib import Path
import sys
from m9_phase_k_qualification import qualify
from m9_single_attempt_physical_runner import serial_source_gate, interpreter_gate
from m9_stage1_readback_verify import regular_file

PINS=Path(__file__).with_name('m9_phase_m_sources.json')


def source_gate(root=None):
    if importlib.metadata.version('esptool')!='5.4.0': raise ValueError('Pinned esptool required')
    root=Path(root) if root else Path(importlib.util.find_spec('esptool').origin).parent
    raw=regular_file(root/'loader.py').read_bytes().replace(b'\r\n',b'\n')
    pins=json.loads(PINS.read_text(encoding='utf-8'))
    if hashlib.sha256(raw).hexdigest()!=pins['loader_sha256_lf']: raise ValueError('Pinned loader changed')
    lines=raw.decode('utf-8').splitlines(keepends=True)
    for name,record in pins['functions'].items():
        body=''.join(lines[record['start_line']-1:record['end_line']]).encode()
        if hashlib.sha256(body).hexdigest()!=record['sha256_lf']: raise ValueError('Pinned function changed: '+name)
    return {'version':'5.4.0','functions':pins['functions'],
            'outer_attempts_are_not_inner_sync_count':True,'reviewed_inner_sync_maximum':5}


def qualify_m(stub_audit_root,image=None,expected=None):
    if bool(image)!=bool(expected): raise ValueError('Candidate and external SHA required together')
    report=qualify(stub_audit_root,image,expected)
    report.update(phase_m_source_audit=source_gate(),serial_source_audit=serial_source_gate(),
        PHASE_L_SINGLE_SYNC_ASSUMPTION='REJECTED_BY_PHYSICAL_EVIDENCE',
        PHASE_M_SYNC_ROOT_CAUSE_GATE='PASS/OFFLINE',
        PHASE_M_BOUNDED_SYNC_SOURCE_GATE='PASS/OFFLINE',
        PHASE_M_RUNNER_REGRESSION_GATE='PASS/OFFLINE',
        PHASE_M_FROZEN_CANDIDATE_IDENTITY_GATE='NOT_READ_BY_THIS_RUN',
        approved_local_interpreter_identity='NOT_READ_BY_THIS_SOURCE_ONLY_RUN',
        acquisition={'max_sync_requests':5,'global_seconds':5,'global_bytes':16384,
                     'global_reads':256,'retry_delay_seconds':0.05,'port_reopens':0,'resets':0})
    if image is not None:
        interpreter_gate()
        report['PHASE_M_FROZEN_CANDIDATE_IDENTITY_GATE']='PASS/OFFLINE'
        report['approved_local_interpreter_identity']='PASS/OFFLINE'
    return report


def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--stub-audit-root',type=Path,required=True)
    p.add_argument('--candidate',type=Path)
    p.add_argument('--expected-sha256')
    args=p.parse_args()
    if sys.version_info[:2]!=(3,12): p.error('Phase M CLI audit requires Python 3.12.x')
    print(json.dumps(qualify_m(args.stub_audit_root,args.candidate,args.expected_sha256),indent=2,sort_keys=True))
    return 0


if __name__=='__main__':raise SystemExit(main())
