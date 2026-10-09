// SPDX-License-Identifier: GPL-3.0-or-later
#pragma once
#include <new>
#include "ShinoWifiPolicy.h"
#if defined(SHINO_MEMORY_TRACE) && SHINO_MEMORY_TRACE
#include "ShinoMemoryTrace.h"
#endif
namespace ShinoInstall {
// Only a trusted, separately reviewed owner-consent supplier may queue this.
// There is no HTTP route, default key, installer override or device trigger.
struct Consent { const char* device; const char* build; const uint8_t* key; bool owner; bool dryRun=false; };
template<class Http, class Upload, class Hooks> class Maintenance {
public:
    enum Mode { Normal, Pending, Uploading, Hold, Committed };
    explicit Maintenance(Hooks& hooks):hooks_(hooks){http_=new(slot_) Http;}
    ~Maintenance(){if(upload_){upload_->stop();upload_->~Upload();}if(http_){http_->quiesce();http_->~Http();}erase();}
    Http& http(){return *http_;}
    Mode mode()const{return mode_;}
#if defined(SHINO_MEMORY_TRACE) && SHINO_MEMORY_TRACE
    const MemoryTrace& measurements()const{return trace_;}
#endif
    bool request(const Consent& c){
        if(mode_!=Normal || !c.owner || !c.device || !c.build || !c.key || !hex(c.device,16) || !hex(c.build,64))return false;
        uint8_t nonzero=0;for(unsigned i=0;i<32;++i)nonzero|=c.key[i];if(!nonzero)return false;
        std::strcpy(device_,c.device);std::strcpy(build_,c.build);std::memcpy(key_,c.key,32);dryRun_=c.dryRun;mode_=Pending;return true;
    }
    // Called at the next cooperative loop boundary, never in an HTTP callback.
    // False pauses HTTP, dashboard, telemetry handlers and normal JSON work.
    // Keep the state-machine dispatch out of StageA::loop. An inlined,
    // conditionally-specialized dispatch obscured the real Native::pump path
    // in Xtensa disassembly. This makes actual reachable machine calls
    // auditable without accepting orphan symbols or callx guesses.
    __attribute__((noinline)) bool tick(){
#if defined(SHINO_MEMORY_TRACE) && SHINO_MEMORY_TRACE
        if(mode_==Normal)sample(TracePoint::Normal);
#endif
        if(mode_==Pending){
            http_->quiesce();http_->~Http();http_=nullptr;
#if defined(SHINO_MEMORY_TRACE) && SHINO_MEMORY_TRACE
            sample(TracePoint::HttpClosed);
#endif
            // No credit for static arrays. Check AFTER dynamic HTTP destruction.
            if(!admit(hooks_.budget())){restore();return mode_==Normal;}
#if defined(SHINO_MEMORY_TRACE) && SHINO_MEMORY_TRACE
            #if defined(SHINO_MAINTENANCE_PROBE) && SHINO_MAINTENANCE_PROBE
            upload_=new(slot_) Upload(device_,build_,key_,&trace_,dryRun_);
#else
            upload_=new(slot_) Upload(device_,build_,key_,&trace_);
#endif
#else
            upload_=new(slot_) Upload(device_,build_,key_);
#endif
            if(!upload_->begin()){finish();return mode_==Normal;}
            mode_=Uploading;
#if defined(SHINO_MEMORY_TRACE) && SHINO_MEMORY_TRACE
            sample(TracePoint::ListenerReady);
#endif
            return false; // No simultaneous normal work on entry.
        }
        if(mode_==Uploading){
            if(!hooks_.budget().safe()){finish();return mode_==Normal;}
            upload_->pump();
#if defined(SHINO_MEMORY_TRACE) && SHINO_MEMORY_TRACE
            sample(TracePoint::DuringStaging);
#endif
#if defined(SHINO_MAINTENANCE_PROBE) && SHINO_MAINTENANCE_PROBE
            if(upload_->probed()){finish();return mode_==Normal;}
#endif
            if(upload_->committed()){mode_=Committed;return false;}
            if(upload_->failed())finish();
            return mode_==Normal;
        }
        return mode_==Normal;
    }
    void cancel(){if(mode_==Pending){erase();mode_=Normal;}else if(mode_==Uploading)finish();}
    static constexpr size_t slotBytes=sizeof(Http)>sizeof(Upload)?sizeof(Http):sizeof(Upload);
private:
    alignas(Http) alignas(Upload) uint8_t slot_[slotBytes];
    Hooks& hooks_;Http* http_=nullptr;Upload* upload_=nullptr;Mode mode_=Normal;
#if defined(SHINO_MEMORY_TRACE) && SHINO_MEMORY_TRACE
    MemoryTrace trace_{};
    void sample(TracePoint point){trace_.add(point,hooks_.budget());}
#endif
    char device_[17]{},build_[65]{};uint8_t key_[32]{};bool dryRun_=false;
    static bool admit(Budget b){return b.safe() && b.heap>=20480+4096+1024;}
    void erase(){volatile uint8_t* p=key_;for(unsigned i=0;i<32;++i)p[i]=0;device_[0]=build_[0]=0;dryRun_=false;}
    void finish(){upload_->stop();upload_->~Upload();upload_=nullptr;restore();}
    void restore(){
#if defined(SHINO_MEMORY_TRACE) && SHINO_MEMORY_TRACE
        sample(TracePoint::Recovery);
#endif
        erase();
        // Same conservative 5120 B construction reserve as upload admission;
        // bounded header/handler payloads are quantified separately. Low memory
        // or lost AP is a terminal HOLD, with no listener/reconnect/retry loop.
        if(!admit(hooks_.budget()) || !hooks_.ap()){mode_=Hold;return;}
        http_=new(slot_) Http;hooks_.resume(*http_);
        if(!hooks_.budget().safe()){http_->quiesce();http_->~Http();http_=nullptr;mode_=Hold;return;}
        mode_=Normal;
#if defined(SHINO_MEMORY_TRACE) && SHINO_MEMORY_TRACE
        sample(TracePoint::Restored);
#endif
    }
};
}
