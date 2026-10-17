// Actual pinned Core Updater/abort adaptation and receiver run against RAM.
#include <iostream>
#include <sstream>
#include <string>
#include <cstdlib>
#include <Updater.h>
#include "ShinoWifiUpdate.h"
#include "eboot_command.h"
HostESP ESP;
extern "C" {volatile uint32_t m9_host_rtc[32]{};}
std::vector<uint8_t> decode(const std::string& s){std::vector<uint8_t> out;for(size_t i=0;i+1<s.size();i+=2)out.push_back(uint8_t(std::stoul(s.substr(i,2),nullptr,16)));return out;}
int main(){
    const char* password=std::getenv("SHINO_TEST_SECRET");if(!password)return 2;
    const char* device="0123456789abcdef";const char* build="aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa";
    const char* nonce="0123456789abcdef0123456789abcdef";
    uint8_t key[32];br_sha256_context hash;br_sha256_init(&hash);br_sha256_update(&hash,password,std::strlen(password));br_sha256_out(&hash,key);
    ShinoInstall::Receiver receiver(device,build,key);std::string line;uint32_t now=1,peer=0xc0a80402;bool privateAp=true;
    ShinoInstall::Budget budget{60000,50000,3248,1};eboot_command_clear();
    while(std::getline(std::cin,line)){
        std::istringstream in(line);std::string op;in>>op;
        if(op=="CAP"){std::string id,cn;in>>id>>cn;char out[512];
            if(id==device && receiver.capability(cn.c_str(),nonce,peer,privateAp,now,out,sizeof(out)))std::cout<<out;else std::cout<<"ERR\n";}
        else if(op=="AUTH"){unsigned command,size;std::string sha,next,proof;in>>command>>size>>sha>>next>>proof;
            std::cout<<(receiver.authorize(command,size,sha.c_str(),next.c_str(),proof.c_str(),peer,privateAp,now,budget,ESP.current)?"READY\n":"ERR\n");}
        else if(op=="DATA"){std::string bytes;in>>bytes;auto data=decode(bytes);if(receiver.add(data.data(),data.size(),now,budget))std::cout<<"ACK "<<receiver.received()<<"\n";else std::cout<<"ERR\n";}
        else if(op=="COMMIT"){if(receiver.commit(now,budget))std::cout<<"STAGED "<<receiver.nextBuild()<<"\n";else std::cout<<"ERR\n";}
        else if(op=="TIME"){in>>now;std::cout<<"TIME\n";}
        else if(op=="BUDGET"){unsigned frag;in>>budget.heap>>budget.block>>budget.stack>>frag;budget.frag=uint8_t(frag);std::cout<<"BUDGET\n";}
        else if(op=="POLICY"){in>>peer>>privateAp;std::cout<<"POLICY\n";}
        else if(op=="FAULT"){std::string fault;in>>fault;ESP.failRead=fault=="read";ESP.failErase=fault=="erase";ESP.failWrite=fault=="write";std::cout<<"FAULT\n";}
        else if(op=="CORRUPT"){uint32_t at;in>>at;ESP.flash[0x200000-((100000+4095)&~4095u)+at]^=1;std::cout<<"CORRUPT\n";}
        else if(op=="ABORT"){receiver.abort();std::cout<<"ABORTED\n";}
        else if(op=="REPORT"){
            eboot_command cmd{};bool boot=eboot_command_read(&cmd)==0;bool fs=true;for(size_t i=0x200000;i<ESP.flash.size();++i)fs&=ESP.flash[i]==0xff;
            std::cout<<"{\"commit\":"<<boot<<",\"running\":"<<!receiver.bufferReleased()<<",\"erase\":"<<ESP.eraseCalls<<",\"writes\":"<<ESP.writeCalls<<",\"fs_preserved\":"<<fs<<",\"received\":"<<receiver.received()<<"}\n";
        }else std::cout<<"ERR\n";
        std::cout.flush();
    }
}
