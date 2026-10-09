"""Paired public Xtensa graph and 256-byte Updater memory scenario.

This is NOT a physical heap/stack high-water certification or flash authority.
"""
import argparse,json
from pathlib import Path
from shino_maintenance_resources import run as measure

def run(base,candidate):
    r=measure(base,candidate)
    assert r['callable_native']=='PASS_OFFLINE'
    assert not r['activation'] and not r['trusted_consent_bound']
    assert r['floors']==dict(heap=20480,largest=16384,stack=2048,fragmentation=25)
    size=256;old=4096
    # Owner baseline minima, static delta, normal known HTTP freed, illustrative
    # NOT measured 4096 B lwIP/TCP scenario. Runtime admission still monitored.
    owner=r['observed_owner']['heap'];delta=r['delta']['static_ram']
    tcp=r['illustrative_tcp_reserve'];http=r['normal_known_dynamic_payload_total']
    pre_tcp=owner-delta+http
    pre_update=pre_tcp-tcp
    post_buffer=pre_update-size
    r['small_core_buffer_bytes']=size
    r['default_core_buffer_bytes']=old
    r['buffer_reduction_bytes']=old-size
    r['core_begin_admission_heap']=20480+size+1024
    r['maintenance_entry_admission_heap']=25600
    r['scenario_pre_tcp_heap']=pre_tcp
    r['scenario_pre_update_heap']=pre_update
    r['scenario_post_256_buffer_heap']=post_buffer
    r['scenario_post_buffer_margin_above_floor']=post_buffer-20480
    r['scenario_is_not_native_high_water']=True
    r['observed_sdk_socket_allocator_peak']='NOT_MEASURED'
    r['physical_probe']='PENDING_USER_AUTHORIZATION_AND_CANDIDATE_REVIEW'
    r['verdict']='HOLD_FOR_NATIVE_OBSERVATION'
    return r

if __name__=='__main__':
    p=argparse.ArgumentParser()
    p.add_argument('base',type=Path);p.add_argument('candidate',type=Path)
    a=p.parse_args()
    print(json.dumps(run(a.base,a.candidate),indent=2))
