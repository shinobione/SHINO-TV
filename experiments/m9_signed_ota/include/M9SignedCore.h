// SPDX-License-Identifier: GPL-3.0-or-later
#pragma once
#if !defined(M9_SIGNED_OTA_UNWIRED) || M9_SIGNED_OTA_UNWIRED != 1
#error "Dedicated unwired research graph only"
#endif
#include <Updater.h>
#include <Updater_Signing.h>
#include <BearSSLHelpers.h>
#include <flash_hal.h>
#include <memory>
#include "M9SignedTransfer.h"
static_assert(ARDUINO_SIGNING==0 && SHINO_ENABLE_FACTORY_RESTORE==0 &&
              SHINO_ENABLE_NATIVE_SIGNED_OTA==0,
              "No global signing/unsigned OEM/native activation in this graph");

namespace M9Signed {
struct Sha256 {
    br_sha256_context context;
    void begin(){br_sha256_init(&context);}
    void add(const uint8_t* p,size_t n){br_sha256_update(&context,p,n);}
    void end(uint8_t* out){br_sha256_out(&context,out);}
};
struct DigestHash {
    static bool hex(const char* p,size_t n,char* out){
        Sha256 hash;Digest digest;hash.begin();hash.add(reinterpret_cast<const uint8_t*>(p),n);hash.end(digest.data());
        constexpr char alphabet[]="0123456789abcdef";
        for(size_t i=0;i<32;++i){out[2*i]=alphabet[digest[i]>>4];out[2*i+1]=alphabet[digest[i]&15];}
        out[64]=0;return true;
    }
};

class NativeAdapter final {
public:
    // Parse the actual verification key from the independently pinned DER;
    // no separately supplied key can bypass that trust binding. Immutable DER
    // outlives this adapter. Provisioning/global writer ownership remain seams.
    NativeAdapter(const uint8_t* der,size_t bytes)
        : key_(der && bytes>=64 && bytes<=2048?der:nullptr,
               der && bytes>=64 && bytes<=2048?bytes:0),der_(der),keyBytes_(bytes) {}
    NativeAdapter(const NativeAdapter&)=delete;NativeAdapter& operator=(const NativeAdapter&)=delete;
    bool begin(const Release& release,const Layout& layout){
        if(used_ || poisoned_)return false;
        used_=true;
        Layout expected;
        if(!expected.select(ESP.getSketchSize(),release.rawBytes) ||
           expected.currentRounded!=layout.currentRounded || expected.stageStart!=layout.stageStart ||
           expected.transport!=layout.transport)return false;
        if(!der_ || keyBytes_>2048 || keyBytes_<64 || !key_.isRSA() || key_.getRSA()->nlen!=256 ||
           !(key_.getRSA()->n[0]&0x80) || ESP.getFlashChipRealSize()!=0x400000 || ESP.getFlashChipMode()!=FM_DIO ||
           FS_start-0x40200000!=FsStart || ((ESP.getSketchSize()+4095)&~4095u)!=layout.currentRounded)
            return false;
        Sha256 keyHash;Digest actual;keyHash.begin();keyHash.add(der_,keyBytes_);keyHash.end(actual.data());
        if(!same(actual,release.publicKeyHash))return false;
        verifier_.reset(new(std::nothrow) BearSSL::SigningVerifier(&key_));
        if(!verifier_ || verifier_->length()!=256)return false;
        // Dedicated signed-only instance, never process-global Update. Do not
        // setMD5, clear verifier pointers, install null or coexist with OEM.
        core_.installSignature(&signingHash_,verifier_.get());
        return core_.begin(layout.transport,U_FLASH) && !core_.hasError();
    }
    size_t write(uint8_t* bytes,size_t count){return poisoned_?0:core_.write(bytes,count);}
    bool precommit(const Release& release,const Layout& layout){
        if(poisoned_ || !used_ || core_.hasError() || !core_.isFinished() || core_.size()!=layout.transport)return false;
        // Rehash staged bytes with CHECKED reads. Streaming hash alone cannot
        // establish that staging writes or flash metadata were preserved.
        Sha256 raw,package;raw.begin();package.begin();
        alignas(4) uint8_t block[128];
        for(uint32_t at=0;at<layout.transport;at+=sizeof(block)){
            const uint32_t count=std::min(uint32_t(sizeof(block)),layout.transport-at);
            if(!ESP.flashRead(layout.stageStart+at,reinterpret_cast<uint32_t*>(block),count))return false;
            package.add(block,count);
            if(at<release.rawBytes)raw.add(block,std::min(count,release.rawBytes-at));
        }
        Digest rawHash,packageHash;raw.end(rawHash.data());package.end(packageHash.data());
        ready_=same(rawHash,release.rawHash)&&same(packageHash,release.packageHash);return ready_;
    }
    bool commit(){
        if(poisoned_ || !ready_ || ended_)return false;
        ended_=true;
        // Native Core RSA then _verifyEnd then eboot_command_write; no reboot.
        return core_.end(false) && !core_.hasError();
    }
    void poison(){poisoned_=true;ready_=false;}
    // No public safe abort in pinned Core. A poisoned fully staged transaction
    // must NOT call end(false) to reset: it could commit. No retry in this
    // object. Core staging buffer may remain held until reviewed process reset;
    // cleanup and recovery remain HOLD, never an automatic reboot here.
private:
    BearSSL::PublicKey key_;const uint8_t* der_;size_t keyBytes_;
    UpdaterClass core_;BearSSL::HashSHA256 signingHash_;
    std::unique_ptr<BearSSL::SigningVerifier> verifier_;
    bool used_=false,poisoned_=false,ready_=false,ended_=false;
};
} // namespace M9Signed
