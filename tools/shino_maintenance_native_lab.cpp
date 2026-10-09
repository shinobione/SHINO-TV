// Actual Native adapter/receiver/Core; mock Wi-Fi bytes, flash and reboot only.
#include <iostream>
#include <sstream>
#include <cstdlib>
#include "ShinoWifiNative.h"
#include "eboot_command.h"
HostESP ESP;
extern "C" {volatile uint32_t m9_host_rtc[32]{};}
static std::vector<uint8_t> decode(const std::string& s){std::vector<uint8_t> out;for(size_t i=0;i+1<s.size();i+=2)out.push_back(uint8_t(std::stoul(s.substr(i,2),nullptr,16)));return out;}
int main(){
 const char* password=std::getenv("SHINO_TEST_SECRET");if(!password)return 2;
 const char* id="0123456789abcdef";const char* build="aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa";
 uint8_t key[32];br_sha256_context h;br_sha256_init(&h);br_sha256_update(&h,password,std::strlen(password));br_sha256_out(&h,key);
 ShinoInstall::Native native(id,build,key);bool begun=false;eboot_command_clear();std::string line;
 while(std::getline(std::cin,line)){
  std::istringstream in(line);std::string op;in>>op;
  if(op=="LISTENFAIL"){listenFail=true;std::cout<<"FAULT\n";}
  else if(op=="START"){begun=true;peer.connected=false;std::cout<<(native.begin()?"STARTED\n":"ERR\n");}
  else if(op=="PUMP"){native.pump();std::cout<<(native.failed()?"ERR\n":"PUMPED\n");}
  else if(op=="TIME"){in>>host_ms;std::cout<<"TIME\n";}
  else if(op=="BUDGET"){unsigned f;in>>ESP.heap>>ESP.block>>ESP.stack>>f;ESP.frag=uint8_t(f);std::cout<<"BUDGET\n";}
  else if(op=="POLICY"){unsigned ip;bool ap;in>>ip>>ap;WiFi.mode=ap?WIFI_AP:WIFI_OFF;peer.ip=IPAddress(ip>>24,ip>>16,ip>>8,ip);std::cout<<"POLICY\n";}
  else if(op=="FAULT"){std::string f;in>>f;ESP.failRead=f=="read";ESP.failErase=f=="erase";ESP.failWrite=f=="write";std::cout<<"FAULT\n";}
  else if(op=="CORRUPT"){uint32_t at;in>>at;ESP.flash[0x200000-((100000+4095)&~4095u)+at]^=1;std::cout<<"CORRUPT\n";}
  else if(op=="ABORT"){native.stop();std::cout<<"ABORTED\n";}
  else if(op=="DISCONNECT"){peer.connected=false;native.pump();std::cout<<"DISCONNECTED\n";}
  else if(op=="REPORT"){
   eboot_command command{};bool commit=eboot_command_read(&command)==0,fs=true;for(size_t i=0x200000;i<ESP.flash.size();++i)fs&=ESP.flash[i]==0xff;
   std::cout<<"{\"commit\":"<<commit<<",\"running\":"<<native.busy()<<",\"erase\":"<<ESP.eraseCalls<<",\"writes\":"<<ESP.writeCalls<<",\"fs_preserved\":"<<fs<<",\"listeners\":"<<listeners<<",\"queued\":"<<pending.size()<<",\"connected\":"<<peer.connected<<",\"host_restart_calls\":"<<ESP.restarts<<"}\n";
  }else{
   if(!begun){begun=true;if(!native.begin()){native.stop();peer.connected=false;}else{pending.push_back(&peer);pending.push_back(&extra);}}
   peer.output.clear();
   if(op=="DATA"){std::string bytes;in>>bytes;auto raw=decode(bytes);peer.input.assign(reinterpret_cast<char*>(raw.data()),raw.size());}
   else peer.input=line+'\n';
   for(unsigned i=0;i<10 && peer.output.empty() && !native.failed();++i)native.pump();
   if(peer.output.empty())std::cout<<"ERR\n";else std::cout<<peer.output;
  }
  std::cout.flush();
 }
}
