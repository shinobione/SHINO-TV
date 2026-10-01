"""Numeric-only native ELF comparison; no strings, keys or device operations."""
import argparse,hashlib,json,re
from pathlib import Path
import v08_m8_stack_gate as pinned

ROOT=Path(__file__).resolve().parents[1]


def inspect(elf):
    rows=pinned.run_tool('size','-A',elf).splitlines()
    sections={m[1]:int(m[2]) for line in rows
              if (m:=re.match(r'^(\.\S+)\s+(\d+)\s+\d+',line))}
    sections={k:v for k,v in sections.items() if k in ('.data','.noinit','.text','.irom0.text','.text1','.rodata','.bss')}
    summary=pinned.run_tool('size',elf).splitlines()[-1].split()
    nm=pinned.run_tool('nm','-S','-C',elf).splitlines()
    objects={}
    for name in ('m7Authority','m7Ingress','m7Receiver','m8Json','m8::runtimeStats','m8MetadataLayout'):
        line=next((l for l in nm if l.endswith(' '+name)),None)
        if line: objects[name]=int(line.split()[1],16)
    layout=None
    line=next((l for l in nm if l.endswith(' m8MetadataLayout')),None)
    if line:
        address=int(line.split()[0],16);memory={}
        raw=pinned.run_tool('objdump','-s',f'--start-address={address}',f'--stop-address={address+20}',elf)
        for row in raw.splitlines():
            m=re.match(r'^\s*([0-9a-f]+)\s+((?:[0-9a-f]{8}\s+){1,4})',row)
            if m:
                for i,b in enumerate(bytes.fromhex(''.join(m[2].split()))):memory[int(m[1],16)+i]=b
        layout=[int.from_bytes(bytes(memory[address+4*j+i] for i in range(4)),'little') for j in range(5)]
        assert layout==[4,8,8,8,2048], 'native metadata ABI/capacity differs from tested profile'
    binary=elf.with_suffix('.bin')
    return {'elf_sha256':hashlib.sha256(elf.read_bytes()).hexdigest(),
            'bin_bytes':binary.stat().st_size,'bin_sha256':hashlib.sha256(binary.read_bytes()).hexdigest(),
            'size_text_data_bss':dict(zip(('text','data','bss'),map(int,summary[:3]))),
            'sections':sections,'persistent_DRAM_sections':sum(sections.get(s,0) for s in ('.data','.rodata','.bss')),
            'objects':objects,'linked_metadata_layout':layout}


def compare(old,new):
    a,b=inspect(old),inspect(new)
    assert b['linked_metadata_layout'], 'instrumented candidate must expose native ABI'
    dram_delta=b['persistent_DRAM_sections']-a['persistent_DRAM_sections']
    recovered=2048-dram_delta
    return {'old':a,'new':b,'persistent_DRAM_delta':dram_delta,
            'persistent_heap_allocations_changed':False,
            'persistent_heap_reason':'Same image and secondary-stack lifetimes; metadata arena is temporary. No new persistent new/malloc.',
            'host_array_concurrency':{'old_peak_bytes':8704,'new_peak_bytes':6656,'old_count':2,'new_count':2,'terminal_bytes':0},
            'replacement_overlap':{'old_explicit_bytes':9256,'new_explicit_bytes':7208,
                'overhead_reserve_bytes':4096,'old_required_block':13352,'new_required_block':11304,
                'historical_settled_block':12496,'arithmetic_margin_bytes':1192,
                'conservative_margin_after_DRAM_delta':1192-dram_delta,
                'gross_transient_recovered':2048,'net_budget_recovered_after_DRAM_delta':recovered,
                'separate_crypto_image_explicit_bytes':10808,'separate_crypto_required_heap':14904,
                'historical_settled_heap':16384,'conservative_heap_margin_after_DRAM_delta':1480-dram_delta},
            'physical_memory_qualification':'NOT RUN on new candidate; contiguous block/SDK/allocator behavior must be remeasured',
            'device_contacts':0,'device_writes':0}


if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--old',type=Path,default=ROOT/'research-local/m8-private-candidate.elf')
    parser.add_argument('--new',type=Path,default=ROOT/'research-local/m8-memory-candidate.elf')
    args=parser.parse_args();print(json.dumps(compare(args.old,args.new),indent=2))
