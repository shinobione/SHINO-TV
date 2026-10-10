// Actual Normal.cpp + parser/Digest + Updater, host loopback and RAM hardware.
#ifdef _WIN32
#pragma comment(lib,"ws2_32.lib")
#pragma comment(lib,"bcrypt.lib")
#endif
#include <HostSocket.h>
#include <ESP8266WiFi.h>
#include <iostream>
uint32_t host_ms=0;
void yield(){std::this_thread::yield();}
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
int main(){
#ifdef _WIN32
WSADATA w{};if(WSAStartup(MAKEWORD(2,2),&w))return 2;
#endif
ConfigManager config;M9NormalStageA::beforeSetup();M9NormalStageA::begin(config);M9NormalStageA::afterSetup();
lab_real_clock=true;std::atomic<bool> done=false;std::atomic<unsigned> advance=0;std::atomic<int> scratchMode{-1};
std::atomic<unsigned> loops=0,lastLoopTime=0;
std::thread control([&](){std::string line;while(std::getline(std::cin,line)){
    if(line=="stop")break;
    if(line.rfind("advance ",0)==0)advance=unsigned(std::stoul(line.substr(8)));
    if(line=="scratch busy")scratchMode=1;
    if(line=="scratch free")scratchMode=0;
    if(line=="stats")std::cout<<"{\"accepted\":"<<accepted<<",\"bytes_read\":"<<bytesRead<<",\"bytes_written\":"<<bytesWritten<<",\"live_sockets\":"<<liveSockets<<",\"destroyed\":"<<destroyed
        <<",\"loops\":"<<loops<<",\"loop_ms\":"<<lastLoopTime<<",\"fd\":"<<last_fd<<",\"ioctl\":"<<last_ioctl<<",\"available\":"<<last_available<<",\"select\":"<<last_select<<",\"peek\":"<<last_peek<<"}"<<std::endl;
}done=true;});
std::cout<<M9NormalStageA::server.getServer().port<<std::endl;
while(!done){
    const unsigned tick=advance.exchange(0);if(tick)host_ms+=tick;
    const int scratch=scratchMode.exchange(-1);
    if(scratch>=0){
        if(scratch==1)std::strcpy(M9NormalStageA::responseBody,"SCRATCH_OWNER_SENTINEL");
        else if(std::strcmp(M9NormalStageA::responseBody,"SCRATCH_OWNER_SENTINEL"))return 3;
        M9NormalStageA::responseBusy=scratch==1;
        std::cout<<"{\"scratch_busy\":"<<(scratch==1?"true":"false")<<"}"<<std::endl;
    }
    ++loops;lastLoopTime=millis();M9NormalStageA::loop();if(tick)std::cout<<"{\"advanced\":true}"<<std::endl;
    std::this_thread::sleep_for(std::chrono::milliseconds(1));
}
control.join();eboot_command cmd{};const bool boot=eboot_command_read(&cmd)==0;
bool fs=true;for(size_t i=0x200000;i<ESP.flash.size();++i)fs&=ESP.flash[i]==0xff;
std::cout<<"{\"commit\":"<<boot<<",\"restarts\":"<<ESP.restarts<<",\"writes\":"<<ESP.writeCalls<<",\"fs_preserved\":"<<(fs?"true":"false")<<"}"<<std::endl;
return 0;
}
