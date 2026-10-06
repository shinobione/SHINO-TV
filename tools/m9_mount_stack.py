#!/usr/bin/env python3
"""Focused profile-2 scratch source/frame audit. No device or build execution."""
import argparse
import hashlib
import json
from pathlib import Path
import re

ROOT = Path(__file__).resolve().parent.parent
PINS = ROOT / 'tools/m9_mount_stack_sources.json'
CHANGED = {'firmware/include/boot/M9ProbeStream.h',
           'firmware/src/boot/M9LittleFsMountProbe.cpp'}


def pins():
    result = json.loads(PINS.read_text(encoding='utf-8'))
    assert set(result['successor_sha256_lf']) == CHANGED
    assert set(result['uninstrumented_successor_sha256_lf']) == CHANGED
    return result


def baseline_sources():
    # Preserve J's historical pins on disk. Only the two owner-authorized
    # workspace transformations have separate current-source pins.
    baseline = json.loads((ROOT/'tools/m9_resource_baseline_sources.json').read_text(encoding='utf-8'))
    baseline['sha256_lf'].update(pins()['uninstrumented_successor_sha256_lf'])
    return baseline


def source_audit(root=ROOT):
    historical=json.loads((ROOT/'tools/m9_phase_k_sources.json').read_text(encoding='utf-8'))
    expected=historical['firmware_sha256_lf'].copy()
    expected.update(pins()['successor_sha256_lf'])
    for name,digest in expected.items():
        actual=hashlib.sha256((root/name).read_bytes().replace(b'\r\n',b'\n')).hexdigest()
        if actual != digest:raise ValueError('Mount-stack source pin changed: '+name)
    for name,digest in pins()['unchanged_tool_sha256_lf'].items():
        if hashlib.sha256((root/name).read_bytes().replace(b'\r\n',b'\n')).hexdigest()!=digest:
            raise ValueError('Physical runner/transaction/policy changed: '+name)
    return {'firmware_files_checked':len(expected),
            'firmware_files_unchanged':len(expected)-len(CHANGED),
            'firmware_mount_stack_changes':sorted(CHANGED),
            'installed_candidate_role':'HISTORICAL_J_PREDECESSOR_ONLY',
            'PHASE_MOUNT_STACK_SOURCE_GATE':'PASS/OFFLINE'}


def frames(directory):
    result={}
    for path in directory.rglob('*.su'):
        if path.name != 'M9LittleFsMountProbe.cpp.su':continue
        for line in path.read_text(encoding='utf-8-sig').splitlines():
            fields=line.split('\t')
            if len(fields)==3:
                name=re.sub(r'^.*?:\d+:\d+:','',fields[0])
                result[name]=max(result.get(name,0),int(fields[1]))
    assert result,'Compiler frames absent'
    return result


def frame_gate(directory, symbols):
    current=frames(directory)
    begin=[v for k,v in current.items() if k=='void M9LittleFsMountProbe::begin()']
    payload=[v for k,v in current.items() if k.endswith('::checkPayloads()')]
    assert len(begin)==1 and len(payload)<=1,'Exact linked mount frames absent'
    linked=symbols.read_text(encoding='utf-8-sig')
    assert 'M9LittleFsMountProbe::begin()' in linked,'Linked begin absent'
    if not payload:
        assert '::checkPayloads()' not in linked and 'M9ProbeStream::validate' not in linked,'Missing compiler frame for linked validation'
    old=pins()['predecessor_frames_bytes']
    reduction=old['begin']+old['checkPayloads']-begin[0]-(payload[0] if payload else 0)
    assert reduction>=384,'Linked mount frames reduction below 384 B'
    assert max(current.values())<=1024,'Affected individual frame exceeds 1024 B'
    workspace=re.findall(r'(?m)^\w+\s+([0-9a-fA-F]+)\s+b\s+M9LittleFsMountProbe::\(anonymous namespace\)::payloadWorkspace$',linked)
    assert len(workspace)==1 and int(workspace[0],16)<=512,'Single bounded BSS workspace absent'
    return {'begin':begin[0],'checkPayloads':payload[0] if payload else 'INLINED_IN_BEGIN',
            'validate':'INLINED_IN_BEGIN' if not payload else 'INLINED_IN_CHECKPAYLOADS',
            'workspace_bss_bytes':int(workspace[0],16),
            'linked_mount_frames_reduction_bytes':reduction,
            'all_probe_frames_bytes':current,
            'compiler_frames_are_not_physical_stack_pass':True}


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--stack',type=Path)
    parser.add_argument('--symbols',type=Path)
    args=parser.parse_args()
    result=source_audit()
    if bool(args.stack)!=bool(args.symbols):parser.error('Stack and symbols required together')
    if args.stack:result['frames']=frame_gate(args.stack,args.symbols)
    result.update(physical_authorization=False,physical_resource_gate='HOLD',
                  device_contacts=0,serial_io=0,flash_writes=0,rtc_writes=0,
                  reboots=0,device_filesystem_writes=0)
    print(json.dumps(result,indent=2,sort_keys=True))


if __name__=='__main__':main()
