"""Actual callable Xtensa graph and explicit remaining native memory uncertainty."""
import argparse,json,os,re,struct,subprocess
from pathlib import Path
from shino_wifi_resources import one
from m9_stagea_resources import symbols_with_data
from m9_stagea_build import ROOT,ENV

def run(baseline,candidate):
    base=one(baseline);built=one(candidate)
    assert base['inputs']['firmware_LF_sha256']==built['inputs']['firmware_LF_sha256']
    assert base['dependencies']==built['dependencies'] and base['identity_sha256']==built['identity_sha256']
    assert built['inputs']['maintenance_callable'] and not built['inputs']['trusted_consent_bound']
    assert base['noinit']==built['noinit']==56
    # Deployed/default/StageA sources remain byte-identical to the old freeze.
    for name in subprocess.check_output(['git','ls-files','firmware'],cwd=ROOT,text=True).splitlines():
        assert subprocess.check_output(['git','show','2b9ef75b4cf650277baae8da871ebe41f3227ddf:'+name],cwd=ROOT).replace(b'\r\n',b'\n')==(ROOT/name).read_bytes().replace(b'\r\n',b'\n')
    elf=Path(candidate)/'.pio/build'/ENV/'firmware.elf';symbols=symbols_with_data(elf)
    rows=[v for k,v in symbols.items() if 'maintenanceSizes' in k];assert len(rows)==1
    types=dict(zip(('http','native','owner','string','handler','uri'),struct.unpack('<6I',rows[0]['data'])))
    assert types['owner']>=max(types['http'],types['native']) and types['string']==12
    assert not any('retainedInstall' in k or 'shinoInstallProof' in k for k in symbols)
    packages=Path(os.environ.get('PLATFORMIO_CORE_DIR',str(Path.home()/'.platformio')))/'packages'
    objdump=next((packages/'toolchain-xtensa/bin').glob('xtensa-lx106-elf-objdump*'))
    disassembly=subprocess.check_output([str(objdump),'-dC',str(elf)],text=True)
    loop=re.search(r'<M9NormalStageA::loop\(\)>:\n(.*?)(?=\n[0-9a-f]+ <|\Z)',disassembly,re.S).group(1)
    calls=[s.strip() for s in loop.splitlines() if 'call' in s]
    assert any('shinoMaintenanceConsent' in s for s in calls)
    assert any('ShinoInstall::Native::pump' in s for s in calls)
    assert any('ShinoInstall::Native::begin' in s for s in calls)
    assert any('ShinoInstall::ReclaimingHttp::quiesce' in s for s in calls)
    delta={k:built[k]-base[k] for k in ('static_ram','bin_bytes','linked_flash','noinit')}
    def frame(term):return max(r['bytes'] for r in built['frames'] if term in r['function'])
    shared=frame('M9NormalStageA::loop')+frame('Native::pump')+frame('Native::line')
    # Exactly five collected header records and five FunctionRequestHandlers.
    # Native sizeof + pinned String rounding; payload only, not malloc/lwIP proof.
    normal_payload=dict(header_records=5*2*types['string'],handlers=5*types['handler'],uris=5*types['uri'],
        header_name_buffers=96,route_string_buffers=128)
    normal_known=sum(normal_payload.values())
    return dict(verdict='NO_GO',principal_blocker='SIMULTANEOUS_NATIVE_MEMORY_FLOOR_NOT_ESTABLISHED',
        callable_native='PASS_OFFLINE',host_lifecycle='SEPARATE_HOST_EVIDENCE',baseline=base,candidate=built,delta=delta,
        native_types=types,loop_direct_calls=calls,normal_known_dynamic_payload=normal_payload,
        normal_known_dynamic_payload_total=normal_known,
        reclaim_credit_limit='724 B native payload is guaranteed only after normal registration. Metadata, request Strings, active/queued clients and fragmentation vary. Host release is not physical high-water.',
        maintenance_dynamic_payload=dict(updater=4096,secondary_stack=0,rsa=0,json=0,ordinary_http=0),
        static_dashboard_or_telemetry_reclaim=0,key='32 B copied into static owner, erased on abort; no double-counted heap key',
        floors=dict(heap=20480,largest=16384,stack=2048,fragmentation=25),
        admission_heap=25600,resume_reserve=5120,normal_construct_payload=normal_known,
        observed_owner=dict(heap=30224,largest=30008,stack=3248,simultaneous=False),
        illustrative_tcp_reserve=4096,scenario_without_http_credit=30224-delta['static_ram']-4096-4096,
        scenario_with_known_http_payload_credit=30224-delta['static_ram']-4096-4096+normal_known,
        scenario_margin_without_http_credit=30224-delta['static_ram']-4096-4096-20480,
        scenario_margin_with_known_http_payload_credit=30224-delta['static_ram']-4096-4096+normal_known-20480,
        partial_auth_frames=shared+frame('Native::authorizeLine')+frame('ShinoInstall::mac'),
        partial_commit_frames=shared+frame('Native::commitLine')+frame('Receiver::stagedImage')+frame('Receiver::segments'),
        unknown='No native upper bound for SDK/AP, ClientContext, tcp_pcb, pbuf/queues, allocator metadata/fragmentation, libc/crypto/network/flash/interrupt stack or supplier overhead. 4096 B TCP allowance is illustrative only.',
        activation=False,trusted_consent_bound=False,physical='NOT_RUN',device_contacts=0,serial_io=0,
        flash_writes=0,rtc_writes=0,reboots=0,device_filesystem_writes=0)
if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('baseline',type=Path);p.add_argument('candidate',type=Path);a=p.parse_args();print(json.dumps(run(a.baseline,a.candidate),indent=2))
