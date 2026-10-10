"""Interleave an unwired RAM transfer with real StageA GET/telemetry handlers.

Only a temporary host lab is augmented; retained Phase N/Q source is unchanged.
There is one existing loopback listener and no OTA network route. This is a
scheduler/state model, not native flash/crypto timing or device concurrency.
"""
import json
from pathlib import Path
import subprocess
import tempfile
from unittest.mock import patch
from urllib.request import Request, build_opener, ProxyHandler, HTTPPasswordMgrWithDefaultRealm
import m9_phase_n_http_runner as inherited
from m9_signed_fixture_image import inert_image
ROOT=Path(__file__).resolve().parent.parent


def run():
    original_run=subprocess.run
    original_workload=inherited.urllib_workload
    with tempfile.TemporaryDirectory(prefix="m9-signed-mixed-public-") as td:
        p=Path(td);fixture=p/"model.inert"
        # Inert signature bytes are deliberate: this adapter models state only.
        fixture.write_bytes(inert_image()+bytes(256)+b"\x00\x01\x00\x00")
        body=(ROOT/"tools/m9_phase_n_http_lab.cpp").read_text()
        marker="static std::string transact"
        include=f'#ifdef M9_ACTUAL_STAGE_A\n#include "{(ROOT/"experiments/m9_signed_ota/host/M9SignedMixed.h").as_posix()}"\n#endif\n'
        body=body.replace(marker,include+marker,1)
        body=body.replace("M9NormalStageA::afterSetup();",f'M9NormalStageA::afterSetup();Mixed::start("{fixture.as_posix()}");',1)
        body=body.replace('if(tick>=0){\n#ifdef M9_ACTUAL_STAGE_A','if(tick>=0){\n#ifdef M9_ACTUAL_STAGE_A\n    Mixed::step();',1)
        body=body.replace('  return 0;\n }','\n#ifdef M9_ACTUAL_STAGE_A\n  Mixed::report();\n#endif\n  return 0;\n }',1)
        candidate=p/"paired.cpp";candidate.write_text(body)
        def compiler_hook(command,*args,**kwargs):
            if isinstance(command,list):
                command=[str(candidate) if str(x)==str(ROOT/"tools/m9_phase_n_http_lab.cpp") else x for x in command]
            return original_run(command,*args,**kwargs)
        def workload(exe,directory,env,actual=False):
            if not actual:return original_workload(exe,directory,env,actual=False)
            from sys import path
            path.insert(0,str(ROOT/"companion"))
            from push_fsless_metrics import TelemetryDigestAuthHandler,NoRedirect
            trace=(directory/"mixed-trace.txt").open("w",encoding="utf-8")
            child=subprocess.Popen([str(exe),'--serve'],cwd=directory,env=env,stdin=subprocess.PIPE,stdout=subprocess.PIPE,stderr=trace,text=True)
            try:
                base=f'http://127.0.0.1:{int(child.stdout.readline())}'
                def client(route):
                    store=HTTPPasswordMgrWithDefaultRealm();store.add_password('SHINO-StageA',base+route,'shino','PUBLIC-INERT-LAB-HTTP-FIXTURE')
                    return build_opener(ProxyHandler({}),NoRedirect(),TelemetryDigestAuthHandler(store,base+route))
                clients={route:client(route) for route in ('/status','/api/v1/bridge/metrics')}
                def exchange(route,data=None):
                    headers={'Accept':'application/json','Cache-Control':'no-store'}
                    if data is not None:headers['Content-Type']='application/json'
                    with clients[route].open(Request(base+route,data=data,headers=headers),timeout=4) as response:
                        assert response.status==200
                        return json.loads(response.read())
                sample=b'{"ok":true,"gpu_available":true,"cpu_usage":22.5,"gpu_usage":34.5,"memory_used_gb":8,"memory_total_gb":16,"gpu_vram_mb":2048,"gpu_temp_c":56,"gpu_power":120}'
                for index in range(196):
                    if index%4==0:assert exchange('/api/v1/bridge/metrics',sample)['status']=='RAM_SAMPLE_ACCEPTED'
                    status=exchange('/status');assert status['mode']=='M9_NORMAL_STAGE_A' and status['native_ota_writer_enabled'] is False
                    metrics=exchange('/api/v1/bridge/metrics');assert metrics['stale'] is False
                    assert (metrics['cpu_usage'],metrics['gpu_usage'],metrics['memory_used_gb'],metrics['gpu_temp_c'])==(22.5,34.5,8,56)
                    child.stdin.write('100\n');child.stdin.flush()
                    assert json.loads(child.stdout.readline())=={'stale':False,'received':True}
                child.stdin.write('stop\n');child.stdin.flush()
                lines=child.communicate(timeout=5)[0].splitlines();assert child.returncode==0
                counts,model=map(json.loads,lines)
                assert model['scheduled_model'] and model['model_chunks']==196 and model['stream_gets']>=392 and model['stream_posts']==49,model
                assert counts['posts']==49 and counts['gets']==392 and counts['policy404']==0 and counts['not_found']==0,counts
                return dict(accepted_post_count=49,normal_gets=392,four_metric_samples=49,
                            model=model,virtual_upload_ms=19600,actual_stagea_handlers=True,
                            source_unchanged=True,native_crypto_timing=False,production_concurrency='HOLD',device_contacts=0)
            finally:
                if child.poll() is None:child.kill();child.communicate()
                trace.close()
        with patch.object(subprocess,"run",compiler_hook),patch.object(inherited,"urllib_workload",workload):
            result=inherited.run()
        # Retain counts and scope, omit potentially noisy public fixture traces.
        result['urllib_workload'].pop('fixture_trace',None)
        return result


if __name__=="__main__":print(json.dumps(run(),indent=2))
