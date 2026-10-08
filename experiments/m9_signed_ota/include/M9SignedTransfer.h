// SPDX-License-Identifier: GPL-3.0-or-later
#pragma once
// Unwired research substrate. Release pins and resource/interface observations
// originate in privileged reviewed code, never in upload JSON/headers.
#include "M9SignedHttp.h"
#include "boot/NativeOtaStrictDigestGate.h"
#include <array>
#include <cstring>

namespace M9Signed {
constexpr uint32_t MaxRaw = 0xFEFF0, FsStart = 0x200000;
constexpr uint32_t ArmLifetime = 60000, TransferDeadline = 60000;
constexpr size_t Chunk = 512;
using Digest = std::array<uint8_t,32>;
struct Release { uint32_t rawBytes; Digest rawHash, packageHash, publicKeyHash; };
struct Budget {
    uint32_t heap, block, fragmentation, stack;
    // Reserve Core's6200B thunk stack,4KiB staging buffer,256B signature,512B chunk
    // from existing floors. Public-key parsing precedes this observation;
    // the SigningVerifier secondary stack is allocated after admission.
    // The 2048B caller reserve covers measured research frames;
    // production parser/callback/concurrency stack remains unqualified.
    bool safe() const { return heap>=20480+6200+4096+256+512 && block>=16384+6200 &&
                              fragmentation<=25 && stack>=2048+2048; }
};
struct Layout {
    uint32_t currentRounded=0, stageStart=0, transport=0;
    bool select(uint32_t current, uint32_t raw) {
        if(current<64000 || current>MaxRaw || raw<64000 || raw>MaxRaw) return false;
        currentRounded=(current+4095)&~4095u; transport=raw+260;
        stageStart=FsStart-((transport+4095)&~4095u);
        return stageStart>=currentRounded+4096;
    }
};
inline bool same(const Digest& a,const Digest& b) {
    uint8_t difference=0; for(size_t i=0;i<32;++i) difference|=a[i]^b[i];
    return difference==0;
}
inline bool nonzero(const Digest& a) { uint8_t x=0;for(auto b:a)x|=b;return x!=0; }
enum class Phase : uint8_t { Idle, Armed, Streaming, Complete, Scheduled, Failed };

template<class Hash,class DigestHash,class Adapter> class Transfer final {
public:
    Transfer(const Release& selected, uint32_t current, Adapter& adapter)
        : release_(selected), current_(current), adapter_(adapter) {}
    Transfer(const Transfer&)=delete; Transfer& operator=(const Transfer&)=delete;
    bool arm(const char* headers,size_t count,const uint8_t* body,size_t bytes,
             uint32_t peer,bool privateAp,bool ownerConfirmed,const char* token32,
             ShinoNativeOta::StrictOtaDigestGate<DigestHash>& auth,
             const char* user,const char* ha1,uint32_t now,const Budget& budget) {
        if(phase_!=Phase::Idle)return phase_==Phase::Armed?fail():false;
        ShinoNativeOta::RawOtaHeaderResult parsed;
        constexpr char Consent[]="{\"confirm\":true}";
        if(!ownerConfirmed || !budget.safe() || !token(token32) ||
           !releaseValid() || !layout_.select(current_,release_.rawBytes) ||
           !prebody(headers,count,peer,privateAp,ShinoNativeOta::RawOtaRequestKind::Arm,parsed) ||
           parsed.contentLength!=sizeof(Consent)-1 || bytes!=sizeof(Consent)-1 || !body ||
           std::memcmp(body,Consent,bytes)!=0 ||
           !auth.verify(peer,parsed.kind,headers+parsed.digestValueOffset,parsed.digestValueLength,user,ha1,now))
            return fail();
        std::memcpy(token_,token32,33); peer_=peer; armed_=now; phase_=Phase::Armed;return true;
    }
    bool begin(const char* headers,size_t count,uint32_t peer,bool privateAp,
               ShinoNativeOta::StrictOtaDigestGate<DigestHash>& auth,const char* user,
               const char* ha1,uint32_t now,const Budget& budget) {
        if(phase_!=Phase::Armed)return phase_==Phase::Streaming?fail():false;
        ShinoNativeOta::RawOtaHeaderResult parsed;
        if(now-armed_>=ArmLifetime || peer!=peer_ || !budget.safe() ||
           !prebody(headers,count,peer,privateAp,ShinoNativeOta::RawOtaRequestKind::SignedTransport,parsed) ||
           parsed.contentLength!=layout_.transport || std::memcmp(token_,parsed.intentToken,33)!=0 ||
           !auth.verify(peer,parsed.kind,headers+parsed.digestValueOffset,parsed.digestValueLength,user,ha1,now) ||
           !adapter_.begin(release_,layout_))return fail();
        raw_.begin(); package_.begin(); start_=now; phase_=Phase::Streaming;return true;
    }
    bool add(uint8_t* data,size_t bytes,uint32_t exactOffset,uint32_t now,const Budget& budget) {
        if(phase_!=Phase::Streaming)return phase_==Phase::Complete?fail():false;
        if(!budget.safe() || now-start_>=TransferDeadline || !data || !bytes || bytes>Chunk ||
           exactOffset!=received_ || bytes>layout_.transport-received_)return fail();
        const size_t rawCount=received_<release_.rawBytes?
            (bytes<release_.rawBytes-received_?bytes:release_.rawBytes-received_):0;
        for(size_t i=0;i<bytes;++i) {
            const uint32_t at=received_+i;
            if(at<4 && data[i]!=(at==0?0xe9:at==1?data[i]:at==2?2:0x40))return fail();
            if(at==1 && (data[i]<1 || data[i]>16))return fail();
            if(at>=layout_.transport-4)trailer_[at-(layout_.transport-4)]=data[i];
        }
        if(rawCount)raw_.add(data,rawCount);
        package_.add(data,bytes);
        if(adapter_.write(data,bytes)!=bytes)return fail();
        received_+=bytes; if(received_==layout_.transport)phase_=Phase::Complete;
        return true;
    }
    bool finish(uint32_t now,const Budget& budget) {
        if(phase_!=Phase::Complete)return phase_==Phase::Streaming?fail():false;
        Digest raw,package;raw_.end(raw.data());package_.end(package.data());
        if(!budget.safe() || now-start_>=TransferDeadline || trailer_!=std::array<uint8_t,4>{{0,1,0,0}} ||
           !same(raw,release_.rawHash) || !same(package,release_.packageHash) ||
           !adapter_.precommit(release_,layout_) || !adapter_.commit())return fail();
        phase_=Phase::Scheduled; return true; // Native RSA passed; NO reboot.
    }
    void disconnect(){if(phase_!=Phase::Scheduled)fail();}
    Phase phase()const{return phase_;} uint32_t received()const{return received_;}
private:
    bool releaseValid()const{return nonzero(release_.rawHash)&&nonzero(release_.packageHash)&&nonzero(release_.publicKeyHash);}
    static bool token(const char* s) {
        if(!s)return false;
        uint8_t x=0;
        for(size_t i=0;i<32;++i){if(!((s[i]>='0'&&s[i]<='9')||(s[i]>='a'&&s[i]<='f')))return false;x|=s[i]!='0';}
        return x && s[32]==0;
    }
    static bool prebody(const char* h,size_t n,uint32_t peer,bool ap,
                        ShinoNativeOta::RawOtaRequestKind kind,ShinoNativeOta::RawOtaHeaderResult& out) {
        return ap && peer>=0xc0a80402 && peer<=0xc0a804fe &&
               HeaderGate::inspect(h,n,out) && out.kind==kind;
    }
    bool fail(){adapter_.poison();std::memset(token_,0,sizeof(token_));phase_=Phase::Failed;return false;}
    const Release release_;const uint32_t current_;Adapter& adapter_;
    Hash raw_,package_;Layout layout_;Phase phase_=Phase::Idle;
    uint32_t received_=0,peer_=0,armed_=0,start_=0;
    char token_[33]{}; std::array<uint8_t,4> trailer_{};
};
} // namespace M9Signed
