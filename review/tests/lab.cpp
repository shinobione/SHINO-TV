// Complete generated B5.3 graph; only radio/SDK/LCD/time/flash seams are HOST.
#include <mutex>
#include <deque>
#define main priorNetworkMain
#include "network_lab.cpp"
#undef main
static unsigned nestedCalls=0;
static void stats(){
 const auto m=FslessMetrics::snapshot();
 std::cout<<"{\"sdk_writes\":"<<testWrites<<",\"flash_writes\":"<<ESP.writeCalls
 <<",\"restarts\":"<<ESP.restarts<<",\"nested_calls\":"<<nestedCalls
 <<",\"samples\":"<<M9NormalStageA::diagnosticJournal.control.word[B53Diagnostic::Samples]
 <<",\"cpu\":"<<m.cpu<<",\"gpu\":"<<m.gpu<<",\"ram\":"<<m.memoryGb<<",\"temperature\":"<<m.gpuTempC
 <<",\"lcd_operations\":"<<DisplayManager::gfx.operations<<"}"<<std::endl;
}
int main(){
#ifdef _WIN32
 WSADATA w{};if(WSAStartup(MAKEWORD(2,2),&w))return 2;
#endif
 if(const char* path=std::getenv("SHINO_TEST_CURRENT_BIN")){
  std::ifstream input(path,std::ios::binary);std::vector<uint8_t> raw{std::istreambuf_iterator<char>(input),{}};
  assert(raw.size()>=64000 && raw.size()<=ShinoHttpOta::MaxImage);
  std::copy(raw.begin(),raw.end(),ESP.flash.begin());ESP.current=uint32_t(raw.size());
 }
 testSaved={};WiFi=WiFiFixture();host_ms=100;ESP.heap=60000;
 ConfigManager config;M9NormalStageA::beforeSetup();M9NormalStageA::begin(config);M9NormalStageA::afterSetup();
 lab_real_clock=true;std::mutex mutex;std::deque<std::string> commands;bool stop=false;
 std::thread input([&](){std::string command;while(std::getline(std::cin,command)){
  std::lock_guard<std::mutex> lock(mutex);commands.push_back(command);if(command=="stop")break;
 }});
 std::cout<<M9NormalStageA::server.getServer().port<<std::endl;
 while(!stop){
  std::string command;{std::lock_guard<std::mutex> lock(mutex);if(!commands.empty()){command=commands.front();commands.pop_front();}}
  if(!command.empty()){
   if(command=="sntp"){if(sntpCallback)sntpCallback(true);std::cout<<"{\"ok\":true}"<<std::endl;continue;}
   if(command=="display reset"){DisplayManager::gfx.clearPrinted();std::cout<<"{\"ok\":true}"<<std::endl;continue;}
   if(command=="display"){
    const auto& gfx=DisplayManager::gfx;
    std::cout<<"{\"temp\":"<<(gfx.has("18.2")?"true":"false")
             <<",\"condition\":"<<(gfx.has("Cloudy")?"true":"false")
             <<",\"stale\":"<<(gfx.has("WEATHER STALE")?"true":"false")
             <<",\"unavailable\":"<<(gfx.has("WEATHER --")?"true":"false")
             <<",\"cpu\":"<<(gfx.has("CPU")?"true":"false")
             <<",\"gpu\":"<<(gfx.has("GPU")?"true":"false")
             <<",\"ram\":"<<(gfx.has("RAM")?"true":"false")
             <<",\"gpu_temp\":"<<(gfx.has("GPU temp")?"true":"false")
             <<",\"text_count\":"<<gfx.printed.size()
             <<",\"operations\":"<<gfx.operations<<"}"<<std::endl;
    continue;
   }
   if(command=="stats"){stats();continue;}
   if(command=="stop"){stop=true;continue;}
   if(command=="mode lan"){WiFi.wifiStatus=WL_CONNECTED;WiFi.sta=IPAddress(10,23,42,82);testLocal=WiFi.sta;testPeer=IPAddress(10,23,42,10);}
   if(command=="heap low")ESP.heap=20479;
   if(command=="heap normal")ESP.heap=60000;
   if(command=="mode ap"){testLocal=IPAddress(192,168,4,1);testPeer=IPAddress(192,168,4,2);}
   if(command=="peer foreign")testPeer=IPAddress(192,168,2,10);
   if(command=="network lost"){WiFi.wifiStatus=0;WiFi.sta=IPAddress();}
   if(command=="freeze")M9NormalStageA::diagnosticJournal.stop(0x900);
   if(command=="hold response")M9NormalStageA::responseBusy=true;
   if(command=="release response")M9NormalStageA::responseBusy=false;
   if(command=="arm nested")hostReentryHook=[](){if(M9NormalStageA::httpBusy){++nestedCalls;M9NormalStageA::loop();}};
   if(command=="disarm nested")hostReentryHook=nullptr;
   if(command.rfind("advance ",0)==0)host_ms+=uint32_t(std::stoul(command.substr(8)));
   B5Lan::poll(false);std::cout<<"{\"ok\":true}"<<std::endl;
  }
  M9NormalStageA::loop();std::this_thread::sleep_for(std::chrono::milliseconds(1));
 }
 input.join();stats();return 0;
}
