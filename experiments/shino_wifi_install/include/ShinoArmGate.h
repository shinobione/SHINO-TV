// SPDX-License-Identifier: GPL-3.0-or-later
#pragma once
// Device-local, one-use owner authority for switching between ordinary HTTP
// and the existing maintenance TCP service. No flash, RTC, FS or reboot APIs.
#include <stdint.h>
#include <stddef.h>
#include <cstring>
#include <cstdio>
#include "ShinoWifiPolicy.h"
namespace ShinoInstall {
struct ArmRequest {
    bool ready=false, dryRun=false;
    const char* device=nullptr;const char* build=nullptr;const uint8_t* key=nullptr;
};
class ArmGate {
public:
    using Mac=void (*)(const uint8_t*,const char*,char*);
    explicit ArmGate(Mac fn):mac_(fn){}
    bool configure(const char* device,const char* build,const char* keyHex){
        if(configured_ || !mac_ || !device || !build || !keyHex ||
            !hex(device,16)||!hex(build,64)||!hex(keyHex,64))return false;
        for(unsigned i=0;i<32;++i){
            key_[i]=(fromHex(keyHex[2*i])<<4)|fromHex(keyHex[2*i+1]);
        }
        uint8_t any=0;for(auto b:key_)any|=b;
        if(!any){wipe();return false;}
        std::strcpy(device_,device);std::strcpy(build_,build);
        configured_=true;return true;
    }
    bool challenge(const uint8_t* random,size_t bytes,uint32_t now,char* out,size_t capacity){
        if(!configured_ || !random || bytes!=16 || !out || capacity<33 || active_)return false;
        uint8_t any=0;for(unsigned i=0;i<16;++i)any|=random[i];
        if(!any)return false;
        static const char* digits="0123456789abcdef";
        for(unsigned i=0;i<16;++i){nonce_[2*i]=digits[random[i]>>4];nonce_[2*i+1]=digits[random[i]&15];}
        nonce_[32]=0;nonceValid_=true;challengeTime_=now;
        return std::snprintf(out,capacity,"%s",nonce_)==32;
    }
    bool arm(bool dryRun,const char* signedProof,uint32_t now,bool normalMode,bool privateAp){
#if defined(SHINO_PUBLIC_INERT_REVIEW) && SHINO_PUBLIC_INERT_REVIEW
        // Public fixture identities/keys can never authorize physical INSTALL.
        // Consume any outstanding challenge and fail closed, even after a probe.
        if(!dryRun){nonceValid_=false;return false;}
#endif
        if(!configured_ || !normalMode || !privateAp || active_ || !nonceValid_ ||
            uint32_t(now-challengeTime_)>=15000 || !signedProof || !hex(signedProof,64)){
            nonceValid_=false;return false;
        }
        // Consume the one-use challenge even when HMAC or mode is denied.
        nonceValid_=false;
        char message[170],expected[65];
        int n=std::snprintf(message,sizeof(message),"SHINO_ARM_1 %s %s %s %s",
                   device_,build_,nonce_,dryRun?"PROBE":"INSTALL");
        if(n<=0 || size_t(n)>=sizeof(message))return false;
        mac_(key_,message,expected);
        if(!same(expected,signedProof,64) || (!dryRun && !probeQualified_))return false;
        if(dryRun)probeQualified_=false; // Requalification before each install.
        dryRun_=dryRun;active_=true;return true;
    }
    bool consume(ArmRequest& result){
        if(!active_)return false;
        result={true,dryRun_,device_,build_,key_};
        active_=false;return true;
    }
    void setProbeResult(bool passed){probeQualified_=passed && configured_;}
    bool probeQualified()const{return probeQualified_;}
    bool configured()const{return configured_;}
    void invalidate(){nonceValid_=false;active_=false;probeQualified_=false;}
private:
    static uint8_t fromHex(char c){return c<='9'?uint8_t(c-'0'):uint8_t(c-'a'+10);}
    static bool same(const char* a,const char* b,size_t n){
        uint8_t v=0;for(size_t i=0;i<n;++i)v|=uint8_t(a[i]^b[i]);return v==0;
    }
    void wipe(){volatile uint8_t* p=key_;for(unsigned i=0;i<32;++i)p[i]=0;}
    Mac mac_;char device_[17]{},build_[65]{},nonce_[33]{};
    uint8_t key_[32]{};
    uint32_t challengeTime_=0;
    bool configured_=false,nonceValid_=false,active_=false,dryRun_=false,probeQualified_=false;
};
static_assert(sizeof(ArmGate)<=208,"Authentication state must be bounded");
}
