// Actual HTTP OTA transfer and pinned Core Updater; flash/RTC replaced by RAM.
#include <iostream>
#include <sstream>
#include <cstdlib>
#include <fstream>
#include <map>
#ifdef SHINO_TEST_LEGACY_FLASH_READER
#include "legacy_receiver.h"
#else
#include "../ota/firmware/ShinoHttpOta.h"
#endif
#include "eboot_command.h"
HostESP ESP;
extern "C" {volatile uint32_t m9_host_rtc[32]{};}
bool healthy=true;
uint32_t unhealthyAfter=UINT32_MAX;
bool check(){return healthy&&ESP.readCalls<unhealthyAfter;}
std::vector<uint8_t> decode(const std::string& s){std::vector<uint8_t> out;for(size_t i=0;i+1<s.size();i+=2)out.push_back(uint8_t(std::stoul(s.substr(i,2),nullptr,16)));return out;}
#ifdef SHINO_TEST_EBOOT
#include "pinned_boot_flash.h"
static uint32_t modelEntry=0,modelBytes=0,bootErases=0,bootWrites=0;
static bool booted=false,copyPhase=false;
static std::map<uint32_t,std::vector<uint8_t>> loaded;
int SPIRead(uint32_t at,void* out,size_t n){
    const auto address=uintptr_t(out);
    if(at>ESP.flash.size()||n>ESP.flash.size()-at||ESP.failRead)return 1;
    if(address>=0x3ffe8000&&address<0x4010c000){
        if(!((address<0x40000000&&n<=0x40000000-address)||
             (address>=0x40100000&&n<=0x4010c000-address)))return 1;
        loaded[uint32_t(address)]={ESP.flash.begin()+at,ESP.flash.begin()+at+n};return 0;
    }
    if(copyPhase&&((at&3u)||(n&3u)||(address&3u)))return 1;
    return ESP.flashRead(at,out,n)?0:1;
}
int SPIEraseSector(uint32_t sector){
    if(sector>=ShinoHttpOta::rounded(modelBytes)/4096||ESP.failErase)return 1;
    ++bootErases;std::fill(ESP.flash.begin()+sector*4096,ESP.flash.begin()+(sector+1)*4096,255);return 0;
}
int SPIWrite(uint32_t at,void* data,size_t n){
    if((at&3u)||(n&3u)||(uintptr_t(data)&3u)||at>ShinoHttpOta::rounded(modelBytes)||
       n>ShinoHttpOta::rounded(modelBytes)-at||ESP.failWrite)return 1;
    ++bootWrites;std::memcpy(ESP.flash.data()+at,data,n);return 0;
}
static void ets_putc(char){}
struct uzlib_uncomp {const uint8_t *source,*source_limit;uint8_t *dest_start,*dest,*dest_limit;int(*source_read_cb)(uzlib_uncomp*);};
static uint8_t gzip_dict[32768],buffer2[4096];static uint32_t uzlib_flash_read_cb_addr;
static int uzlib_flash_read_cb(uzlib_uncomp*){return -1;}
static void uzlib_init(){}
static void uzlib_uncompress_init(uzlib_uncomp*,void*,size_t){}
static int uzlib_gzip_parse_header(uzlib_uncomp*){return -1;}
static int uzlib_uncompress(uzlib_uncomp*){return -1;}
#define TINF_OK 0
#define TINF_DONE 1
#define APP_START_OFFSET 0x1000
#include "pinned_http_eboot.inc"
#endif
int main(){
    const char* password=std::getenv("SHINO_TEST_SECRET");if(!password)return 2;
    uint8_t key[32];br_sha256_context hash;br_sha256_init(&hash);br_sha256_update(&hash,password,std::strlen(password));br_sha256_out(&hash,key);
    const char* device=std::getenv("SHINO_TEST_DEVICE");if(!device)device="0123456789abcdef";
    if(std::strlen(device)!=16)return 3;
    ShinoHttpOta::Transfer transfer(check);ShinoHttpOta::Budget budget{60000,50000,3248,1};
    std::string currentBuild(64,'a'),expectedSha;
    uint32_t expectedBytes=0;
    // Non-erased sentinel data catches unwanted FS/reserved writes, rather
    // than comparing an all-ff filesystem with another all-ff filesystem.
    for(size_t i=0x200000;i<ESP.flash.size();++i)ESP.flash[i]=uint8_t((i*37+(i>>8))&255);
    auto original=ESP.flash;
    eboot_command_clear();std::string line;
    while(std::getline(std::cin,line)){
        std::istringstream in(line);std::string op;in>>op;
        if(op=="BEGIN"){
            unsigned size;std::string sha,build,proof;in>>size>>sha>>build>>proof;
            ShinoHttpOta::Release r{};r.bytes=size;
            if(sha.size()!=64||build.size()!=64||proof.size()!=64){std::cout<<"ERR\n";continue;}
            std::strcpy(r.sha,sha.c_str());std::strcpy(r.build,build.c_str());
            expectedSha=sha;expectedBytes=size;
            std::cout<<(transfer.begin(r,device,currentBuild.c_str(),std::string(32,'1').c_str(),proof.c_str(),key,ESP.current,budget,true)?"READY\n":"ERR\n");
#ifdef SHINO_TEST_EBOOT
        }else if(op=="LOAD_CURRENT"){
            std::string path;std::getline(in,path);path.erase(0,1);
            std::ifstream input(path,std::ios::binary);std::vector<uint8_t> raw{std::istreambuf_iterator<char>(input),{}};
            const std::string bytes(raw.begin(),raw.end()),prefix=std::string("SHINO-HTTP-OTA-1|")+device+"|";
            const auto tag=bytes.find(prefix);
            if(raw.size()<64000||raw.size()>ShinoHttpOta::MaxImage||tag==std::string::npos){std::cout<<"ERR\n";}
            else{
                std::copy(raw.begin(),raw.end(),ESP.flash.begin());ESP.current=uint32_t(raw.size());
                currentBuild=bytes.substr(tag+prefix.size(),64);original=ESP.flash;std::cout<<"CURRENT_LOADED\n";
            }
        }else if(op=="BOOT"){
            eboot_command cmd{};
            if(eboot_command_read(&cmd)!=0||cmd.action!=ACTION_COPY_RAW||cmd.args[0]!=transfer.stage()||
               cmd.args[1]!=0||cmd.args[2]!=expectedBytes){std::cout<<"ERR\n";}
            else{
                modelBytes=expectedBytes;copyPhase=true;
                const int result=copy_raw(cmd.args[0],cmd.args[1],cmd.args[2],false);copyPhase=false;
                eboot_command_clear();
                uint8_t digest[32];char sha[65];br_sha256_context h;br_sha256_init(&h);
                br_sha256_update(&h,ESP.flash.data(),expectedBytes);br_sha256_out(&h,digest);ShinoHttpOta::encode(digest,32,sha);
                booted=result==0&&expectedSha==sha&&load_app_from_flash_raw(0)==0&&
                    modelEntry>=0x40100000&&modelEntry<0x4010c000;
                std::cout<<(booted?"BOOT_MODEL_OK\n":"ERR\n");
            }
#endif
        }else if(op=="ALIGN_PROBE"){
            alignas(4) uint32_t word=0;
            const bool actualCoreContract=
                !ESP.flashRead(0x1000,&word,1) &&
                !ESP.flashRead(0x1003,&word,1) &&
                !ESP.flashRead(0x1003,&word,4) &&
                ESP.flashRead(0x1000,&word,4);
            std::cout<<(actualCoreContract?"ALIGN_OK\n":"ERR\n");
        }else if(op=="CURRENT_BUILD"){
            std::string value;in>>value;
            if(!ShinoHttpOta::hex(value.c_str(),64))std::cout<<"ERR\n";
            else{currentBuild=value;std::cout<<"CURRENT_SET\n";}
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
        else if(op=="HEALTH_AFTER"){in>>unhealthyAfter;std::cout<<"HEALTH\n";}
        else if(op=="BUDGET"){unsigned frag;in>>budget.heap>>budget.block>>budget.stack>>frag;budget.frag=uint8_t(frag);std::cout<<"BUDGET\n";}
        else if(op=="FAULT"){std::string fault;in>>fault;ESP.failRead=fault=="read";ESP.failErase=fault=="erase";ESP.failWrite=fault=="write";std::cout<<"FAULT\n";}
        else if(op=="CORRUPT"){unsigned at;in>>at;ESP.flash[transfer.stage()+at]^=1;std::cout<<"CORRUPT\n";}
        else if(op=="REPORT"){
            eboot_command cmd{};const bool boot=eboot_command_read(&cmd)==0;bool fs=true;
            fs=std::equal(ESP.flash.begin()+0x200000,ESP.flash.begin()+0x3fa000,original.begin()+0x200000);
            const bool reserved=std::equal(ESP.flash.begin()+0x3fa000,ESP.flash.end(),original.begin()+0x3fa000);
            const bool current=std::equal(ESP.flash.begin(),ESP.flash.begin()+ShinoHttpOta::rounded(ESP.current),original.begin());
            std::cout<<"{\"commit\":"<<boot<<",\"running\":"<<transfer.running()<<",\"erase\":"<<ESP.eraseCalls<<",\"writes\":"<<ESP.writeCalls<<",\"fs_preserved\":"<<fs
                <<",\"reserved_preserved\":"<<reserved<<",\"current_preserved\":"<<current<<",\"received\":"<<transfer.received()
                <<",\"rejected_word_reads\":"<<ESP.rejectedReads;
#ifdef SHINO_TEST_EBOOT
            std::cout<<",\"boot_model\":"<<booted<<",\"boot_erase\":"<<bootErases<<",\"boot_writes\":"<<bootWrites
                <<",\"loaded_segments\":"<<loaded.size()<<",\"entry\":"<<modelEntry;
#endif
            std::cout<<"}\n";
        }else std::cout<<"ERR\n";
        std::cout.flush();
    }
}
