// SPDX-License-Identifier: GPL-3.0-or-later
#pragma once
#include <stdint.h>
namespace B53Integration {
enum class Action:uint32_t { Allow=1,Defer,Abort };
enum class Reason:uint32_t { Ready,Disabled,Unconfigured,Critical,Clock,Station,
    Unknown,Invalid,Floor,Reserve,OldMeasurement,Quarantine,Deadline,Frozen,Ownership };
struct Decision { Action action;Reason reason; };
struct Resources {
    uint32_t heap=0,block=0,stack=0;uint8_t frag=0;uint32_t sampledMs=0;bool valid=false;
    bool sane()const{return valid&&heap>0&&heap<=81920&&block>0&&block<=heap&&frag<=100&&stack<=4096&&stack%4==0;}
};
// Certified additional peak for ALL remaining phases, including delayed frees.
// blockRequired is an independently established contiguity requirement, not heap subtraction.
// Native defaults UNKNOWN. HOST fixture values are not native certification.
struct Bounds {
    bool verified=false,sdkStackCovered=false;
    uint32_t extraHeap=0,blockRequired=0,extraStack=0;
    bool sharedPoolsCovered=false,schedulerCovered=false;
    bool known()const{return verified&&sdkStackCovered&&sharedPoolsCovered&&schedulerCovered&&extraHeap>0&&extraHeap<=81920&&
        blockRequired>=17600&&blockRequired<=81920&&extraStack>0&&extraStack<=4096;}
};
inline Reason resourceReason(const Resources& r){
    if(!r.sane())return Reason::Invalid;
    if(r.heap<20480||r.block<16384||r.stack<2048||r.frag>25)return Reason::Floor;
    return Reason::Ready;
}
template<class Conditions> inline Decision gate(bool active,bool enabled,bool configured,bool pending,bool frozen,
                     const Conditions& c,const Resources& r,const Bounds& b,uint32_t now){
    const auto deny=[active](Reason reason){return Decision{active?Action::Abort:Action::Defer,reason};};
    if(frozen)return deny(Reason::Frozen);
    const Reason resource=resourceReason(r);
    if(resource!=Reason::Ready)return deny(resource);
    if(!enabled)return deny(Reason::Disabled);
    if(!configured)return deny(Reason::Unconfigured);
    if(c.ota||c.digest||c.linkPending||c.linkFresh)return deny(Reason::Critical);
    if(!c.sta)return deny(Reason::Station);
    if(!c.utcValid||c.utc<1577836800U||c.utc>4102444799U)return deny(Reason::Clock);
    if(!b.known())return deny(Reason::Unknown);
    if(uint32_t(now-r.sampledMs)>100)return deny(Reason::OldMeasurement);
    if(r.heap<25600||r.heap-25600<b.extraHeap||r.block<b.blockRequired||
       r.stack-2048<b.extraStack)return deny(Reason::Reserve);
    if(pending&&!active)return deny(Reason::Quarantine);
    return {Action::Allow,Reason::Ready};
}
}
