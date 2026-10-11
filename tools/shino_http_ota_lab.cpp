// Actual HTTP OTA transfer and pinned Core Updater; flash/RTC replaced by RAM.
#include <iostream>
#include <sstream>
#include <cstdlib>
#include <fstream>
#include <map>
#ifdef SHINO_TEST_OTA_SAFETY
#include "safety_receiver.h"
#elif defined(SHINO_TEST_LEGACY_FLASH_READER)
#include "legacy_receiver.h"
#else
#include "../ota/firmware/ShinoHttpOta.h"
#endif
#include "eboot_command.h"
HostESP ESP;
extern "C" {volatile uint32_t m9_host_rtc[32]{};}
bool healthy=true;
uint32_t unhealthyAfter=UINT32_MAX;
#ifdef SHINO_TEST_OTA_SAFETY
// Logical budgets include only explicit test pressure and the real Core buffer
// allocation request. They do not model ROM/SDK/IRQ or an actual allocator.
struct SafetyCut {};
struct SafetyResources {uint32_t heap=60000,block=50000,stack=3248;uint8_t frag=1;};
static SafetyResources resources,minimum;
static uint32_t stackWatermark=3248;
static std::string phase="admission",pressurePhase,cutKind,cutMode;
static uint32_t pressureHeap=0,pressureBlock=0,pressureStack=0,cutAt=0;
static unsigned pressureFrag=0;
static size_t liveAllocation=0,allocationRequested=0,allocationOverhead=16;
static bool allocationFail=false,cutSeen=false,unsafeSeen=false;
static std::map<std::string,unsigned> observations,samples;
uint32_t safety_fs_start=0x40400000;
static ShinoHttpOta::Budget safety_budget(){
    const bool inject=phase==pressurePhase;
    auto subtract=[](uint32_t value,size_t cost){return uint32_t(value>cost?value-cost:0);};
    const size_t allocation=liveAllocation?liveAllocation+allocationOverhead:0;
    // ESP.getFreeContStack() reports historical high water: a released frame
    // must NEVER repaint a prior low stack watermark as fresh headroom.
    stackWatermark=std::min(stackWatermark,subtract(resources.stack,inject?pressureStack:0));
    const uint32_t heap=subtract(resources.heap,allocation+(inject?pressureHeap:0));
    return {heap,std::min(heap,subtract(resources.block,allocation+(inject?pressureBlock:0))),
        stackWatermark,uint8_t(inject&&pressureFrag?pressureFrag:resources.frag)};
}
static void observe(){
    const auto b=safety_budget();++observations[phase];unsafeSeen|=!b.safe();
    minimum.heap=std::min(minimum.heap,b.heap);minimum.block=std::min(minimum.block,b.block);
    minimum.stack=std::min(minimum.stack,b.stack);minimum.frag=std::max(minimum.frag,b.frag);
}
void safety_phase(const char* next){phase=next;observe();}
uint32_t safety_heap(){observe();return safety_budget().heap;}
bool safety_before(const char* kind,uint32_t at,size_t n){
    std::string event=kind;
    if(event=="stage_read"&&phase=="commit")event="commit_read";
    if(event!=cutKind||at!=cutAt)return true;
    if(cutMode=="fail")return false;
    if(cutMode=="partial"){
        // An arbitrary torn flash operation; physical bit-level behaviour is
        // unknown. No rollback or valid image is inferred from this model.
        if(event.find("write")!=std::string::npos||event.find("erase")!=std::string::npos){
            if(at>ESP.flash.size()||n>ESP.flash.size()-at)throw std::runtime_error("Invalid fault extent");
            std::fill(ESP.flash.begin()+at,ESP.flash.begin()+at+std::min(size_t(128),n),0x55);
        }
        cutSeen=true;throw SafetyCut{};
    }
    if(cutMode=="before"){cutSeen=true;throw SafetyCut{};}
    return true;
}
void safety_after(const char* kind,uint32_t at){
    std::string event=kind;if(event=="stage_read"&&phase=="commit")event="commit_read";
    if(event==cutKind&&at==cutAt&&cutMode=="after"){cutSeen=true;throw SafetyCut{};}
}
uint8_t* safety_alloc(size_t n){
    allocationRequested=n;safety_phase("allocation");
    if(!safety_before("allocation",0,n)||allocationFail)return nullptr;
    auto* buffer=static_cast<uint8_t*>(std::malloc(n));
    if(buffer){liveAllocation=n;observe();safety_after("allocation",0);}return buffer;
}
void safety_free(uint8_t* buffer){std::free(buffer);liveAllocation=0;}
extern "C" void shino_test_rtc_write(unsigned at,unsigned value){
    if(!safety_before("rtc_word",at,4))return;
    m9_host_rtc[at]=value;safety_after("rtc_word",at);
}
struct SafetyProbe {static uint32_t stage(const UpdaterClass& c){return uint32_t(c._startAddress);}};
namespace ShinoHttpOta {struct TransferProbe {static uint32_t coreStage(const Transfer& t){return SafetyProbe::stage(t.core_);}};}
bool check(){++samples[phase];observe();return healthy&&ESP.readCalls<unhealthyAfter&&safety_budget().safe();}
#else
bool check(){return healthy&&ESP.readCalls<unhealthyAfter;}
#endif
std::vector<uint8_t> decode(const std::string& s){std::vector<uint8_t> out;for(size_t i=0;i+1<s.size();i+=2)out.push_back(uint8_t(std::stoul(s.substr(i,2),nullptr,16)));return out;}
#ifdef SHINO_TEST_EBOOT
#include "pinned_boot_flash.h"
static uint32_t modelEntry=0,modelBytes=0,bootErases=0,bootWrites=0;
static bool booted=false,copyPhase=false;
static int copyResult=-1;
static bool destinationShaMatches=false;
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
#ifdef SHINO_TEST_OTA_SAFETY
    if(copyPhase&&n==4096){
        if(!safety_before(at<ShinoHttpOta::rounded(modelBytes)?"copy_destination_read":"copy_read",at,n))return 1;
        std::memcpy(out,ESP.flash.data()+at,n);
        safety_after(at<ShinoHttpOta::rounded(modelBytes)?"copy_destination_read":"copy_read",at);return 0;
    }
#endif
    return ESP.flashRead(at,out,n)?0:1;
}
int SPIEraseSector(uint32_t sector){
    if(sector>=ShinoHttpOta::rounded(modelBytes)/4096||ESP.failErase)return 1;
#ifdef SHINO_TEST_OTA_SAFETY
    if(!safety_before("copy_erase",sector*4096,4096))return 1;
#endif
    ++bootErases;std::fill(ESP.flash.begin()+sector*4096,ESP.flash.begin()+(sector+1)*4096,255);
#ifdef SHINO_TEST_OTA_SAFETY
    safety_after("copy_erase",sector*4096);
#endif
    return 0;
}
int SPIWrite(uint32_t at,void* data,size_t n){
    if((at&3u)||(n&3u)||(uintptr_t(data)&3u)||at>ShinoHttpOta::rounded(modelBytes)||
       n>ShinoHttpOta::rounded(modelBytes)-at||ESP.failWrite)return 1;
#ifdef SHINO_TEST_OTA_SAFETY
    if(!safety_before("copy_write",at,n))return 1;
#endif
    ++bootWrites;std::memcpy(ESP.flash.data()+at,data,n);
#ifdef SHINO_TEST_OTA_SAFETY
    safety_after("copy_write",at);
#endif
    return 0;
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
#ifdef SHINO_TEST_OTA_SAFETY
    uint32_t coreStage=0;
    UpdaterClass directCore;
#endif
    // Non-erased sentinel data catches unwanted FS/reserved writes, rather
    // than comparing an all-ff filesystem with another all-ff filesystem.
    for(size_t i=0x200000;i<ESP.flash.size();++i)ESP.flash[i]=uint8_t((i*37+(i>>8))&255);
    auto original=ESP.flash;
    eboot_command_clear();std::string line;
    while(std::getline(std::cin,line)){
        std::istringstream in(line);std::string op;in>>op;
#ifdef SHINO_TEST_OTA_SAFETY
        try{
        budget=safety_budget();
#endif
        if(op=="BEGIN"){
            unsigned size;std::string sha,build,proof;in>>size>>sha>>build>>proof;
            ShinoHttpOta::Release r{};r.bytes=size;
            if(sha.size()!=64||build.size()!=64||proof.size()!=64){std::cout<<"ERR\n";continue;}
            std::strcpy(r.sha,sha.c_str());std::strcpy(r.build,build.c_str());
            expectedSha=sha;expectedBytes=size;
            const bool ready=transfer.begin(r,device,currentBuild.c_str(),std::string(32,'1').c_str(),proof.c_str(),key,ESP.current,budget,true);
#ifdef SHINO_TEST_OTA_SAFETY
            coreStage=ShinoHttpOta::TransferProbe::coreStage(transfer);
#endif
            std::cout<<(ready?"READY\n":"ERR\n");
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
                copyResult=copy_raw(cmd.args[0],cmd.args[1],cmd.args[2],false);copyPhase=false;
                eboot_command_clear();
                uint8_t digest[32];char sha[65];br_sha256_context h;br_sha256_init(&h);
                br_sha256_update(&h,ESP.flash.data(),expectedBytes);br_sha256_out(&h,digest);ShinoHttpOta::encode(digest,32,sha);
                destinationShaMatches=expectedSha==sha;
                booted=copyResult==0&&destinationShaMatches&&load_app_from_flash_raw(0)==0&&
                    modelEntry>=0x40100000&&modelEntry<0x4010c000;
                std::cout<<(booted?"BOOT_MODEL_OK\n":"ERR\n");
            }
#ifdef SHINO_TEST_OTA_SAFETY
        }else if(op=="RESOURCES"){
            unsigned frag;in>>resources.heap>>resources.block>>resources.stack>>frag;resources.frag=uint8_t(frag);
            stackWatermark=std::min(stackWatermark,resources.stack);
            minimum=resources;safety_phase("admission");std::cout<<"RESOURCES\n";
        }else if(op=="PRESSURE"){
            in>>pressurePhase>>pressureHeap>>pressureBlock>>pressureStack>>pressureFrag;std::cout<<"PRESSURE\n";
        }else if(op=="CUT"){
            in>>cutKind>>cutAt>>cutMode;std::cout<<"ARMED\n";
        }else if(op=="ALLOC_FAIL"){
            allocationFail=true;std::cout<<"FAULT\n";
        }else if(op=="LAYOUT"){
            in>>safety_fs_start;std::cout<<"LAYOUT\n";
        }else if(op=="MODE"){
            in>>ESP.mode;std::cout<<"MODE\n";
        }else if(op=="LOAD_FS"){
            std::string path;std::getline(in,path);path.erase(0,1);
            std::ifstream input(path,std::ios::binary);std::vector<uint8_t> fs{std::istreambuf_iterator<char>(input),{}};
            if(fs.size()!=0x1fa000)std::cout<<"ERR\n";
            else{std::copy(fs.begin(),fs.end(),ESP.flash.begin()+0x200000);original=ESP.flash;std::cout<<"FS_LOADED\n";}
        }else if(op=="DUMP_FS"){
            std::string path;std::getline(in,path);path.erase(0,1);std::ofstream output(path,std::ios::binary);
            output.write(reinterpret_cast<const char*>(ESP.flash.data()+0x200000),0x1fa000);
            std::cout<<(output?"FS_DUMPED\n":"ERR\n");
        }else if(op=="CORE_BEGIN"){
            unsigned size;in>>size;const bool ok=directCore.begin(size,U_FLASH);
            coreStage=SafetyProbe::stage(directCore);std::cout<<(ok?"READY\n":"ERR\n");
        }else if(op=="CORE_ABORT"){
            directCore.shinoAbort();std::cout<<"ABORTED\n";
        }else if(op=="BOOT_SKIP_PROBE"){
            modelBytes=expectedBytes;copyPhase=true;const unsigned before=bootErases;
            const int result=copy_raw(transfer.stage(),0,4096,false);copyPhase=false;
            std::cout<<(result==0&&bootErases==before?"SKIPPED\n":"ERR\n");
#endif
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
#ifdef SHINO_TEST_OTA_SAFETY
            // The actual Normal.cpp loop samples before each delivery. Preserve
            // that external check as well as Transfer's budget argument.
            if(!check()){transfer.abort();std::cout<<"ERR\n";}
            else
#endif
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
                <<",\"loaded_segments\":"<<loaded.size()<<",\"entry\":"<<modelEntry
                <<",\"boot_copy_result\":"<<copyResult<<",\"destination_sha_matches\":"<<destinationShaMatches;
#endif
#ifdef SHINO_TEST_OTA_SAFETY
            const auto b=safety_budget();
            std::cout<<",\"allocation_requested\":"<<allocationRequested<<",\"allocation_live\":"<<liveAllocation
                <<",\"allocation_overhead_model\":"<<allocationOverhead<<",\"core_stage\":"<<coreStage
                <<",\"receiver_stage\":"<<transfer.stage()<<",\"cut_seen\":"<<cutSeen<<",\"unsafe_seen\":"<<unsafeSeen
                <<",\"heap\":"<<b.heap<<",\"heap_min_model\":"<<minimum.heap
                <<",\"block_min_model\":"<<minimum.block<<",\"stack_min_model\":"<<minimum.stack
                <<",\"observations\":{";
            bool separator=false;for(const auto& item:observations){if(separator)std::cout<<",";separator=true;std::cout<<"\""<<item.first<<"\":"<<item.second;}
            std::cout<<"},\"samples\":{";separator=false;
            for(const auto& item:samples){if(separator)std::cout<<",";separator=true;std::cout<<"\""<<item.first<<"\":"<<item.second;}
            std::cout<<"}";
#endif
            std::cout<<"}\n";
        }else std::cout<<"ERR\n";
#ifdef SHINO_TEST_OTA_SAFETY
        }catch(const SafetyCut&){cutSeen=true;std::cout<<"CUT\n";}
#endif
        std::cout.flush();
    }
}
