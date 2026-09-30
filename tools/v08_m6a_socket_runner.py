"""Compose pinned WebServer and unchanged bridge with real PC loopback sockets.

Generated files live only in TemporaryDirectory. No installed Core writes.
Host portability changes are enumerated; owner/parser/dispatch/auth/response
function bodies are retained apart from the multipart VLA storage seam.
"""
from pathlib import Path
import hashlib
import json
import os
import shutil
import subprocess
import tempfile
from v07_cpp_lab_runner import compiler_environment
from v07_pinned_core_probe import core_root, pinned_sources, _between
from v08_native_overlay import materialize as old_materialize, OUTPUT as OLD_OUTPUT
from v08_m6a_overlay import materialize, OUTPUT

ROOT = Path(__file__).resolve().parents[1]
LAB = ROOT / 'experiments/v08_socket_dispatch'
EXTRA_PINNED = {
    'Uri.h': '8b9197eb9010bb7405cfa57f78bc7b86cb9b96f621879f1d636c7b0ef859b786',
    'detail/RequestHandler.h': 'fe83e7572b02f14bdb3ab7e052c3072d15bcdcdb5c0758a918faeb3a9407a4ab',
    'detail/RequestHandlersImpl.h': 'e539e1ccc58d3a745475cbe04164009e332842708386beb963063db01aebe358',
    'detail/mimetable.h': 'ef452d4f1e34bd0442353ff3350a1f98a3d71a1ee92b2f25046119b05f0b416f',
    'detail/mimetable.cpp': '0ced8b156f62102a451be2d435b26fb98c2161d006f57eb922f60f1a475b03e6',
}

def generate(directory):
    pinned = pinned_sources()
    old_materialize()
    materialize()
    core = core_root() / 'libraries/ESP8266WebServer/src'
    hashes = {}
    for name in ('ESP8266WebServer.h','ESP8266WebServer-impl.h','Parsing-impl.h',
                 *EXTRA_PINNED):
        data = (core / name).read_bytes()
        hashes[name] = hashlib.sha256(data).hexdigest()
        if name in EXTRA_PINNED and hashes[name] != EXTRA_PINNED[name]:
            raise ValueError(f'WRONG_M5_PINNED_SOURCE: {name}')
    for name in ('stock','previous','corrected'):
        target = directory / name
        (target / 'detail').mkdir(parents=True)
        src = core if name == 'stock' else OLD_OUTPUT if name == 'previous' else OUTPUT
        header = (src / 'ESP8266WebServer.h').read_text(encoding='utf-8')
        # MSVC portability only: variadic macro spelling.
        header = header.replace('#define DBGWS(x...)', '#define DBGWS(...)')
        (target / 'ESP8266WebServer.h').write_text(header, encoding='utf-8')
        impl = (src / 'ESP8266WebServer-impl.h').read_text(encoding='utf-8')
        # Exclude unregistered filesystem static routes; keep every other function.
        start = impl.index('template <typename ServerType>\nvoid ESP8266WebServerTemplate<ServerType>::serveStatic')
        end = impl.index('#ifdef SHINO_V08_PREPARSE_EXPERIMENT', start) if name != 'stock' else impl.index('template <typename ServerType>\nvoid ESP8266WebServerTemplate<ServerType>::handleClient()', start)
        impl = impl[:start] + impl[end:]
        impl = '\n'.join(line for line in impl.splitlines() if not line.startswith('#include'))
        impl = '#include <HostSocket.h>\n#include "detail/RequestHandlersImpl.h"\n' + impl
        (target / 'ESP8266WebServer-impl.h').write_text(impl,encoding='utf-8')
        parser = (src / 'Parsing-impl.h').read_text(encoding='utf-8')
        parser = parser.replace('char fastBoundary[ fastBoundaryLen ];','std::vector<char> boundaryStorage(fastBoundaryLen);\n            char* fastBoundary = boundaryStorage.data();')
        parser = '\n'.join(line for line in parser.splitlines() if '"WiFiServer.h"' not in line and '"WiFiClient.h"' not in line)
        (target / 'Parsing-impl.h').write_text(parser,encoding='utf-8')
        for path in ('Uri.h','detail/RequestHandler.h','detail/mimetable.h','detail/mimetable.cpp'):
            shutil.copyfile(core / path,target / path)
        handlers = (core / 'detail/RequestHandlersImpl.h').read_text(encoding='utf-8')
        function = _between(handlers,'template<typename ServerType>\nclass FunctionRequestHandler', 'template<typename ServerType>\nclass StaticRequestHandler')
        (target / 'detail/RequestHandlersImpl.h').write_text('#pragma once\n#include "RequestHandler.h"\nnamespace esp8266webserver {\n'+function+'\n}',encoding='utf-8')
        stream = _between(pinned['stream'],'String Stream::readStringUntil(char terminator) {','// read what can be read')
        (target / 'pinned_stream.inc').write_text(stream,encoding='utf-8')
    return {'core':hashes,'generated':{str(p.relative_to(directory)):hashlib.sha256(p.read_bytes()).hexdigest() for p in sorted(directory.rglob('*')) if p.is_file()}}

def run():
    arduinojson = Path(os.environ.get('SHINO_ARDUINOJSON_SRC',str(ROOT / 'experiments/v08_full_bridge/.pio/libdeps/bridge_baseline/ArduinoJson/src'))).resolve()
    if '#define ARDUINOJSON_VERSION "7.4.3"' not in (arduinojson/'ArduinoJson/version.hpp').read_text(encoding='utf-8'):
        raise ValueError('real ArduinoJson 7.4.3 required')
    with tempfile.TemporaryDirectory(prefix='v08-m6a-sockets-') as td:
        directory=Path(td);hashes=generate(directory)
        compiler,env=compiler_environment(directory)
        results=[]
        for variant,conditional in [('stock',0),('previous',0),('corrected',0),('corrected',1)]:
            output=directory/f'{variant}-{conditional}.exe'
            includes=[directory/variant,LAB/'host_shims',ROOT/'experiments/v08_full_bridge/host_shims',ROOT/'firmware/include',arduinojson]
            sources=[ROOT/'tools/v08_m6a_socket_lab.cpp',ROOT/'firmware/src/boot/FslessMetrics.cpp',ROOT/'firmware/src/boot/FslessWebUI.cpp',directory/variant/'detail/mimetable.cpp']
            defines=[f'SHINO_ENABLE_FACTORY_RESTORE={conditional}',f'LAB_OVERLAY={int(variant!="stock")}']
            defines += [f'LAB_CORRECTED={int(variant=="corrected")}']
            if variant!='stock':defines+=['SHINO_V08_PREPARSE_EXPERIMENT=1']
            if Path(compiler).name.lower()=='cl.exe':
                command=[compiler,'/nologo','/std:c++20','/EHsc','/utf-8',*[f'/D{x}' for x in defines],*[f'/I{x}' for x in includes],*map(str,sources),'/link','ws2_32.lib','bcrypt.lib',f'/OUT:{output}']
            else:
                command=[compiler,'-std=c++20','-pthread',*[f'-D{x}' for x in defines],*[f'-I{x}' for x in includes],*map(str,sources),'-lcrypto','-o',str(output)]
            compiled=subprocess.run(command,cwd=directory,env=env,capture_output=True,text=True,timeout=90)
            if compiled.returncode:raise RuntimeError('\n'.join(line for line in (compiled.stdout+compiled.stderr).splitlines() if 'error' in line)[:10000])
            executed=subprocess.run([str(output)],env=env,capture_output=True,text=True,timeout=90)
            if executed.returncode:raise RuntimeError(executed.stdout+executed.stderr)
            results.append({'variant':variant,'conditional_oem':conditional,'compiler':Path(compiler).name,'result':json.loads(executed.stdout)})
        inputs=[ROOT/'tools/v08_m6a_socket_runner.py',ROOT/'tools/v08_m6a_overlay.py',ROOT/'tools/v08_m6a_socket_lab.cpp',ROOT/'tools/v08_native_overlay.py',
                ROOT/'firmware/src/boot/FirstBootBridge.cpp',ROOT/'firmware/src/boot/FslessMetrics.cpp',ROOT/'firmware/src/boot/FslessWebUI.cpp',
                *sorted((LAB/'host_shims').rglob('*.h'))]
        head=subprocess.run(['git','rev-parse','HEAD'],cwd=ROOT,capture_output=True,text=True,check=True).stdout.strip()
        dirty=subprocess.run(['git','status','--porcelain'],cwd=ROOT,capture_output=True,text=True,check=True).stdout.strip()
        return {'source_head':head,'working_tree_dirty':bool(dirty),'core_version':'3.30102.0','source_hashes':hashes,
                'composition_input_hashes':{str(p.relative_to(ROOT)):hashlib.sha256(p.read_bytes()).hexdigest() for p in inputs},'runs':results}

if __name__=='__main__':
    print(json.dumps(run(),indent=2))
