// SPDX-License-Identifier: GPL-3.0-or-later
#pragma once
#include "B53WeatherLwip.h"
#include "B53Diagnostic.h"
#include "B53Admission.h"
namespace B53Integration {
using B53WeatherDirect::Conditions;
template<class Weather> class Publication {
    Weather last_{};bool sent_=false;
public:
    bool update(const Weather& next){
        if(sent_&&last_.valid==next.valid&&last_.synthetic==next.synthetic&&
           last_.wmoCode==next.wmoCode&&last_.tenthsC==next.tenthsC&&
           last_.observedMs==next.observedMs&&last_.validForMs==next.validForMs&&
           !strcmp(last_.condition,next.condition)&&!strcmp(last_.place,next.place))return false;
        last_=next;sent_=true;return true;
    }
};
class Coordinator {
    B53Diagnostic::Journal& journal_;
    B53WeatherDirect::Client client_;
    B53WeatherLwip::Adapter adapter_;
    bool configured_=false;
    uint32_t transactionStart_=0;
    void trace(uint32_t now){
        using namespace B53Diagnostic;
        const auto& tcp=adapter_.trace();const auto& dns=adapter_.dnsTrace();
        for(unsigned i=0;i<4;++i){
            journal_.peak(Word(CallbackMax0+i),tcp.maxUs[i]);
            journal_.value(Word(CallbackCalls0+i),tcp.calls[i]);
        }
        journal_.peak(CallbackMaxDns,dns.maxUs);journal_.value(DnsQueries,dns.queries);
        journal_.value(DnsCallbacks,dns.callbacks);journal_.value(DnsLate,dns.late);
        journal_.value(DnsPending,adapter_.dnsPending());
        journal_.value(DnsElapsed,uint32_t((adapter_.dnsPending()?now:dns.endedMs)-dns.startedMs));
        journal_.value(PcbCreated,tcp.pcbCreated);journal_.value(PcbReleased,tcp.pcbReleased);
        journal_.value(PbufSeen,tcp.pbufSeen);journal_.value(PbufFreed,tcp.pbufFreed);
        journal_.value(TcpConnectedMs,tcp.connectedMs);journal_.value(TcpReleasedMs,tcp.releasedMs);
        journal_.value(OutstandingPcb,adapter_.hasPcb());
        journal_.value(OutstandingPbuf,tcp.pbufSeen-tcp.pbufFreed);
        journal_.value(DnsStartedMs,dns.startedMs);journal_.value(DnsEndedMs,dns.endedMs);
    }
public:
    explicit Coordinator(B53Diagnostic::Journal& journal):journal_(journal){}
    bool configure(const char* lat,const char* lon){
        suspend(Conditions{},Reason::Unconfigured);
        configured_=client_.configure(lat,lon);return configured_;
    }
    const B53WeatherLwip::Adapter& adapter()const{return adapter_;}
    bool active()const{return client_.active();}
    B53WeatherDirect::Result result()const{return client_.result();}
    bool deferred()const{return adapter_.deferred();}
    void acknowledgeCapture(){adapter_.acknowledgeTrace();}
    void suspend(Conditions c,Reason why=Reason::Critical){
        if(active()){
            journal_.value(B53Diagnostic::LastAbortMs,adapter_.nowMs());
            journal_.value(B53Diagnostic::AbortReason,uint32_t(why));
        }
        c.ota=true;adapter_.policy(c);client_.step(adapter_,c);
    }
    Decision step(const Conditions& c,const Resources& r,const Bounds& b,bool enabled){
        const auto now=adapter_.nowMs();trace(now);
        auto d=gate(active(),enabled,configured_,adapter_.dnsPending(),journal_.frozen(),c,r,b,now);
        const auto& t=adapter_.trace();
        if(t.ownershipFault||t.pbufSeen!=t.pbufFreed||t.pcbReleased>t.pcbCreated||
           t.pcbCreated-t.pcbReleased!=uint32_t(adapter_.hasPcb()))d={Action::Abort,Reason::Ownership};
        if(d.reason!=Reason::Invalid&&d.reason!=Reason::Floor&&d.reason!=Reason::Ownership&&
           active()&&uint32_t(now-transactionStart_)>=B53WeatherDirect::TOTAL_MS)
            d={Action::Abort,Reason::Deadline};
        journal_.value(B53Diagnostic::LastDecision,uint32_t(d.action));
        journal_.value(B53Diagnostic::DecisionReason,uint32_t(d.reason));
        const bool wasActive=active();
        if(d.action==Action::Allow)adapter_.step(client_,c);else suspend(c,d.reason);
        if(!wasActive&&active())transactionStart_=now;
        trace(now);
        if(d.reason==Reason::Invalid||d.reason==Reason::Floor||d.reason==Reason::Ownership)
            journal_.stop(uint32_t(d.reason));
        return d;
    }
    template<class Weather> bool view(Weather& out,uint32_t now,const Conditions& c,bool synthetic=true)const{
        const bool valid=client_.view(out,now,c);out.synthetic=synthetic;return valid;
    }
};
}
