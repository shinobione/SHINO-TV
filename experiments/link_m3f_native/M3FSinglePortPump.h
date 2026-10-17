// SPDX-License-Identifier: GPL-3.0-or-later
#pragma once
// M3-F: OFFLINE cooperative single borrowed WiFiServer-style pump.
// NO begin(), registration, production credentials, OTA, scene mutation,
// network boot, or real legacy delegation. All legacy routes return 503.
// All cryptographically reviewed display commands return 202 applied:false.
// A HOST fake executes the pump; isolated Xtensa/BearSSL source compiles it.
#include "../link_m3c_crypto/M3CAuthenticatedIngress.h"
#include "../link_m3e_legacy/M3ELegacyRouteGate.h"
#include <cstddef>
#include <cstdint>
#include <cstdio>
#include <cstring>
#include <new>

namespace ShinoM3F {
enum class Step : uint8_t { Idle, Pending, Rejected, LegacyHeld, OtaHeld, CryptoReviewedOnly };

template<class Server, class Client, class Crypto>
class SinglePortPump final {
public:
    static constexpr size_t kMaxLine = 128u;
    static constexpr size_t kMaxReadsPerPoll = 32u;
    static constexpr uint32_t kHeaderDeadlineMs = 1000u;
    static constexpr uint32_t kBodyDeadlineMs = 2000u;
    SinglePortPump(Server& server, ShinoM3C::Identity id,
                   const uint8_t* publicTestKey, uint32_t revision=0u)
        : server_(server), id_(id), key_(publicTestKey), ledger_(revision) {}
    SinglePortPump(const SinglePortPump&)=delete;
    SinglePortPump& operator=(const SinglePortPump&)=delete;
    ~SinglePortPump() { if(active_) client_.stop(); drop(); }

    Step poll(uint32_t now) {
        if (!active_) {
            Client next=server_.accept();
            if (!next) return Step::Idle;
            client_=next;
            active_=true;
            accepted_++;
            start_=now;
            lineUsed_=0u;
            stage_=Stage::First;
        }
        if ((stage_==Stage::First || stage_==Stage::Headers)
            && static_cast<uint32_t>(now-start_)>=kHeaderDeadlineMs)
            return finish(Step::Rejected,408);
        if ((stage_==Stage::Body || stage_==Stage::Fin)
            && static_cast<uint32_t>(now-bodyStart_)>=kBodyDeadlineMs)
            return finish(Step::Rejected,408);

        for(size_t budget=0;budget<kMaxReadsPerPoll;++budget) {
            const int available=client_.available();
            if(available<0) return finish(Step::Rejected,403);
            if(stage_==Stage::Fin) {
                if(available>0) return finish(Step::Rejected,403);
                if(!client_.connected()) {
                    if(!gate_ || gate_->finishAfterExactFraming(
                        true,0u,static_cast<uint32_t>(now-bodyStart_))
                        !=ShinoM3C::Phase::VerifiedFrame)
                        return finish(Step::Rejected,403);
                    // CAS is SERIAL in this memory-only lab; no LCD mutation.
                    if(!ledger_.acceptVerifiedForLab(*gate_))
                        return finish(Step::Rejected,409);
                    return finish(Step::CryptoReviewedOnly,202);
                }
                return Step::Pending;
            }
            if(available==0) {
                if(!client_.connected()) return finish(Step::Rejected,403);
                return Step::Pending;
            }
            const int value=client_.read();
            if(value<0||value>255) return finish(Step::Rejected,403);
            ++reads_;
            const char c=static_cast<char>(value);
            if(stage_==Stage::First) {
                if(lineUsed_>=kMaxLine) return finish(Step::Rejected,400);
                first_[lineUsed_++]=c;
                if(c=='\0'||(c=='\n'&&(lineUsed_<2u||first_[lineUsed_-2u]!='\r')))
                    return finish(Step::Rejected,400);
                if(lineUsed_>=2u&&first_[lineUsed_-2u]=='\r'&&c=='\n') {
                    first_[lineUsed_]='\0';
                    const Step result=firstLine(now);
                    if(result!=Step::Pending) return result;
                }
            } else if(stage_==Stage::Headers) {
                if(!gate_||gate_->headerByte<Crypto>(c,now-start_,key_)
                    ==ShinoM3C::Phase::Reject)
                    return finish(Step::Rejected,403);
                if(gate_->phase()==ShinoM3C::Phase::AuthenticatedHeader) {
                    bodyStart_=now;
                    stage_=Stage::Body;
                }
            } else if(stage_==Stage::Body) {
                if(!gate_||gate_->bodyByte<Crypto>(
                    static_cast<uint8_t>(value),now-bodyStart_)
                    ==ShinoM3C::Phase::Reject)
                    return finish(Step::Rejected,403);
                if(gate_->phase()==ShinoM3C::Phase::BodyDigestMatched)
                    stage_=Stage::Fin;
            }
        }
        return Step::Pending;
    }
    size_t readCount() const {return reads_;}
    uint32_t connectionCount() const {return accepted_;}
    bool busy() const {return active_;}
private:
    enum class Stage : uint8_t { First, Headers, Body, Fin };
    Server& server_;
    const ShinoM3C::Identity id_;
    const uint8_t* key_;
    ShinoM3C::OfflineCasLedger ledger_;
    Client client_{};
    bool active_=false;
    uint32_t start_=0u,bodyStart_=0u,accepted_=0u;
    size_t lineUsed_=0u,reads_=0u;
    char first_[kMaxLine+1u]{};
    Stage stage_=Stage::First;
    alignas(ShinoM3C::Gate) uint8_t gateMemory_[sizeof(ShinoM3C::Gate)]{};
    ShinoM3C::Gate* gate_=nullptr;
    void drop() { if(gate_) { gate_->~Gate(); gate_=nullptr; } }

    Step firstLine(uint32_t now) {
        if(std::strcmp(first_,"POST /api/v1/display/mode HTTP/1.1\r\n")!=0) {
            const char* sp=std::strchr(first_,' ');
            const char* sp2=sp?std::strchr(sp+1,' '):nullptr;
            if(!sp || !sp2 || sp2<=sp+1) return finish(Step::Rejected,400);
            const size_t ml=static_cast<size_t>(sp-first_);
            const size_t pl=static_cast<size_t>(sp2-sp-1);
            if(ml==0u||ml>4u||pl==0u||pl>96u||
               std::strcmp(sp2," HTTP/1.1\r\n")!=0)
                return finish(Step::Rejected,400);
            char method[5]{},path[97]{};
            std::memcpy(method,first_,ml);
            std::memcpy(path,sp+1,pl);
            const auto plan=ShinoM3E::LegacyRouteGate::inspect(
                method,path,ShinoM3E::Peer::HomeLan,{true,false,false});
            if(plan.kind==ShinoM3E::Kind::UnsafeOtaReserved)
                return finish(Step::OtaHeld,403);
            if(plan.routePresentInInspectedSource)
                return finish(Step::LegacyHeld,503);
            return finish(Step::Rejected,404);
        }
        if(!key_) return finish(Step::Rejected,403);
        gate_=new(gateMemory_) ShinoM3C::Gate(id_,ledger_.revision());
        for(size_t i=0u;i<lineUsed_;++i)
            if(gate_->headerByte<Crypto>(first_[i],now-start_,key_)
                ==ShinoM3C::Phase::Reject)
                return finish(Step::Rejected,403);
        stage_=Stage::Headers;
        return Step::Pending;
    }
    Step finish(Step outcome,int code) {
        const char* value=code==202
          ? "{\"lab\":\"M3F_CRYPTO_REVIEW\",\"applied\":false}"
          : code==503
            ? "{\"lab\":\"LEGACY_NOT_PORTED\",\"applied\":false}"
            : "{\"lab\":\"REJECTED_NO_MUTATION\",\"applied\":false}";
        const char* reason=code==202?"Accepted":code==503?"Service Unavailable":
          code==408?"Request Timeout":code==409?"Conflict":code==404?"Not Found":
          code==400?"Bad Request":"Forbidden";
        char hdr[160]{};
        const int n=std::snprintf(hdr,sizeof(hdr),
            "HTTP/1.1 %d %s\r\nContent-Length: %u\r\n"
            "Connection: close\r\nContent-Type: application/json\r\n\r\n",
            code,reason,static_cast<unsigned>(std::strlen(value)));
        if(n>0&&static_cast<size_t>(n)<sizeof(hdr)) {
            (void)client_.write(reinterpret_cast<const uint8_t*>(hdr),
                                static_cast<size_t>(n));
            (void)client_.write(reinterpret_cast<const uint8_t*>(value),
                                std::strlen(value));
        }
        client_.stop();
        active_=false;
        drop();
        return outcome;
    }
};
} // namespace ShinoM3F
