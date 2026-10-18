// HOST executes the actual inserted HTTP handlers; Core/socket/SDK are stubs.
#include "B54LanWeather.h"
#include "B54LanStatusPath.h"
#include <algorithm>
#include <cassert>
#include <string>
#include <vector>
#include <map>
#include <cstdio>
using __FlashStringHelper=char;
using PGM_P=const char*;
#define F(x) x
#define PSTR(x) x
#ifdef _MSC_VER
#define __attribute__(x)
#endif
enum{HTTP_GET,HTTP_POST,WL_CONNECTED=3};
static uint32_t clockMs=100,stackFree=2208;
uint32_t millis(){return clockMs++;}
uint32_t micros(){return clockMs*1000;}
void yield(){clockMs+=10;}
struct Esp{uint32_t getFreeContStack(){return stackFree;}void wdtFeed(){}}ESP;
struct Wifi{int state=WL_CONNECTED;int status(){return state;}}WiFi;
struct Text:std::string{using std::string::string;Text(const std::string& s):std::string(s){}bool isEmpty()const{return empty();}};
struct Peer{
 std::vector<uint8_t> body;size_t at=0;bool open=true;size_t chunk=80;
 bool connected(){return open;}
 int available(){return int(body.size()-at);}
 int read(uint8_t* out,size_t n){n=std::min({n,chunk,body.size()-at});memcpy(out,body.data()+at,n);at+=n;return int(n);}
};
struct Server{
 int verb=HTTP_POST,code=0;uint32_t start=100;bool waiting=false,ap=false;size_t queueAfter=9999;
 std::map<std::string,Text> headers;std::vector<std::pair<Text,Text>> args_;Peer peer;
 std::vector<uint8_t> response;
 Text path="/api/v1/weather";const Text& uri(){return path;}
 int method(){return verb;}Text header(const char* name){return headers[name];}
 unsigned args(){return unsigned(args_.size());}Text argName(unsigned i){return args_.at(i).first;}
 Text arg(unsigned i){return args_.at(i).second;}
 uint32_t requestStarted(){return start;}bool waitingPeer(){return waiting||peer.at>=queueAfter;}
 Peer& client(){return peer;}
 void sendHeader(const char*,const char*){}void setContentLength(unsigned){}
 void send_P(int c,const char*,const char*){code=c;}
 void send(int c,const char*,const char*){code=c;}
 void sendContent(const char* p,size_t n){response.assign(p,p+n);}
}server;
namespace M9NormalResources{struct Heap{uint32_t free=28416,largest=26328;uint8_t fragmentation=8;};}
struct Core{M9NormalResources::Heap current;void heap(M9NormalResources::Heap& h){h=current;}}core;
struct Journal{bool stopped=false;bool frozen(){return stopped;}}diagnosticJournal;
bool configReady=true,uploadBusy=false;
namespace B5Lan{bool permitted(Server& s){return !s.ap;}bool apPeer(Server& s){return s.ap;}}
bool length(uint32_t& n){
 const auto text=server.header("Content-Length");n=0;
 for(char c:text){if(c<'0'||c>'9'||n>9999999)return false;n=n*10+unsigned(c-'0');}return true;
}
namespace B54LanNative{
 B54LanWeather::Receiver receiver;bool held=false;
 bool key(uint8_t* out){for(unsigned i=0;i<32;++i)out[i]=uint8_t(i);return true;}
 bool ready(){return receiver.state().ready;}
 bool acquire(){if(held||!ready())return false;held=true;return true;}
 void release(){receiver.clearWorkspace();held=false;}
 uint8_t* buffer(){return receiver.workspace().wire;}
 bool status(uint8_t kind,const uint8_t* nonce){return receiver.status(kind,nonce,1791955392,key);}
 B54LanWeather::Result accept(){return receiver.receive(buffer(),80,1791955392,true,clockMs,key);}
 void record(uint32_t,uint32_t){}void invalidate(){receiver.poll(0,false,clockMs);}
}
#include "B54LanHttp.inc"
#include "vectors.inc"
static std::vector<uint8_t> bytes(const char* s){
 std::vector<uint8_t> out;for(size_t i=0;i<strlen(s);i+=2){char pair[]={s[i],s[i+1],0};out.push_back(uint8_t(strtoul(pair,nullptr,16)));}return out;
}
static void reset(){
 server=Server{};clockMs=100;stackFree=2208;core=Core{};diagnosticJournal=Journal{};
 WiFi.state=WL_CONNECTED;configReady=true;uploadBusy=false;B54LanNative::held=false;
 const uint8_t device[]={1,2,3,4,5,6,7,8},boot[]={0x10,0x20,0x30,0x40,0x50,0x60,0x70,0x80};
 B54LanNative::receiver.configure(device,boot,reinterpret_cast<const uint8_t*>("DEMO0001"));
 server.peer.body=bytes(FrozenSample);server.headers["Content-Length"]="80";
 server.headers["Content-Type"]="application/octet-stream";
}
int main(){
 reset();assert(weatherPrebody());weatherReceive();assert(server.code==200&&server.response.size()==80);
 assert(B54LanNative::receiver.state().sequence==1&&!B54LanNative::held);
 for(unsigned i=0;i<sizeof(B54LanWeather::Workspace);++i)assert(reinterpret_cast<uint8_t*>(&B54LanNative::receiver.workspace())[i]==0);
 for(unsigned n=0;n<80;++n){reset();server.peer.body.resize(n);assert(weatherPrebody());weatherReceive();assert(server.code!=200);assert(B54LanNative::receiver.state().sequence==0);}
 reset();server.peer.body.push_back(1);weatherReceive();assert(server.code==400&&B54LanNative::receiver.state().sequence==0);
 for(const char* field:{"Transfer-Encoding","Expect","Origin"}){
  reset();server.headers[field]="forbidden";assert(!weatherPrebody()&&server.peer.at==0);
 }
 for(const char* length_:{"79","81","080","-1","999999999999999999"}){
  reset();server.headers["Content-Length"]=length_;assert(!weatherPrebody()&&server.peer.at==0);
 }
 for(unsigned cause=0;cause<12;++cause){reset();
  switch(cause){case 0:core.current.free=20479;break;case 1:core.current.largest=16383;break;
   case 2:stackFree=2047;break;case 3:core.current.fragmentation=26;break;case 4:uploadBusy=true;break;
   case 5:diagnosticJournal.stopped=true;break;case 6:WiFi.state=0;break;case 7:server.waiting=true;break;
   case 8:configReady=false;break;case 9:server.ap=true;break;case 10:clockMs=2100;break;case 11:server.peer.open=false;break;}
  assert(!weatherPrebody()&&server.peer.at==0&&B54LanNative::receiver.state().sequence==0);
 }
 reset();server.peer.chunk=1;server.queueAfter=20;weatherReceive();assert(server.code==408&&server.peer.at==20&&B54LanNative::receiver.state().sequence==0);
 reset();B54LanNative::held=true;weatherReceive();assert(server.code==503&&server.peer.at==0);
 reset();server.verb=HTTP_GET;server.headers["Content-Length"]="0";server.path="/api/v1/weather/status/3132333435363738";
 assert(weatherPrebody());weatherStatus();assert(server.code==200&&server.response.size()==80&&B54LanNative::receiver.state().sequence==0);
 reset();server.verb=HTTP_GET;server.headers["Content-Length"]="0";server.path="/api/v1/weather/status/UPPERCASEBADHEX!!";weatherStatus();assert(server.code==400);
 puts("B54_LAN_HTTP_HOST_PASS actual-handlers truncations=80 prebody/guards/critical-peer/expiry/lease-wipe; Core-lwIP-SDK=STUB");
}
