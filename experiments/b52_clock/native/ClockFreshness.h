// SPDX-License-Identifier: GPL-3.0-or-later
#pragma once
#include <display/ClockFoundation.h>
#ifdef HOST_MOCK
#include <bearssl.h>
#else
#include <bearssl/bearssl.h>
#endif
#include <cstring>

namespace ClockFreshness {
constexpr size_t FRAME_BYTES=64, TOKEN_BYTES=16;
constexpr uint32_t CHALLENGE_MS=2000;
struct Workspace {br_hmac_key_context key; br_hmac_context mac;};
inline void wipe(void* p,size_t n){auto* v=static_cast<volatile uint8_t*>(p);while(n--)*v++=0;}
inline bool equal(const uint8_t* a,const uint8_t* b,size_t n){
    uint8_t diff=0;for(size_t i=0;i<n;++i)diff|=uint8_t(a[i]^b[i]);return diff==0;
}
inline bool nonzero(const uint8_t* p){uint8_t any=0;for(size_t i=0;i<TOKEN_BYTES;++i)any|=p[i];return any!=0;}
__attribute__((noinline)) inline void tag(Workspace& w,const char* password,
    const uint8_t* boot,const uint8_t* frame,uint8_t* out){
    uint8_t derived[32];
    static constexpr char keyDomain[]="SHINO-PC-CLOCK-KEY-2\n";
    static constexpr char syncDomain[]="SHINO-PC-CLOCK-SYNC-2\n";
    br_hmac_key_init(&w.key,&br_sha256_vtable,password,std::strlen(password));
    br_hmac_init(&w.mac,&w.key,32);
    br_hmac_update(&w.mac,keyDomain,sizeof(keyDomain)-1);br_hmac_out(&w.mac,derived);
    br_hmac_key_init(&w.key,&br_sha256_vtable,derived,sizeof(derived));
    br_hmac_init(&w.mac,&w.key,32);
    br_hmac_update(&w.mac,syncDomain,sizeof(syncDomain)-1);
    br_hmac_update(&w.mac,boot,TOKEN_BYTES);br_hmac_update(&w.mac,frame,32);
    br_hmac_out(&w.mac,out);wipe(derived,sizeof(derived));
}
class Gate {
    uint8_t boot_[TOKEN_BYTES]{},nonce_[TOKEN_BYTES]{};
    uint32_t issued_=0;
    bool initialized_=false,active_=false,busy_=false;
    struct Lease {bool& busy;explicit Lease(bool& b):busy(b){busy=true;}~Lease(){busy=false;}};
public:
    using Entropy=bool(*)(uint8_t*,size_t);
    using TimeSource=uint32_t(*)();
    void expire(uint32_t now){if(active_&&uint32_t(now-issued_)>=CHALLENGE_MS)active_=false;}
    bool issue(Entropy random,uint32_t now){
        if(busy_||!random)return false;
        Lease lease(busy_);active_=false;
        if(!initialized_){
            if(!random(boot_,TOKEN_BYTES)||!nonzero(boot_)){wipe(boot_,TOKEN_BYTES);return false;}
            initialized_=true;
        }
        uint8_t next[TOKEN_BYTES];
        if(!random(next,TOKEN_BYTES)||!nonzero(next)||equal(next,nonce_,TOKEN_BYTES)||equal(next,boot_,TOKEN_BYTES)){
            wipe(next,sizeof(next));return false;
        }
        std::memcpy(nonce_,next,TOKEN_BYTES);wipe(next,sizeof(next));
        issued_=now;active_=true;return true;
    }
    const uint8_t* boot()const{return boot_;}
    const uint8_t* nonce()const{return nonce_;}
    __attribute__((noinline)) bool accept(ClockFoundation::State& clock,Workspace& w,
        const char* password,const uint8_t* p,size_t n,uint32_t started,uint32_t now,TimeSource completedTime=nullptr){
        if(busy_||!active_||!password||!*password||!p||n!=FRAME_BYTES)return false;
        Lease lease(busy_);
        if(uint32_t(now-issued_)>=CHALLENGE_MS||uint32_t(started-issued_)>=CHALLENGE_MS){active_=false;return false;}
        if(!equal(p+16,nonce_,TOKEN_BYTES))return false;
        // Spend before MAC/time validation. No yield/application callback follows.
        active_=false;
        uint8_t expected[32];tag(w,password,boot_,p,expected);
        const bool verified=equal(expected,p+32,32);wipe(expected,sizeof(expected));
        if(!verified||std::memcmp(p,"SHINOCL2",8))return false;
        const uint32_t completed=completedTime?completedTime():now;
        if(uint32_t(completed-issued_)>=CHALLENGE_MS)return false;
        const uint32_t utc=uint32_t(p[8])|(uint32_t(p[9])<<8)|(uint32_t(p[10])<<16)|(uint32_t(p[11])<<24);
        const unsigned raw=unsigned(p[12])|(unsigned(p[13])<<8);
        const int offset=raw>=32768U?int(raw)-65536:int(raw);
        const unsigned seconds=unsigned(p[14])|(unsigned(p[15])<<8);
        return clock.synchronize(utc,offset,seconds,started,completed);
    }
};
} // namespace ClockFreshness
