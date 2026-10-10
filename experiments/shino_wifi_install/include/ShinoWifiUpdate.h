// SPDX-License-Identifier: GPL-3.0-or-later
// Small Core ArduinoOTA-style application receiver. No HTTP, FS or reboot API.
#pragma once
#include <Updater.h>
#ifdef HOST_MOCK
#include <bearssl.h>
#else
#include <bearssl/bearssl.h>
#endif
#include <cstring>
#include <cstdio>
#include <cstdlib>
#include <algorithm>
#include "ShinoWifiPolicy.h"
namespace ShinoInstall {
constexpr uint32_t FsStart=0x200000, MaxImage=0xFEFF0;
#if defined(SHINO_SMALL_OTA_BUFFER) && SHINO_SMALL_OTA_BUFFER
constexpr uint32_t CoreBufferAdmission=256;
#else
constexpr uint32_t CoreBufferAdmission=4096;
#endif
inline void encode(const uint8_t* in,size_t n,char* out){const char* a="0123456789abcdef";for(size_t i=0;i<n;++i){out[2*i]=a[in[i]>>4];out[2*i+1]=a[in[i]&15];}out[2*n]=0;}
inline void mac(const uint8_t* key,const char* message,char* out){
    br_hmac_key_context k; br_hmac_context h; uint8_t digest[32];
    br_hmac_key_init(&k,&br_sha256_vtable,key,32);br_hmac_init(&h,&k,32);
    br_hmac_update(&h,message,std::strlen(message));br_hmac_out(&h,digest);encode(digest,32,out);
}
inline bool equal(const char* a,const char* b,size_t n){uint8_t v=0;for(size_t i=0;i<n;++i)v|=uint8_t(a[i]^b[i]);return v==0;}
// Engine owns a dedicated unsigned Updater. Authentication is a private
// maintenance HMAC, NOT vendor signing. Installed StageA never constructs it.
class Receiver {
public:
    Receiver(const char* device,const char* build,const uint8_t* key,bool dryRun=false):device_(device),build_(build),key_(key),dryRun_(dryRun){}
    ~Receiver(){abort();}
    bool capability(const char* clientNonce,const char* serverNonce,uint32_t peer,bool privateAp,uint32_t now,char* out,size_t cap){
        if(state_!=Idle || !key_ || !hex(device_,16) || !hex(build_,64) || !privateAp || !peer ||
           !hex(clientNonce,32)||!hex(serverNonce,32))return false;
        std::strcpy(client_,clientNonce);std::strcpy(nonce_,serverNonce);peer_=peer;start_=last_=now;state_=Challenge;
        char body[256],proof[65];std::snprintf(body,sizeof(body),"CAP %s %s %s 4m2m APP_ONLY %s",device_,client_,build_,nonce_);mac(key_,body,proof);
        return std::snprintf(out,cap,"%s %s\n",body,proof)>0 && std::strlen(body)+66<cap;
    }
    bool authorize(unsigned command,uint32_t size,const char* sha,const char* build,const char* proof,
                   uint32_t peer,bool privateAp,uint32_t now,Budget budget,uint32_t current){
        // U_FS and every other command fail BEFORE Updater.begin/allocation/write.
        if(state_!=Challenge || command!=U_FLASH || !privateAp || peer!=peer_ || !timely(now) ||
           !budget.safe() || budget.heap<20480+CoreBufferAdmission+1024 || !hex(sha,64)||!hex(build,64)||!hex(proof,64)||
           size<64000 || size>MaxImage || FsStart-round(size)<round(current)+4096)return reject();
#if defined(SHINO_PUBLIC_INERT_REVIEW) && SHINO_PUBLIC_INERT_REVIEW
        // Defense in depth: the public review firmware cannot stage a real
        // update, even if a caller bypasses the normal ARM route.
        if(!dryRun_)return reject();
#endif
        char body[320],expected[65];
        std::snprintf(body,sizeof(body),"AUTH %s %s %s %u %u %s %s",device_,client_,nonce_,command,size,sha,build);mac(key_,body,expected);
        if(!equal(expected,proof,64))return reject();
        size_=size;stage_=FsStart-round(size);std::strcpy(sha_,sha);std::strcpy(nextBuild_,build);
        if(dryRun_){
            // Physical DRY-RUN reserves a real heap allocation equal to the
            // isolated Core buffer but calls NO Updater/flash/RTC functions.
            // It measures one real allocation, NOT full OTA high-water.
            probeReserve_=std::malloc(CoreBufferAdmission);
            if(!probeReserve_)return reject();
            volatile uint8_t* ptr=static_cast<volatile uint8_t*>(probeReserve_);
            ptr[0]=0;ptr[CoreBufferAdmission-1]=0;
        }else if(!core_.begin(size_,U_FLASH))return reject();
        br_sha256_init(&hash_);state_=Receiving;last_=now;return true;
    }
    bool add(uint8_t* p,size_t n,uint32_t now,Budget b){
        if(state_!=Receiving || !timely(now)||!b.safe() || !n || n>512 || n>size_-received_)return reject();
        if(received_==0 && (n<4 || p[0]!=0xE9 || p[2]!=2 || p[3]!=0x40))return reject();
        if(!dryRun_ && (core_.write(p,n)!=n || core_.hasError()))return reject();
        br_sha256_update(&hash_,p,n);received_+=uint32_t(n);last_=now;return true;
    }
    // Called only on explicit COMMIT after exact byte count; no end(true).
    bool commit(uint32_t now,Budget b){
        if(state_!=Receiving || !timely(now)||!b.safe() || received_!=size_ || (!dryRun_ && !core_.isFinished()))return reject();
        uint8_t digest[32];char actual[65];br_sha256_out(&hash_,digest);encode(digest,32,actual);
        if(!equal(actual,sha_,64))return reject();
        if(!dryRun_ && (!stagedImage() || !core_.end(false)))return reject();
        // Probe commits ONLY a RAM-only SHA-256 check. No Updater call.
        releaseProbeReserve();state_=Committed;return true;
    }
    void abort(){releaseProbeReserve();if(state_!=Committed){if(!dryRun_)core_.shinoAbort();state_=Failed;}}
    bool receiving()const{return state_==Receiving;}
    bool dryRun()const{return dryRun_;}
    bool committed()const{return state_==Committed;}
    uint32_t received()const{return received_;}
    const char* nextBuild()const{return nextBuild_;}
    bool bufferReleased(){return dryRun_?probeReserve_==nullptr:!core_.isRunning();}
private:
    enum State:uint8_t{Idle,Challenge,Receiving,Committed,Failed};State state_=Idle;
    UpdaterClass core_;br_sha256_context hash_{};
    const char *device_,*build_;const uint8_t* key_;bool dryRun_=false;
    void* probeReserve_=nullptr;
    void releaseProbeReserve(){if(probeReserve_){std::free(probeReserve_);probeReserve_=nullptr;}}
    char client_[33]{},nonce_[33]{},sha_[65]{},nextBuild_[65]{};
    uint32_t peer_=0,start_=0,last_=0,size_=0,stage_=0,received_=0;
    static uint32_t round(uint32_t n){return (n+4095)&~4095u;}
    bool timely(uint32_t now)const{return uint32_t(now-start_)<60000 && uint32_t(now-last_)<3000;}
    bool reject(){abort();return false;}
    bool read(uint32_t at,void* out,size_t n){
        // This retired/unwired receiver is still a CI dependency. Keep its
        // real Core contract correct rather than weakening the shared mock.
        if(!out||!n||at>size_||n>size_-at||stage_>FsStart||round(size_)>FsStart-stage_)return false;
        const uint32_t limit=stage_+round(size_);uint32_t source=stage_+at;
        auto* target=static_cast<uint8_t*>(out);size_t left=n;alignas(4) uint32_t word=0;
        if(source&3u){
            const uint32_t aligned=source&~uint32_t(3);
            if(aligned>limit-4||!ESP.flashRead(aligned,&word,4))return false;
            const size_t skip=source&3u,take=std::min(left,size_t(4)-skip);
            std::memcpy(target,reinterpret_cast<const uint8_t*>(&word)+skip,take);
            target+=take;source+=uint32_t(take);left-=take;
        }
        const size_t bulk=left&~size_t(3);
        if(bulk){
            if(uintptr_t(target)%4==0){
                if(!ESP.flashRead(source,reinterpret_cast<uint32_t*>(target),bulk))return false;
            }else{
                for(size_t i=0;i<bulk;i+=4){
                    if(!ESP.flashRead(source+uint32_t(i),&word,4))return false;
                    std::memcpy(target+i,&word,4);
                }
            }
            target+=bulk;source+=uint32_t(bulk);left-=bulk;
        }
        if(left){if(source>limit-4||!ESP.flashRead(source,&word,4))return false;std::memcpy(target,&word,left);}
        return true;
    }
    bool stagedImage(){
        // Rehash ACTUAL staging and validate CRC, both eboot/app segment bounds
        // and checksums. Flash/RAM seams execute exactly this code in host tests.
        alignas(4) uint8_t block[128];br_sha256_context h;br_sha256_init(&h);uint32_t crc=0xffffffff,stored[2];
        if(!read(0x1010,stored,8)||stored[0]!=size_)return false;
        for(uint32_t at=0;at<size_;at+=sizeof(block)){
            uint32_t n=std::min(uint32_t(sizeof(block)),size_-at);if(!read(at,block,n))return false;
            br_sha256_update(&h,block,n);
            for(uint32_t i=0;i<n;++i){uint8_t v=(at+i>=0x1010 && at+i<0x1018)?0:block[i];
                for(unsigned mask=128;mask;mask>>=1){bool bit=bool(crc&0x80000000)^bool(v&mask);crc<<=1;if(bit)crc^=0x04c11db7;}}
            yield();
        }
        uint8_t digest[32];char actual[65];br_sha256_out(&h,digest);encode(digest,32,actual);
        return equal(actual,sha_,64) && crc==stored[1] && segments(0) && segments(0x1000);
    }
    bool segments(uint32_t off){
        alignas(4) uint8_t hdr[8];if(!read(off,hdr,8)||hdr[0]!=0xE9||hdr[1]<1||hdr[1]>16||hdr[2]!=2||hdr[3]!=0x40)return false;
        uint32_t entry;std::memcpy(&entry,hdr+4,4);uint32_t iramLo=off?0x40100000:0x4010f000,iramHi=off?0x4010c000:0x40110000;
        if(entry<iramLo||entry>=iramHi)return false;
        uint32_t at=off+8;uint8_t sum=0xef;uint32_t starts[16]{},ends[16]{};bool entryLoaded=false;
        for(unsigned s=0;s<hdr[1];++s){alignas(4) uint32_t seg[2];if(!read(at,seg,8))return false;at+=8;
            uint32_t address=seg[0],n=seg[1],limit=0;
            if(address>=0x3ffe8000 && address<(off?0x40000000u:0x3fffc000u))limit=off?0x40000000u:0x3fffc000u;
            if(address>=iramLo&&address<iramHi)limit=iramHi;
            if(off && address>=0x40201010&&address<0x402ffff0 && address==0x40200000+at)limit=0x402ffff0;
            if(!limit || address%4 || !n || n>limit-address || at>size_ || n>size_-at)return false;
            for(unsigned old=0;old<s;++old)if(address<ends[old] && starts[old]<address+n)return false;starts[s]=address;ends[s]=address+n;
            if(address>=iramLo&&address<iramHi&&entry>=address&&entry-address<n)entryLoaded=true;
            alignas(4) uint8_t chunk[128];
            for(uint32_t used=0;used<n;used+=sizeof(chunk)){uint32_t count=std::min(uint32_t(sizeof(chunk)),n-used);if(!read(at+used,chunk,count))return false;
                for(uint32_t i=0;i<count;++i)sum^=(off && at+used+i>=0x1010 && at+used+i<0x1018)?0:chunk[i];yield();}
            at+=n;
        }
        uint32_t footer=((at-off)/16)*16+15+off;alignas(4) uint8_t last[4]{};
        if(!entryLoaded||!read(footer,last,1)||last[0]!=sum)return false;
        return off?footer+1==size_:footer+1<=4096;
    }
};
}
