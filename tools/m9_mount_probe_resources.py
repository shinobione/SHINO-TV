#!/usr/bin/env python3
"""Phase J OFFLINE source/Core/paired image/resource gate; no device executor."""
from __future__ import annotations
import argparse
from configparser import ConfigParser
import hashlib
import json
from pathlib import Path
import re
from m9_mount_probe import ROOT, source_gate as probe_source_gate, build_gate

FLAG = "SHINO_M9_MOUNT_PROBE_RESOURCE_DIAGNOSTICS"
ENV = "env:esp12e_m9_4m2m_mount_probe_resources"


def uninstrumented_source(path: str, text: str) -> str:
    from m9_phase_n_compat import predecessor
    text = predecessor(path, text)
    text = text.replace('#include "boot/M9MountProbeResources.h"\n', '')
    if path.endswith('main.cpp'):
        for call in ('beforeMount()', 'afterMount()', 'poll()'):
            text = re.sub(r'#if '+FLAG+r' == 1\n    M9MountProbeResources::'+
                          re.escape(call)+r';[^\n]*\n#endif\n', '', text)
    elif path.endswith('FirstBootBridge.cpp'):
        text = text.replace('#if '+FLAG+' == 1\n'
            '        if (!M9MountProbeResources::sendStatus(server))\n'
            '            respond(500, F("{\\"error\\":\\"PROBE_STATUS_OVERFLOW\\"}"));\n#else\n', '')
        text = text.replace('        respond(200, body);\n#endif\n', '        respond(200, body);\n')
    elif path.endswith('M9LittleFsMountProbe.cpp'):
        text = text.replace('#if '+FLAG+' == 0\n    observeHeap();\n#endif\n', '    observeHeap();\n')
    return text


def source_gate(root: Path = ROOT) -> dict:
    probe_source_gate(root)
    from m9_mount_stack import baseline_sources
    pins = baseline_sources()
    for path, digest in pins['sha256_lf'].items():
        source = (root/path).read_text(encoding='utf-8')
        restored = uninstrumented_source(path, source)
        assert hashlib.sha256(restored.encode()).hexdigest() == digest, path
    ini = ConfigParser(interpolation=None)
    ini.read(root/'firmware/platformio.ini', encoding='utf-8')
    for key, expected in pins['environments'].items():
        assert dict(ini[key]) == expected, key
    assert ini[ENV]['extends'] == 'env:esp12e_m9_4m2m_mount_probe'
    assert ini[ENV]['build_flags'].splitlines() == [
        '', '${env:esp12e_m9_4m2m_mount_probe.build_flags}', '-D'+FLAG+'=1']
    main = (root/'firmware/src/main.cpp').read_text()
    profile = main.split('#elif SHINO_BOOT_PROFILE == 2')[1].split('#else')[0]
    calls = ['FirstBootBridge::run()', 'M9MountProbeResources::beforeMount()',
             'M9LittleFsMountProbe::begin()', 'M9MountProbeResources::afterMount()',
             'EspClass::wdtEnable']
    assert all(profile.count(x)==1 for x in calls), 'Missing/duplicate mount-window call'
    assert [profile.index(x) for x in calls] == sorted(profile.index(x) for x in calls)
    loop = main.split('void loop()')[1].split('#elif SHINO_BOOT_PROFILE == 2')[1].split('#else')[0]
    calls = ['FirstBootBridge::loop()', 'M9LittleFsMountProbe::poll()', 'M9MountProbeResources::poll()']
    assert all(loop.count(x)==1 for x in calls), 'Missing/duplicate loop observation call'
    assert [loop.index(x) for x in calls] == sorted(loop.index(x) for x in calls)
    observer = (root/'firmware/include/boot/M9ResourceObserver.h').read_text()
    assert observer.count('source_.resetStack();') == 2
    poll = observer.split('    void poll()')[1].split('    const Observation&')[0]
    assert 'resetStack' not in poll and '< 1000' in poll and 'lastAttemptMs_ = now;' in poll
    adapter = (root/'firmware/src/boot/M9MountProbeResources.cpp').read_text()
    for call in ('ESP.getHeapStats(&out.free, &out.largest, &out.fragmentation)',
                 'ESP.getFreeContStack()', 'ESP.resetFreeContStack()'):
        assert adapter.count(call) == 1, call
    send = adapter.split('bool sendStatus(')[1]
    assert 'observer.status()' in send
    for forbidden in ('observer.poll', 'observer.afterMount', 'observer.beforeMount', 'ESP.', 'millis()'):
        assert forbidden not in send, forbidden
    header = (root/'firmware/include/boot/M9ResourceJson.h').read_text()
    for forbidden in ('ESP.', 'millis()', 'heap(', 'stack(', 'ArduinoJson', 'String'):
        assert forbidden not in header, forbidden
    from m9_fsless_gate import code_only, FORBIDDEN
    for source in map(code_only, (observer, adapter, header)):
        assert FORBIDDEN.search(source) is None, 'Storage/flash/RTC writer in observer'
        for forbidden in ('LittleFS.', 'ConfigManager', 'SecureStorage', 'EEPROM.', 'WiFi.',
                          'Update.', 'new ', 'malloc(', 'Ticker', 'attachInterrupt', 'ESP.restart'):
            assert forbidden not in source, forbidden
    assert re.findall(r'ESP\.(\w+)\(',adapter) == ['resetFreeContStack','getFreeContStack','getHeapStats']
    assert 'JSON_CHUNK_BYTES = 768' in header and '12 * 8 + 3 * 1 + 3' in header
    assert header.index('!suffix(') < header.index('sink.begin(')
    return {'PHASE_J_RESOURCE_INSTRUMENTATION_SOURCE_GATE':'PASS/OFFLINE',
            'profile':2, 'environment':ENV, 'sample_interval_ms':1000,
            'PHYSICAL_RESOURCE_THRESHOLD':'REVIEW_REQUIRED',
            'MOUNT_PROBE_PHYSICAL_GATE':'PARTIAL / HOLD',
            'MOUNT_PROBE_RESOURCE_PHYSICAL_GATE':'HOLD / NOT_RUN',
            'NORMAL_PROFILE_LITTLEFS_MOUNT_GATE':'NOT_RUN', 'NORMAL_PROFILE_RUNTIME_GATE':'NOT_RUN',
            'device_contacts':0, 'device_writes':0, 'physical_authorization':False}


def core_gate(core: Path) -> dict:
    from m9_mount_probe import core_gate as probe_core_gate
    probe_core_gate(core)
    assert json.loads((core/'package.json').read_text())['version'] == '3.30102.0'
    pins = json.loads((ROOT/'tools/m9_resource_core_sources.json').read_text())
    for path, expected in pins.items():
        assert hashlib.sha256((core/path).read_bytes().replace(b'\r\n',b'\n')).hexdigest() == expected, path
    header = (core/'cores/esp8266/Esp.h').read_text()
    assert 'getHeapStats(uint32_t* free = nullptr, uint32_t* max = nullptr, uint8_t* frag = nullptr)' in header
    impl = (core/'cores/esp8266/Esp.cpp').read_text()
    assert 'return cont_get_free_stack(g_pcont);' in impl
    assert 'cont_repaint_stack(g_pcont);' in impl
    assert '#define CONT_STACKSIZE 4096' in (core/'cores/esp8266/cont.h').read_text()
    return {'status':'PASS_PINNED_CORE_RESOURCE_APIS', 'resource_source_files_checked':len(pins),
            'fs_source_files_checked':7, 'continuation_stack_bytes':4096,
            'stack_reset':'Repaint below current SP minus 64 bytes; not a device reset',
            'fragmentation':'Core L2 / Euclidean free-hole metric, not 100*(1-largest/free)'}


def section_sizes(path: Path) -> dict:
    result = {}
    for line in path.read_text(encoding='utf-8-sig').splitlines():
        parts = line.split()
        if len(parts)==3 and parts[0].startswith('.') and parts[1].isdigit():result[parts[0]]=int(parts[1])
    return {'linked_flash_bytes':sum(result[x] for x in ('.data','.rodata','.text','.text1','.irom0.text')),
            'static_ram_bytes':sum(result[x] for x in ('.data','.rodata','.bss')),
            'noinit_bytes':result['.noinit']}


def stack_frames(directory: Path) -> dict:
    frames = {}
    for path in directory.rglob('*.su'):
        if path.name not in ('main.cpp.su','FirstBootBridge.cpp.su','M9LittleFsMountProbe.cpp.su','M9MountProbeResources.cpp.su'):continue
        for line in path.read_text(encoding='utf-8-sig').splitlines():
            parts=line.split('\t')
            if len(parts)==3:
                name=re.sub(r'^.*?:\d+:\d+:', '', parts[0])
                key=path.name+':'+name
                frames[key]=max(frames.get(key,0),int(parts[1]))
    assert frames, 'Compiler stack reports absent'
    return frames


def paired_build(baseline_sections: Path, instrumented_sections: Path,
                 baseline_stack: Path, instrumented_stack: Path) -> dict:
    baseline=section_sizes(baseline_sections);instrumented=section_sizes(instrumented_sections)
    delta={k:instrumented[k]-baseline[k] for k in baseline}
    assert delta['static_ram_bytes'] <= 512, 'Static RAM review budget exceeded'
    assert delta['linked_flash_bytes'] <= 8192, 'Linked flash review budget exceeded'
    old=stack_frames(baseline_stack);new=stack_frames(instrumented_stack)
    added={k:v for k,v in new.items() if k.startswith('M9MountProbeResources.cpp.su:')}
    assert added and max(added.values()) <= 1024, 'New individual frame review budget exceeded'
    assert all(v<=1024 for k,v in new.items() if k not in old), 'New handler/setup frame budget exceeded'
    return {'PHASE_J_RESOURCE_INSTRUMENTATION_BUILD_GATE':'PASS/OFFLINE',
            'baseline':baseline, 'instrumented':instrumented, 'delta':delta,
            'new_individual_frames_bytes':added,
            'common_frame_deltas_bytes':{k:new[k]-v for k,v in old.items() if k in new},
            'baseline_frames_bytes':old, 'instrumented_frames_bytes':new,
            'compiler_frames_are_not_physical_stack_margin':True}


def future_packet() -> dict:
    from m9_mount_probe import future_packet as original_packet
    packet=original_packet()
    packet['scope']='PRINT ONLY / NOT AUTHORIZED BY PHASE J'
    command=packet['steps'][2].replace('PHASE H','PHASE J').replace('<EXACT_PROBE_BIN>','<EXACT_RESOURCE_PROBE_BIN>')
    packet['steps'] = [
        'Fresh same-unit ROM/chip/4 MiB qualification; private rollback authority verified',
        'Exact instrumented application/source/policy/hash and fresh exact-operation owner consent',
        'GPIO0 LOW throughout fresh full 4 MiB PRE / application-only write / full POST before first application boot',
        'PRE[0x200000:0x3FA000] equals retained frozen Stage-2 image; no private dump/digest/path publication',
        'REVIEW REQUIRED before any write: executor must prohibit automatic/internal uncertain retries; connect-attempts 1 alone does not prove that policy',
        command,
        'Full POST exact candidate at zero; POST[rounded_candidate_end:0x400000] == PRE[rounded_candidate_end:0x400000]',
        'Powered RTC words 0/0 verified; GPIO0 release and existing RST; no cold-power substitution',
        'Normal boot; mount/inventory/config exact and blocked_write_attempts == 0',
        'Capture mount-phase continuation start/min-free and post-probe free/largest-block/fragmentation',
        '180-second LINK stable/stale/recovery, no reset; runtime free/block minima, max fragmentation, min continuation free',
        'resource_measurements_valid == true, rejected samples == 0, sample count advances, final mount status exact',
        'PHYSICAL_RESOURCE_THRESHOLD = REVIEW_REQUIRED; separately reviewed floor and actual measurements required before gate closure',
        'No automatic retry or rollback; any ambiguous result = STOP; do not activate full normal profile']
    packet['automatic_retry']=False
    packet['executor_retry_policy']='REVIEW_REQUIRED before any write; command template is not an executable no-retry qualification'
    return packet


def main() -> int:
    p=argparse.ArgumentParser(description=__doc__)
    for name in ('core-root','symbols','candidate','baseline-sections','instrumented-sections','baseline-stack','instrumented-stack'):
        p.add_argument('--'+name,type=Path)
    args=p.parse_args();report=source_gate()
    if args.core_root:report['core']=core_gate(args.core_root)
    if bool(args.symbols)!=bool(args.candidate):p.error('symbols/candidate required together')
    if args.candidate:
        report['image']=build_gate(args.symbols,args.candidate)
        assert 'M9MountProbeResources::' in args.symbols.read_text(encoding='utf-8-sig')
        report['image']['filesystem_ceiling_margin_bytes']=0x200000-report['image']['sector_rounded_write_extent']
    pair=(args.baseline_sections,args.instrumented_sections,args.baseline_stack,args.instrumented_stack)
    if any(pair) and not all(pair):p.error('all four paired resource inputs required')
    if all(pair):report['paired_build']=paired_build(*pair)
    report['future_packet']=future_packet()
    print(json.dumps(report,sort_keys=True,indent=2))
    return 0
if __name__=='__main__':raise SystemExit(main())
