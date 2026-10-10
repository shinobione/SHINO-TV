"""Phase T source-executed one-listener wire integration, RAM sink only."""
import hashlib,importlib.util,json,socket,subprocess,tempfile,time
from pathlib import Path
from unittest.mock import patch
from urllib.request import Request,build_opener,ProxyHandler,HTTPPasswordMgrWithDefaultRealm,HTTPDigestAuthHandler
import m9_phase_n_http_runner as inherited
ROOT=Path(__file__).resolve().parents[1]
SAMPLE=b'{"ok":true,"gpu_available":true,"cpu_usage":22.5,"gpu_usage":34.5,"memory_used_gb":8,"memory_total_gb":16,"gpu_vram_mb":2048,"gpu_temp_c":56,"gpu_power":120}'
TOKEN='abcdefabcdefabcdefabcdefabcdefab'
ARM='/api/v1/bridge/ota/arm';UPLOAD='/api/v1/bridge/ota/upload'

def headers(arm=True,**changes):
    path=ARM if arm else UPLOAD;nonce='23456789abcdef0123456789abcdef01' if arm else '3456789abcdef0123456789abcdef012'
    ha1=hashlib.sha256(b'shino:SHINO-OTA:PUBLIC-INERT').hexdigest()
    ha2=hashlib.sha256(('POST:'+path).encode()).hexdigest()
    proof=hashlib.sha256(f'{ha1}:{nonce}:00000001:inertcnonce:auth:{ha2}'.encode()).hexdigest()
    auth=f'Digest username="shino", realm="SHINO-OTA", nonce="{nonce}", opaque="cdef0123456789abcdef0123456789ab", uri="{path}", algorithm=SHA-256, qop=auth, nc=00000001, cnonce="inertcnonce", response="{proof}"'
    fields={'Host':'192.168.4.1','Origin':'http://192.168.4.1','Content-Type':'application/json' if arm else 'application/octet-stream',
            'Content-Length':'16' if arm else '100260','Authorization':auth,'Connection':'close'}
    if not arm:fields['X-Shino-Intent']=TOKEN
    fields.update(changes)
    return (f'POST {path} HTTP/1.1\r\n'+''.join(f'{k}: {v}\r\n' for k,v in fields.items())+'\r\n').encode()

def workload(exe,directory,env,actual=False):
    if not actual:return ORIGINAL_WORKLOAD(exe,directory,env,False)
    import sys;sys.path.insert(0,str(ROOT/'companion'))
    from push_fsless_metrics import TelemetryDigestAuthHandler,NoRedirect
    package=(ROOT/'experiments/m9_signed_ota/fixtures/signed.inert').read_bytes()
    assert hashlib.sha256(package).hexdigest()=='fba6f824ac53cdc12ac6cbbd55ca983802b1c65764c68180d6a6f0d81986738e'
    results=[];latencies=[]
    def one(name,attack=None,arm=True,case='good',action=None):
        with (directory/(name+'.trace')).open('w',encoding='utf-8') as trace:
            child=subprocess.Popen([str(exe),'--serve',case],cwd=directory,env=env,stdin=subprocess.PIPE,stdout=subprocess.PIPE,stderr=trace,text=True)
            active=None
            try:
                port=int(child.stdout.readline());base=f'http://127.0.0.1:{port}'
                def client(route,cached=True):
                    store=HTTPPasswordMgrWithDefaultRealm();store.add_password('SHINO-StageA',base+route,'shino','PUBLIC-INERT-LAB-HTTP-FIXTURE')
                    return build_opener(ProxyHandler({}),NoRedirect(),TelemetryDigestAuthHandler(store,base+route) if cached else HTTPDigestAuthHandler(store))
                clients={p:client(p) for p in ('/status','/api/v1/m9/normal/status','/api/v1/m9/normal/resources','/api/v1/bridge/metrics')}
                normal_gets=links=0
                def normal(post=False,route='/status'):
                    nonlocal normal_gets,links
                    route='/api/v1/bridge/metrics' if post else route
                    before=time.monotonic()
                    with clients[route].open(Request(base+route,data=SAMPLE if post else None,headers={'Content-Type':'application/json','Cache-Control':'no-store'}),timeout=4) as response:
                        assert response.status==200;data=json.loads(response.read())
                    latencies.append((time.monotonic()-before)*1000)
                    if post:assert data['status']=='RAM_SAMPLE_ACCEPTED';links+=1
                    elif route!='/api/v1/bridge/metrics':assert data['mode']=='M9_NORMAL_STAGE_A';normal_gets+=1
                    else:
                        assert (data['cpu_usage'],data['gpu_usage'],data['memory_used_gb'],data['gpu_temp_c'])==(22.5,34.5,8,56);normal_gets+=1
                    return data
                def connect(data):
                    sock=socket.create_connection(('127.0.0.1',port),timeout=4);sock.sendall(data);return sock
                def receive(sock):
                    out=b''
                    try:
                        while True:
                            b=sock.recv(4096)
                            if not b:break
                            out+=b
                    except (ConnectionResetError,BrokenPipeError):pass
                    return out
                def advance(ms):child.stdin.write(str(ms)+'\n');child.stdin.flush();json.loads(child.stdout.readline())
                def armed():
                    sock=connect(headers()+b'{"confirm":true}');response=receive(sock);sock.close();assert response.startswith(b'HTTP/1.1 200'),response
                normal(True);normal();normal(route='/api/v1/m9/normal/resources')
                if name in ('good','wrap'):
                    armed();normal(True);normal(route='/api/v1/m9/normal/status')
                    active=connect(headers(False))
                    for i,at in enumerate(range(0,len(package),512)):
                        active.sendall(package[at:at+512])
                        normal(route='/api/v1/m9/normal/resources');normal(route='/api/v1/bridge/metrics')
                        if i%4==0:normal(True)
                        if name=='wrap' and i==2:advance(5000) # uint32 rollover, below TTL/deadline.
                    assert receive(active).startswith(b'HTTP/1.1 200');active.close();active=None
                    replay=connect(headers(False));assert not receive(replay).startswith(b'HTTP/1.1 200');replay.close()
                    advance(6001);assert normal(route='/api/v1/bridge/metrics')['stale'] is True
                    normal(True);assert normal(route='/api/v1/bridge/metrics')['stale'] is False
                    normal(True)
                    for route in ('/status','/api/v1/m9/normal/status','/api/v1/m9/normal/resources'):normal(route=route)
                else:
                    if not arm:armed()
                    data=attack if attack is not None else headers(arm)
                    active=connect(data)
                    if action=='headers_slow':normal(True);normal();advance(2001)
                    elif action in ('timeout','disconnect'):
                        time.sleep(.04);normal(True);normal()
                        if action=='timeout':advance(60001)
                        else:active.shutdown(socket.SHUT_WR)
                    elif action=='busy':
                        time.sleep(.04);normal(True);normal()
                        duplicate=connect(headers(False));assert not receive(duplicate).startswith(b'HTTP/1.1 200');duplicate.close()
                    elif action=='requestline':
                        time.sleep(.04)
                        slow=connect(b'GET /status HTTP/1.1\r')
                        normal(True);normal();assert not receive(slow);slow.close();advance(60001)
                    elif action=='stream':
                        # Complete body supplied separately; fixed public fixture.
                        active.sendall(package)
                    response=receive(active);active.close();active=None
                    assert not response.startswith(b'HTTP/1.1 200'),(name,response)
                    normal(True);normal()
                child.stdin.write('stop\n');child.stdin.flush();lines=child.communicate(timeout=6)[0].splitlines()
                assert child.returncode==0,(name,child.returncode)
                counts,ota=map(json.loads,lines)
                assert counts['not_found']==0 and counts['policy404']==0,(name,counts)
                assert ota['watchdog_feeds']>=ota['pump_calls'] and ota['max_stream_step']<=512,ota
                if name in ('good','wrap'):
                    assert ota['commits']==1 and ota['begins']==1 and ota['received']==100260 and ota['phase']==4,ota
                    assert links==53 and normal_gets==400,(links,normal_gets)
                else:
                    assert ota['commits']==0 and ota['poisoned'],(name,ota)
                    if arm:assert ota['begins']==ota['writes']==0,(name,ota)
                    elif name in ('token','upload_length','arm_replay'):assert ota['begins']==0,(name,ota)
                results.append(dict(name=name,ota=ota,normal_gets=normal_gets,links=links,no_unexpected_404=True))
            except Exception as error:
                trace.flush()
                raise RuntimeError(name+': '+str(error)+'\n'+(directory/(name+'.trace')).read_text()[-5000:]) from error
            finally:
                if active is not None:active.close()
                if child.poll() is None:child.kill();child.communicate()
    one('good');one('wrap',case='wrap')
    for name,changes in [('host',{'Host':'evil'}),('origin',{'Origin':'http://evil'}),('Basic',{'Authorization':'Basic aW5lcnQ='}),
        ('cookie_only',{'Authorization':'','Cookie':'read-session'}),('TE',{'Transfer-Encoding':'chunked'}),('Expect',{'Expect':'100-continue'}),
        ('bad_length',{'Content-Length':'016'}),('oversized',{'Content-Length':'1002610'}),('digest_target',{'Authorization':headers(False).decode().split('Authorization: ')[1].split('\r\n')[0]})]:
        one(name,headers(**changes))
    for name,data in [('duplicate',headers().replace(b'Host:',b'Host: 192.168.4.1\r\nHost:',1)),
        ('version',headers().replace(b'HTTP/1.1',b'HTTP/1.01',1)),('method',headers().replace(b'POST ',b'PUT ',1)),
        ('route',headers().replace(ARM.encode(),b'/api/v1/bridge/ota/wrong')),
        ('header_bound',headers().replace(b'Connection:',b'X-Large: '+b'x'*2048+b'\r\nConnection:')),
        ('nonce_replay',headers().replace(b'nc=00000001',b'nc=00000002')),
        ('bad_consent_body',headers()+b'{"confirm":nope}')]:one(name,data)
    for case in ('peer','interface','consent','budget'):one(case,headers()+b'{"confirm":true}',case=case)
    one('headers_slow',headers()[:80],action='headers_slow')
    one('missing_body',headers(),action='timeout')
    one('arm_replay',headers()+b'{"confirm":true}',False)
    for name,data,action,case in [('token',headers(False,**{'X-Shino-Intent':'1'*32}),None,'good'),
        ('upload_length',headers(False,**{'Content-Length':'100259'}),None,'good'),
        ('disconnect',headers(False)+package[:512],'disconnect','good'),('total_deadline',headers(False)+package[:512],'timeout','good'),
        ('timeout_wrap',headers(False)+package[:512],'timeout','wrap'),
        ('busy_upload',headers(False)+package[:512],'busy','good'),
        ('requestline_starvation',headers(False)+package[:512],'requestline','good'),
        ('allocator',headers(False),None,'allocator'),('write_failure',headers(False),'stream','write'),
        ('staging_corrupt',headers(False),'stream','corrupt'),
        ('raw_changed',headers(False)+package[:1000]+bytes([package[1000]^1])+package[1001:],None,'good'),
        ('trailer_changed',headers(False)+package[:-4]+b'\x01\x01\x00\x00',None,'good'),
        ('overflow',headers(False)+package+b'x',None,'good')]:one(name,data,False,case,action)
    assert max(latencies)<3000, max(latencies) # Declared HOST bound, not RF/flash timing.
    return dict(PHASE_T_SINGLE_OWNER_HTTP='PASS_OFFLINE',wire_cases=results,max_normal_response_ms=max(latencies),
        response_bound_ms=3000,one_listener=True,header_chunk_union=True,chunk_max=512,
        cooperative_pump=True,real_stagea_handlers=True,native_crypto_timing=False,
        device_contacts=0,serial_io=0,flash_writes=0,rtc_writes=0,reboots=0,device_filesystem_writes=0)

ORIGINAL_WORKLOAD=inherited.urllib_workload

def run():
    original_run=subprocess.run;original_spec=importlib.util.spec_from_file_location
    with tempfile.TemporaryDirectory(prefix='m9-t-wire-') as td:
        directory=Path(td);source=(ROOT/'tools/m9_phase_n_http_lab.cpp').read_text()
        source=source.replace('static std::string transact',f'#ifdef M9_ACTUAL_STAGE_A\n#include "{(ROOT/"experiments/m9_stagea_ota/host/Wire.h").as_posix()}"\n#endif\nstatic std::string transact',1)
        source=source.replace('int main(int argc,char**)','int main(int argc,char** argv)',1)
        source=source.replace('M9NormalStageA::afterSetup();','M9NormalStageA::afterSetup();Wire::start(server,argc>2?argv[2]:"good");',1)
        source=source.replace('   M9NormalStageA::loop();','   M9NormalStageA::loop();Wire::pump();',1)
        source=source.replace('  return 0;\n }','\n#ifdef M9_ACTUAL_STAGE_A\n  Wire::report();\n#endif\n  return 0;\n }',1)
        candidate=directory/'wire.cpp';candidate.write_text(source)
        def compile_hook(cmd,*args,**kwargs):
            if isinstance(cmd,list) and str(ROOT/'tools/m9_phase_n_http_lab.cpp') in map(str,cmd):
                cmd=[str(candidate) if str(x)==str(ROOT/'tools/m9_phase_n_http_lab.cpp') else x for x in cmd]
                include=ROOT/'experiments/m9_stagea_ota/include';signed=ROOT/'experiments/m9_signed_ota/include'
                cmd[1:1]=[('/I' if Path(cmd[0]).name.lower()=='cl.exe' else '-I')+str(p) for p in (include,signed)]
            return original_run(cmd,*args,**kwargs)
        def spec_hook(name,location,*args,**kwargs):
            if name=='m9_normal_webserver':location=ROOT/'tools/m9_stagea_webserver.py'
            return original_spec(name,location,*args,**kwargs)
        with patch.object(subprocess,'run',compile_hook),patch.object(importlib.util,'spec_from_file_location',spec_hook),patch.object(inherited,'urllib_workload',workload):result=inherited.run()
        result['urllib_workload'].pop('fixture_trace',None)
        return result

if __name__=='__main__':print(json.dumps(run(),indent=2))
