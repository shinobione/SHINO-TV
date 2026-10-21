"""Build/run the actual imported B5.4 HTTP graph on loopback, RAM-only hardware."""
import argparse, hashlib, importlib.util, json, os, re, struct, subprocess, sys
from pathlib import Path
from materialize import HERE, prepare

def module(path, name):
    spec=importlib.util.spec_from_file_location(name,path)
    value=importlib.util.module_from_spec(spec);spec.loader.exec_module(value);return value

def command(args, cwd, env, log):
    p=subprocess.run(args,cwd=cwd,env=env,capture_output=True,text=True,errors="replace",timeout=120)
    with log.open('a',encoding='utf-8') as f:
        f.write(p.stdout+p.stderr)
    if p.returncode:
        raise RuntimeError('Command failed; see '+str(log)+'\n'+(p.stdout+p.stderr)[-4000:])

def build(output, area):
    root=output/area;builder=module(root/'tests/build_host.py','b54_builder')
    builder.OUT.mkdir();cc,env=builder.compiler_environment();msvc=Path(cc).name.lower()=='cl.exe'
    inc=[root,*[root/x for x in ('core','host','seams/core','seams/wifi','seams/base','vendor/bearssl/inc','vendor/bearssl/src')]]
    flags=[('/I' if msvc else '-I')+str(p) for p in inc]
    sources=[root/'vendor/bearssl/src/hash/sha2small.c',root/'vendor/bearssl/src/hash/md5.c',root/'vendor/bearssl/src/mac/hmac.c',*sorted((root/'vendor/bearssl/src/codec').glob('*.c')),root/'core/eboot_command.c']
    log=output/(area+'-build.log')
    command([cc,'/nologo','/TC','/O2','/c',*flags,*map(str,sources)] if msvc else ['gcc','-O2','-c',*flags,*map(str,sources)],builder.OUT,env,log)
    definitions=['HOST_MOCK=1','ARDUINOJSON_POOL_CAPACITY=8','SHINO_B53_AUTONOMY_EXPERIMENTAL=1','SHINO_B53_DIAGNOSTIC_OFF=1','SHINO_B54_LAN_WEATHER=1','SHINO_UPDATER_FLASH_BUFFER_512=1','SHINO_M3C_INCREMENTAL_HMAC=1']
    if area=='patched':definitions+=['SHINO_M3R_B54_HOST_HANDOFF=1']
    objects=[builder.OUT/(p.stem+('.obj' if msvc else '.o')) for p in sources]
    exe=builder.OUT/('receiver.exe' if msvc else 'receiver')
    cxx=[root/'tests/lab.cpp',root/'core/Updater.cpp']
    args=[cc,'/nologo','/std:c++20','/EHsc','/O2',*['/D'+d for d in definitions],*flags,*map(str,cxx),*map(str,objects),'/link','/MAP:'+str(builder.OUT/'receiver.map'),'/OUT:'+str(exe)] if msvc else [cc,'-std=c++20','-O2','-pthread',*['-D'+d for d in definitions],*flags,*map(str,cxx),*map(str,objects),'-Wl,-Map='+str(builder.OUT/'receiver.map'),'-o',str(exe)]
    command(args,builder.OUT,env,log)
    return exe

def resources(path):
    raw=path.read_bytes();out=dict(bytes=len(raw),sha256=hashlib.sha256(raw).hexdigest())
    if raw[:2]==b'MZ':
        offset=struct.unpack_from('<I',raw,0x3c)[0];count=struct.unpack_from('<H',raw,offset+6)[0];optional=struct.unpack_from('<H',raw,offset+20)[0];sections={}
        for n in range(count):
            at=offset+24+optional+40*n;name=raw[at:at+8].split(b'\0')[0].decode()
            sections[name]=dict(virtual_bytes=struct.unpack_from('<I',raw,at+8)[0],raw_bytes=struct.unpack_from('<I',raw,at+16)[0])
        out['format']='Windows_x64_HOST_PE';out['sections']=sections
    else:
        out['format']='HOST_ELF';out['size_sections']=subprocess.check_output(['size','-A',str(path)],text=True)
    return out

def main():
    parser=argparse.ArgumentParser(__doc__);parser.add_argument('--source-review',type=Path,required=True);parser.add_argument('--output',type=Path,required=True)
    args=parser.parse_args();output=args.output.resolve()
    receipt=prepare(args.source_review,output)
    # Fresh output, exact frozen overlay; no source/identity manifest is rewritten.
    binaries={a:build(output,a) for a in ('base','patched')}
    env=dict(os.environ,PYTHONUTF8='1',SHINO_M3R_LAB_OUT=str(output),P0_B54_HOST_EXE=str(binaries['patched']),M3_AREA='patched')
    counts={}
    for file,expected in (('test_handoff.py',19),('run_regressions.py',13),('test_integrity.py',4)):
        log=output/(file+'.log')
        command([sys.executable,'-B',str(HERE/file)],HERE,env,log)
        text=log.read_text(encoding='utf-8')
        found=re.search(r'Ran (\d+) tests',text)
        if not found or int(found[1])!=expected or not text.strip().endswith('OK') or 'skipped=' in text:
            raise RuntimeError('Incomplete/skipped qualification: '+file)
        counts[file]=int(found[1])
    result={a:resources(p) for a,p in binaries.items()}
    result['scope']='HOST_SIMULATOR_AND_INSTRUMENTATION_NOT_ESP8266_BIN_RAM_HEAP_CONT'
    result['host_exe_delta']=result['patched']['bytes']-result['base']['bytes']
    result['observation']=json.loads((output/'host-resource-observation.json').read_text())
    result['tests']={'handoff':counts['test_handoff.py'],'regressions':counts['run_regressions.py'],'integrity':counts['test_integrity.py'],'status':'PASS'}
    (output/'resources.json').write_text(json.dumps(result,indent=2))
    print(json.dumps(dict(status='B54_M3R_SOCKET_HANDOFF_HOST_TESTS_PASS',tests=result['tests'],host_exe_delta=result['host_exe_delta'],gate_bytes=result['observation']['m3_gate_bytes'],native_heap_CONT='NOT_MEASURED')))

if __name__=='__main__':main()
