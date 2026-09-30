"""Fresh isolated native link/static section comparison, never runtime RAM."""
import hashlib
import json
import os
from pathlib import Path
import subprocess

import v08_native_size_report as size
from v07_pinned_core_probe import pinned_sources

ROOT = Path(__file__).resolve().parents[1]


def run():
    pinned_sources()
    size.ROOT = ROOT/'experiments/v08_m6a/.pio/build'
    nm = size.TOOL.with_name('xtensa-lx106-elf-nm' + ('.exe' if os.name=='nt' else ''))
    rows = {}
    for name in ('baseline_compile','previous_compile','corrected_compile'):
        row = size.one(name)
        elf = size.ROOT/name/'firmware.elf'
        symbols = subprocess.check_output([str(nm),'-S',str(elf)],text=True)
        owner = [line.split() for line in symbols.splitlines() if line.endswith(' _ZL9labServer')]
        if len(owner)!=1: raise ValueError('one labServer required')
        row['server_object'] = int(owner[0][1],16)
        row['elf_sha256'] = hashlib.sha256(elf.read_bytes()).hexdigest()
        rows[name] = row
    keys = ('text','data','bss','bin','server_object')
    return {'source_head':subprocess.check_output(['git','rev-parse','HEAD'],cwd=ROOT,text=True).strip(),
            'working_tree_dirty':bool(subprocess.check_output(['git','status','--porcelain'],cwd=ROOT,text=True).strip()),
            'builds':rows,
            'corrected_minus_stock':{k:rows['corrected_compile'][k]-rows['baseline_compile'][k] for k in keys},
            'corrected_minus_previous':{k:rows['corrected_compile'][k]-rows['previous_compile'][k] for k in keys}}


if __name__=='__main__': print(json.dumps(run(),indent=2))
