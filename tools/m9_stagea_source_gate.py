"""Phase T public source closure, retaining all previous frozen source gates."""
import hashlib,json,subprocess
from pathlib import Path
from m9_signed_ota_runner import source_gate as signed_gate
from v07_pinned_core_probe import core_root
ROOT=Path(__file__).resolve().parents[1]

def run():
    previous=signed_gate();core=core_root()
    pins=json.loads((ROOT/'tools/m9_stagea_core_sources.json').read_text())
    for name,digest in pins.items():
        assert hashlib.sha256((core/name).read_bytes().replace(b'\r\n',b'\n')).hexdigest()==digest,name
    for name in subprocess.check_output(['git','ls-files','firmware','companion','tools/m9_single_attempt*'],cwd=ROOT,text=True).splitlines():
        # Explicit new issue43 installer files; old transport identities stay pinned.
        if name in ('companion/shino_install.py','companion/test_shino_install.py','companion/SHINO-INSTALL.cmd','companion/SHINO_INSTALL.md','companion/SHINO-OFFLINE-CHECK.cmd'):
            continue
        original=subprocess.check_output(['git','show','b59964af43b555b75d415e6d063580945e6d99f7:'+name],cwd=ROOT)
        assert (ROOT/name).read_bytes().replace(b'\r\n',b'\n')==original.replace(b'\r\n',b'\n'),name
    stage=(ROOT/'firmware/src/boot/M9NormalStageA.cpp').read_text()
    assert 'M9StageAHttp' not in stage and 'setStageARawHook' not in stage
    graph=(ROOT/'experiments/m9_stagea_ota/include/M9StageALink.inc').read_text()
    assert 'retainedStageAProof' in graph and 'retainedStageAPump' in graph
    for bad in ('end(true)','ESP.restart','ESP.reset(','Update.','installSignature(nullptr','private.key','PUBLIC-INERT','BEGIN PRIVATE'):
        assert bad not in graph,bad
    files=[*sorted((ROOT/'experiments/m9_stagea_ota').rglob('*')),*sorted((ROOT/'tools').glob('m9_stagea*'))]
    return dict(PHASE_T_SOURCE='PASS_OFFLINE',previous=previous,additional_core_LF_pins=len(pins),
        deployed_source_identity='b59964af43b555b75d415e6d063580945e6d99f7',default_stagea_ota=False,
        composition_LF_sha256={str(p.relative_to(ROOT)):hashlib.sha256(p.read_bytes().replace(b'\r\n',b'\n')).hexdigest() for p in files if p.is_file()},
        device_contacts=0,serial_io=0,flash_writes=0,rtc_writes=0,reboots=0,device_filesystem_writes=0)

if __name__=='__main__':print(json.dumps(run(),indent=2))
