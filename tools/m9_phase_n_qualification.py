#!/usr/bin/env python3
"""Phase N source/link/resource qualification. Local inputs only; no devices."""
from pathlib import Path
from configparser import ConfigParser
import argparse, hashlib, json, re
from m9_first_migration import inspect_candidate
ROOT=Path(__file__).resolve().parent.parent
ENV='esp12e_m9_4m2m_normal_qualification'
COUNTERS=dict(device_contacts=0,serial_io=0,flash_writes=0,rtc_writes=0,reboots=0,device_filesystem_writes=0)

def source_gate(root=ROOT):
    pins=json.loads((ROOT/'tools/m9_phase_n_sources.json').read_text())
    for name,digest in pins['current_sha256_lf'].items():
        actual=hashlib.sha256((root/name).read_bytes().replace(b'\r\n',b'\n')).hexdigest()
        if actual!=digest:raise ValueError('StageA source drift: '+name)
    from m9_mount_stack import source_audit
    predecessor=source_audit(root) # unchanged historical pins/physical tools; explicit projection scope.
    from m9_mount_probe_resources import source_gate as probe_gate
    probe_gate(root)
    ini=ConfigParser(interpolation=None);ini.read(root/'firmware/platformio.ini')
    normal=ini['env:'+ENV]
    assert normal['extends']=='env:esp12e_m9_4m2m'
    assert normal['board_build.ldscript']=='eagle.flash.4m2m.ld'
    assert normal['build_src_filter']=='+<*> -<boot/FirstBootBridge.cpp>'
    assert normal['build_flags'].split()==['${env:esp12e.build_flags}','-DSHINO_BOOT_PROFILE=1','-DSHINO_M9_NORMAL_QUALIFICATION=1','-fstack-usage']
    main=(root/'firmware/src/main.cpp').read_text()
    for body,required in ((main.split('void setup()')[1].split('#elif SHINO_BOOT_PROFILE == 1')[1].split('#elif SHINO_BOOT_PROFILE == 2')[0], 'M9NormalStageA::begin(configManager)'),
                          (main.split('void loop()')[1].split('#elif SHINO_BOOT_PROFILE == 1')[1].split('#elif SHINO_BOOT_PROFILE == 2')[0], 'M9NormalStageA::loop()')):
        assert required in body and 'FirstBootBridge::' not in body
    stage=(root/'firmware/src/boot/M9NormalStageA.cpp').read_text()
    config=(root/'firmware/src/config/ConfigManager.cpp').read_text().split('bool ConfigManager::loadMountedReadOnly')[1].split('#endif')[0]
    from m9_fsless_gate import code_only
    for text in (stage,config):
        body=code_only(text)
        for bad in ('FirstBootBridge::','SecureStorage::','secure.','EEPROM','rtcUserMemoryWrite','WiFi.begin(',
                    'RescueMode::','registerApiEndpoints','LittleFS.begin(','LittleFS.end(','LittleFS.format(',
                    'FactoryRollback::','Update.','connectToNetwork','startStationMode','serveStaticC','beginFS(',
                    'ESP.restart','ESP.reset(','config.save(','config.load()'):
            assert bad not in body,bad
    assert stage.count('M9LittleFsMountProbe::begin()')==1
    assert stage.index('WiFi.persistent(false)')<stage.index('network.startAccessPointMode()')
    status=stage.split('void status()')[1].split('void telemetry()')[0]
    assert 'if (!auth()) return;' in status
    for bad in ('ESP.','millis()','observer.poll','resetStack','M9LittleFsMountProbe::json'):assert bad not in status
    assert stage.count('observer.poll()')==1
    assert 'setStageAPrebody(beforeBody)' in stage and 'const String& payload' in stage
    assert 'loadMountedReadOnly(fs.mounted && fs.inventory_exact && fs.config_seed_exact)' in stage
    return dict(PHASE_N_SOURCE_GATE='PASS/OFFLINE',profile=1,environment=ENV,
                predecessor=predecessor,normal_physical_mount_gate='NOT_RUN',normal_physical_runtime_gate='NOT_RUN',
                physical_authorization=False,**COUNTERS)

def build_gate(candidate,symbols,sections,stack):
    text=symbols.read_text(encoding='utf-8-sig')
    for symbol,address in (('_FS_start',0x40400000),('_FS_end',0x405FA000),('_FS_block',8192),('_FS_page',256)):
        assert re.search(rf'(?mi)^{address:08x}\s+(?:[0-9a-f]+\s+)?A\s+{symbol}$',text),symbol
    for bad in ('FirstBootBridge::','ConfigManager::load()','ConfigManager::save()',
                'SecureStorage::begin(', 'SecureStorage::get(', 'SecureStorage::put(', 'SecureStorage::remove(',
                'EEPROMClass::begin(', 'EEPROMClass::commit(', 'RescueMode::', 'HomeLan::',
                'registerApiEndpoints(', 'WiFiManager::startStationMode(', 'WiFiManager::begin()',
                'WiFiManager::connectToNetwork(', 'NTPClient::', 'FactoryRollback::',
                'UpdaterClass::begin(', 'UpdaterClass::write(', 'UpdaterClass::end(', 'EspClass::rtcUserMemoryWrite('):
        assert bad not in text,bad
    for required in ('M9NormalStageA::begin(', 'M9NormalStageA::loop()', 'ConfigManager::loadMountedReadOnly(',
                     'M9LittleFsMountProbe::begin()', 'ReadOnlyImpl::denyProg(', 'ReadOnlyImpl::denyErase(',
                     'FslessMetrics::apply(', 'M9NormalDashboard::render()', 'Webserver::begin()', 'DisplayManager::begin('):
        assert required in text,required
    image=inspect_candidate(candidate)
    assert image['sector_rounded_write_extent']<0x100000
    sizes={k:int(v) for k,v in re.findall(r'(?m)^(\.\S+)\s+(\d+)\s+\d+',sections.read_text())}
    ram=sum(sizes.get(k,0) for k in ('.data','.rodata','.bss'))
    flash=sum(sizes.get(k,0) for k in ('.text','.text1','.irom0.text','.data','.rodata'))
    assert ram<=49152,'Static RAM budget: retain >=32 KiB before runtime allocations'
    assert sizes.get('.noinit',0)==56,'Reserved noinit must not grow'
    frames={}
    selected={'main.cpp.su','M9NormalStageA.cpp.su','M9NormalDashboard.cpp.su','ConfigManager.cpp.su','M9LittleFsMountProbe.cpp.su','Webserver.cpp.su'}
    abi_proofs={}
    for path in stack.rglob('*.su'):
        if path.name not in selected:continue
        source=path.read_text(encoding='utf-8-sig')
        if path.name in ('Webserver.cpp.su','M9NormalStageA.cpp.su'):
            assert 'm9-normal-libs/esp8266webserver/src/' in source.replace('\\','/').lower(), 'Mixed stock/StageA Webserver ABI'
            abi_proofs[path.name]='ENVIRONMENT_LOCAL_STAGE_A_HEADER'
        for line in source.splitlines():
            fields=line.split('\t')
            if len(fields)!=3:continue
            name=re.sub(r'^.*?:\d+:\d+:','',fields[0])
            # Legacy ConfigManager::load/save are compiled but GC-unlinked.
            if 'ConfigManager::load()' in name or 'ConfigManager::save()' in name:continue
            frames[name]=max(frames.get(name,0),int(fields[1]))
    assert frames and any('M9NormalStageA::begin(' in name for name in frames)
    assert len(abi_proofs)==2 and any('_parseRequest(' in name for name in frames)
    assert max(frames.values())<=1024,'Individual major StageA frame exceeds 1024 B'
    return dict(PHASE_N_LINK_RESOURCE_GATE='PASS/OFFLINE',image=image,linked_flash_bytes=flash,
                static_ram_bytes=ram,noinit_bytes=sizes['.noinit'],major_frames_bytes=frames,
                webserver_abi_proofs=abi_proofs,
                compiler_frames_are_not_physical_stack_pass=True,physical_authorization=False,**COUNTERS)

def main():
    p=argparse.ArgumentParser(description=__doc__)
    for arg in ('candidate','symbols','sections','stack'):p.add_argument('--'+arg,type=Path)
    args=p.parse_args();r=source_gate()
    values=[getattr(args,arg) for arg in ('candidate','symbols','sections','stack')]
    if any(values):
        if not all(values):p.error('All four local build inputs required')
        r['build']=build_gate(*values)
    print(json.dumps(r,indent=2,sort_keys=True))
if __name__=='__main__':main()
