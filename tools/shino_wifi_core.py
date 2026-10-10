"""Exact isolated Core header adaptation, never patches an installed Core."""
import hashlib,json
from pathlib import Path
from v07_pinned_core_probe import core_root
ROOT=Path(__file__).resolve().parents[1]
ABORT='    void shinoAbort() { _error = UPDATE_ERROR_STREAM; _reset(false); }\n'
def materialize(directory,core=None,small_buffer=False):
    core=Path(core or core_root());directory=Path(directory);directory.mkdir(parents=True,exist_ok=True)
    pins=json.loads((ROOT/'tools/m9_signed_core_sources.json').read_text())
    for name in ('Updater.cpp','Updater.h','Updater_Signing.h'):
        source=(core/'cores/esp8266'/name).read_text(encoding='utf-8')
        assert hashlib.sha256(source.encode()).hexdigest()==pins['cores/esp8266/'+name]
        if name=='Updater.h':
            assert source.count('  private:')==1
            source=source.replace('  private:',ABORT+'\n  private:')
        if name=='Updater.cpp' and small_buffer:
            # Arduino Core 3.1.2 already has a 256 B low-memory buffer path;
            # force it in this disposable Core copy only. Never patch SDK cache.
            original='if (ESP.getFreeHeap() > 2 * FLASH_SECTOR_SIZE) {'
            assert source.count(original)==1
            source=source.replace(original,'if (false) { // SHINO public low-memory 256-byte updater qualification')
        (directory/name).write_text(source,encoding='utf-8',newline='\n')
    return directory
