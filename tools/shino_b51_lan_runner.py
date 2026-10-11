"""Execute B5.1 target handlers, pinned HTTP/Digest/Core with RAM radio/SDK.

Only HOST_LOOPBACK sockets. SDK22x getters deliberately leave threshold
untouched, as the pinned binary does. No private inputs or device transport.
"""
import argparse
import json
import re
import shutil
import subprocess
import tempfile
from pathlib import Path
from unittest.mock import patch

import shino_http_ota_network as network
from shino_b5_lan_build import materialize_http, patch_normal, add_b5_routes, once
from shino_wifi_runner import build, ROOT

LEGACY = "8de4d4556f26d47b62b1f19a6b03216a12f7e718"
SDK_SHIM = r'''
#pragma once
#include <cstdint>
#include <cstring>
#include <cassert>
#include <ESP8266WiFi.h>
enum {AUTH_WPA2_PSK=3, AUTH_WPA_WPA2_PSK=4, DHCP_STOPPED=0, DHCP_STARTED=1};
struct station_config {uint8_t ssid[32],password[64],bssid_set,bssid[6];
 struct {int8_t rssi;uint32_t authmode;} threshold;};
inline station_config testSaved{};
inline unsigned testReads=0,testWrites=0,testCurrents=0,testConnects=0,testFailReadAt=0;
inline bool testWriteOk=true,testWriteAfter=false,testMismatch=false,testReadbackFail=false;
inline bool testCurrentOk=true,testDhcpOk=true,testConnectOk=true,testWpa2Applied=false;
inline int testDhcp=DHCP_STOPPED;
inline void(*testDuringWrite)()=nullptr;
// Exact SDK22x output fields: threshold/rssi are NOT populated, in any mode.
inline bool wifi_station_get_config_default(station_config* out){
 ++testReads;if(testReads==testFailReadAt)return false;
 memcpy(out->ssid,testSaved.ssid,32);memcpy(out->password,testSaved.password,64);
 out->bssid_set=testSaved.bssid_set;memcpy(out->bssid,testSaved.bssid,6);return true;
}
inline bool wifi_station_set_config(station_config* in){
 ++testWrites;assert((WiFi.modeValue&WIFI_STA)!=0 && !WiFi.persisted);
 assert(in->threshold.authmode==AUTH_WPA2_PSK && in->threshold.rssi==-127);
 if(testWriteOk||testWriteAfter){testSaved=*in;if(testMismatch)testSaved.password[0]^=1;}
 if(testReadbackFail)testFailReadAt=testReads+1;
 if(testDuringWrite)testDuringWrite();
 return testWriteOk;
}
inline bool wifi_station_set_config_current(station_config* in){
 ++testCurrents;testWpa2Applied=in->threshold.authmode==AUTH_WPA2_PSK&&in->threshold.rssi==-127&&!in->bssid_set;
 return testCurrentOk;
}
inline int wifi_station_dhcpc_status(){return testDhcp;}
inline bool wifi_station_dhcpc_start(){if(testDhcpOk)testDhcp=DHCP_STARTED;return testDhcpOk;}
inline bool wifi_station_connect(){++testConnects;return testConnectOk;}
inline bool wifi_station_disconnect(){return true;}
'''
WIFI_SHIM = r'''
#pragma once
#include <HostSocket.h>
enum {WIFI_OFF=0,WIFI_STA=1,WIFI_AP=2,WIFI_AP_STA=3,WL_CONNECTED=3,WL_WRONG_PASSWORD=6,WL_NO_SSID_AVAIL=1};
inline void(*testStaHook)()=nullptr;
struct WiFiFixture {
 bool persisted=true,staOk=true,apOk=true;int modeValue=WIFI_OFF,wifiStatus=0;
 unsigned apPeers=1;IPAddress sta;
 void persistent(bool x){persisted=x;}void setAutoReconnect(bool){}
 bool mode(int x){modeValue=x;return true;}int getMode(){return modeValue;}
 bool enableSTA(bool x){if(!staOk)return false;modeValue=x?(modeValue|WIFI_STA):(modeValue&~WIFI_STA);if(x&&testStaHook)testStaHook();return true;}
 bool enableAP(bool x){if(!apOk)return false;modeValue=x?(modeValue|WIFI_AP):(modeValue&~WIFI_AP);return true;}
 bool softAP(const char*,const char*,int,bool,int){return apOk;}
 bool softAPdisconnect(bool){modeValue&=~WIFI_AP;return true;}
 IPAddress softAPIP(){return IPAddress(192,168,4,1);}IPAddress localIP(){return sta;}
 IPAddress subnetMask(){return IPAddress(255,255,255,0);}int status(){return wifiStatus;}
 unsigned softAPgetStationNum(){return apPeers;}
};inline WiFiFixture WiFi;
'''


def prepare_host(host, legacy=False, device="0123456789abcdef", current_build="a"*64):
    with patch.object(network, "materialize_http", materialize_http):
        network.prepare_host(host, device, current_build)
    socket = (host/"HostSocket.h").read_text()
    socket, count = re.subn(r"struct IPAddress \{.*?\};", r'''struct IPAddress {
 uint32_t value=0;IPAddress()=default;
 IPAddress(unsigned a,unsigned b,unsigned c,unsigned d):value(a<<24|b<<16|c<<8|d){}
 uint8_t operator[](size_t i)const{return uint8_t(value>>(24-i*8));}
 bool operator==(const IPAddress& p)const{return value==p.value;}
 bool operator!=(const IPAddress& p)const{return value!=p.value;}
 String toString()const{char out[16];snprintf(out,sizeof(out),"%u.%u.%u.%u",(*this)[0],(*this)[1],(*this)[2],(*this)[3]);return out;}
};inline IPAddress testLocal(192,168,4,1),testPeer(192,168,4,2);''', socket, count=1)
    if count!=1:raise ValueError("Host IPv4 shim drift")
    socket=once(socket,"IPAddress remoteIP()const{return {};}","IPAddress remoteIP()const{return testPeer;}")
    socket=once(socket,"IPAddress localIP(){return {};}","IPAddress localIP(){return testLocal;}")
    (host/"HostSocket.h").write_text(socket)
    (host/"ESP8266WiFi.h").write_text(WIFI_SHIM)
    (host.parent/"core/user_interface.h").write_text(SDK_SHIM)
    arduino=(host/"Arduino.h").read_text()
    arduino=once(arduino,"return 3248;","return hostStack;")
    arduino=once(arduino,"*b=50000;*f=1;","*b=hostBlock;*f=hostFrag;")
    arduino=once(arduino,"inline void(*hostReadHook)(uint32_t)=nullptr;",
        "inline uint32_t hostStack=3248,hostBlock=50000;inline uint8_t hostFrag=1;\ninline void(*hostReadHook)(uint32_t)=nullptr;")
    (host/"Arduino.h").write_text(arduino)
    policy=once((host/"boot/HomeLanPolicy.h").read_text(),"fsStart==0x100000","fsStart==0x200000")
    (host/"boot/HomeLanPolicy.h").write_text(policy)
    if legacy:
        def old(path):return subprocess.check_output(["git","show",LEGACY+":"+path],cwd=ROOT).decode()
        header=old("ota/lan/B5Lan.h");source=old("ota/lan/B5Lan.cpp")
        namespace={"__file__":str(ROOT/"tools/shino_b5_lan_build.py"),"__name__":"b5_legacy"}
        exec(old("tools/shino_b5_lan_build.py"),namespace)
        compose=lambda x:namespace["add_b5_routes"](namespace["patch_normal"](x))
    else:
        header=(ROOT/"ota/lan/B5Lan.h").read_text();source=(ROOT/"ota/lan/B5Lan.cpp").read_text()
        compose=lambda x:add_b5_routes(patch_normal(x))
    for name,value in (("_FS_start","0x200000u"),("_FS_end","0x3fa000u"),("_EEPROM_start","0x3fb000u")):
        source=once(source,"uint32_t(&"+name+")-base",value)
    (host/"B5Lan.h").write_text(header);(host/"B5Lan_host.inc").write_text(source)
    normal=compose((host/"normal_host.inc").read_text())
    (host/"normal_host.inc").write_text(normal)
    composition=(host/"network_composition.inc").read_text()
    (host/"network_composition.inc").write_text('#include "B5Lan_host.inc"\n'+composition)


def compile_host(directory, legacy=False, device="0123456789abcdef", current_build="a"*64):
    return build(directory,ROOT/"tools/shino_b51_lan_lab.cpp",
        lambda h:prepare_host(h,legacy,device,current_build),
        defines=("ARDUINOJSON_POOL_CAPACITY=8", *(("SHINO_B51_LEGACY=1",) if legacy else ())),threaded=True)


def run():
    rows=[]
    for legacy in (True,False):
        with tempfile.TemporaryDirectory(prefix="shino-b51-unit-") as td:
            directory=Path(td);exe,env=compile_host(directory,legacy)
            result=subprocess.run([str(exe),"unit"],cwd=directory,env=env,capture_output=True,text=True,timeout=45)
            if result.returncode:raise RuntimeError(result.stdout+result.stderr)
            rows.append(json.loads(result.stdout))
    return dict(scope="actual target B5/B5.1 + pinned parser/Core; SDK/radio/RAM mocked",
                legacy=rows[0],candidate=rows[1],physical="NOT_RUN",device_contacts=0)


if __name__=="__main__":
    argparse.ArgumentParser(description=__doc__).parse_args()
    print(json.dumps(run(),indent=2))
