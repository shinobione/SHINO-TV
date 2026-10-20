"""Build one real windowed Windows EXE from a strict source/data allowlist.

python tools/build_link_windows.py --output <isolated new folder>
Install companion/requirements-windows-build.txt in an isolated venv first.
No private config, credentials, firmware, inspector, updater or HMAC lab data.
"""
import argparse
import hashlib
import importlib.metadata
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys

ROOT = Path(__file__).resolve().parents[1]
SOURCES = ('shino_link_windows.pyw','link_windows.py','link_windows_smoke.py',
           'shino_link.py','link_mode_tray.py','link_display_modes.py',
           'metrics_server.py','push_fsless_metrics.py','shino_digest_coord.py',
           'clock_sync.py','link_clock.py','provision_home_wifi.py')


def main():
    parser=argparse.ArgumentParser(__doc__)
    parser.add_argument('--output', required=True, type=Path)
    args=parser.parse_args()
    if sys.platform != 'win32': parser.error('Build requires Windows')
    output=args.output.resolve()
    output.mkdir(parents=True, exist_ok=False)
    stage=output/'build-source'
    stage.mkdir()
    sources={}
    for name in SOURCES:
        source=ROOT/'companion'/name
        shutil.copyfile(source, stage/name)
        sources[name]=hashlib.sha256(source.read_bytes()).hexdigest()
    # Generate the same existing LINK tray motif; no external image dependency.
    sys.path.insert(0,str(stage))
    from link_windows import tray_picture
    tray_picture('CONNECTED').save(stage/'link_windows.ico', sizes=[(16,16),(32,32),(48,48),(64,64)])
    command=[sys.executable,'-m','PyInstaller','--noconfirm','--clean','--onefile',
             '--windowed','--noupx','--name','SHINO-LINK','--paths',str(stage),
             '--icon',str(stage/'link_windows.ico'),
             '--add-data',str(stage/'link_windows.ico')+os.pathsep+'.',
             '--hidden-import','pystray._win32','--hidden-import','link_windows_smoke',
             '--exclude-module','link_firmware_identity','--exclude-module','tkinter',
             '--distpath',str(output),'--workpath',str(output/'build'),
             '--specpath',str(output/'build'),str(stage/'shino_link_windows.pyw')]
    with (output/'BUILD.log').open('w',encoding='utf-8') as log:
        subprocess.run(command, cwd=stage, stdout=log, stderr=subprocess.STDOUT, check=True)
    exe=output/'SHINO-LINK.exe'
    packages={d.metadata['Name']:d.version for d in importlib.metadata.distributions()}
    manifest=dict(version='1.0.0',platform=sys.platform,python=sys.version,
                  executable=exe.name,bytes=exe.stat().st_size,
                  sha256=hashlib.sha256(exe.read_bytes()).hexdigest(),
                  sources=sources,dependencies=packages,
                  device_contact='NOT_RUN',owner_desktop_smoke='NOT_RUN')
    (output/'BUILD-MANIFEST.json').write_text(json.dumps(manifest,indent=2),encoding='utf-8')
    print(json.dumps({k:manifest[k] for k in ('executable','bytes','sha256')}))


if __name__=='__main__': main()
