"""ELF32/compiler-frame evidence for disconnected public research builds."""
import json
from pathlib import Path
import struct
import re
from m9_signed_release import validate_image
ROOT=Path(__file__).resolve().parent.parent
BUILD=ROOT/"experiments/m9_signed_ota/.pio/build"


def elf_sections(path):
    data=path.read_bytes();assert data[:7]==b'\x7fELF\x01\x01\x01'
    shoff=struct.unpack_from('<I',data,32)[0]
    entry,count,names=struct.unpack_from('<HHH',data,46)
    headers=[struct.unpack_from('<10I',data,shoff+i*entry) for i in range(count)]
    header=headers[names];strings=data[header[4]:header[4]+header[5]]
    return {strings[h[0]:].split(b'\0',1)[0].decode():h[5] for h in headers if h[2]&2}


def elf_symbols(path):
    data=path.read_bytes();shoff=struct.unpack_from('<I',data,32)[0]
    entry,count,_=struct.unpack_from('<HHH',data,46)
    headers=[struct.unpack_from('<10I',data,shoff+i*entry) for i in range(count)]
    symbols=[]
    for header in headers:
        if header[1]!=2:continue
        linked=headers[header[6]];strings=data[linked[4]:linked[4]+linked[5]]
        for at in range(header[4],header[4]+header[5],header[9]):
            name,_,_,info,_,_=struct.unpack_from('<IIIBBH',data,at)
            symbols.append((strings[name:].split(b'\0',1)[0].decode(),info>>4))
    return symbols


def one(environment):
    directory=BUILD/environment;sections=elf_sections(directory/'firmware.elf')
    symbols=elf_symbols(directory/'firmware.elf')
    roots=[name for name,binding in symbols if 'unwiredProof' in name]
    if environment=='signed_compile_only':
        assert len(roots)==1 and all(binding==0 for name,binding in symbols if 'unwiredProof' in name or 'retainedProof' in name)
        assert any('SigningVerifier' in name for name,_ in symbols)
        assert any('UpdaterClass3endEb' in name for name,_ in symbols)
    else:assert not roots
    frames=[]
    for path in sorted(directory.rglob('*.su')):
        for line in path.read_text(errors='replace').splitlines():
            if any(part in line for part in ('M9Signed','StrictOtaDigestGate','unwiredProof','UpdaterClass::end','UpdaterClass::_verifyEnd','PublicKey::','decode_public_key','read_public_key')):
                function,size,kind=line.rsplit('\t',2);frames.append(dict(function=re.sub(r'^.*?:\d+:\d+:','',function),bytes=int(size),kind=kind))
    ram=sum(sections.get(name,0) for name in ('.data','.rodata','.bss','.noinit'))
    image=(directory/'firmware.bin').read_bytes()
    validated=validate_image(image)
    return dict(sections=sections,static_ram=ram,raw_compile_only_bin_bytes=len(image),raw_image_checks=validated,
                proof_root_internal=bool(roots),no_exported_proof_endpoint=True,
                noinit_bytes=sections.get('.noinit',0),compiler_frames_not_high_water=frames)


def run():
    baseline,candidate=one('inert_baseline'),one('signed_compile_only')
    assert candidate['static_ram']<81920
    assert max(row['bytes'] for row in candidate['compiler_frames_not_high_water'])<=1136
    root=max(row['bytes'] for row in candidate['compiler_frames_not_high_water'] if 'unwiredProof(' in row['function'])
    return dict(scope='Xtensa compile/link only, no StageA install or runtime measurement',baseline=baseline,candidate=candidate,
                delta=dict(static_ram=candidate['static_ram']-baseline['static_ram'],
                           noinit=candidate['noinit_bytes']-baseline['noinit_bytes'],
                           raw_bin=candidate['raw_compile_only_bin_bytes']-baseline['raw_compile_only_bin_bytes']),
                floors=dict(heap=20480,block=16384,fragmentation=25,continuation=2048),
                admission=dict(heap=31544,block=22584,fragmentation=25,continuation=4096),
                dynamic_costs=dict(bearssl_secondary_stack=6200,updater_buffer=4096,signature=256,chunk=512),
                stack_call_path_estimate=root+672+192,stack_estimate_scope='measured root +672 strict Digest +192 SHA frame; excludes network callbacks/SDK/crypto callees',
                production_concurrency='HOLD',device_contacts=0)


if __name__=='__main__':print(json.dumps(run(),indent=2))
