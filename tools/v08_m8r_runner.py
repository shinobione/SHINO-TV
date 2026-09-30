"""No-skip real BearSSL/native owner/loopback and unchanged-wire differential."""
from pathlib import Path
import hashlib,json,os,subprocess,tempfile,sys,shutil
import v08_m6a_socket_runner as inherited
import v08_m8r_overlay as candidate
from v07_pinned_core_probe import core_root,pinned_sources
ROOT=candidate.ROOT;BASE='5179eb04ea51c2a92c7f796f07ebb963e2167e00'

def compiler_environment(directory):
    if os.name != 'nt': return inherited.compiler_environment(directory)
    from v07_cpp_lab_runner import VSDEV
    batch=directory/'compiler-env.cmd'
    batch.write_text('@echo off\ncall "'+str(VSDEV)+'" -arch=x64 >nul\nset\n')
    run=subprocess.run(['cmd.exe','/d','/c',str(batch)],capture_output=True,text=True,timeout=30,check=True)
    env={k:v for k,v in os.environ.items() if k.upper()!='PATH'}
    for line in run.stdout.splitlines():
        key,sep,value=line.partition('=')
        if sep and key: env['PATH' if key.upper()=='PATH' else key]=value
    compiler=shutil.which('cl.exe',path=env.get('PATH'))
    if not compiler: raise RuntimeError('No MSVC compiler in captured environment')
    return compiler,env

def fixture_source(fixtures):
    def literal(s):return json.dumps(s,ensure_ascii=True)
    lines=['struct Fixture { const char* header; const char* body; const char* nonce; };']
    lines += [f'const char* retainedKey={literal(fixtures["retained_key"])};',f'const char* syntheticKey={literal(fixtures["synthetic_key"])};']
    for name,e in fixtures['retained'].items():lines.append(f'Fixture {name}={{{literal(e["header"])},{literal(e["body_hex"])},{literal(e["nonce"])}}};')
    for w,entries in fixtures['groups'].items():lines.append(f'Fixture group{w}[]={{'+','.join('{'+','.join(literal(e[k]) for k in ('header','body_hex','nonce'))+'}' for e in entries)+'};')
    return '\n'.join(lines)

def run():
    pinned_sources()
    aj=Path(os.environ.get('SHINO_ARDUINOJSON_SRC',str(ROOT/'experiments/v08_full_bridge/.pio/libdeps/bridge_baseline/ArduinoJson/src'))).resolve()
    assert '#define ARDUINOJSON_VERSION "7.4.3"' in (aj/'ArduinoJson/version.hpp').read_text()
    fixtures=json.loads(subprocess.check_output(['node',str(ROOT/'tools/v08_m7_fixtures.js')],text=True))
    bear=core_root()/'tools/sdk/ssl/bearssl'
    # Exact pinned implementation; compile only crypto subset, no signing code.
    sources=[*sorted((bear/'src/int').glob('i15_*.c')),*sorted((bear/'src/codec').glob('*.c')),
             *[bear/'src/ec'/n for n in ('ec_p256_m31.c','ec_secp256r1.c','ec_secp384r1.c','ec_secp521r1.c','ecdsa_i15_vrfy_raw.c','ecdsa_i15_bits.c')],bear/'src/hash/sha2small.c']
    crypto_hashes={str(p.relative_to(bear)):hashlib.sha256(p.read_bytes()).hexdigest() for p in sources}
    manifest=json.loads((ROOT/'tools/v08_m8r_bearssl_manifest.json').read_text())
    for name,digest in manifest.items():
        assert hashlib.sha256((bear/name).read_bytes()).hexdigest()==digest, 'BearSSL source drift: '+name
    runs=[]
    with tempfile.TemporaryDirectory(prefix='v08-m8r-') as td:
        directory=Path(td);(directory/'fixtures.inc').write_text(fixture_source(fixtures),encoding='utf-8')
        inherited.OUTPUT=directory/'input';inherited.materialize=lambda:candidate.materialize(inherited.OUTPUT)
        hashes=inherited.generate(directory)
        compiler,env=compiler_environment(directory);msvc=Path(compiler).name.lower()=='cl.exe'
        cinc=[ROOT/'experiments/v08_m7/host_shims',bear/'inc',bear/'src'];objects=[]
        for i,p in enumerate(sources):
            obj=directory/(str(i)+('.obj' if msvc else '.o'));objects.append(obj)
            if msvc:cmd=[compiler,'/nologo','/TC','/c','/O2','/DBR_LOMUL=1','/DBR_SLOW_MUL15=1',*[f'/I{x}' for x in cinc],str(p),f'/Fo{obj}']
            else:cmd=['gcc','-O2','-DBR_LOMUL=1','-DBR_SLOW_MUL15=1','-fstack-usage',*[f'-I{x}' for x in cinc],'-c',str(p),'-o',str(obj)]
            c=subprocess.run(cmd,cwd=directory,env=env,capture_output=True,text=True,timeout=45)
            if c.returncode:raise RuntimeError(c.stdout+c.stderr)
        for oem in (0,1):
            output=directory/f'm7-{oem}.exe'
            includes=[directory/'corrected',ROOT/'experiments/v08_m8r/native',directory,*cinc,inherited.LAB/'host_shims',ROOT/'experiments/v08_full_bridge/host_shims',ROOT/'firmware/include',aj]
            cpp=[ROOT/'tools/v08_m8r_lab.cpp',ROOT/'firmware/src/boot/FslessMetrics.cpp',ROOT/'firmware/src/boot/FslessWebUI.cpp',directory/'corrected/detail/mimetable.cpp']
            defs=[f'SHINO_ENABLE_FACTORY_RESTORE={oem}','LAB_OVERLAY=1','LAB_CORRECTED=1','SHINO_V08_PREPARSE_EXPERIMENT=1']
            if msvc:cmd=[compiler,'/nologo','/std:c++20','/EHsc','/utf-8',*[f'/D{x}' for x in defs],*[f'/I{x}' for x in includes],*map(str,cpp),*map(str,objects),'/link','ws2_32.lib','bcrypt.lib',f'/OUT:{output}']
            else:cmd=[compiler,'-std=c++20','-pthread','-O2','-fstack-usage',*[f'-D{x}' for x in defs],*[f'-I{x}' for x in includes],*map(str,cpp),*map(str,objects),'-lcrypto','-o',str(output)]
            c=subprocess.run(cmd,cwd=directory,env=env,capture_output=True,text=True,timeout=90)
            if c.returncode:raise RuntimeError(c.stdout+c.stderr)
            e=subprocess.run([str(output)],cwd=directory,env=env,capture_output=True,text=True,timeout=90)
            if e.returncode:raise RuntimeError(e.stdout+e.stderr)
            runs.append({'oem':oem,'compiler':Path(compiler).name,'result':json.loads(e.stdout)})
            if oem==0:
                differential=wire_diff(output,env)
                cases=json.loads(subprocess.check_output(['node',str(ROOT/'tools/v08_m7_profile_cases.js')],text=True))
                probe=subprocess.run([str(output),'headers'],input='\n'.join(x['hex'] for x in cases)+'\n',env=env,capture_output=True,text=True,timeout=30,check=True)
                assert [int(x) for x in probe.stdout.splitlines()]==[int(x['accepted']) for x in cases]
                profile_differential={'cases':len(cases),'admitted':sum(x['accepted'] for x in cases),'agreement':True}
    inputs=[ROOT/'tools/v08_m8r_runner.py',ROOT/'tools/v08_m8r_lab.cpp',ROOT/'tools/v08_m8r_overlay.py',ROOT/'tools/v08_m8r_bearssl_manifest.json',ROOT/'tools/v08_m7_fixtures.js',ROOT/'tools/v08_m7_profile_cases.js',*sorted((ROOT/'experiments/v08_m8r/native').glob('*.h')),
            ROOT/'experiments/v08_m8r/native/MediaStackThunk.cpp',ROOT/'tools/v08_m8r_core_manifest.json',ROOT/'tools/v08_m6a_socket_runner.py',ROOT/'tools/v08_m6a_socket_lab.cpp',ROOT/'firmware/src/boot/FirstBootBridge.cpp',ROOT/'companion/media_wire_v2_host.py']
    def git(*args):return subprocess.check_output(['git',*args],cwd=ROOT,text=True).strip()
    changed=git('diff','--name-only',BASE,'--').splitlines()
    # Mission 8 continuity continuation explicitly authorizes these PC-only files.
    # Retain exact-path scope; firmware and unrelated companion code stay excluded.
    companion_continuity={
        'companion/shino_link.py','companion/push_fsless_metrics.py',
        'companion/test_shino_link.py','companion/test_push_fsless_metrics.py',
        'companion/SHINO_LINK.md',
    }
    allowed=lambda p:p in ('.gitignore','.github/workflows/ci.yml') or p in companion_continuity or p.startswith(('experiments/v08_m8r/','tools/v08_m8r_','docs/V08_MISSION_8'))
    assert all(allowed(p) for p in changed),changed
    return {'head':git('rev-parse','HEAD'),'dirty':bool(git('status','--porcelain')),'base':BASE,'runs':runs,'wire_differential':differential,'profile_differential':profile_differential,'crypto_source_hashes':crypto_hashes,'owner_source_hashes':hashes,'input_hashes':{str(p.relative_to(ROOT)):hashlib.sha256(p.read_bytes()).hexdigest() for p in inputs},'public_only_generated_vectors':fixtures,'historical_preservation':True}

def wire_diff(exe,env):
    sys.path.insert(0,str(ROOT/'companion'));import media_wire_v2_host as w
    v=json.loads((ROOT/'tools/v08_crypto_vectors.json').read_text());b=bytes.fromhex(v['entries']['begin']['body_hex']);tx=bytes.fromhex(v['tx']);epoch=int(v['epoch_hex'],16)
    cases=[b]
    for i in range(40):
        for n in range(256):
            if n!=b[i]:m=bytearray(b);m[i]=n;cases.append(bytes(m))
    cases.extend([b[:i] for i in (0,1,39,40,len(b)-1)]+[b+b'X'])
    e=subprocess.run([str(exe),'wire'],input='\n'.join(x.hex() for x in cases)+'\n',env=env,capture_output=True,text=True,timeout=45,check=True)
    actual=[int(x) for x in e.stdout.splitlines()];assert len(actual)==len(cases)
    expected=[]
    for x in cases:
        try:w.HostReceiver(epoch).receive(x[:40],x[40:],w.Authority('lab',epoch,w.BEGIN,tx),now=0);expected.append(1)
        except w.WireError:expected.append(0)
    assert actual==expected
    return {'cases':len(cases),'admitted':sum(actual),'agreement':True}

if __name__=='__main__':print(json.dumps(run(),indent=2))
