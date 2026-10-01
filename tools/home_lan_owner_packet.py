"""Prepare one private active P1 image locally. No device/network/write client.

Reuse reviewed AP/Digest credentials and the retained Mission 8 public point;
never generate a key or household credentials. Output must be outside Git.
"""
import argparse, hashlib, importlib.util, json, os, re, shutil, struct
import subprocess, sys
from pathlib import Path
from owner_install_packet_gate import private_pair, macros
from wifi_flash_preflight import inspect_image, staging_model
from v08_m8r_memory import inspect
from v08_m8_stack_gate import run_tool
from v07_pinned_core_probe import core_root

ROOT=Path(__file__).resolve().parents[1]
OEM_SHA='a6421f5bfee7860d97bed26620c346b8008f503e513702d4bfdf6e01010a7718'
V21_SHA='3252ba5cd1f85683945d4d9a87ce49118568c0977605debc089267f54d7f3b0e'
M8_SHA='269fcf2be7e61b4f581f892f36c519cca5ebf1ef41759d9923d9df90aad682fa'
INPUTS=('POLICY','CREDENTIALS','MEDIA_FIXTURE','OEM','V21','M8')
APP_NAME='SHINO-TV-P1-OWNER-NOT-A-FLASH-APPROVAL.bin'

def digest(path): return hashlib.sha256(Path(path).read_bytes()).hexdigest()

def regular(path):
    p=Path(path)
    if not p.is_file() or p.is_symlink(): raise ValueError('Regular local input required')
    return p.resolve()

def outside(path,root=ROOT):
    p=Path(path).resolve()
    if p==root.resolve() or root.resolve() in p.parents:
        raise ValueError('Private policy/credentials/output must be outside Git')
    return p

def checked_inputs(values):
    paths={k:regular(values[k]) for k in INPUTS}
    outside(paths['POLICY']); outside(paths['CREDENTIALS'])
    for k,n,h in [('OEM',494144,OEM_SHA),('V21',405712,V21_SHA),('M8',446944,M8_SHA)]:
        if paths[k].stat().st_size!=n or digest(paths[k])!=h:
            raise ValueError('Retained '+k+' bytes/hash mismatch')
    policy=macros(paths['POLICY'])
    for k,v in {'SHINO_BOOT_PROFILE':'0','SHINO_ENABLE_FACTORY_RESTORE':'1',
                'SHINO_FS_IMAGE_PRESENT':'0','SHINO_ENABLE_FS_MIGRATION':'0',
                'SHINO_ENABLE_NATIVE_SIGNED_OTA':'0'}.items():
        if policy.get(k)!=v: raise ValueError('Private policy safety prerequisite: '+k)
    if paths['MEDIA_FIXTURE'].stat().st_size>500000: raise ValueError('Fixture cap')
    point=bytes.fromhex(json.loads(paths['MEDIA_FIXTURE'].read_text(encoding='utf-8'))['public_point'])
    if len(point)!=65 or point[0]!=4 or point not in paths['M8'].read_bytes():
        raise ValueError('Retained media public identity does not match installed-lineage image')
    oem=inspect_image(paths['OEM'].read_bytes(),'OEM')
    official={'firmware_sha256':OEM_SHA,'firmware_md5_for_updater':oem['md5_for_arduino_updater']}
    private_pair(paths['POLICY'],paths['CREDENTIALS'],official,paths['V21'].read_bytes())
    return paths,point,official

def prepare_owner_shadow(repo,shadow,main,flags):
    if os.environ.get('CI') or os.environ.get('GITHUB_ACTIONS'):
        raise ValueError('Private owner build forbidden in CI')
    if 'SHINO_P1_OWNER_PRIVATE=1' not in str(flags): raise ValueError('Owner flag required')
    values={k:os.environ.get('SHINO_P1_'+k,'') for k in INPUTS}
    if not all(values.values()): raise ValueError('Explicit private owner inputs required')
    expected=os.environ.get('SHINO_P1_SOURCE_SHA','')
    actual=subprocess.check_output(['git','rev-parse','HEAD'],cwd=repo,text=True).strip()
    if not re.fullmatch('[0-9a-f]{40}',expected) or expected!=actual:
        raise ValueError('Exact private source SHA required')
    paths,point,_=checked_inputs(values)
    (shadow/'include/shino_private_policy.h').write_bytes(paths['POLICY'].read_bytes())
    (shadow/'include/M8TestKey.h').write_text('#pragma once\nstatic const uint8_t M8_TEST_PUBLIC_POINT[65]={'+','.join(map(str,point))+'};\n',encoding='utf-8')
    (shadow/'include/project_version.h').write_text('#pragma once\n#define PROJECT_VER_STR "P1-OWNER-QUALIFICATION"\n',encoding='utf-8')
    main.write_text('#include <Arduino.h>\n#include "original_main.inc"\nvoid setup(){shinoResearchSetup();}\nvoid loop(){shinoResearchLoop();}\n',encoding='utf-8')
    bridge=shadow/'src/boot/FirstBootBridge.cpp'
    s=bridge.read_text(encoding='utf-8')
    s='void p1OwnerObservation(JsonDocument&);\n'+s.replace('    heapDiagnostic.appendReadOnlyStatus(doc);','    heapDiagnostic.appendReadOnlyStatus(doc);\n    p1OwnerObservation(doc);')
    # Declaration must follow ArduinoJson include; use explicit include first.
    s='#include <ArduinoJson.h>\n'+s
    s+='''
void p1OwnerObservation(JsonDocument& doc) {
  // Prior cooperative counters only. No sample, action, secrets or reset here.
  const auto& r=m8::runtimeStats; const auto& c=m8::cryptoStats;
  JsonObject q=doc["p1_observation"].to<JsonObject>();
  q["boot"]=m8Boot; q["reset_reason"]=ESP.getResetInfoPtr()->reason;
  q["min_heap"]=r.minHeap; q["min_block"]=r.minBlock; q["min_cont"]=r.minCont;
  q["allocation_failures"]=r.allocationFailures+c.allocationFailures;
  q["canary_failures"]=c.canaryFailures; q["secondary_refs"]=stack_thunk_get_refcnt();
  q["secondary_used_max"]=c.maxUsed; q["arena_used_max"]=r.arenaMax;
  q["image_bytes"]=m7Receiver.imageBytes(); q["receiver_pending"]=m7Receiver.pending;
  q["render_max_us"]=artworkTiming.maxUs; q["render_slices"]=artworkTiming.slices;
}
'''
    bridge.write_text(s,encoding='utf-8')

def checksum(path):
    source=core_root()/'tools/elf2bin.py'
    spec=importlib.util.spec_from_file_location('p1_pinned_elf2bin',source)
    module=importlib.util.module_from_spec(spec);spec.loader.exec_module(module)
    data=bytearray(Path(path).read_bytes())
    length,crc=struct.unpack_from('<II',data,module.crcsize_offset)
    data[module.crcsize_offset:module.crcval_offset+4]=bytes(8)
    if length!=len(data) or module.crc8266(data)!=crc: raise ValueError('Core image CRC mismatch')
    for start in (0,4096):
        if data[start]!=0xe9 or data[start+2:start+4]!=bytes([2,64]): raise ValueError('ESP8266 DIO/4MiB/40MHz header mismatch')
        pos=start+8; value=0xef
        for _ in range(data[start+1]):
            _,size=struct.unpack_from('<II',data,pos);pos+=8
            if pos+size>len(data): raise ValueError('Segment exceeds image')
            for b in data[pos:pos+size]: value^=b
            pos+=size
        if data[start+((pos-start+16)//16)*16-1]!=value: raise ValueError('Segment XOR mismatch')
    return {'core_crc32':'PASS','original_segment_XOR_after_zeroing_reserved_CRC_fields':'PASS','elf2bin_sha256':digest(source)}

def verify_candidate(build,paths,point,official):
    app=build/'firmware.bin';elf=build/'firmware.elf';data=app.read_bytes()
    pairing=private_pair(paths['POLICY'],paths['CREDENTIALS'],official,data)
    if point not in data or b'PUBLIC-INERT-LAB' in data or b'P1-OFFLINE-UNSTARTED' in data:
        raise ValueError('Private active identity mismatch')
    for marker in (b'P1-OWNER-QUALIFICATION',b'SDK_SYSTEM_PARAMETERS_3FD000_400000',b'p1_observation',b'render_max_us'):
        if marker not in data: raise ValueError('Private owner capability marker absent')
    header=inspect_image(data,'P1 private candidate')
    if len(data)>=494144: raise ValueError('Conservative OEM application budget exceeded')
    nm=run_tool('nm','-C',elf)
    offsets={}
    for k,v in {'_FS_start':0x40300000,'_FS_end':0x405fa000,'_EEPROM_start':0x405fb000}.items():
        m=re.search(r'^([0-9a-f]+)\s+\w\s+'+k+r'$',nm,re.M)
        if not m or int(m[1],16)!=v: raise ValueError('Actual ELF linker offset mismatch')
        offsets[k]=v-0x40200000
    if 'shinoArtworkOfflineGuard' in nm or 'shinoResearchDisabled' in nm:
        raise ValueError('Inactive guard remained linked')
    if 'm8CryptoVerifyNative' not in nm or 'p1OwnerObservation' not in nm:
        raise ValueError('Native receiver/owner observations not linked')
    expected=json.loads((ROOT/'tools/home_lan_storage_manifest.json').read_text(encoding='utf-8'))
    if {k:digest(core_root()/k) for k in expected}!=expected: raise ValueError('Pinned SDK storage drift')
    models={k:staging_model(a,b,0x100000) for k,a,b in [('M8_to_OEM',446944,494144),('OEM_to_P1',494144,len(data)),('P1_to_OEM',len(data),494144),('OEM_to_V21',494144,405712)]}
    if any(not v['nominal_no_overlap'] or v['free_gap_bytes']<4096 for v in models.values()): raise ValueError('Wi-Fi-only staging gap failed')
    return {'candidate':header,'linked':inspect(elf),'linker_offsets':offsets,'image_checks':checksum(app),
            'pairing':pairing,'media_public_identity_matches_M8':True,'native_signed_OTA_enabled':False,
            'staging_models':models,'runtime_flash_geometry':'fresh read-only device preflight required',
            'rollback':{k:{'bytes':paths[k].stat().st_size,'sha256':digest(paths[k])} for k in ('OEM','V21','M8')},
            'device_contacts':0,'device_writes':0,'permission_to_flash':False}

def build_packet(args):
    if os.environ.get('CI') or os.environ.get('GITHUB_ACTIONS'): raise ValueError('Private build forbidden in CI')
    sha=subprocess.check_output(['git','rev-parse','HEAD'],cwd=ROOT,text=True).strip()
    if sha!=args.expected_source_sha: raise ValueError('Source SHA mismatch')
    if subprocess.check_output(['git','status','--porcelain'],cwd=ROOT,text=True).strip(): raise ValueError('Commit focused source before private build')
    values={k:str(getattr(args,k.lower())) for k in INPUTS}
    paths,point,official=checked_inputs(values)
    out=outside(args.out_dir)
    if out.exists() or not out.parent.is_dir(): raise ValueError('New private output directory required')
    out.mkdir()
    environment=dict(os.environ,**{'SHINO_P1_'+k:str(v) for k,v in paths.items()},SHINO_P1_SOURCE_SHA=sha)
    # Capture potentially private compiler diagnostics ONLY in the private kit.
    with (out/'PRIVATE-build.log').open('wb') as log:
        run=subprocess.run([sys.executable,'-m','platformio','run','-d','experiments/home_lan','-e','owner_compile'],cwd=ROOT,env=environment,stdout=log,stderr=subprocess.STDOUT,timeout=900)
    if run.returncode: raise ValueError('Private compile failed; inspect private log locally')
    build=ROOT/'experiments/home_lan/.pio/build/owner_compile'
    report=verify_candidate(build,paths,point,official)
    for name in ('firmware.bin','firmware.elf'):
        shutil.copyfile(build/name,out/(APP_NAME if name.endswith('.bin') else 'PRIVATE-candidate.elf'))
    for k,name in [('POLICY','shino_private_policy.h'),('CREDENTIALS','credentials.txt'),('OEM','OEM-V9.0.44-APPLICATION-ONLY.bin'),('V21','V21-review-003-ROLLBACK.bin'),('M8','M8-current-ROLLBACK.bin')]: shutil.copyfile(paths[k],out/name)
    report['source_commit']=sha;report['status']='PRIVATE_OFFLINE_READY__INSTALL_AUTHORIZATION_PENDING'
    public=json.dumps(report,indent=2)+'\n'
    secrets=macros(paths['POLICY'])
    if any(secrets[k] in public for k in ('SHINO_SETUP_AP_PSK','SHINO_RESCUE_HTTP_PASSWORD','SHINO_BOOTSTRAP_API_TOKEN')): raise ValueError('Sanitized report secret check failed')
    (out/'PREFLIGHT.json').write_text(public,encoding='utf-8')
    return report

def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--expected-source-sha',required=True)
    parser.add_argument('--out-dir',type=Path,required=True)
    for k in INPUTS: parser.add_argument('--'+k.lower().replace('_','-'),type=Path,required=True)
    try: report=build_packet(parser.parse_args())
    except Exception:
        print('Private preparation stopped; no device operation. Inspect local private prerequisites/log.',file=sys.stderr);return 1
    print(json.dumps({'source_commit':report['source_commit'],'candidate':{'bytes':report['candidate']['size_bytes'],'sha256':report['candidate']['sha256']},'status':report['status'],'device_writes':0}))
    return 0
if __name__=='__main__':raise SystemExit(main())
