// SPDX-License-Identifier: GPL-3.0-or-later
#pragma once
#include "B53Admission.h"
#include "B53Diagnostic.h"
namespace B53OffDiagnostic {
// Compile-time OFF profile. No weather client, dynamic allocation, lazy buffer,
// DNS callback or runtime enable path. Keep the same resource gate and LINK log.
class Monitor {
    B53Diagnostic::Journal* log_=nullptr;
    uint32_t lastLink_=0,serviced_=0;
    bool linkSeen_=false,wasFresh_=false,servicedOnce_=false;
public:
    void begin(B53Diagnostic::Journal& journal){
        if(log_)return;
        log_=&journal;log_->value(B53Diagnostic::Version,2);
    }
    void observe(uint32_t heap,uint32_t block,uint8_t frag,uint32_t stack,uint32_t now){
        if(!log_||!log_->started()||log_->frozen())return;
        const B53Integration::Resources r{heap,block,stack,frag,now,true};
        const auto reason=B53Integration::resourceReason(r);
        if(reason!=B53Integration::Reason::Ready){
            log_->value(B53Diagnostic::LastDecision,uint32_t(B53Integration::Action::Defer));
            log_->value(B53Diagnostic::DecisionReason,uint32_t(reason));
            log_->stop(uint32_t(reason));
        }
    }
    void linkAccepted(uint32_t latencyMs,uint32_t now){
        if(!log_)return;
        log_->peak(B53Diagnostic::LinkLatencyMax,latencyMs);
        log_->count(B53Diagnostic::LinkAccepts);
        if(linkSeen_)log_->peak(B53Diagnostic::LinkAcceptIntervalMax,uint32_t(now-lastLink_));
        lastLink_=now;linkSeen_=wasFresh_=true;
    }
    void poll(bool linkFresh,uint32_t now){
        if(!log_||!log_->started()||log_->frozen())return;
        if(linkSeen_&&linkFresh)log_->peak(B53Diagnostic::LinkAgeMax,uint32_t(now-lastLink_));
        if(linkSeen_&&wasFresh_&&!linkFresh)log_->count(B53Diagnostic::LinkStaleEpisodes);
        wasFresh_=linkFresh;
        if(servicedOnce_&&uint32_t(now-serviced_)<20)return;
        serviced_=now;servicedOnce_=true;
        log_->value(B53Diagnostic::LastDecision,uint32_t(B53Integration::Action::Defer));
        log_->value(B53Diagnostic::DecisionReason,uint32_t(B53Integration::Reason::Disabled));
    }
};
}
