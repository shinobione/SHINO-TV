"""One-command, DEVICE-DISCONNECTED qualification for SHINO 256-byte Core.

Builds only public, inert StageA copies in a disposable directory. This script
never opens COM, performs serial I/O, flashes, reboots, or enables live OTA.
GitHub Actions being queued does not authorize a physical candidate.
"""
import json,os,shutil,subprocess,sys,tempfile,time,traceback
from pathlib import Path
from m9_stagea_build import ROOT,ENV
from shino_wifi_build import prepare as prepare_baseline
from shino_maintenance_build import prepare as prepare_small

RESULT=ROOT/'research-local'/'shino-offline-check-result.json'
LOG=ROOT/'research-local'/'shino-offline-check-last.log'

def step(name,argv,log):
    print('[SHINO OFFLINE]',name,flush=True)
    with log.open('a',encoding='utf-8',errors='replace') as stream:
        stream.write('\n## '+name+'\n')
        stream.flush()
        r=subprocess.run(argv,cwd=ROOT,stdout=stream,stderr=subprocess.STDOUT,
                         stdin=subprocess.DEVNULL,check=False)
    if r.returncode:
        last=log.read_text(encoding='utf-8',errors='replace')[-3000:]
        raise RuntimeError(name+' FAILED ('+str(r.returncode)+'). Last log:\n'+last)

def main():
    (ROOT/'research-local').mkdir(exist_ok=True)
    if RESULT.exists(): RESULT.unlink()
    LOG.write_text('SHINO / OFFLINE 256-BYTE CHECK — no device operations\n',encoding='utf-8')
    step('Xtensa nested call-graph verifier regression', [sys.executable,str(ROOT/'tools/test_shino_xtensa_callgraph.py')],LOG)
    step('Windows/POSIX local framework URI regression', [sys.executable,str(ROOT/'tools/test_shino_local_uri.py')],LOG)
    pio=shutil.which('pio') or shutil.which('platformio')
    if not pio: raise RuntimeError('Install PlatformIO 6.1.18 and its pinned public Core; no hardware needed.')
    with tempfile.TemporaryDirectory(prefix='shino-256-review-',dir=ROOT/'research-local') as scratch:
        temp=Path(scratch);baseline=temp/'baseline';candidate=temp/'candidate'
        prepare_baseline(baseline,False)
        prepare_small(candidate,small_buffer=True)
        # Only the build command: no "upload", no port, no serial, no live flag.
        cmd=[pio,'run','-e',ENV]
        step('Baseline public Xtensa StageA build',cmd[:2]+['-d',str(baseline)]+cmd[2:],LOG)
        step('Real locally patched 256 B Xtensa build',cmd[:2]+['-d',str(candidate)]+cmd[2:],LOG)
        host=temp/'host.json';resource=temp/'resources.json'
        with host.open('w',encoding='utf-8') as out:
            p=subprocess.run([sys.executable,str(ROOT/'tools/shino_small_buffer_native.py')],
                 cwd=ROOT,stdin=subprocess.DEVNULL,stdout=out,stderr=subprocess.PIPE,
                 text=True,check=False)
        if p.returncode: raise RuntimeError('Pinned Core host faults failed: '+p.stderr[-2500:])
        with resource.open('w',encoding='utf-8') as out:
            p=subprocess.run([sys.executable,str(ROOT/'tools/shino_small_buffer_resources.py'),
                 str(baseline),str(candidate)],cwd=ROOT,stdin=subprocess.DEVNULL,
                 stdout=out,stderr=subprocess.PIPE,text=True,check=False)
        if p.returncode: raise RuntimeError('Real ELF/package proof failed: '+p.stderr[-2500:])
        h=json.loads(host.read_text());r=json.loads(resource.read_text())
        assert h['actual_core'] and h['cases']==230 and h['interruption_boundaries']==197
        assert h['core_updater_buffer_bytes']==256 and h['network_calls']==0
        assert r['isolated_framework_package_verified'] and r['small_core_buffer_bytes']==256
        assert r['verdict']=='HOLD_FOR_NATIVE_OBSERVATION'
        assert r['floors']==dict(heap=20480,largest=16384,stack=2048,fragmentation=25)
        assert not r['activation'] and not r['trusted_consent_bound']
        assert r['delta']['noinit']==0
        for n in ('device_contacts','serial_io','flash_writes','rtc_writes','reboots',
                  'device_filesystem_writes'):
            assert r[n]==0
        result={'status':'PASS_OFFLINE_NOT_PHYSICAL',
                'measured_device_memory':'NOT_MEASURED',
                'live_installer':'DISABLED',
                'exact_core_256_verified':True,
                'host_cases':h['cases'],'interruptions':h['interruption_boundaries'],
                'bin_delta':r['delta']['bin_bytes'],
                'static_ram_delta':r['delta']['static_ram'],
                'illustrative_heap_margin':r['scenario_post_buffer_margin_above_floor'],
                'physical_flash_authorized':False}
        RESULT.write_text(json.dumps(result,indent=2)+'\n',encoding='utf-8')
        print(json.dumps(result,indent=2),flush=True)
        print('Saved: '+str(RESULT))
    return 0

if __name__=='__main__':
    try: sys.exit(main())
    except Exception as exc:
        print('SHINO qualification stopped: '+str(exc),file=sys.stderr)
        print('See '+str(LOG),file=sys.stderr)
        sys.exit(2)
