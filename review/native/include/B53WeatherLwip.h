// SPDX-License-Identifier: GPL-3.0-or-later
#pragma once
// Isolated prototype. Raw APIs only, serialized lwIP/Core context, never ISR.
#include "B53WeatherDirect.h"
#ifdef B53_LWIP_HOST
#include "LwipDouble.h"
#else
#include <Arduino.h>
#include <ESP8266WiFi.h>
extern "C" {
#include <lwip/dns.h>
#include <lwip/tcp.h>
#include <lwip/pbuf.h>
}
#endif

namespace B53WeatherLwip {
using B53WeatherDirect::Io;
// Callback-only scalar writes. Heap/stack sampling belongs to the owner loop.
struct TcpTrace {
    uint32_t calls[4]{},maxUs[4]{};
    uint32_t pcbCreated=0,pcbReleased=0,pbufSeen=0,pbufFreed=0;
    uint32_t connectedMs=0,releasedMs=0,deferred=0,ownershipFault=0;
};
struct DnsTrace {
    uint32_t queries=0,callbacks=0,late=0,startedMs=0,endedMs=0,maxUs=0,deferred=0;
};
class Adapter final : public B53WeatherDirect::Transport {
    struct Ticket {
        Adapter* owner=nullptr;
        uint64_t identity=0,generation=0;
        bool pending=false;
        DnsTrace trace{};
    };
    // Outlives every Adapter, including adapters destroyed with pending DNS.
    // One physical weather lookup globally; never overwrite a pending ticket.
    static Ticket& ticket(){static Ticket value;return value;}
    static uint64_t& sequence(){static uint64_t value=0;return value;}
    static uint32_t clockUs(){
#ifdef B53_LWIP_HOST
        return uint32_t(millis())*1000U;
#else
        return uint32_t(micros());
#endif
    }
    static void bump(uint32_t& n){if(n!=UINT32_MAX)++n;}
    struct CallbackTimer {
        uint32_t &calls,&maximum,&deferred,start;
        CallbackTimer(uint32_t& c,uint32_t& m,uint32_t& d):calls(c),maximum(m),deferred(d),start(clockUs()){bump(calls);deferred=1;}
        ~CallbackTimer(){const auto elapsed=uint32_t(clockUs()-start);if(elapsed>maximum)maximum=elapsed;}
    };
    TcpTrace trace_{};
    enum class Dns { None, Waiting, Ready, Failed };
    Dns dns_=Dns::None;
    tcp_pcb* pcb_=nullptr;
    ip_addr_t address_{};
    uint8_t rx_[1024]={};
    size_t head_=0,count_=0;
    uint64_t identity_=0,generation_=0;
    uint32_t start_=0,connectStart_=0;
    size_t unacked_=0;
    bool allowed_=false,connected_=false,fin_=false,failed_=false;
    static bool eligible(const B53WeatherDirect::Conditions& c){
        return c.sta&&c.utcValid&&c.utc>=1577836800U&&c.utc<=4102444799U &&
            !c.ota&&!c.digest&&!c.linkPending&&!c.linkFresh;
    }
    bool expired()const{return uint32_t(nowMs()-start_)>=B53WeatherDirect::TOTAL_MS;}
    bool canUse()const{
#ifndef B53_LWIP_HOST
        if(WiFi.status()!=WL_CONNECTED)return false;
#endif
        return allowed_&&!failed_&&identity_&&!expired();
    }
    void freePbuf(pbuf* p){if(p){pbuf_free(p);bump(trace_.pbufFreed);}}
    void releaseTcp(){
        tcp_pcb* dying=pcb_;pcb_=nullptr;connected_=false;unacked_=0;
        if(dying){
            tcp_arg(dying,nullptr);tcp_recv(dying,nullptr);tcp_sent(dying,nullptr);
            tcp_err(dying,nullptr);tcp_poll(dying,nullptr,0);
            tcp_abort(dying); // no flush, ACK wait or TIME_WAIT retention
            bump(trace_.pcbReleased);trace_.releasedMs=nowMs();trace_.deferred=1;
        }
        head_=count_=0;fin_=false;
    }
    err_t abortCallback(){failed_=true;releaseTcp();return ERR_ABRT;}
    static void dnsFound(const char*,const ip_addr_t* address,void* arg){
        auto& q=*static_cast<Ticket*>(arg);
        CallbackTimer timer(q.trace.callbacks,q.trace.maxUs,q.trace.deferred);
        q.trace.endedMs=uint32_t(millis());
        Adapter* owner=q.owner;
        if(owner && q.pending && owner->identity_==q.identity &&
           owner->generation_==q.generation && owner->allowed_ && !owner->expired() &&
           uint32_t(owner->nowMs()-owner->start_)<B53WeatherDirect::DNS_MS){
            if(address){owner->address_=*address;owner->dns_=Dns::Ready;}
            else owner->dns_=Dns::Failed;
        }else {bump(q.trace.late);if(owner)owner->dns_=Dns::Failed;}
        // No reentry, allocation, TCP work or next lookup here. lwIP still
        // clears its callback table AFTER this function returns.
        q.owner=nullptr;q.pending=false;
    }
    static err_t connected(void* arg,tcp_pcb* pcb,err_t err){
        auto* self=static_cast<Adapter*>(arg);
        if(!self)return ERR_OK;
        CallbackTimer timer(self->trace_.calls[0],self->trace_.maxUs[0],self->trace_.deferred);
        if(self->pcb_!=pcb){self->trace_.ownershipFault=1;return ERR_OK;}
        if(err!=ERR_OK || !self->canUse() ||
           uint32_t(self->nowMs()-self->connectStart_)>=B53WeatherDirect::CONNECT_MS)
            return self->abortCallback();
        self->connected_=true;self->trace_.connectedMs=self->nowMs();return ERR_OK;
    }
    static err_t received(void* arg,tcp_pcb* pcb,pbuf* p,err_t err){
        auto* self=static_cast<Adapter*>(arg);
        if(!self){if(p)pbuf_free(p);return ERR_OK;}
        CallbackTimer timer(self->trace_.calls[1],self->trace_.maxUs[1],self->trace_.deferred);
        if(p)bump(self->trace_.pbufSeen);
        if(self->pcb_!=pcb){self->trace_.ownershipFault=1;self->freePbuf(p);return ERR_OK;}
        if(err!=ERR_OK || !self->canUse()){
            self->freePbuf(p);
            return self->abortCallback();
        }
        if(!p){self->fin_=true;return ERR_OK;}
        const size_t n=p->tot_len;
        if(n>sizeof(self->rx_)-self->count_){self->freePbuf(p);return self->abortCallback();}
        // Two bounded copies, no parser and no retained pbuf ownership.
        const size_t tail=(self->head_+self->count_)%sizeof self->rx_;
        const size_t first=n<sizeof(self->rx_)-tail?n:sizeof(self->rx_)-tail;
        const size_t copied=pbuf_copy_partial(p,self->rx_+tail,u16_t(first),0);
        const size_t copied2=n>first?pbuf_copy_partial(p,self->rx_,u16_t(n-first),u16_t(first)):0;
        self->freePbuf(p);
        if(copied!=first || copied2!=n-first)return self->abortCallback();
        self->count_+=n;
        // Credit only when the main-loop consumer reads: bounded backpressure.
        return ERR_OK;
    }
    static err_t sent(void* arg,tcp_pcb* pcb,u16_t length){
        auto* self=static_cast<Adapter*>(arg);
        if(!self)return ERR_OK;
        CallbackTimer timer(self->trace_.calls[2],self->trace_.maxUs[2],self->trace_.deferred);
        if(self->pcb_!=pcb){self->trace_.ownershipFault=1;return ERR_OK;}
        if(length>self->unacked_)self->trace_.ownershipFault=1;
        if(!self->canUse() || length>self->unacked_)return self->abortCallback();
        self->unacked_-=length;return ERR_OK;
    }
    static void error(void* arg,err_t){
        auto* self=static_cast<Adapter*>(arg);
        if(!self)return;
        CallbackTimer timer(self->trace_.calls[3],self->trace_.maxUs[3],self->trace_.deferred);
        bump(self->trace_.pcbReleased);self->trace_.releasedMs=self->nowMs();
        // lwIP already freed this PCB. Never detach/abort/dereference it.
        self->pcb_=nullptr;self->connected_=false;self->failed_=true;
        self->head_=self->count_=self->unacked_=0;self->fin_=false;
    }
public:
    Adapter()=default;
    Adapter(const Adapter&)=delete;
    Adapter& operator=(const Adapter&)=delete;
    ~Adapter()override{close();}
    uint32_t nowMs()const override{return uint32_t(millis());}
    static bool dnsPending(){return ticket().pending;}
    const TcpTrace& trace()const{return trace_;}
    static const DnsTrace& dnsTrace(){return ticket().trace;}
    bool hasPcb()const{return pcb_!=nullptr;}
    bool deferred()const{return trace_.deferred||ticket().trace.deferred;}
    void acknowledgeTrace(){trace_.deferred=0;ticket().trace.deferred=0;}
    // Future owner must call before critical work or Wi-Fi state changes.
    // DNS already in flight remains logically detached, never physically cancelled.
    void policy(const B53WeatherDirect::Conditions& c){
        allowed_=eligible(c);if(!allowed_)close();
    }
    void step(B53WeatherDirect::Client& client,const B53WeatherDirect::Conditions& c){
        policy(c);client.step(*this,c);
    }
    Io resolve(const char* host)override{
        if(!allowed_||!host||strcmp(host,"api.open-meteo.com"))return Io::Failed;
        if(dns_==Dns::Ready)return canUse()?Io::Done:Io::Failed;
        if(dns_==Dns::Failed)return Io::Failed;
        if(dns_==Dns::Waiting)return Io::Pending;
        auto& q=ticket();
        if(q.pending || sequence()==UINT64_MAX)return Io::Failed;
        identity_=++sequence();generation_=identity_;start_=nowMs();failed_=false;
        dns_=Dns::Waiting;
        q.owner=this;q.identity=identity_;q.generation=generation_;q.pending=true;
        bump(q.trace.queries);q.trace.startedMs=start_;q.trace.deferred=1;
        // Arm BEFORE calling: no-server/error paths may invoke callback inline.
        ip_addr_t immediate{};
        const err_t result=dns_gethostbyname(host,&immediate,dnsFound,&q);
        if(result==ERR_OK){
            q.pending=false;q.owner=nullptr;address_=immediate;dns_=Dns::Ready;
            q.trace.endedMs=nowMs();
        }else if(result!=ERR_INPROGRESS){q.pending=false;q.owner=nullptr;dns_=Dns::Failed;q.trace.endedMs=nowMs();}
        return dns_==Dns::Ready?Io::Done:(dns_==Dns::Waiting?Io::Pending:Io::Failed);
    }
    Io connect(unsigned port)override{
        if(!canUse()||dns_!=Dns::Ready||port!=80)return Io::Failed;
        if(connected_)return Io::Done;
        if(pcb_)return Io::Pending;
        pcb_=tcp_new();if(!pcb_){failed_=true;return Io::Failed;}
        bump(trace_.pcbCreated);trace_.deferred=1;
        tcp_setprio(pcb_,TCP_PRIO_MIN); // weather first to evict under pressure
        tcp_arg(pcb_,this);tcp_recv(pcb_,received);tcp_sent(pcb_,sent);tcp_err(pcb_,error);
        connectStart_=nowMs();
        const err_t result=tcp_connect(pcb_,&address_,80,connected);
        if(result!=ERR_OK){failed_=true;releaseTcp();return Io::Failed;}
        return connected_?Io::Done:Io::Pending;
    }
    Io write(const char* data,size_t size,size_t& wrote)override{
        wrote=0;if(!canUse()||!pcb_||!connected_||fin_)return Io::Failed;
        const size_t room=tcp_sndbuf(pcb_);
        const size_t n=size<64?size:64;
        const size_t take=n<room?n:room;
        if(!take)return Io::Pending;
        const err_t result=tcp_write(pcb_,data,u16_t(take),TCP_WRITE_FLAG_COPY);
        if(result==ERR_MEM)return Io::Pending;
        if(result!=ERR_OK){failed_=true;releaseTcp();return Io::Failed;}
        unacked_+=take;wrote=take;
        const err_t output=tcp_output(pcb_);
        if(output!=ERR_OK&&output!=ERR_MEM){failed_=true;releaseTcp();return Io::Failed;}
        return failed_?Io::Failed:Io::Done;
    }
    Io read(uint8_t* bytes,size_t cap,size_t& got)override{
        got=0;if(!canUse()||!pcb_)return Io::Failed;
        size_t n=cap<64?cap:64;if(n>count_)n=count_;
        for(size_t i=0;i<n;++i)bytes[i]=rx_[(head_+i)%sizeof rx_];
        head_=(head_+n)%sizeof rx_;count_-=n;got=n;
        if(n)tcp_recved(pcb_,u16_t(n));
        return fin_&&!count_?Io::Done:Io::Pending;
    }
    void close()override{
        auto& q=ticket();
        if(q.pending&&q.owner==this)q.owner=nullptr;
        identity_=generation_=0;dns_=Dns::None;
        releaseTcp();
    }
};
}
