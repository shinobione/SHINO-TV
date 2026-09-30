"""Address-keyed linked Xtensa path inventory. Never hides unresolved calls."""
import argparse, configparser, hashlib, json, re, subprocess
from pathlib import Path
import v08_m8_stack_gate as prior

ROOT = prior.ROOT
ELF = ROOT / 'experiments/v08_m8r/.pio/build/media_compile/firmware.elf'

def inspect(environment='media_compile'):
    ELF=ROOT / ('experiments/v08_m8r/.pio/build/'+environment+'/firmware.elf')
    configured=6144 if environment=='stack_sensitivity_compile' else 4096
    dis = prior.run_tool('objdump', '-d', '-C', ELF)
    raw = prior.run_tool('objdump', '-s', ELF)
    memory = {}
    for line in raw.splitlines():
        m = re.match(r'^\s*([0-9a-f]+)\s+((?:[0-9a-f]{8}\s+){1,4})', line)
        if m:
            for i, b in enumerate(bytes.fromhex(''.join(m[2].split()))):
                memory[int(m[1],16)+i] = b
    def word(a):
        try: return int.from_bytes(bytes(memory[a+i] for i in range(4)), 'little')
        except KeyError: return None
    marks = list(re.finditer(r'^([0-9a-f]+) <(.+)>:$',dis,re.M))
    symbols=prior.run_tool('nm','-S',ELF).splitlines()
    extents={int(x.split()[0],16):int(x.split()[1],16) for x in symbols
             if len(x.split())>=4 and x.split()[2] in ('T','t','W','w')}
    fs = {}
    for i,m in enumerate(marks):
        address=int(m[1],16)
        if address not in extents: continue
        lines = dis[m.end():marks[i+1].start() if i+1<len(marks) else len(dis)].splitlines()
        ins=[]
        for line in lines:
            a=re.match(r'^\s*([0-9a-f]+):\s+[0-9a-f]+\s+([a-z0-9.]+)\s*(.*)$',line)
            if a and int(a[1],16)<address+extents[address]:
                ins.append((int(a[1],16),a[2],a[3],line.strip()))
        fs[address]={'name':m[2],'linked_symbol_bytes':extents[address],'instructions':ins}
    ecaddr = next(int(x.split()[0],16) for x in prior.run_tool('nm','-S',ELF).splitlines() if x.endswith(' br_ec_p256_m31'))
    ec = {offset:word(ecaddr+offset) for offset in range(4,28,4)}
    for addr,f in fs.items():
        registers={}; frame=0; edges=[]; unknown=[]; prologue=[]
        for pc,op,arg,line in f['instructions']:
            parts=[x.strip() for x in arg.split(',')]
            if op in ('movi','movi.n'):
                try: registers[parts[0]]=int(parts[1],0)
                except ValueError: registers.pop(parts[0],None)
            elif op=='l32r':
                registers[parts[0]]=word(int(parts[1].split()[0],16))
            elif op in ('addmi','addi','addi.n') and parts[0]!='a1':
                base=registers.get(parts[1])
                registers[parts[0]]=None if base is None else base+int(parts[2],0)
            elif op=='sub' and parts[:2]==['a1','a1']:
                n=registers.get(parts[2]);
                if n is None: unknown.append({'pc':hex(pc),'reason':'dynamic stack subtraction','line':line})
                else: frame+=n; prologue.append(line)
            elif op in ('addi','addi.n') and parts[:2]==['a1','a1']:
                n=int(parts[2],0)
                if n<0: frame-=n; prologue.append(line)
            elif op in ('call0','call4','call8','call12','j'):
                t=re.match(r'([0-9a-f]+)',arg)
                if t and (op!='j' or int(t[1],16) in fs and int(t[1],16)!=addr):
                    edges.append({'pc':hex(pc),'target':int(t[1],16),'kind':op,'line':line})
            elif op in ('callx0','callx4','callx8','jx'):
                target=registers.get(arg.strip())
                if target is not None:
                    edges.append({'pc':hex(pc),'target':target,'kind':op,'line':line,'resolution':'linked literal'})
                else: unknown.append({'pc':hex(pc),'reason':'indirect call or tail','line':line})
            # Do not carry scratch registers through a call.
            if op.startswith('call'):
                for reg in ('a0','a2','a3','a4','a5','a6','a7','a8','a9','a10','a11'):
                    registers.pop(reg,None)
        f.update(frame=frame,prologue=prologue,edges=edges,unknown=unknown)
    # Explicit EC callbacks in the unmodified raw verifier, proved from supplied
    # br_ec_p256_m31 object and actual loads at offsets in this exact ELF.
    verifier=next(f for f in fs.values() if f['name']=='br_ecdsa_i15_vrfy_raw')
    for issue in list(verifier['unknown']):
        pc=int(issue['pc'],16); ins=verifier['instructions']; index=next(i for i,x in enumerate(ins) if x[0]==pc)
        prev=ins[max(0,index-16):index]
        loads=[re.search(r'l32i(?:\.n)?\s+(a\d+), a15, (\d+)',x[3]) for x in prev]
        loads=[x for x in loads if x and issue['line'].endswith('\t'+x[1])]
        if loads and int(loads[-1][2]) in ec:
            off=int(loads[-1][2]); verifier['edges'].append({'pc':issue['pc'],'target':ec[off],'kind':'callx0','line':issue['line'],'resolution':'br_ec_p256_m31 offset '+str(off)})
            verifier['unknown'].remove(issue)
    roots=['app_entry_redefinable','cont_run','cont_wrapper','loop_wrapper()', 'loop', 'FirstBootBridge::loop()', 'esp8266webserver::ESP8266WebServerTemplate<WiFiServer>::handleClient()',
           'm7::Ingress::verifyHeaders()', 'm7::Ingress::parse()', 'bool m7::Ingress::poll<WiFiClient>(WiFiClient&)',
           'm7::metadata(m7::Record const&, m7::Metadata&)', 'br_ecdsa_i15_vrfy_raw','br_sha224_update','br_sha256_out']
    roots.extend(f['name'] for f in fs.values() if 'Receiver7receive' in f['name'] or 'm7::Receiver::receive' in f['name'])
    # Do not turn an unconstrained whole-SDK graph into a fictitious maximum:
    # literal pools, mutually exclusive branches, recursion and SYS stack
    # switches need CFG/context analysis. Publish only an inventory here.
    paths={}
    for name in roots:
        addr=next(a for a,f in fs.items() if f['name']==name); f=fs[addr]
        paths[name]={'gate':'UNKNOWN','complete_nested_maximum_bytes':None,
            'root_address':hex(addr),'root_frame_bytes':f['frame'],
            'unresolved_indirect_sites':f['unknown'],
            'linked_direct_target_inventory':list({e['target']: {'address':hex(e['target']),
                'function':fs[e['target']]['name'] if e['target'] in fs else 'opaque external/ROM'} for e in f['edges']}.values())}
    row=prior.run_tool('size',ELF).splitlines()[1].split()
    # This asserted chain is a LOWER BOUND. Opaque ROM calls remain UNKNOWN;
    # exploratory graph sums above are not complete path maxima or safe margins.
    names=['br_ecdsa_i15_vrfy_raw','api_muladd','p256_mul','p256_add','mul_f256']
    chain=[]
    for name in names:
        matches=[(a,f) for a,f in fs.items() if f['name']==name]
        assert len(matches)==1, name
        addr,f=matches[0]; chain.append({'address':hex(addr),'function':name,'frame_bytes':f['frame'],'prologue':f['prologue']})
    assert [x['frame_bytes'] for x in chain]==[720,272,592,304,336]
    for left,right in zip(chain,chain[1:]):
        assert any(e['target']==int(right['address'],16) for e in fs[int(left['address'],16)]['edges']), (left,right)
    assert fs[int(chain[-1]['address'],16)]['edges']
    assert all(e['target']==0x4000dcf0 for e in fs[int(chain[-1]['address'],16)]['edges'])
    verify=next(f for f in fs.values() if f['name']=='m7::Ingress::verifyHeaders()')
    rawaddr=int(chain[0]['address'],16)
    assert any(e['target']==rawaddr for e in verify['edges'])
    for f in fs.values():
        if f['name'] in ('m7::Ingress::parse()','bool m7::Ingress::poll<WiFiClient>(WiFiClient&)'):
            assert not any(e['target']==rawaddr for e in f['edges'])
    cont=Path.home()/'.platformio/packages/framework-arduinoespressif8266/cores/esp8266/cont.h'
    assert '#define CONT_STACKSIZE 4096' in cont.read_text()
    config=configparser.ConfigParser(interpolation=None)
    config.read(ROOT/'experiments/v08_m8r/platformio.ini')
    assert all('CONT_STACKSIZE' not in config[x]['build_flags'] for x in ('env:legacy_compile','env:media_compile'))
    if configured==6144: assert '-DCONT_STACKSIZE=6144' in config['env:stack_sensitivity_compile']['build_flags']
    rommap=Path.home()/'.platformio/packages/framework-arduinoespressif8266/tools/sdk/ld/eagle.rom.addr.v6.ld'
    romnames={int(a,16):name for name,a in re.findall(r'PROVIDE\s*\(\s*(\w+)\s*=\s*(0x[0-9a-f]+)',rommap.read_text())}
    cryptoaddrs=[int(x['address'],16) for x in chain]
    opaque={hex(e['target']):romnames.get(e['target'],'not in pinned ROM map') for a in cryptoaddrs for e in fs[a]['edges'] if e['target'] not in fs}
    nm=prior.run_tool('nm','-S','-C',ELF).splitlines()
    objects={name:int(next(x.split()[1] for x in nm if x.endswith(' '+name)),16) for name in ('m7Authority','m7Ingress','m7Receiver')}
    result={'gate':'UNKNOWN__COMPLETE_LINKED_PATH_NOT_YET_ACCOUNTED','elf_sha256':prior.digest(ELF),
        'head_at_analysis':subprocess.check_output(['git','rev-parse','HEAD'],cwd=ROOT,text=True).strip(),
        'source_parent':'5179eb04ea51c2a92c7f796f07ebb963e2167e00',
        'dirty':bool(subprocess.check_output(['git','status','--porcelain'],cwd=ROOT,text=True).strip()),
        'bin_sha256':prior.digest(ELF.with_suffix('.bin')),'bin_bytes':ELF.with_suffix('.bin').stat().st_size,
        'sections':dict(zip(('text','data','bss'),map(int,row[:3]))),'cont_stack_bytes':configured,'environment':environment,
        'known_crypto_chain_lower_bound_bytes':sum(x['frame_bytes'] for x in chain),
        'known_crypto_chain':chain,'objects':objects,'rom_map_sha256':prior.digest(rommap),'cont_header_sha256':prior.digest(cont),'opaque_targets':opaque,
        'analysis_limitations':['no unconstrained graph sum is presented as a complete upper bound',
          'ROM callees have addresses but no instruction bodies in linked ELF',
          'virtual callbacks and recursive JSON paths require context-sensitive bounds',
          'normal and abort/reset paths need separation and continuation/SYS-stack switch accounting'],
        'function_extent_source':'actual linked nm -S text symbols; trailing literal pools excluded',
        'ec_table':{'address':hex(ecaddr),'fields':{str(k):{'address':hex(v),'function':fs[v]['name']} for k,v in ec.items()}},
        'paths':paths,'functions':{hex(a):{k:v for k,v in f.items() if k!='instructions'} for a,f in fs.items() if f['name'].startswith(('m7::','br_ecdsa','br_sha','api_','p256_','mul_f256','square_f256','sha2small_out')) or f['name'] in roots},'device_contacts':0,'device_writes':0}
    return result

if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--environment',choices=('media_compile','stack_sensitivity_compile'),default='media_compile')
    print(json.dumps(inspect(parser.parse_args().environment),indent=2))
