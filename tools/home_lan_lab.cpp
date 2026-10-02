// Shared target controller/storage/protocol, simulated SDK I/O, no network.
#include "boot/HomeLanPolicy.h"
#include <iostream>
#include <cstdlib>
using namespace HomeLan;
static unsigned checks=0;
static void check(bool ok,const char* label) { ++checks; if(!ok) { std::cerr<<label<<'\n'; std::exit(1); } }
struct FakeSdk {
    Credentials saved;
    unsigned writes=0;
    bool safeLayout=true,readOk=true,writeOk=true,corruptReadback=false,strong=true;
    bool safe() const { return safeLayout; }
    bool wpa2() const { return strong; }
    bool read(Credentials& out) { if(!readOk) return false; out=saved; if(corruptReadback&&writes)out.password[0]^=1; return true; }
    bool write(const Credentials& in) { ++writes; if(!writeOk)return false; saved=in; return true; }
};
int main() {
    check(layoutSafe(0x400000,0x400000,0x100000,0x3fa000,0x3fb000),"4m3m layout");
    for(auto bad:{0u,0x200000u,0x800000u}) check(!layoutSafe(bad,0x400000,0x100000,0x3fa000,0x3fb000),"actual flash mismatch");
    check(!layoutSafe(0x400000,0x200000,0x100000,0x3fa000,0x3fb000),"header mismatch");
    check(!layoutSafe(0x400000,0x400000,0x200000,0x3fa000,0x3fb000),"wrong FS start");
    check(!layoutSafe(0x400000,0x400000,0x100000,0x3fd000,0x3fb000),"FS overlaps SDK");
    check(!layoutSafe(0x400000,0x400000,0x100000,0x3fa000,0x3fc000),"wrong EEPROM");
    Credentials c; bool forget=false;
    const uint8_t packet[]={'C',3,8,'l','a','b','f','i','x','t','u','r','e','1'};
    check(decode(packet,sizeof(packet),c,forget)&&!forget,"public fixture decode");
    FakeSdk io; Store<FakeSdk> store(io); Credentials loaded;
    check(!store.load(loaded)&&io.writes==0,"no credentials no writes");
    check(store.change(c)==Save::Verified&&io.writes==1,"one explicit change");
    check(store.change(c)==Save::Unchanged&&io.writes==1,"unchanged no flash write");
    Store<FakeSdk> reboot(io);
    check(reboot.load(loaded)&&loaded.same(c)&&io.writes==1,"reboot persisted once no write");
    for(unsigned boot=0;boot<100;++boot) { Credentials v; check(reboot.load(v)&&io.writes==1,"100 boots do not write"); }
    io.safeLayout=false;
    check(store.forget()==Save::Denied&&io.writes==1,"unsafe layout no erase");
    check(store.change(c)==Save::Denied&&io.writes==1,"unsafe layout no write");
    io.safeLayout=true; io.readOk=false;
    check(store.change(c)==Save::Failed&&io.writes==1,"read failure preserves saved");
    io.readOk=true; c.password[0]='F'; io.writeOk=false;
    check(store.change(c)==Save::Failed&&io.writes==2,"write failure HOLD");
    check(!io.saved.same(c),"failed write fixture retains old config");
    io.writeOk=true; io.corruptReadback=true;
    check(store.change(c)==Save::Failed&&io.writes==3,"corrupt readback HOLD");
    io.corruptReadback=false;
    check(store.forget()==Save::Verified&&io.writes==4,"explicit Forget clears saved");
    check(store.forget()==Save::Unchanged&&io.writes==4,"Forget already absent no write");
    check(!store.load(loaded)&&io.writes==4,"reboot after Forget no household connect");
    for(size_t n=0;n<sizeof(packet);++n) { Credentials x; check(!decode(packet,n,x,forget),"truncated payload"); }
    uint8_t f='F';check(decode(&f,1,loaded,forget)&&forget,"explicit Forget packet");
    c.ssidBytes=32;c.passwordBytes=64;memset(c.ssid,'s',32);memset(c.password,'a',64);
    check(c.valid(),"32 byte SSID and hex PSK"); c.password[0]='x'; check(!c.valid(),"nonhex 64 PSK");
    c.passwordBytes=63;check(c.valid(),"63 printable passphrase");c.password[0]='\n';check(!c.valid(),"newline forbidden");
    Controller net;
    check(net.begin(0,false)==StartAp&&net.state==State::NoCredentials,"no saved config recovery");
    check(net.tick(0xffffffff,false,false)==None,"no config never connects");
    check(net.begin(0,true)==(StartAp|StartSta),"saved config starts protected AP and bounded STA");
    check(net.tick(19999,false,false)==None&&net.state==State::Connecting,"password/router/DHCP pending");
    check(net.tick(20000,false,false)==None&&net.state==State::Recovery&&net.hasSaved(),"failure preserves credentials");
    check(net.tick(79999,false,false)==None,"bounded backoff");
    check(net.tick(80000,false,false)==StartSta,"automatic retry saved credentials");
    check(net.tick(80001,true,false)==None&&net.state==State::Online,"router returns DHCP valid");
    check(net.tick(95001,true,true)==None,"owner on AP does not get locked out");
    check(net.tick(95002,true,false)==StopAp&&!net.apActive(),"steady STA exclusive");
    check(net.tick(95003,false,false)==(StartAp|StartSta)&&net.hasSaved(),"router loss automatic recovery");
    net.begin(0xfffffff0,true);
    net.tick(uint32_t(0xfffffff0u+20000u),false,false);
    check(net.state==State::Recovery,"millis rollover connect timeout");
    check(net.tick(uint32_t(0xfffffff0u+80000u),false,false)==StartSta,"millis rollover retry");
    net.fault();check(net.tick(0,true,false)==None&&net.state==State::Fault,"fault stops transitions");
    check(peerOnSubnet(0xc0a80402,0xc0a80401,0xffffff00),"AP client valid");
    for(auto p:{0xc0a80400u,0xc0a80401u,0xc0a804ffu,0xc0a80502u})check(!peerOnSubnet(p,0xc0a80401,0xffffff00),"AP peer bound");
    check(!peerOnSubnet(0xc0a80402,0xc0a80401,0xff00ff00),"invalid subnet mask");
    check(authority("192.168.1.12","","192.168.1.12"),"DHCP IP programmatic origin absent");
    check(authority("192.168.1.12:80","http://192.168.1.12:80","192.168.1.12"),"same origin explicit port");
    for(auto h:{"tv.local","192.168.1.12.evil","192.168.1.12:81","evil",""})check(!authority(h,"","192.168.1.12"),"Host/rebinding rejection");
    for(auto o:{"null","https://192.168.1.12","http://evil","http://192.168.4.1"})check(!authority("192.168.1.12",o,"192.168.1.12"),"Origin rejection");
    check(endpoint(false,"/api/v1/bridge/metrics"),"LAN telemetry");
    for(auto route:{"/api/v1/bridge/factory-return","/api/v1/bridge/wifi","/api/v1/bridge/m8","/api/v1/ota/fw"})check(!endpoint(false,route)&&endpoint(true,route),"LAN privileged routes barred");
    check(endpoint(false,"/api/v1/bridge/wifi/recovery"),"explicit protected AP reopening");
    Intent intent; const char* token="0123456789abcdef0123456789abcdef";
    intent.arm(token,2,1,0);
    check(!intent.consume(token,3,1,1)&&intent.live(1),"wrong peer not consumed");
    check(!intent.consume(token,2,4,1),"wrong interface not consumed");
    check(intent.consume(token,2,1,59999)&&!intent.consume(token,2,1,59999),"one-use owner intent");
    intent.arm(token,2,1,0);check(!intent.consume(token,2,1,60000),"expiry exact boundary");
    intent.arm(token,2,1,0xfffffff0);check(intent.consume(token,2,1,16),"intent rollover");
    std::cout<<"{\"checks\":"<<checks<<",\"failed\":0,\"device_contacts\":0,\"device_writes\":0}";
}
