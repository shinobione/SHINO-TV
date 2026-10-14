"""Clock-only real BearSSL HOST/ASan lab; no network/device/private input."""
import argparse
import json
from pathlib import Path
import subprocess
from v08_m8r_runner import compiler_environment
from v07_pinned_core_probe import core_root
ROOT=Path(__file__).resolve().parents[1]

def run(output):
    output=Path(output).resolve();output.mkdir(exist_ok=False)
    core=core_root();bear=core/"tools/sdk/ssl/bearssl"
    compiler,env=compiler_environment(output)
    assert Path(compiler).name.lower()=="cl.exe","This targeted ASan runner uses installed MSVC"
    sources=[bear/"src/hash/sha2small.c",bear/"src/mac/hmac.c",*sorted((bear/"src/codec").glob("*.c"))]
    inc=[f"/I{p}" for p in (ROOT/"experiments/v08_m7/host_shims",bear/"inc",bear/"src",ROOT/"firmware/include",ROOT/"experiments/b52_clock/native")]
    built=subprocess.run([compiler,"/nologo","/TC","/c","/O1","/Zi","/MD","/fsanitize=address",*inc,*map(str,sources)],cwd=output,env=env,capture_output=True,text=True,timeout=90)
    if built.returncode:raise RuntimeError(built.stdout+built.stderr)
    objects=[output/(p.stem+".obj") for p in sources];exe=output/"proof-lab.exe"
    built=subprocess.run([compiler,"/nologo","/std:c++20","/EHsc","/O1","/Zi","/MD","/fsanitize=address","/DHOST_MOCK=1",*inc,str(ROOT/"tools/shino_b52_clock_freshness_lab.cpp"),*map(str,objects),"/link",f"/OUT:{exe}"],cwd=output,env=env,capture_output=True,text=True,timeout=90)
    if built.returncode:raise RuntimeError(built.stdout+built.stderr)
    tested=subprocess.run([str(exe)],cwd=output,env=env,capture_output=True,text=True,timeout=30)
    (output/"run.log").write_text(tested.stdout+tested.stderr)
    if tested.returncode:raise RuntimeError(tested.stdout+tested.stderr)
    report=json.loads(tested.stdout);report.update(sanitizers="MSVC ASan, C crypto and C++ gate",physical="NOT_RUN")
    (output/"proof-report.json").write_text(json.dumps(report,indent=2)+"\n")
    return report

if __name__=="__main__":
    p=argparse.ArgumentParser(description=__doc__);p.add_argument("--output",type=Path,required=True)
    print(json.dumps(run(p.parse_args().output),indent=2))
