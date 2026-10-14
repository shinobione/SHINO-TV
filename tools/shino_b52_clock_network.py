"""Only 127.0.0.1: actual B5.2 parser/Digest/clock, RAM SDK/flash/RTC seams.

No endpoint/host option. All test clock samples and passwords are public fixtures.
No OTA, provisioning or firmware transfer is exercised.
"""
import argparse
import hashlib
import http.client
import json
import os
import shutil
import socket
import struct
import subprocess
import sys
import contextlib
import time
import concurrent.futures
from pathlib import Path
from urllib.error import HTTPError
from urllib.request import Request,build_opener,ProxyHandler,HTTPPasswordMgrWithDefaultRealm
from unittest.mock import patch

import shino_b51_lan_runner as b51
from shino_wifi_runner import build,ROOT
from shino_b52_clock_build import patch_clock,once,NATIVE
from shino_b5_provision import ProvisionDigest
from push_fsless_metrics import NoRedirect
sys.path.insert(0,str(ROOT/"companion"))
import clock_sync as pc_clock
from shino_digest_coord import digest_exchange

FRAME=b"SHINOCLK"+struct.pack("<IhH",1791980760,120,120)

def prepare_host(host,gfx):
    b51.prepare_host(host)
    # Deterministic HOST entropy with unique full-width counter tokens. Hardware
    # RNG remains the pinned ESP.random implementation in the public/native build.
    hardware=host/"Arduino.h"
    hardware.write_text(once(hardware.read_text(),
        'void random(uint8_t* p,size_t n){for(size_t i=0;i<n;++i)p[i]=uint8_t(++lab_random);}',
        'void random(uint8_t* p,size_t n){uint32_t counter=++lab_random;for(size_t i=0;i<n;++i)p[i]=uint8_t((counter>>((i%4)*8))^0x35^i);}'))
    normal=host/"normal_host.inc"
    normal.write_text(patch_clock(normal.read_text(encoding="utf-8")),encoding="utf-8")
    for name in ("B52Clock.h","B52Clock.cpp","B52ClockHttp.inc","ClockFreshness.h"):
        shutil.copyfile(NATIVE/name,host/name)
    # HOST seam: only the compile-inert authority is controllable, never any
    # real SDK/radio/flash. The production source remains volatile const.
    route=host/"B52ClockHttp.inc"
    route_body=once(route.read_text(),"volatile const bool clockPermitted=","volatile bool clockPermitted=")
    route_body=once(route_body,"volatile bool clockPermitted=SHINO_OTA_PRIVATE;",
        "volatile bool clockPermitted=SHINO_OTA_PRIVATE;\ninline bool clockBudgetDrop=false;")
    marker='    if(uint32_t(millis()-server.requestStarted())>=2000||!client.connected()||client.available()){'
    route_body=once(route_body,marker,'    if(clockBudgetDrop)ESP.heap=20479; // HOST fault after body, before crypto\n'+marker)
    route.write_text(route_body)
    for name in ("ClockFoundation.h","SceneEngine.h"):
        shutil.copyfile(ROOT/"firmware/include/display"/name,host/"display"/name)
    (host/"font").mkdir()
    shutil.copyfile(Path(gfx)/"font/glcdfont.h",host/"font/glcdfont.h")
    display=host/"display/DisplayManager.h"
    data=display.read_text()
    data=once(data,"    void setTextColor(uint16_t){}",
        "    void setFont(const void*){}\n"
        "    void draw16bitRGBBitmap(int x,int y,uint16_t*,int w,int h){rect(x,y,w,h);}\n"
        "    void setTextColor(uint16_t){}")
    display.write_text(data)
    composition=host/"network_composition.inc"
    composition.write_text(composition.read_text()+'\n#include "B52Clock.cpp"\n')
    lab=(ROOT/"tools/shino_b51_lan_lab.cpp").read_text()
    lab=once(lab,'#include "shino_http_ota_network_lab.cpp"',
        '#include "'+(ROOT/"tools/shino_http_ota_network_lab.cpp").as_posix()+'"')
    lab=once(lab,'            if(command=="stats"){stats();continue;}',
        '            if(command=="clock public"){M9NormalStageA::clockPermitted=false;std::cout<<"{\\\"ok\\\":true}"<<std::endl;continue;}\n'
        '            if(command=="clock owner"){M9NormalStageA::clockPermitted=true;std::cout<<"{\\\"ok\\\":true}"<<std::endl;continue;}\n'
        '            if(command=="clock reboot"){B52Clock::resetForTest();std::cout<<"{\\\"ok\\\":true}"<<std::endl;continue;}\n'
        '            if(command=="clock tick"){M9NormalStageA::loop();std::cout<<"{\\\"ok\\\":true}"<<std::endl;continue;}\n'
        '            if(command=="clock budget drop"){M9NormalStageA::clockBudgetDrop=true;std::cout<<"{\\\"ok\\\":true}"<<std::endl;continue;}\n'
        '            if(command=="clock budget good"){M9NormalStageA::clockBudgetDrop=false;ESP.heap=50000;std::cout<<"{\\\"ok\\\":true}"<<std::endl;continue;}\n'
        '            if(command=="stats"){stats();continue;}')
    (host.parent/"clock-network.cpp").write_text(lab)
    assert "INADDR_LOOPBACK" in (host/"HostSocket.h").read_text(),"loopback bind required"

def run(output,gfx):
    output=Path(output).resolve()
    if output.exists():raise ValueError("New HOST output directory required")
    output.mkdir(parents=True)
    # Build helper invokes prepare before compiling this generated, HOST-only TU.
    exe,env=build(output,output/"clock-network.cpp",
        lambda h:prepare_host(h,gfx),defines=("ARDUINOJSON_POOL_CAPACITY=8",),threaded=True)
    process=subprocess.Popen([str(exe)],cwd=output,env=env,stdin=subprocess.PIPE,stdout=subprocess.PIPE,stderr=subprocess.PIPE,text=True)
    rows=[]
    def control(command):
        process.stdin.write(command+"\n");process.stdin.flush()
        line=process.stdout.readline()
        if not line:raise RuntimeError(process.stderr.read())
        return json.loads(line)
    try:
        first=process.stdout.readline()
        if not first:raise RuntimeError(process.stderr.read())
        port=int(first);assert 0<port<65536
        base=f"http://127.0.0.1:{port}"
        manager=HTTPPasswordMgrWithDefaultRealm()
        manager.add_password("SHINO-StageA",base,"shino","PUBLIC-INERT-LAB-HTTP-FIXTURE")
        digest=ProvisionDigest(manager,base)
        reader=build_opener(ProxyHandler({}),NoRedirect(),digest)
        authority="192.168.4.1"
        def request(path,body=None,extra=None,auth=True):
            headers={"Host":authority,"Content-Type":"application/octet-stream","Connection":"close"}
            headers.update(extra or {})
            req=Request(base+path,data=body,headers=headers,method="GET" if body is None else "POST")
            selected=reader if auth else build_opener(ProxyHandler({}),NoRedirect())
            try:
                with selected.open(req,timeout=4) as response:return response.status,json.loads(response.read(769))
            except HTTPError as e:
                with e:return e.code,json.loads(e.read(769) or b"{}")
        def check(name,condition):
            if not condition:raise AssertionError(name)
            rows.append(name)
        secret="PUBLIC-INERT-LAB-HTTP-FIXTURE"
        key=pc_clock.derive_key(secret)
        origin=time.monotonic();advance_s=0
        def utc_now():return 1791980760+int(time.monotonic()-origin)+advance_s
        def sample(utc=None):return dict(schema=1,utc_s=utc_now() if utc is None else utc,offset_min=120,lease_s=120)
        def challenge():
            code,state=request("/api/v1/clock/status")
            assert code==200
            pc_clock.challenge_tokens(state)
            return state
        def signed(state,utc=None):return pc_clock.seal(sample(utc),state,key)
        def authorization(raw):
            req=Request(base+"/api/v1/clock/sync",data=raw,method="POST")
            return "Digest "+digest.get_authorization(req,digest.challenge)
        def raw_post(raw,auth):
            connection=http.client.HTTPConnection("127.0.0.1",port,timeout=3)
            try:
                connection.request("POST","/api/v1/clock/sync",raw,headers={"Host":authority,
                    "Authorization":auth,"Content-Length":str(len(raw)),"Content-Type":"application/octet-stream","Connection":"close"})
                response=connection.getresponse();return response.status,json.loads(response.read(769))
            finally:connection.close()
        def expect_rejection(name,raw):
            before=challenge()
            code,_=request("/api/v1/clock/sync",raw)
            after=challenge()
            check(name,code==422 and after["remaining_ms"]<=before["remaining_ms"])
        check("unauthenticated clock GET denied",request("/api/v1/clock/status",auth=False)[0]==401)
        check("unauthenticated clock POST denied",request("/api/v1/clock/sync",FRAME,auth=False)[0]==401)
        initial=challenge()
        check("cold boot is not synchronized",not initial["valid"] and not initial["synced"])
        old=FRAME[:8]+struct.pack("<IhH",1577836800,120,120)
        check("REGRESSION old plausible message at cold boot refused",request("/api/v1/clock/sync",old)[0]==413 and not challenge()["valid"])
        first=challenge();fresh=signed(first);auth=authorization(fresh)
        check("fresh authenticated cryptographic sample accepted",raw_post(fresh,auth)==(200,{"status":"CLOCK_SAMPLE_ACCEPTED","persisted":False}))
        control("advance 60000");advance_s+=60
        code,_=raw_post(fresh,auth)
        after=challenge()
        check("REGRESSION exact body and Digest replay at60s refused without renewal",code==422 and after["valid"] and after["age_ms"]>=60000 and after["remaining_ms"]<=60000)
        control("advance 121000");advance_s+=121
        code,_=raw_post(fresh,auth)
        check("REGRESSION replay after clock expiry cannot restore validity",code==422 and not challenge()["valid"])
        good=challenge();check("fresh reconnect sample accepted",request("/api/v1/clock/sync",signed(good))[0]==200)
        before=challenge();older=signed(before,utc_now()-86400)
        check("REGRESSION new valid authentication and proof cannot rewind one day",request("/api/v1/clock/sync",older)[0]==422)
        after=challenge();check("backward rejection never renews lease",after["remaining_ms"]<=before["remaining_ms"])
        token=challenge();expired=signed(token)
        control("advance 2000");advance_s+=2
        check("challenge expires exactly at2000ms",request("/api/v1/clock/sync",expired)[0]==422)
        left=challenge()
        for name,index in (("UTC body",8),("offset body",12),("lease body",14),("MAC",32)):
            token=challenge();raw=bytearray(signed(token));raw[index]^=1
            before=token
            code,_=request("/api/v1/clock/sync",bytes(raw));after=challenge()
            check(name+" modification refused and lease unchanged",code==422 and after["remaining_ms"]<=before["remaining_ms"])
        token=challenge();wrong=pc_clock.seal(sample(),token,pc_clock.derive_key("PUBLIC-WRONG-CLOCK-FIXTURE"))
        check("wrong proof key refused",request("/api/v1/clock/sync",wrong)[0]==422)
        token=challenge();bad=bytearray(signed(token));bad[-1]^=1
        valid=signed(token)
        check("matching challenge consumed even on bad proof",request("/api/v1/clock/sync",bytes(bad))[0]==422 and request("/api/v1/clock/sync",valid)[0]==422)
        token=challenge();cancelled=signed(token);challenge()
        check("new challenge invalidates previous unused challenge",request("/api/v1/clock/sync",cancelled)[0]==422)
        token=challenge();old_boot=signed(token);control("clock reboot")
        boot_state=challenge()
        check("HOST boot-state reset remains unsynchronized",not boot_state["valid"] and boot_state["boot"]!=token["boot"])
        check("previous boot proof refused",request("/api/v1/clock/sync",old_boot)[0]==422 and not challenge()["valid"])
        control("clock reboot");old_token=challenge();plausible=signed(old_token,1577836800);auth=authorization(plausible)
        control("clock reboot");new_token=challenge()
        check("plausible old v2 message at new unanchored boot refused",raw_post(plausible,auth)[0]==422 and not challenge()["valid"])
        control("clock reboot");full_wrap_token=challenge();full_wrap=signed(full_wrap_token);auth=authorization(full_wrap)
        control("advance 2000");control("clock tick");control("advance 4294965296")
        check("idle challenge expiry latches across complete millis wrap",raw_post(full_wrap,auth)[0]==422 and not challenge()["valid"])
        # This is a trust LIMIT, not a claim to know absolute UTC at cold boot.
        token=challenge();wrong_pc=signed(token,1577836800)
        check("LIMIT fresh paired-PC2020 assertion accepted without absolute UTC anchor",request("/api/v1/clock/sync",wrong_pc)[0]==200)
        control("clock reboot");token=challenge()
        duplicate=signed(token);auth=authorization(duplicate)
        with concurrent.futures.ThreadPoolExecutor(max_workers=2) as pool:
            replies=list(pool.map(lambda _:raw_post(duplicate,auth)[0],range(2)))
        check("simultaneous identical POSTs have at most one clock application",sorted(replies)==[200,422])
        before=challenge();budget_frame=signed(before);control("clock budget drop")
        code,reply=request("/api/v1/clock/sync",budget_frame)
        control("clock budget good");after=challenge()
        check("post-body resource drop503 preserves clock anchor and lease",code==503 and reply.get("error")=="CLOCK_RESOURCE_HOLD" and
            after["valid"] and after["age_ms"]>=before["age_ms"] and after["remaining_ms"]<=before["remaining_ms"])
        token=challenge();raw=signed(token)
        for size in (16,63,65):
            invalid=(raw[:size] if size<64 else raw+b"X")
            check("wrong length refused before body "+str(size),request("/api/v1/clock/sync",invalid)[0]==413)
        check("wrong MIME refused",request("/api/v1/clock/sync",raw,{"Content-Type":"application/json"})[0]==413)
        check("Expect refused",request("/api/v1/clock/sync",raw,{"Expect":"100-continue"})[0]==400)
        check("GET body refused",request("/api/v1/clock/status",None,{"Content-Length":"1"})[0]==400)
        known=challenge();raw=signed(known);auth=authorization(raw)
        connection=http.client.HTTPConnection("127.0.0.1",port,timeout=3)
        connection.putrequest("POST","/api/v1/clock/sync",skip_host=True,skip_accept_encoding=True)
        for k,v in (("Host",authority),("Authorization",auth),("Content-Length","64"),("Content-Type","application/octet-stream"),("Connection","close")):
            connection.putheader(k,v)
        connection.endheaders();connection.send(raw[:8]);connection.sock.shutdown(socket.SHUT_WR)
        try:response=connection.getresponse();response.read()
        except (OSError,http.client.HTTPException):pass
        finally:connection.close()
        check("interrupted frame never renews lease",challenge()["remaining_ms"]<=known["remaining_ms"])
        control("clock public")
        check("public compile authority closed",request("/api/v1/clock/sync",raw)[0]==403)
        public=request("/api/v1/clock/status")[1]
        check("public GET issues no challenge",public["challenge_ms"]==0 and public["challenge"]=="")
        control("clock owner")
        # Real publisher, actual Digest/parser/crypto, no mock network or MAC.
        transport=pc_clock.ClockTransport("192.168.4.1","shino",secret)
        transport.base=base
        manager2=HTTPPasswordMgrWithDefaultRealm();manager2.add_password("SHINO-StageA",base,"shino",secret)
        class LoopbackReader:
            def __init__(self):self.inner=build_opener(ProxyHandler({}),NoRedirect(),pc_clock.ClockHTTPHandler(transport),pc_clock.ClockDigest(manager2,base))
            def open(self,req,timeout):
                assert req.full_url.startswith(base+"/api/v1/clock/")
                req.add_header("Host",authority);return self.inner.open(req,timeout=timeout)
        transport.reader=LoopbackReader()
        def local_lock(host,wait_seconds):return digest_exchange(host,wait_seconds=wait_seconds,directory=output/"locks")
        timings=[];wire=[];original_request=pc_clock.ClockConnection.request
        def counted(self,method,*a,**k):wire.append(method);return original_request(self,method,*a,**k)
        for trial in range(5):
            wire=[];started=time.monotonic()
            with patch.object(pc_clock,"digest_exchange",local_lock),patch.object(pc_clock,"capture_pc_clock",sample),patch.object(pc_clock.ClockConnection,"request",counted):
                result=pc_clock.publish_clock("192.168.4.1",transport,authorize_clock_sync=True)
            elapsed=(time.monotonic()-started)*1000
            check("real publisher exchange "+str(trial),result=="CLOCK_SAMPLE_ACCEPTED" and wire.count("POST")==1 and len(wire)<=3 and elapsed<1000)
            timings.append(dict(total_ms=round(elapsed,3),wire_methods=list(wire)))
        code,known=request("/api/v1/clock/status")
        check("coordinated reader resumes after publisher",code==200 and known["valid"])
        metrics=dict(ok=True,cpu_usage=37.5,gpu_usage=68.0,memory_used_gb=12.4,memory_total_gb=16.0,
            gpu_vram_mb=5000.0,gpu_temp_c=71.2,gpu_power=125.0,gpu_available=True)
        metric_body=json.dumps(metrics,separators=(",",":")).encode()
        check("telemetry Digest admission preserved",request("/api/v1/bridge/metrics",metric_body,{"Content-Type":"application/json"},auth=False)[0]==401)
        # The intentional401 rotates Core's one mutable Digest challenge. Renew
        # with a GET before the distinct authorized operation; never retry POST.
        check("telemetry authenticated preparation refreshes Digest",request("/api/v1/bridge/metrics")[0]==200)
        check("telemetry accepted after clock crypto scratch release",request("/api/v1/bridge/metrics",metric_body,{"Content-Type":"application/json"})[0]==200)
        values=request("/api/v1/bridge/metrics")[1]
        check("four telemetry values and six second TTL unchanged",not values["stale"] and values["ttl_seconds"]==6 and
            all(abs(values[k]-metrics[k])<.01 for k in ("cpu_usage","gpu_usage","memory_used_gb","gpu_temp_c")))
        control("advance 6001");advance_s+=6
        values=request("/api/v1/bridge/metrics")[1]
        check("telemetry expires independently while clock valid",values["stale"] and challenge()["valid"])
        check("telemetry reconnect after expiry accepted",request("/api/v1/bridge/metrics",metric_body,{"Content-Type":"application/json"})[0]==200)
        control("mode lan");authority="192.168.1.82"
        check("authenticated LAN clock path preserved",request("/api/v1/clock/status")[0]==200)
        control("peer foreign")
        check("foreign LAN peer refused",request("/api/v1/clock/status")[0]==403)
        control("mode ap");authority="192.168.4.1"
        stats=control("stats")
        check("no SDK flash or actual restart side effects",stats["sdk_writes"]==stats["flash_writes"]==stats["restarts"]==0)
        report=dict(scope="HOST_LOOPBACK actual parser Digest clock BearSSL; SDK/radio/flash RAM seams",
            cases_passed=len(rows),cases=rows,stats=stats,device_contacts=0,private_inputs=False,physical="NOT_RUN",
            firmware_transfer_tests=0,clock_exchange_timings=timings,pc_exchange_budget_ms=1000,
            challenge_validity_ms=2000,utc_absolute_accuracy="NOT_PROVEN",old_reproductions_now_refused=4)
        (output/"network-report.json").write_text(json.dumps(report,indent=2)+"\n")
        return report
    finally:
        if process.poll() is None:
            try:process.stdin.write("stop\n");process.stdin.flush();process.communicate(timeout=6)
            except Exception:process.kill();process.communicate()

if __name__=="__main__":
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument("--output",type=Path,required=True)
    p.add_argument("--gfx-src",type=Path,required=True)
    a=p.parse_args()
    print(json.dumps(run(a.output,a.gfx_src),indent=2))

