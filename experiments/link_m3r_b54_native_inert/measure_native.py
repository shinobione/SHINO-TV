"""Measure actual INERT ELF/BIN/stack outputs. No execution or device APIs."""
import argparse, hashlib, json, os, re, subprocess
from pathlib import Path

def sha(p): return hashlib.sha256(p.read_bytes()).hexdigest()

def measure(output, toolchain):
    output=Path(output); project=output/'project'
    toolchain_meta=json.loads((Path(toolchain)/'package.json').read_text())
    assert toolchain_meta['version']=='2.100300.220621', 'Toolchain package drift'
    suffix='.exe' if os.name=='nt' else ''
    def tool(name,*args):
        return subprocess.check_output([str(Path(toolchain)/'bin'/('xtensa-lx106-elf-'+name+suffix)),*map(str,args)],text=True)
    reports={}
    for name in ('b54_inert_base','b54_inert_handoff'):
        build=project/'.pio/build'/name; elf=build/'firmware.elf'; binary=build/'firmware.bin'
        receipt=json.loads((build/'inert-bin.json').read_text())
        assert binary.read_bytes()[0]==0 and receipt['bootable'] is False
        assert sha(binary)==receipt['inert_bin_sha256'] and binary.stat().st_size==receipt['bytes']
        sections={m[0]:{'bytes':int(m[1]),'address':int(m[2])} for m in re.findall(r'^(\S+)\s+(\d+)\s+(\d+)\s*$',tool('size','-A',elf),re.M)}
        # Only linked runtime sections; exclude debug and precompiled archive members.
        runtime={n:s for n,s in sections.items() if 0x3ffe8000<=s['address']<0x40300000}
        ram=sum(s['bytes'] for s in runtime.values() if 0x3ffe8000<=s['address']<0x40000000)
        iram=sum(s['bytes'] for s in runtime.values() if 0x40100000<=s['address']<0x40108000)
        symbols=tool('nm','-S','-C',elf); disassembly=tool('objdump','-d','-C',elf)
        (build/'native-symbols.txt').write_text(symbols)
        (build/'native-disassembly.txt').write_text(disassembly)
        for routine in ('setup','loop'):
            match=re.search(r'^[0-9a-f]+ <'+routine+r'(?:\(\))?>:\n(.*?)(?=\n\n)',disassembly,re.M|re.S)
            assert match, 'Missing inert '+routine
            assert 'call' not in match[1] and 'ret' in match[1], match[0]
        required=['M9NormalStageA::loop()', 'B54LanNative::accept()', 'B52Clock::', 'authenticateDigest(', '_parseRequest(', 'UpdaterClass::begin(', 'eboot_command_write', 'shino_m3r_stagea_link_probe']
        for item in required: assert item in symbols, 'Missing linked function '+item
        for sym,address in [('_FS_start',0x40400000),('_FS_end',0x405fa000),('_EEPROM_start',0x405fb000)]:
            assert re.search(r'^'+f'{address:08x}'+r'\s+A\s+'+sym+r'$',symbols,re.M), sym
        # Release objects have no DWARF. Check linked FILE symbols and strong
        # definitions in the actual project object (no stock Updater). Xtensa
        # linker relaxation changes function sizes, so sizes are not identities.
        files=tool('nm','-a',elf)
        assert re.search(r'^0+\s+a\s+Updater512.cpp$',files,re.M)
        assert not re.search(r'^0+\s+a\s+Updater.cpp$',files,re.M)
        begin=re.search(r'^[0-9a-f]+\s+([0-9a-f]+)\s+T\s+UpdaterClass::begin\(',symbols,re.M)[1]
        objsymbols=tool('nm','-S','-C',build/'src/Updater512.cpp.o')
        assert re.search(r'^[0-9a-f]+\s+[0-9a-f]+\s+T\s+UpdaterClass::begin\(',objsymbols,re.M)
        updater_origin='ELF FILE Updater512.cpp; no stock Updater.cpp FILE; strong begin definition in object and ELF'
        selected=[]
        for path in build.rglob('*.su'):
            for row in path.read_text().splitlines():
                parts=row.rsplit('\t',2)
                if len(parts)!=3: continue
                desc,amount,kind=parts
                if any(x in desc for x in ('m3Service()', 'readAuthenticatedHeaders(', 'verifyFrameWithoutSideEffect(', 'authenticateHeader(', 'M9NormalStageA::loop()', 'serviceRequest()', '::upload(uint32_t)', '::beforeBody()', '::_parseRequest(', '::handleClient()', 'UpdaterClass::begin(', 'UpdaterClass::_writeBuffer(', 'UpdaterClass::write(', 'UpdaterClass::end(')):
                    selected.append(dict(unit=path.relative_to(build).as_posix(),function=desc,bytes=int(amount),kind=kind))
        handoff=name.endswith('handoff')
        gates=re.findall(r'^[0-9a-f]+\s+([0-9a-f]+)\s+b\s+.*::m3Storage$',symbols,re.M)
        assert len(gates)==int(handoff)
        assert len(re.findall(r'^.*\s+b\s+.*::httpBusy$',symbols,re.M))==1
        if handoff:
            assert 'readAuthenticatedHeaders' in symbols and 'verifyFrameWithoutSideEffect' in symbols
        rounded=(receipt['bytes']+4095)//4096*4096
        assert ram<81920 and iram<=32768 and rounded*2<=0x200000
        reports[name]=dict(bin=receipt,elf_sha256=sha(elf),runtime_sections=runtime,static_ram_including_noinit=ram,iram_bytes=iram,static_ram_unallocated=81920-ram,gate_bytes=int(gates[0],16) if gates else 0,stack_frames=selected,
            layout=dict(flash_bytes=0x400000,fs_start=0x200000,fs_end=0x3fa000,eeprom=0x3fb000,rfcal=0x3fc000,sdk_start=0x3fd000,rounded_image_bytes=rounded,theoretical_same_size_staging_start=0x200000-rounded,scope='GEOMETRY_ONLY_NONBOOTABLE_IMAGE_NOT_OTA_INPUT'),
            checks=dict(empty_entry=True,linked_services=True,updater512_linked=True,single_http_busy=True,bin_nonbootable=True),updater_origin=updater_origin,physical_heap_CONT_WDT='NON_VERIFIE')
    b,h=reports.values()
    result=dict(toolchain_version=toolchain_meta['version'],scope='NATIVE_XTENSA_COMPILE_AND_LINK_ONLY_NOT_EXECUTED',environments=reports,delta=dict(bin_bytes=h['bin']['bytes']-b['bin']['bytes'],static_ram=h['static_ram_including_noinit']-b['static_ram_including_noinit'],iram=h['iram_bytes']-b['iram_bytes']),physical='HOLD')
    (output/'native-measurements.json').write_text(json.dumps(result,indent=2)+'\n')
    return result

if __name__=='__main__':
    a=argparse.ArgumentParser(); a.add_argument('--output',required=True); a.add_argument('--toolchain',default=str(Path.home()/'.platformio/packages/toolchain-xtensa'));x=a.parse_args()
    r=measure(x.output,x.toolchain)
    print(json.dumps({'scope':r['scope'],'delta':r['delta'],'physical':r['physical']}))
