"""Execute pinned StageA parser/Digest over host loopback, never owner network."""
from pathlib import Path
import hashlib, importlib.util, json, shutil, subprocess, tempfile
from unittest.mock import patch
import v08_m6a_socket_runner as inherited
from v07_pinned_core_probe import core_root
from v08_m8r_runner import compiler_environment
ROOT=Path(__file__).resolve().parent.parent

def run():
    spec=importlib.util.spec_from_file_location('m9_normal_webserver',ROOT/'firmware/scripts/m9_normal_webserver.py')
    module=importlib.util.module_from_spec(spec);spec.loader.exec_module(module)
    with tempfile.TemporaryDirectory(prefix='m9-stagea-http-') as td:
        directory=Path(td)
        def prepare():
            headers=module.materialize(core_root(),directory/'input')
            # Same enumerated host portability seams as the retained parser lab:
            # omit unregistered static handlers, multipart VLA->vector, variadic spelling.
            file=headers/'ESP8266WebServer-impl.h';text=file.read_text()
            marker='template <typename ServerType>\nvoid ESP8266WebServerTemplate<ServerType>::handleClient()'
            file.write_text(text.replace(marker,'#ifdef SHINO_V08_PREPARSE_EXPERIMENT\n#endif\n'+marker))
        prepare()
        with patch.object(inherited,'old_materialize',lambda:None),patch.object(inherited,'materialize',lambda:None),\
             patch.object(inherited,'OLD_OUTPUT',directory/'input/src'),patch.object(inherited,'OUTPUT',directory/'input/src'):
            inherited.generate(directory)
        compiler,env=compiler_environment(directory);exe=directory/'http.exe'
        inc=[directory/'corrected',inherited.LAB/'host_shims',ROOT/'firmware/include']
        sources=[ROOT/'tools/m9_phase_n_http_lab.cpp',directory/'corrected/detail/mimetable.cpp']
        if Path(compiler).name.lower()=='cl.exe':
            cmd=[compiler,'/nologo','/std:c++20','/EHsc','/O2',*[f'/I{x}' for x in inc],*map(str,sources),'/link','ws2_32.lib','bcrypt.lib',f'/OUT:{exe}']
        else:cmd=[compiler,'-std=c++20','-pthread','-O2','-fsanitize=address,undefined',*[f'-I{x}' for x in inc],*map(str,sources),'-lcrypto','-o',str(exe)]
        c=subprocess.run(cmd,cwd=directory,env=env,capture_output=True,text=True,timeout=90)
        if c.returncode:raise RuntimeError(c.stdout+c.stderr)
        c=subprocess.run([str(exe)],cwd=directory,env=env,capture_output=True,text=True,timeout=45)
        if c.returncode:raise RuntimeError(c.stdout+c.stderr)
        result=json.loads(c.stdout)
        result['scope']='StageA pinned parser/Core Digest; host loopback + radio/SDK mocks'
        result['patched_source_sha256']={p.name:hashlib.sha256(p.read_bytes()).hexdigest() for p in (directory/'input/src').glob('*.h')}
        return result
if __name__=='__main__':print(json.dumps(run(),indent=2))
