"""Actual receiver/crypto + software LCD, offline only, with pinned GFX font."""
import argparse, hashlib, json, os, subprocess, tempfile
from pathlib import Path
from v08_m8r_runner import compiler_environment
from v07_pinned_core_probe import core_root, pinned_sources

ROOT = Path(__file__).resolve().parents[1]

def run(previews, scale=5):
    from PIL import Image
    pinned_sources()
    deps = ROOT/'experiments/artwork_pilot/.pio/libdeps/pilot_compile'
    aj = Path(os.environ.get('SHINO_ARDUINOJSON_SRC', str(deps/'ArduinoJson/src'))).resolve()
    gfx = Path(os.environ.get('SHINO_GFX_SRC', str(deps/'GFX Library for Arduino/src'))).resolve()
    assert '#define ARDUINOJSON_VERSION "7.4.3"' in (aj/'ArduinoJson/version.hpp').read_text()
    assert 'version=1.6.4' in (gfx.parent/'library.properties').read_text()
    fixtures = json.loads(subprocess.check_output(['node',str(ROOT/'tools/artwork_pilot_fixtures.js')],text=True))
    bear = core_root()/'tools/sdk/ssl/bearssl'
    manifest = json.loads((ROOT/'tools/v08_m8r_bearssl_manifest.json').read_text())
    for name, digest in manifest.items():
        assert hashlib.sha256((bear/name).read_bytes()).hexdigest() == digest
    sources = [*sorted((bear/'src/int').glob('i15_*.c')),*sorted((bear/'src/codec').glob('*.c')),
               *[bear/'src/ec'/n for n in ('ec_p256_m31.c','ec_secp256r1.c','ec_secp384r1.c','ec_secp521r1.c','ecdsa_i15_vrfy_raw.c','ecdsa_i15_bits.c')],bear/'src/hash/sha2small.c']
    previews = previews.resolve();previews.mkdir(parents=True,exist_ok=True)
    with tempfile.TemporaryDirectory(prefix='artwork-offline-') as td:
        directory = Path(td)
        lines = ['struct Packet {const char* header;const char* body;const char* nonce;};',
                 'struct Group {const char* name;const char* image;const Packet* packets;unsigned count;};',
                 'const char* publicPoint='+json.dumps(fixtures['public_point'])+';']
        for i,g in enumerate(fixtures['groups']):
            lines.append('const Packet packets'+str(i)+'[]={'+','.join('{'+','.join(json.dumps(p[k]) for k in ('header','body_hex','nonce'))+'}' for p in g['packets'])+'};')
        lines.append('const Group groups[]={'+','.join('{'+json.dumps(g['name'])+','+json.dumps(g['image_hex'])+',packets'+str(i)+','+str(len(g['packets']))+'}' for i,g in enumerate(fixtures['groups']))+'};')
        (directory/'fixtures.inc').write_text('\n'.join(lines),encoding='utf-8')
        compiler, env = compiler_environment(directory)
        msvc = Path(compiler).name.lower() == 'cl.exe'
        includes = [ROOT/'experiments/v08_m7/host_shims',bear/'inc',bear/'src']
        objects = []
        def execute(cmd,timeout=90):
            p = subprocess.run(cmd,cwd=directory,env=env,capture_output=True,text=True,timeout=timeout)
            if p.returncode: raise RuntimeError(p.stdout+p.stderr)
            return p
        for i,p in enumerate(sources):
            obj=directory/(str(i)+('.obj' if msvc else '.o'));objects.append(obj)
            if msvc:
                cmd=[compiler,'/nologo','/TC','/c','/O2','/DBR_LOMUL=1','/DBR_SLOW_MUL15=1',*[f'/I{x}' for x in includes],str(p),f'/Fo{obj}']
            else:
                cmd=['gcc','-O2','-DBR_LOMUL=1','-DBR_SLOW_MUL15=1',*[f'-I{x}' for x in includes],'-c',str(p),'-o',str(obj)]
            execute(cmd)
        exe=directory/'artwork.exe'
        includes += [ROOT/'experiments/v08_m8r/native',ROOT/'firmware/include',aj,gfx,directory]
        if msvc:
            cmd=[compiler,'/nologo','/std:c++20','/EHsc','/O2','/utf-8','/DSHINO_ARTWORK_DISPLAY_PILOT=1',f'/DSHINO_ARTWORK_SCALE={scale}',*[f'/I{x}' for x in includes],str(ROOT/'tools/scene_engine_lab.cpp'),*map(str,objects),'/link',f'/OUT:{exe}']
        else:
            cmd=[compiler,'-std=c++20','-O2','-g','-fsanitize=address,undefined','-fno-omit-frame-pointer',
                 '-DSHINO_ARTWORK_DISPLAY_PILOT=1',f'-DSHINO_ARTWORK_SCALE={scale}',*[f'-I{x}' for x in includes],str(ROOT/'tools/scene_engine_lab.cpp'),*map(str,objects),'-o',str(exe)]
        execute(cmd)
        report=json.loads(execute([str(exe),str(directory)]).stdout)
        for ppm in sorted(directory.glob('*.ppm')):
            with Image.open(ppm) as image:
                assert image.size==(240,240)
                image.save(previews/(ppm.stem+'.png'),optimize=True)
        # Compact review sheet only; each underlying preview remains 240x240.
        sheet=Image.new('RGB',(960,480),(3,8,20))
        for i,name in enumerate(('idle','playing','paused','no-artwork','marquee-start','marquee-middle','marquee-end','offline')):
            with Image.open(previews/(name+'.png')) as image: sheet.paste(image,((i%4)*240,(i//4)*240))
        sheet.save(previews/'contact-sheet.png',optimize=True)
        report.update(compiler=Path(compiler).name, sanitizers='ASan + UBSan' if not msvc else 'not enabled (MSVC)',
                      font_sha256=hashlib.sha256((gfx/'font/glcdfont.h').read_bytes()).hexdigest(),
                      preview_hashes={p.name:hashlib.sha256(p.read_bytes()).hexdigest() for p in sorted(previews.glob('*.png'))},
                      native_render_time='NOT MEASURED - no device contact',device_writes=0)
        for name in ('idle','playing','paused','no-artwork','marquee-start','marquee-middle','marquee-end','offline'):
            with Image.open(previews/(name+'.png')) as image:
                assert image.size==(240,240), name
        report['individual_preview_size']=[240,240]
        return report

if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--previews',type=Path,default=ROOT/'docs/artwork-pilot/scenes')
    p.add_argument('--scale',type=int,choices=(3,4,5),default=5)
    args=p.parse_args()
    print(json.dumps(run(args.previews,args.scale),indent=2))
