"""Execute shared P1 C++ policy/storage/state machine with fake SDK I/O only."""
import json, subprocess, tempfile
from pathlib import Path
from v08_m8r_runner import compiler_environment
ROOT=Path(__file__).resolve().parents[1]
def run():
    with tempfile.TemporaryDirectory(prefix='p1-policy-') as td:
        directory=Path(td); compiler,env=compiler_environment(directory)
        msvc=Path(compiler).name.lower()=='cl.exe';exe=directory/'policy.exe'
        source=ROOT/'tools/home_lan_lab.cpp';includes=ROOT/'firmware/include'
        cmd=([compiler,'/nologo','/std:c++20','/EHsc','/O2',f'/I{includes}',str(source),'/link',f'/OUT:{exe}'] if msvc else
             [compiler,'-std=c++20','-Wall','-Wextra','-Werror','-O2','-fsanitize=address,undefined',f'-I{includes}',str(source),'-o',str(exe)])
        c=subprocess.run(cmd,cwd=directory,env=env,capture_output=True,text=True,timeout=90)
        if c.returncode:raise RuntimeError(c.stdout+c.stderr)
        c=subprocess.run([str(exe)],env=env,capture_output=True,text=True,timeout=30)
        if c.returncode:raise RuntimeError(c.stdout+c.stderr)
        result=json.loads(c.stdout);result['compiler']=Path(compiler).name
        result['scope']='shared target logic; simulated SDK I/O, no native power-loss claim'
        return result
if __name__=='__main__':print(json.dumps(run(),indent=2))
