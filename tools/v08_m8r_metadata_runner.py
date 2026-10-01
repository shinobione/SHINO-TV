"""Bounded metadata corpus on real ArduinoJson with 32-bit host ABI, no device."""
import copy,hashlib,json,os,shutil,subprocess,sys,tempfile
import itertools,random
from pathlib import Path
from v07_cpp_lab_runner import VSDEV
from v07_pinned_core_probe import core_root
ROOT=Path(__file__).resolve().parent.parent
BASELINE='c5bb1a813113af802b8736939a22de5a78097acd'
sys.path.insert(0,str(ROOT/'companion'))
import media_wire_v2_host as wire

def corpus():
    epoch=0x1122334455667788;tx=wire.transaction(epoch,1).hex();cases=[]
    def add(name,raw):
        if isinstance(raw,dict):raw=json.dumps(raw,ensure_ascii=False,separators=(',',':'),sort_keys=True).encode()
        try:value=wire.parse_metadata(raw);valid=value['tx']==tx
        except (wire.WireError,UnicodeError,ValueError):valid=False
        cases.append({'name':name,'bytes':raw,'expected':valid})
    bases=[]
    for w in (0,32,48):
        image=bytes([0xa5])*w*w*2
        m=dict(album='Album',artist='Artist',cover_len=len(image),cover_sha256=hashlib.sha256(image).hexdigest() if w else None,duration=60,height=w,pixel_format='RGB565LE' if w else 'NONE',position=0,source='qualification',state='PLAYING',tile_count=len(image)//512,title='Test',track_key='0'*64,tx=tx,v=2,width=w)
        bases.append(m);add('retained-width-'+str(w),m)
        # Split the complete 512-byte budget across multiple distinct strings.
        # Include tiny-string, alignment and builder growth boundaries.
        edges=(0,1,3,4,7,8,15,16,17,31,32,33,47,48,49,60,63,64,65,80)
        for sizes in itertools.product(edges,[n for n in edges if n<=60],[n for n in edges if n<=60]):
            c=copy.deepcopy(m)
            for field,char,n in zip(('source','title','artist'),('s','t','r'),sizes):c[field]=char*n
            c['album']='';remaining=512-len(json.dumps(c,separators=(',',':'),sort_keys=True).encode())
            if remaining>=0:
                c['album']='a'*min(48,remaining);add(f'{w}-split-'+str(sizes),c)
        for field,limit in (('source',80),('title',60),('artist',60),('album',48)):
            for char in ('x','é','界','😀'):
                for n in range(limit+2):
                    c=copy.deepcopy(m);c[field]=char*n;add(f'{w}-{field}-{ord(char)}-{n}',c)
        for size in (511,512,513):
            c=copy.deepcopy(m);b=json.dumps(c,separators=(',',':'),sort_keys=True).encode();c['source']='q'*(len(c['source'])+size-len(b));add(f'{w}-payload-{size}',c)
        for key in list(m):
            c=copy.deepcopy(m);del c[key];add(f'{w}-missing-{key}',c)
            for value in (True,False,[],{},None,-1,1.5):
                c=copy.deepcopy(m);c[key]=value;add(f'{w}-type-{key}-{str(value)}',c)
            if isinstance(m[key],str):
                c=copy.deepcopy(m);c[key]+='\0tail';add(f'{w}-NUL-value-{key}',c)
            c=copy.deepcopy(m);c[key+'\0tail']=c.pop(key);add(f'{w}-NUL-key-{key}',c)
        raw=json.dumps(m,separators=(',',':'),sort_keys=True).encode()
        add(f'{w}-duplicate',raw.replace(b'{',b'{"album":"Album",',1))
        add(f'{w}-whitespace',b' '+raw);add(f'{w}-order',json.dumps(m,separators=(',',':')).encode())
        for bad in (b'\xc0\xaf',b'\xed\xa0\x80',b'\xf4\x90\x80\x80',b'\xe2',b'\x80'):
            add(f'{w}-utf8-{bad.hex()}',raw.replace(b'Album',bad))
        for escape in (b'\\u0000',b'\\u001f',b'\\u0080',b'\\ud800',b'\\u0041'):
            add(f'{w}-escape-{escape.hex()}',raw.replace(b'Album',escape))
        for depth in (1,2,3,10):
            add(f'{w}-nest-{depth}',raw.replace(b'"Album"',b'['*depth+b'"Album"'+b']'*depth))
        for number in (b'1e999',b'18446744073709551616',b'604801',b'-0'):
            add(f'{w}-number-{number.decode()}',raw.replace(b'"position":0',b'"position":'+number))
    for n in range(1,75):
        add(f'adversarial-members-{n}',json.dumps({f'k{i}':str(i)*3 for i in range(n)},separators=(',',':')).encode())
    for n in range(1,100):add(f'adversarial-long-string-{n}',b'{"a":"'+b'x'*n+b'","b":'+b'['*3+b'0'+b']'*3+b'}')
    rand=random.Random(801)
    for i in range(3000):
        m=copy.deepcopy(bases[i%3])
        for field,limit in (('source',80),('title',60),('artist',60),('album',48)):
            m[field]=''.join(rand.choice('abcXYZé界😀') for _ in range(rand.randrange(limit+2)))
        add(f'seeded-metadata-{i}',m)
    return tx,cases

def compiler32(directory):
    if os.name!='nt':return shutil.which('g++'),os.environ.copy(),['-m32']
    batch=directory/'compiler32.cmd';batch.write_text('@echo off\ncall "'+str(VSDEV)+'" -arch=x86 >nul\nset\n',encoding='utf-8')
    run=subprocess.run(['cmd.exe','/d','/c',str(batch)],capture_output=True,text=True,check=True,timeout=30)
    env={k:v for k,v in os.environ.items() if k.upper()!='PATH'}
    for line in run.stdout.splitlines():
        k,sep,v=line.partition('=')
        if sep and k:env['PATH' if k.upper()=='PATH' else k]=v
    return shutil.which('cl.exe',path=env.get('PATH')),env,[]

def run():
    tx,cases=corpus();aj=Path(os.environ.get('SHINO_ARDUINOJSON_SRC',ROOT/'experiments/v08_m8r/.pio/libdeps/media_compile/ArduinoJson/src')).resolve()
    assert '#define ARDUINOJSON_VERSION "7.4.3"' in (aj/'ArduinoJson/version.hpp').read_text()
    bear=core_root()/'tools/sdk/ssl/bearssl';profiles=[]
    with tempfile.TemporaryDirectory(prefix='m8-metadata32-') as td:
        d=Path(td);compiler,env,arch=compiler32(d);assert compiler,'32-bit host compiler required'
        inc=[ROOT/'experiments/v08_m8r/native',ROOT/'experiments/v08_m7/host_shims',aj,bear/'inc',bear/'src']
        old=subprocess.check_output(['git','show',BASELINE+':experiments/v08_m8r/native/MediaReceiver.h'],cwd=ROOT,text=True)
        old=old.replace('  JsonArena() : bytes(new(std::nothrow) uint8_t[capacity]) {','  inline static size_t lastUsage=0,maxUsage=0;\n  inline static bool lastDenied=false,denyBackingAllocation=false;\n  ~JsonArena(){lastUsage=used;if(used>maxUsage)maxUsage=used;}\n  JsonArena() : bytes(new(std::nothrow) uint8_t[capacity]) {\n    if(denyBackingAllocation)bytes.reset();')
        first=old.index('class JsonArena');last=old.index('M8R_NOINLINE inline bool metadata')
        old=old[:first]+old[first:last].replace('return nullptr;','return (lastDenied=true,nullptr);')+old[last:]
        # GCC x86 -m32 has max_align_t=16; reproduce pinned Xtensa's measured
        # alignment=8 for the old allocator too. Pointer/slot/string sizes stay real.
        old=old.replace('alignof(max_align_t)', '8')
        baseline=d/'baseline';baseline.mkdir();(baseline/'MediaReceiver.h').write_text(old,encoding='utf-8')
        objects=[]
        for source in [bear/'src/hash/sha2small.c',*sorted((bear/'src/codec').glob('*32be.c'))]:
            obj=d/(source.stem+('.obj' if os.name=='nt' else '.o'));objects.append(obj)
            if os.name=='nt':cmd=[compiler,'/nologo','/TC','/c','/O2',*[f'/I{x}' for x in inc],str(source),f'/Fo{obj}']
            else:cmd=['gcc',*arch,'-O2',*[f'-I{x}' for x in inc],'-c',str(source),'-o',str(obj)]
            subprocess.run(cmd,cwd=d,env=env,capture_output=True,text=True,timeout=45,check=True)
        for variant,capacity in (('baseline',4096),('new',4096),('new',2048),('pressure',1024)):
            exe=d/f'metadata-{variant}-{capacity}.exe';defs=[f'SHINO_M8_METADATA_ARENA_BYTES={capacity}','M8R_ARENA_TEST_PROFILE=1'];includes=([baseline]+inc) if variant=='baseline' else inc
            if variant=='baseline':defs.append('M8R_BASELINE_PROFILE=1')
            if os.name=='nt':cmd=[compiler,'/nologo','/std:c++20','/EHsc','/O2','/utf-8',*[f'/D{x}' for x in defs],*[f'/I{x}' for x in includes],str(ROOT/'tools/v08_m8r_metadata_lab.cpp'),*map(str,objects),'/link',f'/OUT:{exe}']
            else:cmd=[compiler,*arch,'-std=c++20','-O2',*[f'-D{x}' for x in defs],*[f'-I{x}' for x in includes],str(ROOT/'tools/v08_m8r_metadata_lab.cpp'),*map(str,objects),'-o',str(exe)]
            c=subprocess.run(cmd,cwd=d,env=env,capture_output=True,text=True,timeout=90)
            if c.returncode:raise RuntimeError(c.stdout+c.stderr)
            raw=tx+'\n'+'\n'.join(c['bytes'].hex() for c in cases)+'\n'
            out=subprocess.run([str(exe)],input=raw,cwd=d,env=env,capture_output=True,text=True,timeout=30,check=True)
            actual=[tuple(map(int,l.split())) for l in out.stdout.splitlines()];assert len(actual)==len(cases)
            failures=[cases[i]['name'] for i,a in enumerate(actual) if bool(a[0])!=cases[i]['expected']]
            if variant=='baseline':assert all('NUL' in name or name.endswith('escape-5c7530303030') for name in failures),'baseline non-NUL drift'
            elif variant=='pressure':assert not any(a[0] for a in actual),'undersized arena must fail closed'
            else:assert not failures,failures[:8]
            layout=out.stderr.splitlines()[0].split()
            assert tuple(int(layout[i]) for i in (1,3,4))==(4,8,8), 'pointer/slot/string ABI drift'
            profiles.append({'variant':variant,'pointer_bytes':4,'native_arena_alignment':8,'capacity':capacity,'cases':len(cases),'valid':sum(c['expected'] for c in cases),'max_valid_usage':max((a[1] for a in actual if a[0]),default=0),'max_all_usage':max(a[1] for a in actual),'denials':sum(a[2] for a in actual),'known_baseline_NUL_failures':failures if variant=='baseline' else [],'ABI_and_lifetime':out.stderr.splitlines()})
    return {'profiles':profiles,'device_contacts':0,'corpus_sha256':hashlib.sha256(b''.join(c['bytes'] for c in cases)).hexdigest(),'target_capacity_test_is_not_8192_host_profile':True}
if __name__=='__main__':print(json.dumps(run(),indent=2))
