// Execute the unchanged pinned raw-copy function with RAM SPI seams only.
#include <algorithm>
#include <cstdint>
#include <cstring>
#include <fstream>
#include <iostream>
#include <stdexcept>
#include <vector>
#define FLASH_SECTOR_SIZE 4096
#ifdef _MSC_VER
#define __attribute__(x) // Host portability only; RAM SPIRead uses memcpy.
#endif
struct PowerCut {};
static std::vector<uint8_t> flash,original,package;
static unsigned sectorCut=0,cutMode=0,checks=0,cases=0;
static uint32_t stage;
static void check(bool value){++checks;if(!value)throw std::runtime_error("eboot RAM assertion");}
static int SPIRead(uint32_t at,void* out,uint32_t size){if(at>flash.size() || size>flash.size()-at)return 1;memcpy(out,flash.data()+at,size);return 0;}
static int SPIEraseSector(uint32_t sector){check(sector*4096<0x200000);memset(flash.data()+sector*4096,255,4096);if(cutMode==1 && sector==sectorCut)throw PowerCut{};return 0;}
static int SPIWrite(uint32_t at,const void* data,uint32_t size){check(at+size<=0x200000);memcpy(flash.data()+at,data,cutMode==2 && at/4096==sectorCut?128:size);if((cutMode==2 || cutMode==3) && at/4096==sectorCut)throw PowerCut{};return 0;}
static void ets_putc(char){}
// GZIP is not admitted by signed raw-image framing; these stubs must not run.
struct uzlib_uncomp {const uint8_t *source,*source_limit;uint8_t *dest_start,*dest,*dest_limit;int(*source_read_cb)(uzlib_uncomp*);};
static uint8_t gzip_dict[32768],buffer2[4096];static uint32_t uzlib_flash_read_cb_addr;
static int uzlib_flash_read_cb(uzlib_uncomp*){throw std::runtime_error("forbidden gzip");}
static void uzlib_init(){throw std::runtime_error("forbidden gzip");}
static void uzlib_uncompress_init(uzlib_uncomp*,void*,size_t){throw std::runtime_error("forbidden gzip");}
static int uzlib_gzip_parse_header(uzlib_uncomp*){throw std::runtime_error("forbidden gzip");}
static int uzlib_uncompress(uzlib_uncomp*){throw std::runtime_error("forbidden gzip");}
#define TINF_OK 0
#define TINF_DONE 1
#include "pinned_eboot_copy.inc"
static void reset(){++cases;flash.assign(0x400000,0xa5);stage=0x200000-uint32_t((package.size()+4095)&~4095u);std::copy(package.begin(),package.end(),flash.begin()+stage);
    // Same bootloader sector: actual copy_raw skips it. Previous application
    // bytes are an inert pattern, not an owner image or bootability claim.
    std::copy(package.begin(),package.begin()+4096,flash.begin());original=flash;}
static void preserved(){check(std::equal(flash.begin()+0x200000,flash.end(),original.begin()+0x200000));check(std::equal(flash.begin()+stage,flash.begin()+0x200000,original.begin()+stage));}
int main(int argc,char** argv)try {
    check(argc==2);std::ifstream input(argv[1],std::ios::binary);package={std::istreambuf_iterator<char>(input),{}};check(package.size()==100260);
    reset();cutMode=0;check(copy_raw(stage,0,100000,false)==0);check(std::equal(package.begin(),package.begin()+100000,flash.begin()));preserved();
    unsigned interrupted=0;
    // Each application sector: after erase, partial write and complete write.
    // Successful final-sector boundary is still not a rollback transaction.
    for(unsigned mode=1;mode<=3;++mode)for(unsigned sector=1;sector<25;++sector){
        reset();cutMode=mode;sectorCut=sector;bool cut=false;
        try{copy_raw(stage,0,100000,false);}catch(const PowerCut&){cut=true;}
        check(cut);preserved();++interrupted;
        check(!std::equal(flash.begin(),flash.begin()+100000,original.begin()));
        if(mode!=3 || sector!=24)check(!std::equal(package.begin(),package.begin()+100000,flash.begin()));
    }
    // Mutation after signature/RTC commit is copied without reauthentication.
    reset();cutMode=0;flash[stage+5000]^=1;check(copy_raw(stage,0,100000,false)==0);check(flash[5000]!=package[5000]);
    check(std::equal(flash.begin()+0x200000,flash.end(),original.begin()+0x200000));
    std::cout<<"{\"actual_pinned_raw_copy\":true,\"cases\":"<<cases<<",\"checks\":"<<checks<<",\"interrupted_sector_boundaries\":"<<interrupted
        <<",\"postcommit_corruption_copied\":true,\"rollback\":false,\"hardware_timing\":false,\"device_contacts\":0,\"device_writes\":0}";
}catch(const std::exception& error){std::cerr<<error.what()<<'\n';return 1;}
