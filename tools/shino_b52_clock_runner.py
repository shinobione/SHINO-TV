"""Targeted native clock/render lab; no socket or private/device input."""
import argparse
import hashlib
import json
import subprocess
from pathlib import Path
from v08_m8r_runner import compiler_environment

ROOT=Path(__file__).resolve().parents[1]

def run(output,gfx,asan=False):
    from PIL import Image
    output=Path(output).resolve()
    if output.exists():
        raise ValueError("New lab output directory required")
    gfx=Path(gfx).resolve()
    if "version=1.6.4" not in (gfx.parent/"library.properties").read_text():
        raise ValueError("Pinned GFX 1.6.4 required")
    output.mkdir(parents=True)
    compiler,env=compiler_environment(output)
    exe=output/"clock-lab.exe"
    includes=[ROOT/"firmware/include",gfx]
    if Path(compiler).name.lower()=="cl.exe":
        cmd=[compiler,"/nologo","/std:c++20","/EHsc","/O2","/utf-8",*(["/fsanitize=address","/Zi","/MD"] if asan else []),*[f"/I{x}" for x in includes],
             str(ROOT/"tools/shino_b52_clock_lab.cpp"),"/link",f"/OUT:{exe}"]
        sanitizers="MSVC ASan" if asan else "NOT_RUN (MSVC)"
    else:
        cmd=[compiler,"-std=c++20","-O2","-g","-fsanitize=address,undefined","-fno-omit-frame-pointer",
             *[f"-I{x}" for x in includes],str(ROOT/"tools/shino_b52_clock_lab.cpp"),"-o",str(exe)]
        sanitizers="ASan + UBSan"
    built=subprocess.run(cmd,cwd=output,env=env,capture_output=True,text=True,timeout=90)
    if built.returncode:
        raise RuntimeError(built.stdout+built.stderr)
    tested=subprocess.run([str(exe),str(output)],cwd=output,env=env,capture_output=True,text=True,timeout=30)
    if tested.returncode:
        raise RuntimeError(tested.stdout+tested.stderr)
    report=json.loads(tested.stdout)
    for ppm in output.glob("*.ppm"):
        with Image.open(ppm) as image:
            assert image.size==(240,240)
            image.save(output/(ppm.stem+".png"),optimize=True)
    report.update(compiler=Path(compiler).name,sanitizers=sanitizers,
        font_sha256=hashlib.sha256((gfx/"font/glcdfont.h").read_bytes()).hexdigest(),
        preview_hashes={p.name:hashlib.sha256(p.read_bytes()).hexdigest() for p in output.glob("*.png")},
        source_hashes={p:hashlib.sha256((ROOT/p).read_bytes()).hexdigest() for p in
            ("firmware/include/display/ClockFoundation.h","firmware/include/display/SceneEngine.h","tools/shino_b52_clock_lab.cpp")},
        physical="NOT_RUN",fixture_time="SYNTHETIC_HOST_ONLY",native_heap_stack_measured=False)
    (output/"host-report.json").write_text(json.dumps(report,indent=2)+"\n")
    return report

if __name__=="__main__":
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument("--output",type=Path,required=True)
    p.add_argument("--gfx-src",type=Path,required=True)
    p.add_argument("--asan",action="store_true")
    a=p.parse_args()
    print(json.dumps(run(a.output,a.gfx_src,a.asan),indent=2))

