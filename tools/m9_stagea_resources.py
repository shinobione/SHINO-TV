"""Actual paired StageA ELF and allocation evidence; never a physical PASS."""
from pathlib import Path
import argparse,hashlib,json,re,struct
from m9_signed_ota_resources import elf_sections,elf_symbols
from m9_signed_release import validate_image
from m9_stagea_build import ENV,POLICY
ROOT=Path(__file__).resolve().parents[1]
COUNTERS=dict(device_contacts=0,serial_io=0,flash_writes=0,rtc_writes=0,reboots=0,device_filesystem_writes=0)

def symbols_with_data(path):
    data=path.read_bytes();offset=struct.unpack_from('<I',data,32)[0];entry,count,_=struct.unpack_from('<HHH',data,46)
    sections=[struct.unpack_from('<10I',data,offset+i*entry) for i in range(count)];out={}
    for section in sections:
        if section[1]!=2:continue
        names=sections[section[6]];strings=data[names[4]:names[4]+names[5]]
        for at in range(section[4],section[4]+section[5],section[9]):
            name,address,size,info,_,index=struct.unpack_from('<IIIBBH',data,at)
            label=strings[name:].split(b'\0',1)[0].decode()
            content=b''
            if index<len(sections) and sections[index][1]!=8:
                segment=sections[index];start=segment[4]+address-segment[3];content=data[start:start+size]
            out[label]=dict(bytes=size,binding=info>>4,data=content)
    return out

def one(directory,integrated):
    directory=Path(directory);build=directory/'.pio/build'/ENV;elf=build/'firmware.elf'
    sections=elf_sections(elf);symbols=elf_symbols(elf);rows=symbols_with_data(elf)
    assert sections['.noinit']==56
    assert (directory/'include/shino_private_policy.h').read_text()==POLICY
    inputs=json.loads((directory/'public-inputs.json').read_text())
    dependencies={}
    for library in ('ArduinoJson','GFX Library for Arduino','AnimatedGIF'):
        folder=build.parent.parent/'libdeps'/ENV/library
        digest=hashlib.sha256()
        for path in sorted(folder.rglob('*')):
            if path.is_file() and path.suffix in ('.h','.hpp','.c','.cpp'):
                digest.update(str(path.relative_to(folder)).replace('\\','/').encode()+b'\0')
                digest.update(path.read_bytes().replace(b'\r\n',b'\n'))
        assert any(folder.rglob('*.h')),library
        dependencies[library]=digest.hexdigest()
    frames=[]
    for path in sorted(build.rglob('*.su')):
        for line in path.read_text(errors='replace').splitlines():
            if any(part in line for part in ('M9Signed','M9StageA','StrictOtaDigestGate','stageAUnwired','_parseRequest(',
                'handleClient()','M9NormalStageA::','UpdaterClass::end','decode_public_key','PublicKey::','SigningVerifier::')):
                parts=line.rsplit('\t',2)
                if len(parts)==3:frames.append(dict(function=re.sub(r'^.*?:\d+:\d+:','',parts[0]),bytes=int(parts[1]),kind=parts[2]))
    selected={}
    for term in ('nativeStorage','httpStorage','policyStorage','nativeCosts'):
        matches=[row for name,row in rows.items() if term in name]
        if integrated:
            assert len(matches)==1 and matches[0]['binding']==0,term
            selected[term]=matches[0]['bytes']
            if term=='nativeCosts':selected['type_sizes']=dict(zip(('key_decoder','signing_verifier','string'),struct.unpack('<3I',matches[0]['data'])))
        else:assert not matches
    required=('M9NormalStageA5begin','M9NormalStageA4loop','FslessMetrics5apply','M9NormalDashboard6render')
    for term in required:assert any(term in name for name,_ in symbols),term
    for term in ('stageAUnwiredProof','stageAUnwiredPump','SigningVerifier','UpdaterClass3endEb'):
        assert any(term in name for name,_ in symbols)==integrated,term
    for term in ('retainedStageAProof','retainedStageAPump','stageAUnwiredProof','stageAUnwiredPump'):
        assert all(binding==0 for name,binding in symbols if term in name),term
    image=(build/'firmware.bin').read_bytes();validate_image(image)
    return dict(sections=sections,static_ram=sum(sections.get(n,0) for n in ('.data','.rodata','.bss','.noinit')),
        bin_bytes=len(image),linked_flash_bytes=sum(sections.get(n,0) for n in ('.data','.rodata','.text','.text1','.irom0.text')),
        bin_sha256=hashlib.sha256(image).hexdigest(),elf_sha256=hashlib.sha256(elf.read_bytes()).hexdigest(),
        compiler_frames_not_high_water=frames,objects=selected,public_inputs=inputs,dependency_source_tree_sha256=dependencies)

def run(baseline,integrated):
    base=one(baseline,False);candidate=one(integrated,True)
    assert base['public_inputs']['firmware_LF_sha256']==candidate['public_inputs']['firmware_LF_sha256']
    assert base['public_inputs']['identity_sha256']==candidate['public_inputs']['identity_sha256']==hashlib.sha256(POLICY.encode()).hexdigest()
    assert base['dependency_source_tree_sha256']==candidate['dependency_source_tree_sha256']
    delta=candidate['static_ram']-base['static_ram'];types=candidate['objects']['type_sizes']
    assert delta>0 and candidate['static_ram']<=49152
    # All simultaneous native payload allocations in this selected RSA2048 path.
    # Key decoder is freed before staging; modulus/exponent/key structure persist.
    native=6200+4096+256+types['signing_verifier']+256+3+20
    observed=dict(heap=30224,block=30008,continuation=3248,fragmentation=1,samples=445,rejects=0)
    admission=dict(heap=31544,block=22584,continuation=4096,fragmentation=25)
    # Bound controllable parser String payloads using actual16B WString rounding.
    # Retained post body + current line/copies + response/auth intermediates.
    # This is an explicit conservative model, not an allocator/lwIP peak proof.
    parser_model=dict(request_and_route_strings=4*272,header_line_name_value=3*528,
        retained_collected_values=5*528,post_body_and_argument=2*400,
        response_and_digest_intermediates=8*528,header_and_argument_objects=7*2*types['string'])
    concurrent=native+sum(parser_model.values())
    frames=candidate['compiler_frames_not_high_water']
    def maximum(term):
        selected=[f['bytes'] for f in frames if term in f['function']];assert selected,term;return max(selected)
    partial_stack=maximum('stageAUnwiredPump')+maximum('>::arm(')+maximum('>::verify(')+maximum('DigestHash::hex')
    return dict(PHASE_T_NATIVE_LINK='PASS_OFFLINE',PHASE_T_MEMORY='HOLD_PHYSICAL',RESOURCE_GATE='HOLD_PHYSICAL_MEASUREMENT_REQUIRED',
        baseline=base,integrated=candidate,delta=dict(static_ram=delta,noinit=0,bin=candidate['bin_bytes']-base['bin_bytes'],
            linked_flash=candidate['linked_flash_bytes']-base['linked_flash_bytes']),
        observed_owner_minima=observed,admission_unchanged=admission,physical_floors=dict(heap=20480,block=16384,continuation=2048,fragmentation=25),
        direct_observed_shortfalls=dict(heap=1320,continuation=848),
        allocations=dict(native_payload_bytes=native,bearssl_stack=6200,updater=4096,signature=256,key_decoder_temporary=types['key_decoder'],
            persistent_rsa_key=279,verifier=types['signing_verifier'],parser_model_bytes=parser_model,
            modeled_concurrent_payload_bytes=concurrent,allocator_metadata_and_fragmentation='UNKNOWN',
            json_pool_lwip_tcp_sdk_and_callback_allocations='NOT_BOUNDED_BY_THIS_MODEL'),
        scenario_only=dict(projected_heap_before_ota=observed['heap']-delta,
            projected_heap_after_known_native_payload=observed['heap']-delta-native,
            projected_heap_after_concurrent_model=observed['heap']-delta-concurrent,
            disclaimer='Owner minima are not simultaneous; static delta projection is NOT integrated runtime evidence'),
        partial_compiler_call_chain=partial_stack,unknown_stack='network/SDK/interrupts/realloc/crypto callees and simultaneous high-water',
        continuation_total_core=4096,admission_at_in_call_observation='4096 is not demonstrated attainable inside a nonzero-frame callback; unchanged, reject-only',
        admission_rechecked_each_chunk='Live heap must still exceed31544 AFTER native allocation; initial threshold alone cannot qualify transfer',
        known_minimum_initial_heap_for_live_full_reserve=31544+6200+4096+types['signing_verifier'],
        scratch_saved=512,production='HOLD',safe_physical_integration='BLOCKED_CORE_HAS_NO_SAFE_ABORT',physical='NOT_RUN',**COUNTERS)

if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('baseline',type=Path);p.add_argument('integrated',type=Path);a=p.parse_args()
    print(json.dumps(run(a.baseline,a.integrated),indent=2))
