"""Qualification of isolated ESP8266 Core 3.1.2 256-byte update buffer.

Tests the ACTUAL unchanged native receiver, except for a one-line buffer
selection in a disposable pinned Updater.cpp copy. No device or real network.
"""
import json
from shino_maintenance_native import host_shims
from shino_wifi_runner import build,run,ROOT

def small_builder(directory):
    return build(directory,ROOT/'tools/shino_maintenance_native_lab.cpp',
                 host_shims,small_buffer=True)

if __name__=='__main__':
    r=run(small_builder,native=True)
    assert r['cases']==230 and r['interruption_boundaries']==197
    assert r['actual_core'] and r['actual_python_sender'] and r['network_calls']==0
    for row in r['rows']:
        assert row['fs_preserved'] and row['listeners']==row['queued']==0
        assert row['host_restart_calls']==row['commit']
        assert not row['connected'] and not row['running']
        if row['name'] not in ('valid_real_sender','time_wrap'):
            assert row['commit']==0
    r['core_updater_buffer_bytes']=256
    r['compared_default_core_buffer_bytes']=4096
    r['reduced_heap_buffer_allocation_bytes']=3840
    r['candidate']='ISOLATED_CORE_ONLY'
    r['physical']='NOT_RUN'
    print(json.dumps(r,indent=2))
