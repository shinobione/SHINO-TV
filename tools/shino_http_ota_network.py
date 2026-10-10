"""Actual complete normal HTTP OTA graph on loopback, RAM flash/RTC only."""
import hashlib
import http.client
import json
import queue
import shutil
import socket
import subprocess
import sys
import tempfile
import threading
from pathlib import Path
from unittest.mock import patch
from urllib.request import Request,build_opener,ProxyHandler,HTTPPasswordMgrWithDefaultRealm,HTTPDigestAuthHandler
from urllib.error import HTTPError
from shino_http_ota_build import materialize_http
from shino_wifi_runner import build,ROOT
from v07_pinned_core_probe import core_root
import v08_m6a_socket_runner as inherited
from test_m9_phase_n_routes import STUBS
from test_shino_http_ota import fixture
sys.path.insert(0,str(ROOT/"companion"))
from shino_update import signature
from push_fsless_metrics import NoRedirect

PASSWORD="PUBLIC-INERT-HTTP-OTA-TEST-PASSWORD"

def prepare_host(host):
    directory=host.parent;headers=materialize_http(core_root(),directory/"http-input")
    file=headers/"ESP8266WebServer-impl.h";body=file.read_text()
    marker='template <typename ServerType>\nvoid ESP8266WebServerTemplate<ServerType>::handleClient()'
    file.write_text(body.replace(marker,'#ifdef SHINO_V08_PREPARSE_EXPERIMENT\n#endif\n'+marker))
    with patch.object(inherited,"old_materialize",lambda:None),patch.object(inherited,"materialize",lambda:None),patch.object(inherited,"OLD_OUTPUT",headers),patch.object(inherited,"OUTPUT",headers):inherited.generate(directory)
    shutil.copytree(directory/"corrected",host,dirs_exist_ok=True)
    for shim in (inherited.LAB/"host_shims").glob("*.h"):
        if shim.name not in ("Arduino.h","HostSocket.h","ESP8266WiFi.h","MD5Builder.h"):shutil.copyfile(shim,host/shim.name)
    (host/"pgmspace.h").write_text('#pragma once\n#ifdef __cplusplus\n#include <Arduino.h>\n#endif\n#include <string.h>\n#ifndef PROGMEM\n#define PROGMEM\n#endif\n#define memcpy_P memcpy\n#define pgm_read_byte(p) (*(const unsigned char*)(p))\n#define pgm_read_word(p) (*(const unsigned short*)(p))\n#define pgm_read_dword(p) (*(const unsigned int*)(p))\n')
    arduino=(inherited.LAB/"host_shims/Arduino.h").read_text()
    native=(ROOT/"experiments/m9_signed_ota/host/Arduino.h").read_text()
    start=native.index("enum FlashMode_t");end=native.index("extern HostESP ESP;")
    hardware=native[start:end].replace("HostESP","EspFixture")
    hardware=hardware.replace("bool failWrite=false", "uint32_t restarts=0;void restart(){++restarts;}\n    bool failWrite=false")
    hardware=hardware.replace("bool checkFlashConfig", "void random(uint8_t* p,size_t n){for(size_t i=0;i<n;++i)p[i]=uint8_t(++lab_random);}\n    void resetFreeContStack(){}uint32_t getFreeContStack(){return 3248;}\n    void getHeapStats(uint32_t* h,uint32_t* b,uint8_t* f){*h=heap;*b=50000;*f=1;}\n    void wdtFeed(){}bool checkFlashConfig")
    arduino=arduino[:arduino.index("struct EspFixture {")]+hardware+"\ninline EspFixture ESP;\n"
    arduino+='\n#define LOW 0\n#define OUTPUT 1\ninline uint32_t os_random(){return ++lab_random;}\ninline void delay(int n){std::this_thread::sleep_for(std::chrono::milliseconds(n));}\ninline void pinMode(int,int){}inline void digitalWrite(int,int){}\nstruct Print{template<class... A>void printf_P(const char*,A...) {}};\n'
    arduino+='\n#ifdef _MSC_VER\n#define strcasecmp _stricmp\n#endif\n'
    arduino=arduino.replace("#include <chrono>","#include <chrono>\n#include <thread>")
    arduino=arduino.replace('lab_real_clock?uint32_t(', 'lab_real_clock?host_ms+uint32_t(')
    (host/"Arduino.h").write_text(arduino)
    socket=(inherited.LAB/"host_shims/HostSocket.h").read_text()
    socket=socket.replace('#include <openssl/evp.h>','#include <bearssl.h>')
    socket=socket.replace('#include <unistd.h>','#include <unistd.h>\n#include <fcntl.h>')
    # ESP WiFiServer.accept() is nonblocking. POSIX select may report a pending
    # connection that is aborted before accept; a blocking shim can stall forever.
    socket=socket.replace('trackSocket();sockaddr_in a{};',
                          'trackSocket();\n#ifndef _WIN32\nfcntl(listener,F_SETFL,fcntl(listener,F_GETFL,0)|O_NONBLOCK);\n#endif\nsockaddr_in a{};')
    socket=socket.replace('if(s!=INVALID_SOCKET){pending.emplace_back(s);accepted++;}',
                          'if(s!=INVALID_SOCKET){\n#ifndef _WIN32\nfcntl(s,F_SETFL,fcntl(s,F_GETFL,0)|O_NONBLOCK);\n#endif\npending.emplace_back(s);accepted++;}')
    socket=socket.replace('unsigned len=0;EVP_Digest(input.data(),input.size(),digest,&len,EVP_md5(),nullptr);',
                          'br_md5_context md5;br_md5_init(&md5);br_md5_update(&md5,input.data(),input.size());br_md5_out(&md5,digest);')
    socket=socket.replace('inline std::atomic<size_t> allocs',
                          'inline std::atomic<int> last_fd{-1},last_ioctl{-9},last_available{-9},last_select{-9},last_peek{-9};\ninline std::atomic<size_t> allocs')
    socket=socket.replace('int n=0;ioctl(ctx->fd,FIONREAD,&n);','int n=0;last_fd=ctx->fd;last_ioctl=ioctl(ctx->fd,FIONREAD,&n);last_available=n;')
    socket=socket.replace('return select(int(ctx->fd)+1,&f,nullptr,nullptr,&t)>0;',
                          'last_select=select(int(ctx->fd)+1,&f,nullptr,nullptr,&t);return last_select>0;')
    socket=socket.replace('return recv(ctx->fd,&c,1,MSG_PEEK)>0;',
                          'last_peek=recv(ctx->fd,&c,1,MSG_PEEK);return last_peek>0;')
    socket=socket.replace('struct IPAddress {uint32_t value=1;','struct IPAddress {uint32_t value=1;IPAddress()=default;IPAddress(int,int,int,int){}uint8_t operator[](size_t i)const{return i==0?192:i==1?168:i==2?4:2;}bool operator==(const IPAddress& p)const{return value==p.value;}')
    socket=socket.replace('void setTimeout(int ms)', 'int read(uint8_t* out,size_t n){if(!readable())return 0;return recv(ctx->fd,reinterpret_cast<char*>(out),int(n),0);}\n void setNoDelay(bool){} void flush(int){} IPAddress localIP(){return {};}\n void setTimeout(int ms)')
    socket=socket.replace('virtual ~Stream()=default;','virtual ~Stream()=default;int peek(){return 0;}size_t readBytes(uint8_t*,size_t){return 0;}')
    socket=socket.replace('String toString(){return result;}','String toString()const{return result;}')
    socket=socket.replace('public:\n void begin(){input.clear();result.clear();}', 'public:\n void add(uint8_t* p,size_t n){input.append(reinterpret_cast<char*>(p),n);}\n void getBytes(uint8_t* p){for(unsigned i=0;i<16;++i)p[i]=uint8_t(std::stoul(result.substr(2*i,2),nullptr,16));}\n void begin(){input.clear();result.clear();}')
    (host/"HostSocket.h").write_text(socket)
    (host/"MD5Builder.h").write_text('#pragma once\n#include <HostSocket.h>\n')
    (host/"ESP8266WiFi.h").write_text('#pragma once\n#include <HostSocket.h>\nenum{WIFI_AP,WIFI_OFF};struct WiFiFixture{bool persisted=true;void persistent(bool b){persisted=b;}int getMode(){return WIFI_AP;}IPAddress softAPIP(){return {};}};inline WiFiFixture WiFi;\n')
    for name in ("shino_private_policy.h","config/ConfigManager.h","display/DisplayManager.h"):
        target=host/name;target.parent.mkdir(parents=True,exist_ok=True);body=STUBS[name]
        if name=="shino_private_policy.h":body=body.replace('SHINO_RESCUE_HTTP_USER "lab"','SHINO_RESCUE_HTTP_USER "shino"')
        target.write_text(body)
    target=host/"wireless/WiFiManager.h";target.parent.mkdir(parents=True,exist_ok=True)
    target.write_text('#pragma once\nclass WiFiManager{public:WiFiManager(const char*,const char*,const char*,const char*){}bool startAccessPointMode(){return !WiFi.persisted;}};\n')
    shutil.copytree(ROOT/"firmware/include/boot",host/"boot",dirs_exist_ok=True)
    key=hashlib.sha256(PASSWORD.encode()).digest()
    (host/"ShinoRelease.h").write_text('#pragma once\n#define SHINO_OTA_PRIVATE 1\n#define SHINO_OTA_DEVICE "0123456789abcdef"\n#define SHINO_OTA_BUILD "'+'a'*64+'"\nstatic constexpr uint8_t ShinoReleaseKey[32]={'+','.join(str(x) for x in key)+'};\n')
    shutil.copyfile(ROOT/"ota/firmware/ShinoHttpOta.h",host/"ShinoHttpOta.h")
    aj=ROOT/"firmware/.pio/libdeps/esp12e/ArduinoJson/src"
    if not aj.is_dir():
        import os
        aj=Path(os.environ["SHINO_ARDUINOJSON_SRC"])
    shutil.copytree(aj,host,dirs_exist_ok=True)
    (host/"network_composition.inc").write_text(''.join(f'#include "{(ROOT/p).as_posix()}"\n' for p in ("ota/firmware/Normal.cpp","firmware/src/boot/M9NormalDashboard.cpp","firmware/src/boot/FslessMetrics.cpp")))


def run():
    with tempfile.TemporaryDirectory(prefix="shino-http-network-") as td:
        directory=Path(td);exe,env=build(directory,ROOT/"tools/shino_http_ota_network_lab.cpp",prepare_host,threaded=True)
        process=subprocess.Popen([str(exe)],cwd=directory,env=env,stdin=subprocess.PIPE,stdout=subprocess.PIPE,stderr=subprocess.PIPE,text=True)
        requests=0
        try:
            port_line=process.stdout.readline()
            if not port_line:raise RuntimeError(process.stderr.read())
            port=int(port_line);base=f"http://127.0.0.1:{port}"
            mgr=HTTPPasswordMgrWithDefaultRealm();mgr.add_password("SHINO-StageA",base,"shino","PUBLIC-INERT-LAB-HTTP-FIXTURE")
            reader=build_opener(ProxyHandler({}),NoRedirect(),HTTPDigestAuthHandler(mgr))
            def get(path):
                with reader.open(Request(base+path,headers={"Connection":"keep-alive"}),timeout=6) as r:return json.loads(r.read())
            sample=b'{"ok":true,"gpu_available":true,"cpu_usage":22.5,"gpu_usage":34.5,"memory_used_gb":8,"memory_total_gb":16,"gpu_vram_mb":2048,"gpu_temp_c":56,"gpu_power":120}'
            for _ in range(30):
                with reader.open(Request(base+"/api/v1/bridge/metrics",data=sample,headers={"Content-Type":"application/json","Connection":"keep-alive"}),timeout=6) as response:
                    assert json.loads(response.read())["status"]=="RAM_SAMPLE_ACCEPTED"
                requests+=1
                for path in ("/status","/api/v1/m9/normal/status","/api/v1/m9/maintenance/result","/api/v1/update/status"):
                    get(path);requests+=1
            before=get("/api/v1/update/status");assert before["metrics_fresh"]
            process.stdin.write("scratch busy\n");process.stdin.flush()
            assert json.loads(process.stdout.readline())=={"scratch_busy":True}
            # Shared scratch lease now protects ALL five JSON handlers,
            # including the legacy normal-status streaming route which used
            # to place a 512-byte chunk buffer on continuation stack.
            for path in ("/api/v1/update/status","/api/v1/bridge/metrics",
                         "/status","/api/v1/m9/normal/status","/api/v1/m9/normal/resources"):
                try:get(path);raise AssertionError("Nested scratch use was accepted: "+path)
                except HTTPError as error:
                    assert error.code==503 and json.loads(error.read())["error"]=="RESPONSE_BUSY";error.close()
            process.stdin.write("scratch free\n");process.stdin.flush()
            assert json.loads(process.stdout.readline())=={"scratch_busy":False}
            assert get("/api/v1/update/status")["metrics_fresh"]
            assert get("/api/v1/bridge/metrics")["cpu_usage"]==22.5
            for path in ("/status","/api/v1/m9/normal/status","/api/v1/m9/normal/resources"):
                normal=get(path)
                assert normal["mode"]=="M9_NORMAL_STAGE_A" and normal["config_loaded_readonly"]
                assert normal["private_ap_ready"] and normal["physical_authorization"] is False
            process.stdin.write("advance 7000\n");process.stdin.flush()
            assert json.loads(process.stdout.readline())=={"advanced":True}
            assert not get("/api/v1/update/status")["metrics_fresh"]
            with reader.open(Request(base+"/api/v1/bridge/metrics",data=sample,headers={"Content-Type":"application/json"}),timeout=6) as response:
                assert json.loads(response.read())["status"]=="RAM_SAMPLE_ACCEPTED"
            before=get("/api/v1/update/status");assert before["metrics_fresh"]
            raw=fixture();m=dict(device="0123456789abcdef",bytes=len(raw),sha256=hashlib.sha256(raw).hexdigest(),build_id="b"*64)
            headers={"Content-Type":"application/octet-stream","Content-Length":str(len(raw)),"Connection":"close","X-Shino-SHA256":m["sha256"],"X-Shino-Build":m["build_id"],"X-Shino-Nonce":before["nonce"],"X-Shino-Proof":"0"*64}
            c=http.client.HTTPConnection("127.0.0.1",port,timeout=6);c.request("POST","/api/v1/update",body=b"",headers=headers);r=c.getresponse();assert r.status==503;r.read();c.close()
            assert get("/api/v1/update/status")["last_update"]=="REFUSED"
            # The real callback must abort safely and remain routable after a
            # disconnected partial body or a fully received invalid image.
            rejected=[]
            for label in ("partial_disconnect","full_bad_hash","transfer_encoding"):
                before=get("/api/v1/update/status");headers["X-Shino-Nonce"]=before["nonce"]
                headers["X-Shino-Proof"]=signature(dict(device=m["device"],maintenance_password=PASSWORD),before["nonce"],m)
                outgoing=dict(headers);payload=raw
                if label=="partial_disconnect":payload=raw[:8192]
                elif label=="full_bad_hash":payload=raw[:-1]+bytes([raw[-1]^1])
                else:outgoing["Transfer-Encoding"]="chunked";payload=b""
                c=http.client.HTTPConnection("127.0.0.1",port,timeout=15);c.request("POST","/api/v1/update",body=payload,headers=outgoing)
                if label=="partial_disconnect":c.sock.shutdown(socket.SHUT_WR)
                r=c.getresponse();assert r.status==(400 if label=="transfer_encoding" else 422);r.read();c.close()
                assert get("/api/v1/update/status")["last_update"]=="FAILED_NO_COMMIT"
                rejected.append(label)
            before=get("/api/v1/update/status");headers["X-Shino-Nonce"]=before["nonce"]
            headers["X-Shino-Proof"]=signature(dict(device=m["device"],maintenance_password=PASSWORD),before["nonce"],m)
            c=http.client.HTTPConnection("127.0.0.1",port,timeout=15);c.request("POST","/api/v1/update",body=raw,headers=headers);r=c.getresponse();body=json.loads(r.read());assert r.status==200 and body["status"]=="STAGED_PENDING_BOOT";c.close()
            process.stdin.write("stop\n");process.stdin.flush();output,error=process.communicate(timeout=8)
            if process.returncode:raise RuntimeError(error)
            report=json.loads(output);assert report["commit"]==report["restarts"]==1 and report["fs_preserved"]
            return dict(authenticated_post_get_requests=requests,scratch_guard_rejections=2,normal_status_guard_rejections=3,scratch_owner_preserved=True,ttl_stale_and_recovery=True,rejected_transfers_recovered=rejected,update=body,actual_normal_parser_digest_core=True,network="HOST_LOOPBACK",flash_rtc_radio="MOCKED",device_contacts=0,**report)
        except Exception:
            diagnostic="process terminated"
            if process.poll() is None:
                process.stdin.write("stats\n");process.stdin.flush();reply=queue.Queue()
                threading.Thread(target=lambda:reply.put(process.stdout.readline()),daemon=True).start()
                try:diagnostic=reply.get(timeout=2).strip()
                except queue.Empty:diagnostic="stats unavailable"
            print(f"Loopback failure after {requests} accepted requests: {diagnostic}",file=sys.stderr)
            raise
        finally:
            if process.poll() is None:process.kill();process.communicate()

if __name__=="__main__":print(json.dumps(run(),indent=2))
