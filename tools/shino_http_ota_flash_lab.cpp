// Real receiver byte reader vs extracted Core 3.1.2 typed flashRead.
// SPI/flash is RAM; this does not measure an ESP8266 or contact hardware.
#include <iostream>
#include <stdexcept>
#include "../ota/firmware/ShinoHttpOta.h"
HostESP ESP;
extern "C" {volatile uint32_t m9_host_rtc[32]{};}
constexpr int SPI_FLASH_RESULT_OK=0;
static int spi_flash_read(uint32_t at,uint32_t* p,size_t n){
    if((at&3u)||(n&3u)||(uintptr_t(p)&3u)||!p||at>ESP.flash.size()||n>ESP.flash.size()-at)return 1;
    std::memcpy(p,ESP.flash.data()+at,n);return SPI_FLASH_RESULT_OK;
}
struct ReferenceESP {bool flashRead(uint32_t,uint32_t*,size_t);};
#include "pinned_flash_read.inc"
namespace ShinoHttpOta {
struct TransferProbe {
    static void seed(Transfer& t,uint32_t stage,uint32_t bytes){t.stage_=stage;t.release_.bytes=bytes;}
    static bool read(Transfer& t,uint32_t at,void* out,size_t n){return t.read(at,out,n);}
};
}
static unsigned checks=0,reads=0;
static void require(bool b){++checks;if(!b)throw std::runtime_error("Flash contract regression");}
int main()try{
    ReferenceESP real;ShinoHttpOta::Transfer transfer;
    constexpr uint32_t stage=0x1ff000,bytes=4096;
    for(size_t i=0;i<ESP.flash.size();++i)ESP.flash[i]=uint8_t((i*37+(i>>8))&255);
    ShinoHttpOta::TransferProbe::seed(transfer,stage,bytes);
    const unsigned sizes[]={1,2,3,4,5,15,16,127,128,129};
    alignas(4) uint8_t out[160];
    for(unsigned offset=0;offset<4;++offset)for(unsigned size:sizes)for(unsigned dest=0;dest<4;++dest){
        std::memset(out,0xa5,sizeof(out));
        const bool expected=(offset%4==0&&size%4==0&&dest%4==0);
        require(real.flashRead(stage+offset,reinterpret_cast<uint32_t*>(out+4+dest),size)==expected);
        require(ESP.flashRead(stage+offset,reinterpret_cast<uint32_t*>(out+4+dest),size)==expected);
        std::memset(out,0xa5,sizeof(out));
        require(ShinoHttpOta::TransferProbe::read(transfer,offset,out+4+dest,size));++reads;
        require(!std::memcmp(out+4+dest,ESP.flash.data()+stage+offset,size));
        for(unsigned i=0;i<4+dest;++i)require(out[i]==0xa5);
        for(unsigned i=4+dest+size;i<sizeof(out);++i)require(out[i]==0xa5);
    }
    // Every possible byte-sized image tail, ending immediately before FS.
    for(unsigned tail=0;tail<4;++tail){
        const uint32_t actual=bytes-tail;ShinoHttpOta::TransferProbe::seed(transfer,stage,actual);
        for(unsigned size:sizes)for(unsigned dest=0;dest<4;++dest){
            std::memset(out,0xa5,sizeof(out));
            require(ShinoHttpOta::TransferProbe::read(transfer,actual-size,out+4+dest,size));++reads;
            require(!std::memcmp(out+4+dest,ESP.flash.data()+stage+actual-size,size));
            const auto calls=ESP.readCalls;
            require(!ShinoHttpOta::TransferProbe::read(transfer,actual-size+1,out,size));
            require(ESP.readCalls==calls); // Refuse before any hardware read.
        }
        for(uint32_t at:{actual,actual+1,UINT32_MAX}){
            const auto calls=ESP.readCalls;
            require(!ShinoHttpOta::TransferProbe::read(transfer,at,out,1));
            require(ESP.readCalls==calls);
        }
    }
    ShinoHttpOta::TransferProbe::seed(transfer,stage,bytes);
    const auto calls=ESP.readCalls;
    require(!ShinoHttpOta::TransferProbe::read(transfer,0,out,0));
    require(!ShinoHttpOta::TransferProbe::read(transfer,0,nullptr,1));
    require(!ShinoHttpOta::TransferProbe::read(transfer,1,out,SIZE_MAX));
    require(ESP.readCalls==calls);
    ESP.failRead=true;require(!ShinoHttpOta::TransferProbe::read(transfer,1,out,1));ESP.failRead=false;
    require(ESP.readFirst>=stage&&ESP.readEnd<=0x200000);
    // The historical direct uint32_t* reader deterministically fails the
    // footer that ends an otherwise valid ESP image. Correct reader succeeds.
    alignas(4) uint32_t last=0;
    require(!ESP.flashRead(stage+bytes-1,&last,1));
    require(ShinoHttpOta::TransferProbe::read(transfer,bytes-1,&last,1));
    // Reject a corrupted internal range before crossing into LittleFS.
    ShinoHttpOta::TransferProbe::seed(transfer,0x200000,bytes);
    require(!ShinoHttpOta::TransferProbe::read(transfer,0,out,1));
    require(ESP.eraseCalls==0&&ESP.writeCalls==0);
    std::cout<<"{\"checks\":"<<checks<<",\"valid_byte_reads\":"<<reads
        <<",\"offsets\":4,\"destinations\":4,\"sizes\":10,\"image_tails\":4"
        <<",\"actual_core_typed_read\":true,\"legacy_footer_rejected\":true"
        <<",\"staging_bounds\":true,\"device_contacts\":0,\"native_measurement\":false}";
}catch(const std::exception& e){std::cerr<<e.what()<<'\n';return 1;}
