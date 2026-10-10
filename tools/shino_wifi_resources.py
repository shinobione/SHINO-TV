"""Actual ELF pair and explicit conservative memory scenario, not high-water."""
import argparse,hashlib,json,re,subprocess
from pathlib import Path
from m9_signed_ota_resources import elf_sections
from m9_stagea_resources import symbols_with_data
from m9_signed_release import validate_image
from m9_stagea_build import ENV,ROOT
def one(directory):
    directory=Path(directory);p=directory/'.pio/build'/ENV;sections=elf_sections(p/'firmware.elf')
    raw=(p/'firmware.bin').read_bytes();validate_image(raw)
    frames=[]
    for file in p.rglob('*.su'):
        for line in file.read_text(errors='replace').splitlines():
            if any(n in line for n in ('ShinoInstall','shinoInstallPump','shinoInstallProof','UpdaterClass::end','M9NormalStageA::loop')):
                parts=line.rsplit('\t',2)
                if len(parts)==3:frames.append(dict(function=re.sub(r'^.*?:\d+:\d+:','',parts[0]),bytes=int(parts[1])))
    dependencies={}
    for name in ('ArduinoJson','GFX Library for Arduino','AnimatedGIF'):
        library=directory/'.pio/libdeps'/ENV/name;h=hashlib.sha256()
        for f in sorted(library.rglob('*')):
            if f.is_file() and f.suffix in ('.h','.hpp','.cpp','.c'):h.update(f.relative_to(library).as_posix().encode()+b'\0'+f.read_bytes().replace(b'\r\n',b'\n'))
        dependencies[name]=h.hexdigest()
    return dict(bin_bytes=len(raw),linked_flash=sum(sections.get(s,0) for s in ('.data','.rodata','.text','.text1','.irom0.text')),
        static_ram=sum(sections.get(s,0) for s in ('.data','.rodata','.bss','.noinit')),noinit=sections['.noinit'],sections=sections,frames=frames,
        inputs=json.loads((directory/'public-inputs.json').read_text()),dependencies=dependencies,
        identity_sha256=hashlib.sha256((directory/'include/shino_private_policy.h').read_bytes()).hexdigest())
def run(baseline,integrated):
    base=one(baseline);candidate=one(integrated)
    assert base['inputs']['firmware_LF_sha256']==candidate['inputs']['firmware_LF_sha256'] and base['dependencies']==candidate['dependencies'] and base['identity_sha256']==candidate['identity_sha256']
    assert base['noinit']==candidate['noinit']==56
    for name in subprocess.check_output(['git','ls-files','firmware'],cwd=ROOT,text=True).splitlines():
        assert subprocess.check_output(['git','show','2b9ef75b4cf650277baae8da871ebe41f3227ddf:'+name],cwd=ROOT).replace(b'\r\n',b'\n')==(ROOT/name).read_bytes().replace(b'\r\n',b'\n')
    delta={name:candidate[name]-base[name] for name in ('bin_bytes','linked_flash','static_ram','noinit')}
    symbols=symbols_with_data(Path(integrated)/'.pio/build'/ENV/'firmware.elf')
    native=[v for k,v in symbols.items() if 'shinoInstallStorage' in k];assert len(native)==1 and native[0]['binding']==0
    assert all(v['binding']==0 for k,v in symbols.items() if 'retainedInstall' in k or 'shinoInstallProof' in k)
    def frame(term):return max(r['bytes'] for r in candidate['frames'] if term in r['function'])
    return dict(verdict='NO_GO',principal_blocker='SIMULTANEOUS_NATIVE_MEMORY_FLOOR_NOT_ESTABLISHED',native_link='PASS_OFFLINE',
        baseline=base,integrated=candidate,delta=delta,native_object_bytes=native[0]['bytes'],
        floors=dict(heap=20480,largest=16384,stack=2048,fragmentation=25),observed_owner=dict(heap=30224,largest=30008,stack=3248),
        known_dynamic_updater=4096,no_rsa_or_bearssl_secondary_stack=True,
        conservative_tcp_scenario_reserve=4096,private_key_payload=32,
        scenario_heap_after_payloads=30224-delta['static_ram']-4096-4096-32,
        scenario_margin_above_heap_floor=30224-delta['static_ram']-4096-4096-32-20480,
        partial_auth_frames=frame('Native::pump')+frame('Native::line')+frame('ShinoInstall::mac'),
        partial_commit_frames=frame('Native::pump')+frame('Native::line')+frame('Receiver::stagedImage')+frame('Receiver::segments'),
        unknown='TCP/lwIP/pbuf/HTTP ownership, SDK Wi-Fi, allocator metadata/fragmentation, libc/crypto/flash callees and transient stack/heap high-water',
        model_limit='4096 TCP reserve is an illustrative conservative allowance, not a proven upper bound. Owner minima are not simultaneous.',
        activation=False,physical='NOT_RUN',device_contacts=0,serial_io=0,flash_writes=0,rtc_writes=0,reboots=0,device_filesystem_writes=0)
if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('baseline',type=Path);p.add_argument('integrated',type=Path);a=p.parse_args();print(json.dumps(run(a.baseline,a.integrated),indent=2))
