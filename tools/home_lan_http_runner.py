"""Real pinned HTTP parser/Digest and HomeLan.cpp over loopback; SDK/radio mocks.

Three linker-address reads become reviewed constants in host only. Every
controller, SDK adapter and handler body otherwise executes from target source.
Media crypto is covered separately by retained native receiver/scene tests.
"""
import json,subprocess,tempfile,shutil
from pathlib import Path
import v08_m6a_socket_runner as inherited
from home_lan_overlay import materialize
from v08_m8r_runner import compiler_environment
ROOT=Path(__file__).resolve().parents[1]

def run():
    with tempfile.TemporaryDirectory(prefix='p1-http-') as td:
        directory=Path(td)
        inherited.OUTPUT=directory/'input';inherited.materialize=lambda:materialize(inherited.OUTPUT)
        inherited.generate(directory)
        shims=directory/'shims';shims.mkdir()
        sockets=(inherited.LAB/'host_shims/HostSocket.h').read_text(encoding='utf-8')
        sockets=sockets.replace('struct IPAddress {uint32_t value=1;bool operator!=(const IPAddress& p)const{return value!=p.value;}};', '''struct IPAddress {
 uint32_t value=0; IPAddress()=default; IPAddress(unsigned a,unsigned b,unsigned c,unsigned d):value(a<<24|b<<16|c<<8|d){}
 bool operator!=(const IPAddress& p)const{return value!=p.value;} bool operator==(const IPAddress& p)const{return value==p.value;}
 uint8_t operator[](unsigned i)const{return uint8_t(value>>(24-i*8));}
 String toString()const{char p[16];snprintf(p,sizeof p,"%u.%u.%u.%u",(*this)[0],(*this)[1],(*this)[2],(*this)[3]);return p;}
};
inline IPAddress testLocal(192,168,4,1),testPeer(192,168,4,2);''')
        sockets=sockets.replace(' IPAddress remoteIP()const{return {};}',' IPAddress remoteIP()const{return testPeer;}\n IPAddress localIP()const{return testLocal;}')
        (shims/'HostSocket.h').write_text(sockets)
        arduino=(inherited.LAB/'host_shims/Arduino.h').read_text(encoding='utf-8').replace(' uint32_t getSketchSize()', ' uint32_t getFlashChipSize(){return 4*1024*1024;}\n uint32_t getSketchSize()')
        (shims/'Arduino.h').write_text(arduino)
        (shims/'ESP8266WiFi.h').write_text('''#pragma once
#include <HostSocket.h>
enum {WIFI_AP,WIFI_OFF,WIFI_AP_STA,WIFI_STA,WL_CONNECTED=3};
struct WiFiFixture {
 bool persisted=true;int modeValue=WIFI_AP;int wifiStatus=0;IPAddress sta;
 void persistent(bool b){persisted=b;}bool mode(int m){modeValue=m;return true;}
 bool enableSTA(bool){modeValue=WIFI_AP_STA;return true;}void setAutoReconnect(bool){}
 bool softAP(const char*,const char*,int,bool,int){return true;}void softAPdisconnect(bool){}
 IPAddress softAPIP(){return IPAddress(192,168,4,1);}IPAddress localIP(){return sta;}
 IPAddress subnetMask(){return IPAddress(255,255,255,0);}int status(){return wifiStatus;}
 unsigned softAPgetStationNum(){return 1;}
};inline WiFiFixture WiFi;
''')
        (shims/'user_interface.h').write_text('''#pragma once
#include <cstdint>
#include <cstring>
enum {AUTH_WPA2_PSK=3,AUTH_WPA_WPA2_PSK=4};
struct station_config {uint8_t ssid[32],password[64];struct {int8_t rssi;uint8_t authmode;} threshold;};
inline station_config testSaved{};inline unsigned testWrites=0,testConnects=0;inline bool testWriteOk=true;
inline bool wifi_station_get_config_default(station_config* c){*c=testSaved;return true;}
inline bool wifi_station_set_config_current(station_config*){return true;}
inline bool wifi_station_set_config(station_config* c){++testWrites;if(testWriteOk)testSaved=*c;return testWriteOk;}
inline bool wifi_station_dhcpc_start(){return true;}inline bool wifi_station_connect(){++testConnects;return true;}
inline bool wifi_station_disconnect(){return true;}
''')
        (shims/'MediaIngress.h').write_text('''#pragma once
namespace m7 {struct Ingress {
 void service(){}void cancel(){}bool needsProof(){return false;}bool verifyHeaders(){return false;}
 bool begin(const char*,unsigned){return false;}template<class C>bool poll(C&){return false;}
 void setExpectedHost(const char*){}
};}
''')
        source=(ROOT/'firmware/src/boot/HomeLan.cpp').read_text(encoding='utf-8')
        for name,offset in [('_FS_start','0x100000u'),('_FS_end','0x3fa000u'),('_EEPROM_start','0x3fb000u')]:
            source=source.replace('uint32_t(&'+name+')-base',offset)
        (directory/'HomeLan_host.inc').write_text(source)
        compiler,env=compiler_environment(directory);msvc=Path(compiler).name.lower()=='cl.exe';exe=directory/'http.exe'
        inc=[directory/'corrected',shims,directory,inherited.LAB/'host_shims',ROOT/'firmware/include']
        sources=[ROOT/'tools/home_lan_http_lab.cpp',directory/'corrected/detail/mimetable.cpp']
        defs=['SHINO_V08_PREPARSE_EXPERIMENT=1','SHINO_ENABLE_HOME_LAN=1','SHINO_HOME_LAN_PREBODY=1']
        cmd=([compiler,'/nologo','/std:c++20','/EHsc','/O2',*[f'/D{x}' for x in defs],*[f'/I{x}' for x in inc],*map(str,sources),'/link','ws2_32.lib','bcrypt.lib',f'/OUT:{exe}'] if msvc else
             [compiler,'-std=c++20','-pthread','-O2','-fsanitize=address,undefined',*[f'-D{x}' for x in defs],*[f'-I{x}' for x in inc],*map(str,sources),'-lcrypto','-o',str(exe)])
        c=subprocess.run(cmd,cwd=directory,env=env,capture_output=True,text=True,timeout=90)
        if c.returncode:raise RuntimeError(c.stdout+c.stderr)
        c=subprocess.run([str(exe)],cwd=directory,env=env,capture_output=True,text=True,timeout=45)
        if c.returncode:raise RuntimeError(c.stdout+c.stderr)
        report=json.loads(c.stdout)
        report['scope']='native target HomeLan.cpp + pinned parser/Digest; loopback only, radio/SDK/linker mocks'
        return report
if __name__=='__main__':print(json.dumps(run(),indent=2))
