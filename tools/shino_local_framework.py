"""Copy pinned public ESP8266 Core into a disposable, isolated local package.

The user's installed PlatformIO package is NEVER modified. Only local copy
Updater.cpp (256-byte Core buffer path) and Updater.h (noncommitting abort)
differ. PIO must then build from this local package, not original framework.
"""
from pathlib import Path
import hashlib,json,shutil
from v07_pinned_core_probe import core_root
from shino_wifi_core import materialize,ROOT

def prepare(directory):
    directory=Path(directory).resolve()
    original=Path(core_root()).resolve()
    assert original.is_dir() and (original/'package.json').is_file()
    pins=json.loads((ROOT/'tools/m9_signed_core_sources.json').read_text())
    for name in ('Updater.cpp','Updater.h','Updater_Signing.h'):
        source=original/'cores/esp8266'/name
        assert hashlib.sha256(source.read_bytes()).hexdigest()==pins['cores/esp8266/'+name]
    dest=directory/'isolated-shino-framework'
    assert not dest.exists(), 'Require a fresh disposable public build; never reuse patched package'
    shutil.copytree(original,dest,ignore=shutil.ignore_patterns('__pycache__','*.pyc'))
    generated=materialize(directory/'isolated-updater-source',original,small_buffer=True)
    for name in ('Updater.cpp','Updater.h'):
        shutil.copyfile(generated/name,dest/'cores/esp8266'/name)
    assert dest.joinpath('package.json').is_file()
    cpp=(dest/'cores/esp8266/Updater.cpp').read_text()
    assert cpp.count('if (false) { // SHINO public low-memory 256-byte updater qualification')==1
    assert 'void shinoAbort()' in (dest/'cores/esp8266/Updater.h').read_text()
    (directory/'isolated-framework-proof.json').write_text(json.dumps({
        'source_package_version':json.loads((original/'package.json').read_text()).get('version'),
        'source_updater_sha256':pins['cores/esp8266/Updater.cpp'],
        'isolated_core_updater_sha256':hashlib.sha256((dest/'cores/esp8266/Updater.cpp').read_bytes()).hexdigest(),
        'local_override_only':True,'global_core_modified':False
    },indent=2))
    return dest

if __name__=='__main__':
    import sys
    print(prepare(Path(sys.argv[1])))
