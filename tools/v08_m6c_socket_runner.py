"""Stock / Mission 6A / partial R7 actual source loopback differential."""
import hashlib
import json
import os
from pathlib import Path
import subprocess
import tempfile
import v08_m6a_socket_runner as inherited
import v08_m6a_overlay as previous
import v08_m6c_overlay as candidate

ROOT = inherited.ROOT
BASE = '7d40df9f69bead1aa3a8c7ebd88dbfa0121968e0'

def run():
    # Reuse only the explicitly documented pinned-source portability generator.
    inherited.old_materialize = previous.materialize
    inherited.OLD_OUTPUT = previous.OUTPUT
    aj=Path(os.environ.get('SHINO_ARDUINOJSON_SRC', str(ROOT/'experiments/v08_full_bridge/.pio/libdeps/bridge_baseline/ArduinoJson/src'))).resolve()
    if '#define ARDUINOJSON_VERSION "7.4.3"' not in (aj/'ArduinoJson/version.hpp').read_text():
        raise ValueError('ArduinoJson 7.4.3 required')
    results=[]
    with tempfile.TemporaryDirectory(prefix='v08-m6c-') as td:
        directory=Path(td)
        inherited.OUTPUT = directory/'candidate-input'
        inherited.materialize = lambda: candidate.materialize(inherited.OUTPUT)
        hashes=inherited.generate(directory)
        compiler,env=inherited.compiler_environment(directory)
        for variant,oem in [('stock',0),('previous',0),('corrected',0),('stock',1),('previous',1),('corrected',1)]:
            output=directory/f'{variant}-{oem}.exe'
            includes=[directory/variant,inherited.LAB/'host_shims',ROOT/'experiments/v08_full_bridge/host_shims',ROOT/'firmware/include',aj]
            sources=[ROOT/'tools/v08_m6c_socket_lab.cpp',ROOT/'firmware/src/boot/FslessMetrics.cpp',ROOT/'firmware/src/boot/FslessWebUI.cpp',directory/variant/'detail/mimetable.cpp']
            defines=[f'SHINO_ENABLE_FACTORY_RESTORE={oem}',f'LAB_OVERLAY={int(variant!="stock")}',f'LAB_CORRECTED={int(variant!="stock")}',f'LAB_R7={int(variant=="corrected")}']
            if variant!='stock': defines+=['SHINO_V08_PREPARSE_EXPERIMENT=1']
            if Path(compiler).name.lower()=='cl.exe':
                command=[compiler,'/nologo','/std:c++20','/EHsc','/utf-8',*[f'/D{x}' for x in defines],*[f'/I{x}' for x in includes],*map(str,sources),'/link','ws2_32.lib','bcrypt.lib',f'/OUT:{output}']
            else:
                command=[compiler,'-std=c++20','-pthread',*[f'-D{x}' for x in defines],*[f'-I{x}' for x in includes],*map(str,sources),'-lcrypto','-o',str(output)]
            c=subprocess.run(command,cwd=directory,env=env,capture_output=True,text=True,timeout=90)
            if c.returncode: raise RuntimeError(c.stdout+c.stderr)
            e=subprocess.run([str(output)],env=env,capture_output=True,text=True,timeout=45)
            if e.returncode: raise RuntimeError(e.stdout+e.stderr)
            results.append({'variant':variant,'conditional_oem':oem,'compiler':Path(compiler).name,'result':json.loads(e.stdout)})
    def git(*args): return subprocess.run(['git',*args],cwd=ROOT,check=True,capture_output=True,text=True).stdout.strip()
    changed=git('diff','--name-only',BASE,'--').splitlines()
    allowed={'.github/workflows/ci.yml',*[f'tools/v08_m6c_{n}' for n in ['overlay.py','socket_lab.cpp','socket_runner.py']],*[f'docs/V08_MISSION_6C_{n}.md' for n in ['R7_REMEDIATION_REPORT','FINDINGS_MATRIX','GATE']]}
    if set(changed)-allowed: raise AssertionError(changed)
    inputs=[ROOT/'tools/v08_m6c_overlay.py',ROOT/'tools/v08_m6c_socket_lab.cpp',ROOT/'tools/v08_m6c_socket_runner.py',ROOT/'firmware/src/boot/FirstBootBridge.cpp',ROOT/'firmware/src/boot/FslessMetrics.cpp',ROOT/'firmware/src/boot/FslessWebUI.cpp',*sorted((inherited.LAB/'host_shims').rglob('*.h'))]
    return {'source_head':git('rev-parse','HEAD'),'working_tree_dirty':bool(git('status','--porcelain')),'base':BASE,'evidence_class':'HOST ONLY; partial R7; pre-body authorization BLOCKED BY ARCHITECTURE','source_hashes':hashes,'composition_input_hashes':{str(p.relative_to(ROOT)):hashlib.sha256(p.read_bytes()).hexdigest() for p in inputs},'historical_preservation':True,'runs':results}

if __name__=='__main__': print(json.dumps(run(),indent=2))
