"""Exact public transition ELF/BIN comparison; NOT a physical OTA clearance.

Compares two disposable 4m2m StageA builds using the same isolated 256-byte
Core. The comparison gives real linked/static deltas, not a simultaneous native
heap/stack high-water bound. Public fixture INSTALL remains forbidden.
"""
import argparse
import json
from pathlib import Path
from shino_wifi_resources import one

FLOORS=dict(heap=20480,largest=16384,stack=2048,fragmentation=25)

def run(baseline, candidate):
    baseline=Path(baseline)
    candidate=Path(candidate)
    b=one(baseline)
    c=one(candidate)
    assert b['inputs']['firmware_LF_sha256']==c['inputs']['firmware_LF_sha256']
    assert b['identity_sha256']==c['identity_sha256']
    assert b['dependencies']==c['dependencies']
    assert b['noinit']==c['noinit']==56
    assert b['inputs']['maintenance_callable'] and not b['inputs']['trusted_consent_bound']
    assert c['inputs']['maintenance_callable'] and c['inputs']['experimental_auth_arm']
    assert c['inputs']['public_inert_hmac_credential_only']
    assert c['inputs']['public_install_denied'] and c['inputs']['not_flashable_or_owner_qualified']
    ini=(candidate/'platformio.ini').read_text()
    assert '-DSHINO_PUBLIC_INERT_REVIEW=1' in ini
    # Both paired builds must really use the exact same isolated Core sources,
    # not the shared/global Arduino cache or a theoretical 256-byte estimate.
    for name in ('Updater.cpp','Updater.h'):
        a=(baseline/'isolated-shino-framework/cores/esp8266'/name).read_bytes()
        d=(candidate/'isolated-shino-framework/cores/esp8266'/name).read_bytes()
        assert a==d
        assert d==(candidate/'.pio/isolated-packages/framework-arduinoespressif8266/cores/esp8266'/name).read_bytes()
    delta={name:c[name]-b[name] for name in ('bin_bytes','linked_flash','static_ram','noinit')}
    return dict(
        verdict='NO_GO_FOR_PHYSICAL_INSTALL',
        scope='DISPOSABLE_PUBLIC_TEST_GRAPH_ONLY',
        baseline={k:b[k] for k in ('bin_bytes','linked_flash','static_ram','noinit')},
        candidate={k:c[k] for k in ('bin_bytes','linked_flash','static_ram','noinit')},
        delta=delta,buffer_bytes=256,
        public_install_enabled=False,ram_only_probe_compiled=True,
        floors=FLOORS,physical_memory_high_water='NOT_MEASURED',
        sdk_tcp_allocator_stack_upper_bound='NOT_ESTABLISHED',
        qualified_live=False,physical_flash_authorized=False,
        device_contacts=0,serial_io=0,flash_writes=0,rtc_writes=0,
        device_filesystem_writes=0,reboots=0,
    )

if __name__=='__main__':
    parser=argparse.ArgumentParser()
    parser.add_argument('baseline',type=Path)
    parser.add_argument('candidate',type=Path)
    args=parser.parse_args()
    print(json.dumps(run(args.baseline,args.candidate),indent=2))
