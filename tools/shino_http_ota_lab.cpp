// Actual HTTP OTA transfer and pinned Core Updater; flash/RTC replaced by RAM.
#include <iostream>
#include <sstream>
#include <cstdlib>
#include "../ota/firmware/ShinoHttpOta.h"
#include "eboot_command.h"
HostESP ESP;
extern "C" {volatile uint32_t m9_host_rtc[32]{};}
bool healthy=true;
bool check(){return healthy;}
std::vector<uint8_t> decode(const std::string& s){std::vector<uint8_t> out;for(size_t i=0;i+1<s.size();i+=2)out.push_back(uint8_t(std::stoul(s.substr(i,2),nullptr,16)));return out;}
int main(){
    const char* password=std::getenv("SHINO_TEST_SECRET");if(!password)return 2;
    uint8_t key[32];br_sha256_context hash;br_sha256_init(&hash);br_sha256_update(&hash,password,std::strlen(password));br_sha256_out(&hash,key);
    const char* device=std::getenv("SHINO_TEST_DEVICE");if(!device)device="0123456789abcdef";
    if(std::strlen(device)!=16)return 3;
    ShinoHttpOta::Transfer transfer(check);ShinoHttpOta::Budget budget{60000,50000,3248,1};
    eboot_command_clear();std::string line;
    while(std::getline(std::cin,line)){
        std::istringstream in(line);std::string op;in>>op;
        if(op=="BEGIN"){
            unsigned size;std::string sha,build,proof;in>>size>>sha>>build>>proof;
            ShinoHttpOta::Release r{};r.bytes=size;
            if(sha.size()!=64||build.size()!=64||proof.size()!=64){std::cout<<"ERR\n";continue;}
            std::strcpy(r.sha,sha.c_str());std::strcpy(r.build,build.c_str());
            std::cout<<(transfer.begin(r,device,std::string(64,'a').c_str(),std::string(32,'1').c_str(),proof.c_str(),key,ESP.current,budget,true)?"READY\n":"ERR\n");
        }else if(op=="ALIGN_PROBE"){
            alignas(4) uint32_t word=0;
            const bool actualCoreContract=
                !ESP.flashRead(0x1000,&word,1) &&
                !ESP.flashRead(0x1003,&word,1) &&
                !ESP.flashRead(0x1003,&word,4) &&
                ESP.flashRead(0x1000,&word,4);
            std::cout<<(actualCoreContract?"ALIGN_OK\n":"ERR\n");
        }else if(op=="PROOF_GUARD"){
            ShinoHttpOta::ProofWorkspace workspace{};workspace.busy=true;
            std::memset(&workspace.key,0xa5,sizeof(workspace.key));std::memset(&workspace.mac,0xa5,sizeof(workspace.mac));
            const auto owned=workspace;char output[65];std::memset(output,'#',sizeof(output));
            ShinoHttpOta::Release r{};r.bytes=64000;std::strcpy(r.sha,std::string(64,'b').c_str());std::strcpy(r.build,r.sha);
            bool intact=!ShinoHttpOta::proof(workspace,key,"0123456789abcdef",std::string(32,'1').c_str(),r,output);
            intact&=workspace.busy&&!std::memcmp(&workspace.key,&owned.key,sizeof(workspace.key))&&!std::memcmp(&workspace.mac,&owned.mac,sizeof(workspace.mac));
            for(char value:output)intact&=value=='#';
            workspace.busy=false;intact&=ShinoHttpOta::proof(workspace,key,"0123456789abcdef",std::string(32,'1').c_str(),r,output)&&!workspace.busy;
            std::cout<<(intact?"GUARD_OK\n":"ERR\n");
        }else if(op=="DATA"){
            std::string bytes;in>>bytes;auto data=decode(bytes);
            if(transfer.add(data.data(),data.size(),budget))std::cout<<"ACK "<<transfer.received()<<"\n";else std::cout<<"ERR\n";
        }else if(op=="FINISH")std::cout<<(transfer.finish(budget)?"STAGED\n":"ERR\n");
        else if(op=="ABORT"){transfer.abort();std::cout<<"ABORTED\n";}
        else if(op=="HEALTH"){in>>healthy;std::cout<<"HEALTH\n";}
        else if(op=="BUDGET"){unsigned frag;in>>budget.heap>>budget.block>>budget.stack>>frag;budget.frag=uint8_t(frag);std::cout<<"BUDGET\n";}
        else if(op=="FAULT"){std::string fault;in>>fault;ESP.failRead=fault=="read";ESP.failErase=fault=="erase";ESP.failWrite=fault=="write";std::cout<<"FAULT\n";}
        else if(op=="CORRUPT"){unsigned at;in>>at;ESP.flash[transfer.stage()+at]^=1;std::cout<<"CORRUPT\n";}
        else if(op=="REPORT"){
            eboot_command cmd{};const bool boot=eboot_command_read(&cmd)==0;bool fs=true;
            for(size_t i=0x200000;i<ESP.flash.size();++i)fs&=ESP.flash[i]==0xff;
            std::cout<<"{\"commit\":"<<boot<<",\"running\":"<<transfer.running()<<",\"erase\":"<<ESP.eraseCalls<<",\"writes\":"<<ESP.writeCalls<<",\"fs_preserved\":"<<fs<<",\"received\":"<<transfer.received()<<"}\n";
        }else std::cout<<"ERR\n";
        std::cout.flush();
    }
}
