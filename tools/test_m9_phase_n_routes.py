"""Compile actual StageA controller/dashboard/telemetry with fake hardware.

Requires the pinned ArduinoJson include tree installed by an offline app build.
No socket, serial adapter or device transport exists in this fixture.
"""
from pathlib import Path
import os, shutil, subprocess, tempfile, unittest
from m9_phase_n_qualification import ROOT

STUBS={
'Arduino.h':r'''
#pragma once
#include <cstdint>
#include <string>
#include <cstring>
#include <cstdio>
struct String:std::string {using std::string::string;using std::string::operator=;
    String(const std::string& s):std::string(s){}bool startsWith(const char* p)const{return rfind(p,0)==0;}
    size_t length()const{return size();}};
#define F(x) x
inline uint32_t clockMs=0;inline uint32_t millis(){return clockMs;}inline void yield(){}
struct EspClass{static void wdtFeed(){}};
struct FakeESP{unsigned resets=0,gets=0;uint32_t margin=4000;
    void resetFreeContStack(){++resets;margin=4000;}uint32_t getFreeContStack(){++gets;return margin;}
    void getHeapStats(uint32_t* f,uint32_t* b,uint8_t* p){++gets;*f=32000;*b=30000;*p=2;}};
inline FakeESP ESP;
''',
'shino_private_policy.h':r'''
#pragma once
#define SHINO_BOOT_PROFILE 1
#define SHINO_M9_NORMAL_QUALIFICATION 1
#define SHINO_ENABLE_FACTORY_RESTORE 0
#define SHINO_ENABLE_NATIVE_SIGNED_OTA 0
#define SHINO_ENABLE_FS_MIGRATION 0
#define SHINO_SETUP_AP_PSK "PUBLIC-INERT-LAB-AP-FIXTURE"
#define SHINO_BOOTSTRAP_API_TOKEN "PUBLIC-INERT-LAB-API-TOKEN-FIXTURE"
#define SHINO_RESCUE_HTTP_USER "lab"
#define SHINO_RESCUE_HTTP_PASSWORD "PUBLIC-INERT-LAB-HTTP-FIXTURE"
''',
'config/ConfigManager.h':r'''
#pragma once
#include <string>
class ConfigManager{public:unsigned loads=0;std::string token;
    bool loadMountedReadOnly(bool valid){++loads;return valid;}
    void setApiToken(const char* t){token=t;}};
''',
'wireless/WiFiManager.h':r'''
#pragma once
#include <cassert>
inline bool failAP=false;inline unsigned apStarts=0;
struct FakeWiFi{bool volatileMode=false;void persistent(bool enabled){assert(!enabled);volatileMode=true;}};
inline FakeWiFi WiFi;
class WiFiManager{public:WiFiManager(const char*,const char*,const char*,const char*){}
    bool startAccessPointMode(){assert(WiFi.volatileMode);++apStarts;return !failAP;}};
''',
'display/DisplayManager.h':r'''
#pragma once
#include "Arduino.h"
#include <cassert>
#define LCD_WHITE 1
#define LCD_BLACK 0
struct Arduino_GFX {
    unsigned cards=0,dashes=0;void fillScreen(uint16_t){}
    void rect(int x,int y,int w,int h){assert(x>=0&&y>=0&&x+w<=240&&y+h<=240);}
    void fillRoundRect(int x,int y,int w,int h,int,uint16_t){rect(x,y,w,h);if(w==108)++cards;}
    void drawRoundRect(int x,int y,int w,int h,int,uint16_t){rect(x,y,w,h);}
    void fillRect(int x,int y,int w,int h,uint16_t){rect(x,y,w,h);if(w==16&&h==2)++dashes;}
    void drawCircle(int x,int y,int r,uint16_t){rect(x-r,y-r,2*r,2*r);}
    void setTextColor(uint16_t){}void setTextSize(int){}void setTextWrap(bool){}
    void setCursor(int x,int y){assert(x>=0&&y>=0&&x<240&&y<240);}template<class T>void print(T){}
};
namespace DisplayManager{inline Arduino_GFX gfx;inline unsigned starts=0;
    inline void begin(int rotation){assert(rotation==0);++starts;}inline Arduino_GFX* getGfx(){return &gfx;}
    inline void clearScreen(){}inline void drawTextWrapped(int,int,const char*,int,int,int,bool){}
}
''',
'web/Webserver.h':r'''
#pragma once
#include "Arduino.h"
#include <functional>
#include <map>
enum HTTPMethod{HTTP_GET,HTTP_POST};constexpr int DIGEST_AUTH=2;
struct ESP8266WebServer{
    bool allowed=false;String authorization,payload;unsigned bodyGets=0,challenges=0,starts=0;int code=0;
    size_t declared=0;std::string response;HTTPMethod verb=HTTP_GET;String path;
    std::function<bool()> prebody;std::map<std::pair<std::string,HTTPMethod>,std::function<void()>> routes;
    std::function<void()> fallback;
    String header(const char* key){if(std::strcmp(key,"Content-Length")==0)return verb==HTTP_POST?String(std::to_string(payload.size())):String();
        if(std::strcmp(key,"Content-Type")==0)return "application/json";
        if(std::strcmp(key,"Transfer-Encoding")==0)return "";
        return authorization;}
    HTTPMethod method(){return verb;}String uri(){return path;}void keepAlive(bool){}
    void setStageAPrebody(std::function<bool()> f){prebody=f;}
    bool authenticate(const char*,const char*){return allowed;}
    void requestAuthentication(int scheme,const char*){if(scheme!=DIGEST_AUTH)std::abort();++challenges;code=401;}
    void sendHeader(const char*,const char*){}template<class... T>void collectHeaders(T...){}
    void setContentLength(size_t n){declared=n;}void send(int c,const char*,const char* b){code=c;response=b;}
    void sendContent(const char* p,size_t n){response.append(p,n);}const String& arg(const char*){++bodyGets;return payload;}
    void request(const char* requestPath,HTTPMethod requestMethod){verb=requestMethod;path=requestPath;
        code=0;response.clear();if(!prebody())return;auto it=routes.find({requestPath,requestMethod});
        if(it==routes.end())fallback();else it->second();}
};
class Webserver{public:ESP8266WebServer server;
    void begin(){++server.starts;}void handleClient(){}ESP8266WebServer& raw(){return server;}
    void on(const char* path,HTTPMethod method,std::function<void()> f){server.routes[{path,method}]=f;}
    void onNotFound(std::function<void()> f){server.fallback=f;}};
''',
}

class StageARoutes(unittest.TestCase):
    def test_actual_controller_auth_closed_routes_stale_recovery_and_failure_modes(self):
        compiler=shutil.which('g++') or shutil.which('cl')
        self.assertIsNotNone(compiler,'Native C++ compiler required')
        deps=Path(os.environ.get('SHINO_ARDUINOJSON_SRC',str(ROOT/'firmware/.pio/libdeps/esp12e/ArduinoJson/src'))).resolve()
        self.assertTrue((deps/'ArduinoJson.h').is_file(),'Build the pinned public firmware environment first')
        source=r'''
#include "boot/M9LittleFsMountProbe.h"
inline bool failFS=false;inline unsigned mountCalls=0;
namespace M9LittleFsMountProbe{LittleFsMountProbeStatus state;
    void begin(){++mountCalls;state.attempted=true;state.autoformat_disabled=true;
        state.mounted=state.inventory_exact=state.config_seed_exact=!failFS;
        state.checked_file_count=24;state.checked_payload_bytes=181402;}
    const LittleFsMountProbeStatus& status(){return state;}}
'''
        source+='\n#include "'+str(ROOT/'firmware/src/boot/M9NormalStageA.cpp').replace('\\','/')+'"\n'
        source+='\n#include "'+str(ROOT/'firmware/src/boot/M9NormalDashboard.cpp').replace('\\','/')+'"\n'
        source+='\n#include "'+str(ROOT/'firmware/src/boot/FslessMetrics.cpp').replace('\\','/')+'"\n'
        source+=r'''
#include <cassert>
int main(int argc,char** argv){
    assert(argc==2);failAP=std::string(argv[1])=="ap";failFS=std::string(argv[1])=="fs";
    ConfigManager config;M9NormalStageA::beforeSetup();M9NormalStageA::begin(config);M9NormalStageA::afterSetup();
    M9NormalStageA::begin(config);assert(mountCalls==1&&config.loads==1&&apStarts==1);
    auto& server=M9NormalStageA::service.raw();
    if(failAP){assert(server.starts==0&&server.routes.empty());return 0;}
    assert(server.starts==1&&server.routes.size()==5);
    server.allowed=true;server.authorization="Basic valid-private-values";
    server.request("/api/v1/bridge/metrics",HTTP_POST);assert(server.code==401&&server.bodyGets==0);
    server.authorization="Digest valid";server.allowed=false;
    server.request("/status",HTTP_GET);assert(server.code==401);
    server.allowed=true;unsigned getterCount=ESP.gets,resetCount=ESP.resets;
    server.request("/api/v1/m9/normal/resources",HTTP_GET);
    assert(server.code==200&&server.declared==server.response.size()&&ESP.gets==getterCount&&ESP.resets==resetCount);
    for(const char* path:{"/config.json","/web/../config.json","/%2e%2e/config.json","/api/config","/api/reboot","/legacyupdate","/api/v1/media/image","/api/v1/ota","/"}){
        server.request(path,HTTP_GET);assert(server.code==404);server.request(path,HTTP_POST);assert(server.code==404);}
    server.payload=String(385,'x');server.request("/api/v1/bridge/metrics",HTTP_POST);assert(server.code==413);
    server.payload="{\"ok\":true,\"gpu_available\":true,\"cpu_usage\":22.5,\"gpu_usage\":34.5,\"memory_used_gb\":8,\"memory_total_gb\":16,\"gpu_vram_mb\":2048,\"gpu_temp_c\":56,\"gpu_power\":120}";
    clockMs=1000;server.request("/api/v1/bridge/metrics",HTTP_POST);
    if(failFS){assert(server.code==503&&!FslessMetrics::snapshot().received&&config.token.empty());return 0;}
    assert(server.code==200&&FslessMetrics::snapshot().cpu==22.5F&&!FslessMetrics::stale());
    M9NormalStageA::loop();assert(DisplayManager::gfx.cards>=8);
    clockMs=7000;assert(!FslessMetrics::stale());clockMs=7001;assert(FslessMetrics::stale());
    unsigned dashCount=DisplayManager::gfx.dashes;M9NormalStageA::loop();assert(DisplayManager::gfx.dashes==dashCount+4);
    server.payload="{\"ok\":false,\"gpu_available\":true}";server.request("/api/v1/bridge/metrics",HTTP_POST);
    assert(server.code==422&&FslessMetrics::snapshot().cpu==22.5F);
    server.payload="{\"ok\":true,\"gpu_available\":false,\"cpu_usage\":30,\"gpu_usage\":0,\"memory_used_gb\":8,\"gpu_vram_mb\":0,\"gpu_temp_c\":0,\"gpu_power\":0}";
    server.request("/api/v1/bridge/metrics",HTTP_POST);assert(server.code==200&&!FslessMetrics::stale());
    clockMs+=1000;M9NormalStageA::loop();assert(FslessMetrics::snapshot().cpu==30&&ESP.resets==4);
    assert(M9NormalStageA::observer.status().samples==3&&mountCalls==1);
}
'''
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp)
            for name,body in STUBS.items():
                target=root/name;target.parent.mkdir(parents=True,exist_ok=True);target.write_text(body)
            cpp=root/'test.cpp';cpp.write_text(source);exe=root/'test.exe'
            includes=[root,ROOT/'firmware/include',deps]
            if Path(compiler).name.lower()=='cl.exe':
                args=[compiler,'/nologo','/std:c++17','/EHsc','/W4','/WX',*[f'/I{p}' for p in includes],str(cpp),f'/Fe:{exe}',f'/Fo:{root}/']
            else:args=[compiler,'-std=c++17','-Wall','-Wextra','-Werror',*[f'-I{p}' for p in includes],str(cpp),'-o',str(exe)]
            result=subprocess.run(args,cwd=root,capture_output=True,text=True)
            self.assertEqual(result.returncode,0,result.stdout+result.stderr)
            for mode in ('normal','fs','ap'):
                result=subprocess.run([str(exe),mode],capture_output=True,text=True)
                self.assertEqual(result.returncode,0,mode+': '+result.stdout+result.stderr)

if __name__=='__main__':unittest.main()
