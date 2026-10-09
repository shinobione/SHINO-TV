// SPDX-License-Identifier: GPL-3.0-or-later
// One application transfer. Core owns flash programming and eboot; no U_FS.
#pragma once
#include <Updater.h>
#ifdef HOST_MOCK
#include <bearssl.h>
#else
#include <bearssl/bearssl.h>
#endif
#include <algorithm>
#include <cstdio>
#include <cstring>

namespace ShinoHttpOta {
constexpr uint32_t FsStart=0x200000, MaxImage=0xFEFF0;
struct Budget {
    uint32_t heap,block,stack; uint8_t frag;
    bool safe()const{return heap>=20480 && block>=16384 && stack>=2048 && frag<=25;}
};
inline bool hex(const char* s,size_t n){
    if(std::strlen(s)!=n)return false;
    for(size_t i=0;i<n;++i)if(!((s[i]>='0'&&s[i]<='9')||(s[i]>='a'&&s[i]<='f')))return false;
    return true;
}
inline void encode(const uint8_t* in,size_t n,char* out){
    const char* a="0123456789abcdef";
    for(size_t i=0;i<n;++i){out[2*i]=a[in[i]>>4];out[2*i+1]=a[in[i]&15];}out[2*n]=0;
}
inline bool equal(const char* a,const char* b,size_t n){uint8_t v=0;for(size_t i=0;i<n;++i)v|=uint8_t(a[i]^b[i]);return v==0;}
struct Release {uint32_t bytes=0;char sha[65]{},build[65]{};};
__attribute__((noinline)) inline void proof(const uint8_t* key,const char* device,const char* nonce,const Release& r,char* out){
    char message[240];
    std::snprintf(message,sizeof(message),"SHINO-HTTP-OTA-1\n%s\n%s\n%u\n%s\n%s",device,nonce,unsigned(r.bytes),r.sha,r.build);
    br_hmac_key_context k; br_hmac_context h; uint8_t digest[32];
    br_hmac_key_init(&k,&br_sha256_vtable,key,32);br_hmac_init(&h,&k,32);
    br_hmac_update(&h,message,std::strlen(message));br_hmac_out(&h,digest);encode(digest,32,out);
}
inline uint32_t rounded(uint32_t n){return (n+4095)&~4095u;}

class Transfer {
public:
    explicit Transfer(bool (*check)()=nullptr):check_(check){}
    ~Transfer(){abort();}
    __attribute__((noinline)) bool begin(const Release& r,const char* device,const char* current,const char* nonce,
               const char* signature,const uint8_t* key,uint32_t currentBytes,Budget b,bool permitted){
        if(active_ || committed_ || !key || !permitted || !b.safe() || b.heap<25600 ||
           !hex(device,16)||!hex(current,64)||!hex(nonce,32)||!hex(signature,64)||
           !hex(r.sha,64)||!hex(r.build,64)||!std::strcmp(current,r.build)||
           r.bytes<64000 || r.bytes>MaxImage || currentBytes<64000 || currentBytes>MaxImage ||
           FsStart-rounded(r.bytes)<rounded(currentBytes)+4096)return false;
        char expected[65];proof(key,device,nonce,r,expected);
        if(!equal(expected,signature,64))return false;
        release_=r;stage_=FsStart-rounded(r.bytes);
        std::snprintf(tag_,sizeof(tag_),"SHINO-HTTP-OTA-1|%s|%s|4m2m|APP_ONLY",device,r.build);
        if(!core_.begin(r.bytes,U_FLASH))return false;
        active_=true;br_sha256_init(&hash_);return (!check_||check_())?true:fail();
    }
    bool add(uint8_t* p,size_t n,Budget b){
        if(!active_||!b.safe()||!n||n>512||n>release_.bytes-received_)return fail();
        if(received_==0 && (n<4||p[0]!=0xE9||p[2]!=2||p[3]!=0x40))return fail();
        if(core_.write(p,n)!=n||core_.hasError())return fail();
        br_sha256_update(&hash_,p,n);received_+=uint32_t(n);return true;
    }
    bool finish(Budget b){
        if(!active_||!b.safe()||received_!=release_.bytes||!core_.isFinished())return fail();
        uint8_t digest[32];char actual[65];br_sha256_out(&hash_,digest);encode(digest,32,actual);
        if(!equal(actual,release_.sha,64)||!stagedImage()||!b.safe()||(check_&&!check_()))return fail();
        // This is the ONLY committing call. Abort never calls end(), including
        // a fully received image whose authentication/CRC/readback failed.
        if(!core_.end(false))return fail();
        active_=false;committed_=true;return true;
    }
    void abort(){if(active_){core_.shinoAbort();active_=false;}}
    uint32_t received()const{return received_;}
    bool running(){return core_.isRunning();}
    bool committed()const{return committed_;}
    uint32_t stage()const{return stage_;}
private:
    UpdaterClass core_;br_sha256_context hash_{};Release release_{};
    uint32_t stage_=0,received_=0;bool active_=false,committed_=false;
    char tag_[128]{};
    bool (*check_)()=nullptr;
    bool fail(){abort();return false;}
    bool read(uint32_t at,void* out,size_t n){return at<=release_.bytes&&n<=release_.bytes-at&&ESP.flashRead(stage_+at,reinterpret_cast<uint32_t*>(out),n);}
    bool stagedImage(){
        // Retained StageA image-validation rules, executed against actual
        // staging: SHA256, Core CRC, both segment tables/checksums and identity.
        alignas(4) uint8_t block[128];br_sha256_context h;br_sha256_init(&h);
        uint32_t crc=0xffffffff,stored[2];size_t matched=0;bool tagFound=false;
        if(!read(0x1010,stored,8)||stored[0]!=release_.bytes)return false;
        for(uint32_t at=0;at<release_.bytes;at+=sizeof(block)){
            if(check_&&!check_())return false;
            const uint32_t n=std::min(uint32_t(sizeof(block)),release_.bytes-at);
            if(!read(at,block,n))return false;
            br_sha256_update(&h,block,n);
            for(uint32_t i=0;i<n;++i){
                if(!tagFound){
                    if(block[i]==uint8_t(tag_[matched])){if(!tag_[++matched])tagFound=true;}
                    else matched=block[i]==uint8_t(tag_[0])?1:0;
                }
                const uint8_t v=(at+i>=0x1010&&at+i<0x1018)?0:block[i];
                for(unsigned mask=128;mask;mask>>=1){const bool bit=bool(crc&0x80000000)^bool(v&mask);crc<<=1;if(bit)crc^=0x04c11db7;}
            }
            yield();
        }
        uint8_t digest[32];char actual[65];br_sha256_out(&h,digest);encode(digest,32,actual);
        return tagFound&&equal(actual,release_.sha,64)&&crc==stored[1]&&segments(0)&&segments(0x1000);
    }
    bool segments(uint32_t off){
        alignas(4) uint8_t hdr[8];if(!read(off,hdr,8)||hdr[0]!=0xE9||hdr[1]<1||hdr[1]>16||hdr[2]!=2||hdr[3]!=0x40)return false;
        uint32_t entry;std::memcpy(&entry,hdr+4,4);
        const uint32_t iramLo=off?0x40100000:0x4010f000,iramHi=off?0x4010c000:0x40110000;
        if(entry<iramLo||entry>=iramHi)return false;
        uint32_t at=off+8;uint8_t sum=0xef;uint32_t starts[16]{},ends[16]{};
        for(unsigned s=0;s<hdr[1];++s){
            alignas(4) uint32_t seg[2];if(!read(at,seg,8))return false;at+=8;
            const uint32_t address=seg[0],n=seg[1];uint32_t limit=0;
            if(address>=0x3ffe8000&&address<(off?0x40000000u:0x3fffc000u))limit=off?0x40000000u:0x3fffc000u;
            if(address>=iramLo&&address<iramHi)limit=iramHi;
            if(off&&address>=0x40201010&&address<0x402ffff0&&address==0x40200000+at)limit=0x402ffff0;
            if(!limit||address%4||!n||n>limit-address||at>release_.bytes||n>release_.bytes-at)return false;
            for(unsigned old=0;old<s;++old)if(address<ends[old]&&starts[old]<address+n)return false;
            starts[s]=address;ends[s]=address+n;
            alignas(4) uint8_t chunk[128];
            for(uint32_t used=0;used<n;used+=sizeof(chunk)){
                if(check_&&!check_())return false;
                const uint32_t count=std::min(uint32_t(sizeof(chunk)),n-used);if(!read(at+used,chunk,count))return false;
                for(uint32_t i=0;i<count;++i)sum^=(off&&at+used+i>=0x1010&&at+used+i<0x1018)?0:chunk[i];
                yield();
            }
            at+=n;
        }
        const uint32_t footer=((at-off)/16)*16+15+off;alignas(4) uint8_t last[4]{};
        if(!read(footer,last,1)||last[0]!=sum)return false;
        return off?footer+1==release_.bytes:footer+1<=4096;
    }
};
} // namespace ShinoHttpOta
