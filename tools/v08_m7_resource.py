"""Full native links and compiler frames; never runtime heap/stack/WDT proof."""
from pathlib import Path
import hashlib,json,os,subprocess,tempfile
from v07_pinned_core_probe import core_root,pinned_sources
ROOT=Path(__file__).resolve().parents[1];BUILD=ROOT/'experiments/v08_m7/.pio/build'
BIN=Path.home()/'.platformio/packages/toolchain-xtensa/bin'
def tool(name):return str(BIN/('xtensa-lx106-elf-'+name+('.exe' if os.name=='nt' else '')))
def linked(name):
    path=BUILD/name;elf=path/'firmware.elf';image=path/'firmware.bin'
    fields=subprocess.check_output([tool('size'),str(elf)],text=True).splitlines()[1].split()
    sizes=dict(zip(('text','data','bss'),map(int,fields[:3])));sizes['bin']=image.stat().st_size
    symbols=subprocess.check_output([tool('nm'),'-S','-C',str(elf)],text=True)
    server=[s.split() for s in symbols.splitlines() if s.endswith(' b (anonymous namespace)::server')];assert len(server)==1
    sizes['server']=int(server[0][1],16)
    objects={}
    for name in ('m7Authority','m7Ingress','m7Receiver'):
        rows=[s.split() for s in symbols.splitlines() if s.endswith(' '+name)]
        if rows:assert len(rows)==1;objects[name]=int(rows[0][1],16)
    frames=[]
    for p in path.rglob('*.su'):
        for line in p.read_text(encoding='utf-8').splitlines():
            if any(x in line for x in ('m7::','::_v08ReadFirstLine(','::handleClient()')):
                f,n,kind=line.rsplit('\t',2);frames.append({'function':f,'frame':int(n),'kind':kind})
    return {'sizes':sizes,'objects':objects,'frames_not_high_water':frames,'elf_sha256':hashlib.sha256(elf.read_bytes()).hexdigest()}
def crypto_frames():
    # Compile exact native BearSSL C, including default Xtensa assembly calls,
    # just for compiler frames. Precompiled linked library has no .su files.
    c=core_root();b=c/'tools/sdk/ssl/bearssl';paths=[b/'src/ec/ecdsa_i15_vrfy_raw.c',b/'src/ec/ec_p256_m15.c',b/'src/hash/sha2small.c']
    result=[]
    with tempfile.TemporaryDirectory(prefix='m7-xtensa-frames-') as td:
        d=Path(td)
        for p in paths:
            includes=[c/'cores/esp8266',c/'tools/sdk/include',c/'tools/sdk/include/bearssl',b/'src']
            cmd=[tool('gcc'),'-c','-Os','-mlongcalls','-mtext-section-literals','-ffunction-sections','-fdata-sections','-fstack-usage','-DESP8266','-D__ets__','-DICACHE_FLASH',*[f'-I{x}' for x in includes],str(p),'-o',str(d/(p.stem+'.o'))]
            e=subprocess.run(cmd,capture_output=True,text=True,timeout=45)
            if e.returncode:raise RuntimeError(e.stdout+e.stderr)
            result.append({'source':str(p.relative_to(b)),'hash':hashlib.sha256(p.read_bytes()).hexdigest(),'frames':(d/(p.stem+'.su')).read_text().splitlines()})
    return result
def run():
    pinned_sources();a=linked('legacy_compile');b=linked('media_compile')
    return {'head':subprocess.check_output(['git','rev-parse','HEAD'],cwd=ROOT,text=True).strip(),'dirty':bool(subprocess.check_output(['git','status','--porcelain'],cwd=ROOT,text=True).strip()),'legacy':a,'media':b,'delta':{k:b['sizes'][k]-a['sizes'][k] for k in a['sizes']},'crypto_compiler_frames':crypto_frames(),'limits':{'header':1025,'body_max':552,'image_max':4608,'native_json_arena':4096,'challenges':4,'principals':16},'evidence':'Xtensa full graph link/static frames only; no device runtime'}
if __name__=='__main__':print(json.dumps(run(),indent=2))
