"""Execute pinned StageA parser/Digest over host loopback, never owner network."""
from pathlib import Path
import hashlib, importlib.util, json, shutil, subprocess, tempfile
import base64
from urllib.request import build_opener, ProxyHandler, HTTPPasswordMgrWithDefaultRealm, HTTPDigestAuthHandler, Request
from urllib.error import HTTPError
from unittest.mock import patch
import v08_m6a_socket_runner as inherited
from v07_pinned_core_probe import core_root
from v08_m8r_runner import compiler_environment
ROOT=Path(__file__).resolve().parent.parent

def urllib_workload(exe,directory,env,actual=False):
    import sys
    sys.path.insert(0,str(ROOT/'companion'))
    from push_fsless_metrics import TelemetryDigestAuthHandler, NoRedirect, read_credentials
    fixture=directory/'public-inert-credentials.txt'
    fixture.write_text('Rescue HTTP Digest user: shino\nRescue HTTP Digest password: PUBLIC-INERT-LAB-HTTP-FIXTURE\n',encoding='utf-8')
    user,password=read_credentials(fixture)
    with (directory/'trace.txt').open('w+',encoding='utf-8') as trace:
        p=subprocess.Popen([str(exe),'--serve'],cwd=directory,env=env,stdin=subprocess.PIPE,stdout=subprocess.PIPE,stderr=trace,text=True)
        try:
            port=int(p.stdout.readline());base=f'http://127.0.0.1:{port}'
            def opener(path,cached=False):
                store=HTTPPasswordMgrWithDefaultRealm()
                store.add_password('SHINO-StageA',base+path,user,password)
                handler=TelemetryDigestAuthHandler(store,base+path) if cached else HTTPDigestAuthHandler(store)
                return build_opener(ProxyHandler({}),NoRedirect(),handler)
            def exchange(client,path,body=None):
                headers={'Accept':'application/json','Cache-Control':'no-store'}
                if body is not None:headers['Content-Type']='application/json'
                req=Request(base+path,data=body,method='POST' if body is not None else 'GET',headers=headers)
                with client.open(req,timeout=4) as response:
                    assert response.status==200
                    data=json.loads(response.read())
                    if actual:
                        assert data.get('status')=='RAM_SAMPLE_ACCEPTED' if body is not None else data.get('mode')=='M9_NORMAL_STAGE_A'
                    else:assert data=={}
                return response.status
            def advance(ms):
                p.stdin.write(str(ms)+'\n');p.stdin.flush()
                return json.loads(p.stdout.readline())
            codes=[exchange(opener(path),path) for path in ('/status','/api/v1/m9/normal/status')]
            stale_recovery=[]
            final_gets=[]
            path='/api/v1/bridge/metrics'
            for cached in (False,True):
                client=opener(path,cached)
                sample=b'{"ok":true,"gpu_available":true,"cpu_usage":22.5,"gpu_usage":34.5,"memory_used_gb":8,"memory_total_gb":16,"gpu_vram_mb":2048,"gpu_temp_c":56,"gpu_power":120}' if actual else b'x'*32
                for _ in range(100):
                    codes.append(exchange(client,path,sample))
                    if actual:assert advance(2000)=={'stale':False,'received':True}
                if actual:
                    state=advance(6001);assert state=={'stale':True,'received':True}
                    stale_recovery.append(state)
                    codes.append(exchange(client,path,sample))
                    state=advance(0);assert state=={'stale':False,'received':True}
                    stale_recovery.append(state)
                for final in ('/status','/api/v1/m9/normal/status','/api/v1/m9/normal/resources'):
                    for final_cached in (False,True):
                        code=exchange(opener(final,final_cached),final);codes.append(code)
                        final_gets.append(dict(path=final,client='Phase_P_cached' if final_cached else 'stock_urllib',code=code))
            negatives={}
            if actual:
                for path in ('/missing','/api/reboot','/config.json'):
                    try:exchange(opener(path),path)
                    except HTTPError as error:
                        assert error.code==404;negatives[path]=error.code;error.close()
                    else:raise AssertionError('unknown route accepted')
                basic=base64.b64encode((user+':'+password).encode()).decode()
                req=Request(base+'/status',headers={'Authorization':'Basic '+basic,'Connection':'close'})
                try:build_opener(ProxyHandler({}),NoRedirect()).open(req,timeout=4)
                except HTTPError as error:assert error.code==401;negatives['Basic']=error.code;error.close()
                else:raise AssertionError('Basic accepted')
                path='/api/v1/bridge/metrics'
                for name,body,code in [('oversized',b'x'*385,413),('invalid_json',b'x'*32,422)]:
                    try:exchange(opener(path),path,body)
                    except HTTPError as error:assert error.code==code;negatives[name]=error.code;error.close()
                    else:raise AssertionError('invalid POST accepted')
                codes.append(exchange(opener('/status'),'/status'))
            p.stdin.write('stop\n');p.stdin.flush()
            tail=p.communicate(timeout=5)[0];assert p.returncode==0
            counts=json.loads(tail)
            assert counts==({'posts':203,'gets':15,'not_found':0,'policy404':3} if actual else {'posts':200,'gets':14,'not_found':0,'policy404':0}),counts
            trace.flush();trace.seek(0);state_trace=trace.read()
            if actual:
                lines=state_trace.splitlines()
                get_handlers=[s for s in lines if 'phase=handler ' in s and 'method=1 ' in s]
                assert len(get_handlers)==15 and all('handler=1 ' in s and 'args=0 ' in s and 'plain_nonempty=0 ' in s for s in get_handlers)
                assert any('phase=prebody ' in s and 'method=1 ' in s and 'plain_nonempty=1 ' in s for s in lines)
                assert sum('policy=404 ' in s for s in lines)==3
                assert not any('phase=fallback ' in s for s in lines)
            return dict(accepted_post_count=202 if actual else 200,successful_http_codes={'200':len(codes)},handler_counts=counts,
                        stock_and_phase_p_cached_digest=True,stale_recovery=stale_recovery,negative_codes=negatives,
                        final_gets=final_gets,fixture_trace=state_trace.splitlines())
        finally:
            if p.poll() is None:p.kill();p.communicate()

def replay_generated_maintenance_routes(exe,directory,env):
    """Exercise generated maintenance GET allowlist after live mock POST traffic.

    Real pinned HTTP parser, Digest and normal StageA controller; maintenance
    handlers are status-only host stubs, never a real PROBE/INSTALL action.
    """
    import sys
    from urllib.request import build_opener, ProxyHandler, HTTPPasswordMgrWithDefaultRealm
    from urllib.request import HTTPDigestAuthHandler, Request
    sys.path.insert(0,str(ROOT/'companion'))
    from push_fsless_metrics import NoRedirect
    sample=b'{"ok":true,"gpu_available":true,"cpu_usage":22.5,"gpu_usage":34.5,"memory_used_gb":8,"memory_total_gb":16,"gpu_vram_mb":2048,"gpu_temp_c":56,"gpu_power":120}'
    with (directory/'m9-generated-route-trace.txt').open('w+',encoding='utf-8') as trace:
        proc=subprocess.Popen([str(exe),'--serve'],cwd=directory,env=env,stdin=subprocess.PIPE,
                              stdout=subprocess.PIPE,stderr=trace,text=True)
        try:
            port=int(proc.stdout.readline())
            base=f'http://127.0.0.1:{port}'
            paths=('/api/v1/m9/normal/status',
                   '/api/v1/m9/maintenance/result',
                   '/api/v1/m9/maintenance/challenge',
                   '/api/v1/m9/maintenance/probe',
                   '/api/v1/m9/maintenance/install')
            def send(path,body=None):
                mgr=HTTPPasswordMgrWithDefaultRealm()
                mgr.add_password('SHINO-StageA',base+path,'shino','PUBLIC-INERT-LAB-HTTP-FIXTURE')
                op=build_opener(ProxyHandler({}),NoRedirect(),HTTPDigestAuthHandler(mgr))
                headers={'Accept':'application/json','Connection':'close'}
                if body is not None:headers['Content-Type']='application/json'
                req=Request(base+path,headers=headers,method='POST' if body is not None else 'GET',data=body)
                with op.open(req,timeout=5) as response:
                    if response.status!=200:raise RuntimeError('StageA generated route not accepted')
                    data=json.loads(response.read())
                    if body is not None:
                        if data.get('status')!='RAM_SAMPLE_ACCEPTED':raise RuntimeError('RAM-only telemetry missing')
                    elif data.get('mode')!='M9_NORMAL_STAGE_A':
                        raise RuntimeError('Generated route handler missing')
            n=0
            for i in range(12):
                send('/api/v1/bridge/metrics',sample);n+=1
                for path in paths:
                    send(path);n+=1
            proc.stdin.write('stop\\n');proc.stdin.flush()
            tail=proc.communicate(timeout=8)[0]
            if proc.returncode!=0:raise RuntimeError('Host route work failed')
            counts=json.loads(tail)
            if counts['policy404']!=0 or counts['not_found']!=0:
                raise RuntimeError('Generated route after POST unexpectedly rejected')
            return {'pass':True,'authenticated_post_get_cycles':12,'accepted':n,
                    'maintenance_endpoints':len(paths)-1,'actual_parser_and_stagea':True,
                    'maintenance_handlers':'READ_ONLY_HOST_STUBS',
                    'radio_sdk_ota':'NOT_TESTED','device_contacts':0,'device_writes':0}
        finally:
            if proc.poll() is None:proc.kill();proc.communicate()


def run(maintenance=False):
    spec=importlib.util.spec_from_file_location('m9_normal_webserver',ROOT/'firmware/scripts/m9_normal_webserver.py')
    module=importlib.util.module_from_spec(spec);spec.loader.exec_module(module)
    with tempfile.TemporaryDirectory(prefix='m9-stagea-http-') as td:
        directory=Path(td)
        def prepare():
            headers=module.materialize(core_root(),directory/'input')
            # Same enumerated host portability seams as the retained parser lab:
            # omit unregistered static handlers, multipart VLA->vector, variadic spelling.
            file=headers/'ESP8266WebServer-impl.h';text=file.read_text()
            marker='template <typename ServerType>\nvoid ESP8266WebServerTemplate<ServerType>::handleClient()'
            file.write_text(text.replace(marker,'#ifdef SHINO_V08_PREPARSE_EXPERIMENT\n#endif\n'+marker))
        prepare()
        with patch.object(inherited,'old_materialize',lambda:None),patch.object(inherited,'materialize',lambda:None),\
             patch.object(inherited,'OLD_OUTPUT',directory/'input/src'),patch.object(inherited,'OUTPUT',directory/'input/src'):
            inherited.generate(directory)
        compiler,env=compiler_environment(directory);exe=directory/'http.exe'
        inc=[directory/'corrected',inherited.LAB/'host_shims',ROOT/'firmware/include']
        sources=[ROOT/'tools/m9_phase_n_http_lab.cpp',directory/'corrected/detail/mimetable.cpp']
        if Path(compiler).name.lower()=='cl.exe':
            cmd=[compiler,'/nologo','/std:c++20','/EHsc','/O2',*[f'/I{x}' for x in inc],*map(str,sources),'/link','ws2_32.lib','bcrypt.lib',f'/OUT:{exe}']
        else:cmd=[compiler,'-std=c++20','-pthread','-O2','-fsanitize=address,undefined',*[f'-I{x}' for x in inc],*map(str,sources),'-lcrypto','-o',str(exe)]
        c=subprocess.run(cmd,cwd=directory,env=env,capture_output=True,text=True,timeout=90)
        if c.returncode:raise RuntimeError(str(c.returncode)+'\n'+c.stdout+c.stderr)
        try:
            c=subprocess.run([str(exe)],cwd=directory,env=env,capture_output=True,text=True,timeout=120)
        except subprocess.TimeoutExpired as e:
            raw=e.stderr or ''
            raise RuntimeError('Host lab timeout\n'+(raw.decode('utf-8',errors='replace') if isinstance(raw,bytes) else raw)) from e
        if c.returncode:raise RuntimeError(str(c.returncode)+'\n'+c.stdout+c.stderr)
        result=json.loads(c.stdout)
        result['urllib_workload']=urllib_workload(exe,directory,env)
        # Compose the unchanged actual StageA controller, status serializer,
        # telemetry and dashboard with the same real parser/Digest. Only
        # hardware, FS/config and network-mode dependencies are inert fixtures.
        from test_m9_phase_n_routes import STUBS
        shims=directory/'stage-shims';shims.mkdir()
        arduino=(inherited.LAB/'host_shims/Arduino.h').read_text()
        arduino=arduino.replace('lab_real_clock?uint32_t(', 'lab_real_clock?host_ms+uint32_t(')
        arduino=arduino.replace(' void wdtFeed(){feeds++;}', ' void resetFreeContStack(){} uint32_t getFreeContStack(){return 4000;}\n void getHeapStats(uint32_t* f,uint32_t* b,uint8_t* p){*f=32000;*b=30000;*p=2;}\n void wdtFeed(){feeds++;}')
        (shims/'Arduino.h').write_text(arduino+'\nstruct EspClass{static void wdtFeed(){ESP.wdtFeed();}};\n')
        for name in ('shino_private_policy.h','config/ConfigManager.h','display/DisplayManager.h'):
            target=shims/name;target.parent.mkdir(parents=True,exist_ok=True)
            body=STUBS[name]
            if name=='shino_private_policy.h':body=body.replace('SHINO_RESCUE_HTTP_USER \"lab\"','SHINO_RESCUE_HTTP_USER \"shino\"')
            if name=='display/DisplayManager.h':body=body.replace('drawTextWrapped(int,int,const char*','drawTextWrapped(int,int,const __FlashStringHelper*')
            target.write_text(body)
        target=shims/'wireless/WiFiManager.h';target.parent.mkdir(parents=True)
        target.write_text('#pragma once\nclass WiFiManager{public:WiFiManager(const char*,const char*,const char*,const char*){} bool startAccessPointMode(){return !WiFi.persisted;}};\n')
        target=shims/'web/Webserver.h';target.parent.mkdir(parents=True)
        target.write_text('#pragma once\nclass Webserver{ObservedServer server{80};public:ObservedServer& raw(){return server;} void begin(){server.begin();} void handleClient(){server.handleClient();}\n void on(const char* p,HTTPMethod m,std::function<void()> f){server.on(p,m,f);} void onNotFound(std::function<void()> f){server.onNotFound(f);}};\n')
        composition='''#include "boot/M9LittleFsMountProbe.h"
namespace M9LittleFsMountProbe{LittleFsMountProbeStatus state;
void begin(){state.attempted=state.autoformat_disabled=state.mounted=state.inventory_exact=state.config_seed_exact=true;state.checked_file_count=24;state.checked_payload_bytes=181402;}
const LittleFsMountProbeStatus& status(){return state;}}
'''
        for name in ('M9NormalStageA.cpp','M9NormalDashboard.cpp','FslessMetrics.cpp'):
            composition+=f'#include "{(ROOT/"firmware/src/boot"/name).as_posix()}"\n'
        (directory/'stage_composition.inc').write_text(composition)
        if maintenance:
            from shino_maintenance_http import prepare_host
            sources=prepare_host(directory,shims,composition,sources)
        import os
        aj=Path(os.environ.get('SHINO_ARDUINOJSON_SRC',str(ROOT/'firmware/.pio/libdeps/esp12e/ArduinoJson/src'))).resolve()
        assert '#define ARDUINOJSON_VERSION "7.4.3"' in (aj/'ArduinoJson/version.hpp').read_text()
        actual=directory/'stage.exe'
        if Path(compiler).name.lower()=='cl.exe':
            cmd=[compiler,'/nologo','/std:c++20','/EHsc','/O2','/DM9_ACTUAL_STAGE_A=1',f'/I{directory}',f'/I{shims}',f'/I{aj}',*[f'/I{x}' for x in inc],*map(str,sources),'/link','ws2_32.lib','bcrypt.lib',f'/OUT:{actual}']
        else:cmd=[compiler,'-std=c++20','-pthread','-O2','-fsanitize=address,undefined','-DM9_ACTUAL_STAGE_A=1',f'-I{directory}',f'-I{shims}',f'-I{aj}',*[f'-I{x}' for x in inc],*map(str,sources),'-lcrypto','-o',str(actual)]
        c=subprocess.run(cmd,cwd=directory,env=env,capture_output=True,text=True,timeout=90)
        if c.returncode:raise RuntimeError(c.stdout+c.stderr)
        result['actual_stage_a_workload']=urllib_workload(actual,directory,env,actual=True)
        if maintenance:
            result['generated_private_http_route_replay']=replay_generated_maintenance_routes(actual,directory,env)
            c=subprocess.run([str(actual),'--maintenance'],cwd=directory,env=env,capture_output=True,text=True,timeout=90)
            if c.returncode:raise RuntimeError(c.stdout+c.stderr)
            result['maintenance_lifecycle']=json.loads(c.stdout)
        result['scope']='StageA pinned parser/Core Digest + actual controller/status/telemetry/dashboard; host loopback + radio/FS/SDK mocks'
        result['owner_residual_404']='NOT_REPRODUCED_ROOT_CAUSE_UNRESOLVED'
        result['firmware_changed']=False
        result['normal_runtime_gate']='HOLD/PARTIAL'
        result['patched_source_sha256']={p.name:hashlib.sha256(p.read_bytes()).hexdigest() for p in (directory/'input/src').glob('*.h')}
        return result
if __name__=='__main__':print(json.dumps(run(),indent=2))
