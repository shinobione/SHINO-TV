// Actual Normal.cpp + parser/Digest + Updater, host loopback and RAM hardware.
#ifdef _WIN32
#pragma comment(lib,"ws2_32.lib")
#pragma comment(lib,"bcrypt.lib")
#endif
#include <HostSocket.h>
#include <ESP8266WiFi.h>
#include <iostream>
#include <fstream>
#include <cassert>
uint32_t host_ms=0;
size_t hostJsonArenaPeak=0;
static void(*hostReentryHook)()=nullptr;
static bool inHostYield=false,reentryArmed=false;
static unsigned hostReentryChecks=0;
static std::atomic<bool> disconnectReadback{false};
void yield(){
    if(hostReentryHook&&!inHostYield){inHostYield=true;hostReentryHook();inHostYield=false;}
    std::this_thread::yield();
}
#include "pinned_stream.inc"
#include <ESP8266WebServer.h>
#include "detail/mimetable.cpp"
#include "boot/M9LittleFsMountProbe.h"
namespace M9LittleFsMountProbe {
LittleFsMountProbeStatus state;
void begin(){state.attempted=state.autoformat_disabled=state.mounted=state.inventory_exact=state.config_seed_exact=true;state.checked_file_count=24;state.checked_payload_bytes=181402;}
const LittleFsMountProbeStatus& status(){return state;}
}
#include "network_composition.inc"
#include "eboot_command.h"
extern "C" {volatile uint32_t m9_host_rtc[32]{};}
void arenaRegression(){
    using M9NormalStageA::JsonArena;
    JsonArena arena;
    assert(!arena.allocate(0)&&!arena.allocate(769));
    auto* a=static_cast<uint8_t*>(arena.allocate(80));auto* b=arena.allocate(48);
    assert(a&&b);std::memset(a,0x5a,80);
    auto* grown=static_cast<uint8_t*>(arena.reallocate(a,160));assert(grown);
    for(unsigned i=0;i<80;++i)assert(grown[i]==0x5a);
    assert(!arena.reallocate(grown,769));assert(grown[0]==0x5a);
    assert(arena.reallocate(grown,16)==grown);arena.deallocate(b);arena.deallocate(grown);
    assert(arena.bytesUsed()==0);
    for(unsigned cycle=0;cycle<256;++cycle){
        void* blocks[32]{};unsigned count=0;
        while(count<32&&(blocks[count]=arena.allocate(8+8*(count%4))))++count;
        assert(count>8);for(unsigned i=0;i<count;i+=2)arena.deallocate(blocks[i]);
        for(unsigned i=1;i<count;i+=2)arena.deallocate(blocks[i]);
        assert(arena.bytesUsed()==0);
        void* whole=arena.allocate(768-alignof(void*));assert(whole);
        arena.deallocate(whole);assert(arena.bytesUsed()==0);
    }
    hostJsonArenaPeak=0; // request peak, excluding the allocator stress fixture
}
int main(){
#ifdef _WIN32
WSADATA w{};if(WSAStartup(MAKEWORD(2,2),&w))return 2;
#endif
arenaRegression();
if(const char* path=std::getenv("SHINO_TEST_CURRENT_BIN")){
    std::ifstream input(path,std::ios::binary);std::vector<uint8_t> raw{std::istreambuf_iterator<char>(input),{}};
    if(raw.size()<64000||raw.size()>ShinoHttpOta::MaxImage)return 4;
    std::copy(raw.begin(),raw.end(),ESP.flash.begin());ESP.current=uint32_t(raw.size());
}
ConfigManager config;M9NormalStageA::beforeSetup();M9NormalStageA::begin(config);M9NormalStageA::afterSetup();
hostReentryHook=[](){
    if(reentryArmed&&M9NormalStageA::httpBusy){
        reentryArmed=false;++hostReentryChecks;
        const auto retained=M9NormalStageA::server.retainedRequestBytes();
        M9NormalStageA::loop();
        assert(M9NormalStageA::httpBusy&&retained==M9NormalStageA::server.retainedRequestBytes());
    }
};
hostReadHook=[](uint32_t at){if(at>=0x100000&&disconnectReadback.exchange(false))M9NormalStageA::server.client().stop();};
lab_real_clock=true;std::atomic<bool> done=false;std::atomic<unsigned> advance=0;std::atomic<int> scratchMode{-1},uploadMode{-1};
std::atomic<unsigned> loops=0,lastLoopTime=0;
std::thread control([&](){std::string line;while(std::getline(std::cin,line)){
    if(line=="stop")break;
    if(line.rfind("advance ",0)==0)advance=unsigned(std::stoul(line.substr(8)));
    if(line=="scratch busy")scratchMode=1;
    if(line=="scratch free")scratchMode=0;
    if(line=="upload busy")uploadMode=1;
    if(line=="upload free")uploadMode=0;
    if(line=="disconnect readback"){disconnectReadback=true;std::cout<<"{\"readback_disconnect_armed\":true}"<<std::endl;}
    if(line=="stats")std::cout<<"{\"accepted\":"<<accepted<<",\"bytes_read\":"<<bytesRead<<",\"bytes_written\":"<<bytesWritten<<",\"live_sockets\":"<<liveSockets<<",\"destroyed\":"<<destroyed
        <<",\"loops\":"<<loops<<",\"loop_ms\":"<<lastLoopTime<<",\"fd\":"<<last_fd<<",\"ioctl\":"<<last_ioctl<<",\"available\":"<<last_available<<",\"select\":"<<last_select<<",\"peek\":"<<last_peek<<"}"<<std::endl;
}done=true;});
std::cout<<M9NormalStageA::server.getServer().port<<std::endl;
while(!done){
    const unsigned tick=advance.exchange(0);if(tick)host_ms+=tick;
    const int scratch=scratchMode.exchange(-1);
    const int uploading=uploadMode.exchange(-1);
    if(uploading>=0){M9NormalStageA::uploadBusy=uploading==1;std::cout<<"{\"upload_busy\":"<<(uploading==1?"true":"false")<<"}"<<std::endl;}
    if(scratch>=0){
        if(scratch==1)std::strcpy(M9NormalStageA::responseBody,"SCRATCH_OWNER_SENTINEL");
        else if(std::strcmp(M9NormalStageA::responseBody,"SCRATCH_OWNER_SENTINEL"))return 3;
        M9NormalStageA::responseBusy=scratch==1;
        std::cout<<"{\"scratch_busy\":"<<(scratch==1?"true":"false")<<"}"<<std::endl;
    }
    ++loops;lastLoopTime=millis();reentryArmed=true;M9NormalStageA::loop();if(tick)std::cout<<"{\"advanced\":true}"<<std::endl;
    std::this_thread::sleep_for(std::chrono::milliseconds(1));
}
control.join();eboot_command cmd{};const bool boot=eboot_command_read(&cmd)==0;
bool fs=true;for(size_t i=0x200000;i<ESP.flash.size();++i)fs&=ESP.flash[i]==0xff;
std::cout<<"{\"commit\":"<<boot<<",\"restarts\":"<<ESP.restarts<<",\"writes\":"<<ESP.writeCalls<<",\"fs_preserved\":"<<(fs?"true":"false")
    <<",\"host_json_arena_peak\":"<<hostJsonArenaPeak<<",\"json_arena_capacity\":768,\"arena_reuse_cycles\":256,\"retained_request_bytes\":"<<M9NormalStageA::server.retainedRequestBytes()
    <<",\"yield_reentry_checks\":"<<hostReentryChecks<<"}"<<std::endl;
return 0;
}
