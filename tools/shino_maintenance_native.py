"""Real Native pump + Core + Python sender, network/flash/RTC exclusively mocked."""
import json
import tempfile
from pathlib import Path
from shino_wifi_runner import build,run,ROOT

def host_shims(host):
    arduino=(ROOT/'experiments/m9_signed_ota/host/Arduino.h').read_text()
    arduino=arduino.replace('struct HostESP {','inline uint32_t host_ms=1;inline uint32_t millis(){return host_ms;}inline uint32_t os_random(){return 0x11223344;}\nstruct HostESP {')
    arduino=arduino.replace('bool failWrite=false', 'uint32_t block=50000,stack=3248,restarts=0;uint8_t frag=1;\n void getHeapStats(uint32_t* h,uint32_t* b,uint8_t* f){*h=heap;*b=block;*f=frag;}uint32_t getFreeContStack(){return stack;}void wdtFeed(){}void restart(){++restarts;}\n bool failWrite=false')
    (host/'Arduino.h').write_text(arduino)
    (host/'ESP8266WiFi.h').write_text('''#pragma once
#include <Arduino.h>
#include <deque>
struct IPAddress {uint8_t p[4];IPAddress(uint8_t a=192,uint8_t b=168,uint8_t c=4,uint8_t d=1):p{a,b,c,d}{}uint8_t operator[](size_t n)const{return p[n];}bool operator==(const IPAddress& b)const{return !std::memcmp(p,b.p,4);}};
enum {WIFI_AP,WIFI_OFF};
struct Wifi {int mode=WIFI_AP;int getMode(){return mode;}IPAddress softAPIP(){return {};}};inline Wifi WiFi;
struct Peer {bool connected=true;std::string input,output;IPAddress ip{192,168,4,2};};inline Peer peer,extra;
inline unsigned listeners=0,aborts=0;inline bool listenFail=false;inline std::deque<Peer*> pending;
struct WiFiClient {Peer* p=nullptr;WiFiClient()=default;WiFiClient(Peer* x):p(x){}explicit operator bool()const{return p && p->connected;}bool connected()const{return bool(*this);}int available()const{return p?int(p->input.size()):0;}
int read(){if(!available())return -1;int c=uint8_t(p->input[0]);p->input.erase(0,1);return c;}int read(uint8_t* out,size_t n){n=std::min(n,size_t(available()));std::memcpy(out,p->input.data(),n);p->input.erase(0,n);return int(n);}
void abort(){if(p && p->connected){p->connected=false;++aborts;}}void stop(){abort();}void flush(int){}IPAddress localIP(){return {};}IPAddress remoteIP(){return p->ip;}void print(const char* s){p->output+=s;}template<class... A>void printf(const char* f,A... a){char out[128];std::snprintf(out,sizeof(out),f,a...);print(out);}};
struct WiFiServer {bool open=false;WiFiServer(int){}int status(){return open?1:0;}void begin(int,int backlog){if(backlog!=1)std::abort();if(listenFail)return;open=true;++listeners;}void close(){if(open){open=false;--listeners;}}void stop(){close();}bool hasClient(){return !pending.empty();}WiFiClient accept(){if(pending.empty())return {};auto p=pending.front();pending.pop_front();return WiFiClient(p);}};
''')

def build_native(directory):return build(directory,ROOT/'tools/shino_maintenance_native_lab.cpp',host_shims)
if __name__=='__main__':
    result=run(build_native,native=True)
    for row in result['rows']:
        assert row['listeners']==row['queued']==0
        if row['commit']:assert row['host_restart_calls']==1
        else:assert row['host_restart_calls']==0 and not row['connected'],row['name']
    result['actual_native_pump']=True;result['sdk_wifi_tcp']='MOCKED_NOT_NATIVE_HIGH_WATER'
    interlocks=[]
    for define in ('ARDUINO_SIGNING=1','SHINO_ENABLE_FACTORY_RESTORE=1'):
        with tempfile.TemporaryDirectory(prefix='shino-maintenance-interlock-') as td:
            try:build(Path(td),ROOT/'tools/shino_maintenance_native_lab.cpp',host_shims,defines=(define,))
            except RuntimeError as e:assert 'Unsigned maintenance must not coexist' in str(e)
            else:raise AssertionError('Unsafe signing/OEM coexistence compiled')
        interlocks.append(define)
    result['compile_rejected_interlocks']=interlocks
    print(json.dumps(result,indent=2))
