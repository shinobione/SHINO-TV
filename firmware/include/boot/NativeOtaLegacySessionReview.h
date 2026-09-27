// SPDX-License-Identifier: GPL-3.0-or-later
#pragma once
// V2.1 HOST-ONLY LEGACY SESSION DECISION PARITY (NOT REGISTERED).
// Models FirstBootBridge's two volatile GET-only session slots, 2h millis
// wrap-safe expiry, bounded Cookie parsing and per-route Digest/cookie rules.
// DigestPassed is an OUTSIDE TEST FIXTURE INPUT, NOT a password verifier.
// FreshToken16 must be supplied by separately reviewed hardware RNG; this
// code never generates credentials. No actual HTTP response, telemetry write,
// ESP server, FS, Updater, restart, OTA permission or real session is created.
#include "boot/NativeOtaPort80Plan.h"
#include <array>
#include <cstddef>
#include <cstdint>

namespace ShinoNativeOta {
enum class LegacySessionDecision : uint8_t {
    DigestChallengeOnly, BackgroundForbiddenNoChallenge, ReadAllowed,
    WouldIssueReadSession, WouldAcceptMetricsPost, FactoryPostDisabled,
    UnknownRequiresDigestThen404
};
struct LegacyDecision {
    LegacySessionDecision decision=LegacySessionDecision::DigestChallengeOnly;
    bool readCookieUsed=false;
    bool wouldIssueCookie=false;
    bool actualDigestChecked=false; // ALWAYS false: fixture-provided flag only.
    bool requestActuallyDispatched=false; // ALWAYS false.
    bool metricsMutationPerformed=false; // ALWAYS false.
    bool flashWriterPresent=false; // ALWAYS false.
};

class NativeOtaLegacySessionReview final {
public:
    static constexpr uint32_t kReadLifetimeMs=2u*60u*60u*1000u;
    static constexpr size_t kMaxCookieHeaderBytes=256u;
    static constexpr size_t kSlots=2u;
    NativeOtaLegacySessionReview()=default;
    NativeOtaLegacySessionReview(const NativeOtaLegacySessionReview&)=delete;
    NativeOtaLegacySessionReview& operator=(const NativeOtaLegacySessionReview&)=delete;

    // cookieBytes is a bounded raw Cookie header *value*, not the full line.
    // proposedFreshToken16 models a fresh 128-bit ESP RNG token when Digest
    // authenticates GET /. All-zero tokens are refused (more conservative
    // than current live source, which relies on successful ESP.random()).
    LegacyDecision decide(Port80Plan route,bool fixtureDigestPassed,
                          const char* cookieBytes,size_t cookieLen,
                          uint32_t privateApPeer,uint32_t nowMs,
                          const std::array<uint8_t,16>& proposedFreshToken16={}) {
        LegacyDecision out{};
        if(route==Port80Plan::OtaReservedArm ||
           route==Port80Plan::OtaReservedUpload ||
           route==Port80Plan::OtaReservedReject ||
           route==Port80Plan::LegacyFactoryReturnPost) {
            out.decision=LegacySessionDecision::FactoryPostDisabled;
            return out;
        }
        if(route==Port80Plan::LegacyAuthenticatedNotFound) {
            out.decision=fixtureDigestPassed
                ? LegacySessionDecision::UnknownRequiresDigestThen404
                : LegacySessionDecision::DigestChallengeOnly;
            return out;
        }
        const bool cookieValid=valid(cookieBytes,cookieLen,privateApPeer,nowMs);
        switch(route) {
        case Port80Plan::LegacyDashboardGet:
            if(cookieValid) {out.decision=LegacySessionDecision::ReadAllowed;out.readCookieUsed=true;return out;}
            if(!fixtureDigestPassed) return out;
            if(!issue(proposedFreshToken16,privateApPeer,nowMs))return out;
            out.decision=LegacySessionDecision::WouldIssueReadSession;
            out.wouldIssueCookie=true;
            return out;
        case Port80Plan::LegacyJavascriptGet:
        case Port80Plan::LegacyCapabilitiesGet:
            if(cookieValid) {out.decision=LegacySessionDecision::ReadAllowed;out.readCookieUsed=true;return out;}
            if(fixtureDigestPassed)out.decision=LegacySessionDecision::ReadAllowed;
            return out;
        case Port80Plan::LegacyMetricsGet:
            // A poll NEVER tries Digest again: avoids rotating Chrome's shared
            // nonce on every ~2s background fetch. Reopen GET / to renew.
            out.decision=cookieValid
                ? LegacySessionDecision::ReadAllowed
                : LegacySessionDecision::BackgroundForbiddenNoChallenge;
            out.readCookieUsed=cookieValid;
            return out;
        case Port80Plan::LegacyMetricsPost:
            // Existing Windows companion is separately Digest authenticated;
            // a READ cookie MUST NOT authorize POST, even if it is valid.
            if(fixtureDigestPassed)out.decision=LegacySessionDecision::WouldAcceptMetricsPost;
            return out;
        case Port80Plan::LegacyStatusGet:
        case Port80Plan::LegacyFsPlanGet:
        case Port80Plan::LegacyFactoryReturnGet:
            if(fixtureDigestPassed)out.decision=LegacySessionDecision::ReadAllowed;
            return out;
        default:
            return out;
        }
    }

    // Returns a token only for assertions in a synthetic fixture. Production
    // generation, Set-Cookie attributes and secret secrecy are separate gates.
    bool tokenForHostTestOnly(size_t slot,char out[33]) const {
        if(slot>=slots_.size() || !slots_[slot].occupied || !out)return false;
        for(size_t i=0u;i<33u;++i)out[i]=slots_[slot].token[i];
        return true;
    }

private:
    struct Session {
        std::array<char,33> token{};
        uint32_t peer=0u,issued=0u;
        bool occupied=false;
    };
    std::array<Session,kSlots> slots_{};

    static bool sameKey(const char* value,size_t n,const char* key) {
        size_t i=0u;
        while(i<n && key[i] && value[i]==key[i])++i;
        return i==n && key[i]=='\0';
    }
    static bool parseCookie(const char* p,size_t length,std::array<char,33>& token) {
        if(!p || length==0u || length>kMaxCookieHeaderBytes)return false;
        bool found=false;
        size_t at=0u;
        while(at<length) {
            size_t end=at;
            while(end<length && p[end]!=';')++end;
            size_t start=at;
            while(start<end && (p[start]==' '||p[start]=='\t'))++start;
            while(end>start && (p[end-1u]==' '||p[end-1u]=='\t'))--end;
            size_t eq=start;
            while(eq<end && p[eq]!='=')++eq;
            if(eq>start && eq<end &&
               sameKey(p+start,eq-start,"SHINO_READ_SESSION")) {
                if(found || end-eq-1u!=32u)return false;
                found=true;
                for(size_t i=0;i<32u;++i)token[i]=p[eq+1u+i];
                token[32u]='\0';
            }
            at=end;
            // Continue from original semicolon even after trimming whitespace.
            while(at<length && p[at]!=';')++at;
            if(at<length)++at;
        }
        return found;
    }
    bool valid(const char* p,size_t length,uint32_t peer,uint32_t now) const {
        if(peer==0u)return false;
        std::array<char,33> provided{};
        if(!parseCookie(p,length,provided))return false;
        for(const Session& s:slots_) {
            if(!s.occupied || s.peer!=peer ||
               static_cast<uint32_t>(now-s.issued)>=kReadLifetimeMs)continue;
            uint8_t diff=0u;
            for(size_t i=0;i<32u;++i)
                diff|=static_cast<uint8_t>(s.token[i]^provided[i]);
            if(diff==0u)return true;
        }
        return false;
    }
    bool issue(const std::array<uint8_t,16>& entropy,uint32_t peer,uint32_t now) {
        if(peer==0u)return false;
        uint8_t nonzero=0u;
        for(uint8_t b:entropy)nonzero|=b;
        if(!nonzero)return false;
        size_t slot=0u;
        uint32_t oldest=0u;
        for(size_t i=0u;i<slots_.size();++i) {
            const uint32_t age=static_cast<uint32_t>(now-slots_[i].issued);
            if(!slots_[i].occupied || age>=kReadLifetimeMs) {
                slot=i;break;
            }
            if(age>=oldest){oldest=age;slot=i;}
        }
        static constexpr char HEX[]="0123456789abcdef";
        Session next{};
        for(size_t i=0;i<16u;++i) {
            next.token[i*2u]=HEX[entropy[i]>>4u];
            next.token[i*2u+1u]=HEX[entropy[i]&0x0fu];
        }
        next.token[32u]='\0';
        next.peer=peer;
        next.issued=now;
        next.occupied=true;
        slots_[slot]=next;
        return true;
    }
};
} // namespace ShinoNativeOta
