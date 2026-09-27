// SPDX-License-Identifier: GPL-3.0-or-later
#pragma once
// V2.1 DISCONNECTED HOST-REVIEW SINGLE-OWNER HTTP INGRESS CONTRACT.
// A bounded first-line and header/body parser classifies the existing legacy
// method/path set but DOES NOT dispatch legacy handlers or authenticate anyone.
// Every OTA-looking request is rejected before header/body accumulation.
// Factory POST is always rejected. No socket/listener, Updater, FS, credentials,
// authorization or firmware write exists in this source. Production replacement
// of ESP8266WebServer still requires distinct live parity review.
#include "boot/NativeOtaPort80Plan.h"
#include <array>
#include <cstddef>
#include <cstdint>

namespace ShinoNativeOta {

enum class SingleIngressReviewPhase : uint8_t {
    FirstLine, Headers, BoundedLegacyBody, AwaitExactClose,
    LegacyRequestReviewedOnly, Rejected
};
enum class SingleIngressRefusal : uint8_t {
    None, Invalid, OtaReservedNoWriter, FactoryWriteDisabled,
    UnsupportedMethodOrPath, LegacyMetricsLengthOutsideBounds,
    InvalidFraming, Deadline
};
struct SingleIngressReviewResult {
    Port80Plan route=Port80Plan::Invalid;
    SingleIngressReviewPhase phase=SingleIngressReviewPhase::FirstLine;
    SingleIngressRefusal refusal=SingleIngressRefusal::None;
    uint32_t bodyBytes=0u;
    uint32_t declaredBodyBytes=0u; // metadata, NEVER an allocation request.
    bool requiresExistingLegacyAuthentication=false;
    bool browserGetCookieMayBeConsidered=false;
    bool routeWasActuallyDispatched=false; // ALWAYS false.
    bool otaWriterCompiled=false;          // ALWAYS false.
};

class NativeOtaSingleIngressShadow final {
public:
    static constexpr size_t kFirstLineBytes=128u;
    static constexpr size_t kHeaderBytes=2048u;
    static constexpr size_t kMaxHeaderCount=24u;
    static constexpr size_t kLegacyMetricsBytes=384u;
    static constexpr uint32_t kHeaderDeadlineMs=10000u;
    static constexpr uint32_t kBodyIdleDeadlineMs=15000u;

    explicit NativeOtaSingleIngressShadow(uint32_t startedMs)
        : startedMs_(startedMs), lastReadMs_(startedMs) {}
    NativeOtaSingleIngressShadow(const NativeOtaSingleIngressShadow&)=delete;
    NativeOtaSingleIngressShadow& operator=(const NativeOtaSingleIngressShadow&)=delete;

    bool feed(const uint8_t* wire,size_t count,uint32_t nowMs) {
        if (phase_!=SingleIngressReviewPhase::FirstLine &&
            phase_!=SingleIngressReviewPhase::Headers &&
            phase_!=SingleIngressReviewPhase::BoundedLegacyBody &&
            phase_!=SingleIngressReviewPhase::AwaitExactClose)
            return false;
        if (!wire || count==0u || !tick(nowMs)) return reject(SingleIngressRefusal::Invalid);
        lastReadMs_=nowMs;
        for(size_t i=0u;i<count;++i) {
            const char c=static_cast<char>(wire[i]);
            if (phase_==SingleIngressReviewPhase::FirstLine) {
                if (lineLength_==kFirstLineBytes)
                    return reject(SingleIngressRefusal::InvalidFraming);
                firstLine_[lineLength_++]=c;
                if (lineLength_>=2u && firstLine_[lineLength_-2u]=='\r' &&
                    firstLine_[lineLength_-1u]=='\n') {
                    classification_=NativeOtaPort80Plan::inspect(
                        firstLine_.data(),lineLength_);
                    if (classification_.plan==Port80Plan::OtaReservedArm ||
                        classification_.plan==Port80Plan::OtaReservedUpload ||
                        classification_.plan==Port80Plan::OtaReservedReject)
                        return reject(SingleIngressRefusal::OtaReservedNoWriter);
                    if (classification_.plan==Port80Plan::LegacyFactoryReturnPost)
                        return reject(SingleIngressRefusal::FactoryWriteDisabled);
                    if (classification_.plan==Port80Plan::Invalid ||
                        classification_.plan==Port80Plan::Incomplete)
                        return reject(SingleIngressRefusal::InvalidFraming);
                    // Unknown non-OTA routes still need independent Digest
                    // BEFORE a future 404, never an actual legacy dispatch.
                    phase_=SingleIngressReviewPhase::Headers;
                }
            } else if (phase_==SingleIngressReviewPhase::Headers) {
                if (headerLength_==kHeaderBytes)
                    return reject(SingleIngressRefusal::InvalidFraming);
                headers_[headerLength_++]=c;
                if (headerLength_>=4u && headers_[headerLength_-4u]=='\r' &&
                    headers_[headerLength_-3u]=='\n' &&
                    headers_[headerLength_-2u]=='\r' &&
                    headers_[headerLength_-1u]=='\n') {
                    if(!inspectHeaders())return reject(SingleIngressRefusal::InvalidFraming);
                    if (classification_.plan==Port80Plan::LegacyMetricsPost &&
                        (bodyExpected_<16u || bodyExpected_>kLegacyMetricsBytes))
                        return reject(SingleIngressRefusal::LegacyMetricsLengthOutsideBounds);
                    phase_=bodyExpected_?
                        SingleIngressReviewPhase::BoundedLegacyBody:
                        SingleIngressReviewPhase::AwaitExactClose;
                }
            } else if (phase_==SingleIngressReviewPhase::BoundedLegacyBody) {
                if (bodyLength_>=bodyExpected_ || bodyExpected_>kLegacyMetricsBytes)
                    return reject(SingleIngressRefusal::InvalidFraming);
                boundedMetrics_[bodyLength_++]=static_cast<uint8_t>(c);
                if (bodyLength_==bodyExpected_)
                    phase_=SingleIngressReviewPhase::AwaitExactClose;
            } else {
                return reject(SingleIngressRefusal::InvalidFraming);
            }
        }
        return true;
    }

    bool tick(uint32_t nowMs) {
        if(phase_==SingleIngressReviewPhase::FirstLine ||
           phase_==SingleIngressReviewPhase::Headers) {
            if(static_cast<uint32_t>(nowMs-startedMs_)>=kHeaderDeadlineMs)
                return reject(SingleIngressRefusal::Deadline);
            return true;
        }
        if(phase_==SingleIngressReviewPhase::BoundedLegacyBody ||
           phase_==SingleIngressReviewPhase::AwaitExactClose) {
            if(static_cast<uint32_t>(nowMs-lastReadMs_)>=kBodyIdleDeadlineMs)
                return reject(SingleIngressRefusal::Deadline);
            return true;
        }
        return false;
    }
    bool finishOnExactTransportClose(uint32_t nowMs) {
        if(phase_!=SingleIngressReviewPhase::AwaitExactClose)return reject(
            SingleIngressRefusal::InvalidFraming);
        if(!tick(nowMs) || bodyLength_!=bodyExpected_)
            return reject(SingleIngressRefusal::InvalidFraming);
        phase_=SingleIngressReviewPhase::LegacyRequestReviewedOnly;
        return true; // Not a permission to invoke a live legacy handler.
    }
    void disconnect() {
        if(phase_!=SingleIngressReviewPhase::LegacyRequestReviewedOnly &&
           phase_!=SingleIngressReviewPhase::Rejected)
            reject(SingleIngressRefusal::InvalidFraming);
    }
    SingleIngressReviewResult result() const {
        SingleIngressReviewResult out{};
        out.route=classification_.plan;
        out.phase=phase_;
        out.refusal=refusal_;
        out.bodyBytes=bodyLength_;
        out.declaredBodyBytes=bodyExpected_;
        out.requiresExistingLegacyAuthentication=
            classification_.plan!=Port80Plan::Invalid &&
            classification_.plan!=Port80Plan::Incomplete &&
            classification_.plan!=Port80Plan::OtaReservedArm &&
            classification_.plan!=Port80Plan::OtaReservedUpload &&
            classification_.plan!=Port80Plan::OtaReservedReject;
        out.browserGetCookieMayBeConsidered=classification_.mayUseBrowserReadCookie;
        return out;
    }
    const uint8_t* boundedMetricsBodyForTestOnly() const {
        return phase_==SingleIngressReviewPhase::LegacyRequestReviewedOnly &&
               classification_.plan==Port80Plan::LegacyMetricsPost
            ? boundedMetrics_.data():nullptr;
    }

    // Raw Cookie HEADER VALUE only, from this already validated host fixture
    // request. Does not confer Digest authority; duplicates are still rejected.
    const char* cookieValueForHostReviewOnly(size_t& n) const {
        n=0u;
        if(phase_!=SingleIngressReviewPhase::LegacyRequestReviewedOnly ||
           !cookiePresent_)return nullptr;
        n=cookieLength_;
        return headers_.data()+cookieStart_;
    }

private:
    struct Span{const char* p;size_t n;};
    static char lower(char c) {return c>='A'&&c<='Z'?static_cast<char>(c+('a'-'A')):c;}
    static bool match(Span s,const char* literal) {
        size_t i=0u;
        while(i<s.n && literal[i] && s.p[i]==literal[i])++i;
        return i==s.n && literal[i]=='\0';
    }
    static bool equalName(Span a,Span b) {
        if(a.n!=b.n)return false;
        for(size_t i=0;i<a.n;++i)if(lower(a.p[i])!=lower(b.p[i]))return false;
        return true;
    }
    static bool token(char c) {
        return (c>='a'&&c<='z')||(c>='A'&&c<='Z')||
               (c>='0'&&c<='9')||c=='-';
    }
    static bool decimal(Span value,uint32_t& out) {
        if(value.n==0u || value.n>9u || (value.n>1u && value.p[0]=='0'))return false;
        uint32_t n=0u;
        for(size_t i=0u;i<value.n;++i) {
            if(value.p[i]<'0'||value.p[i]>'9')return false;
            const uint32_t digit=static_cast<uint32_t>(value.p[i]-'0');
            // A large Content-Length is metadata to reject, not body storage.
            if(n>1000000u)return false;
            n=n*10u+digit;
            if(n>1000000u)return false;
        }
        out=n;return true;
    }
    bool inspectHeaders() {
        size_t at=0u,count=0u;
        Span names[kMaxHeaderCount]{};
        bool host=false,gotLength=false,gotType=false;
        uint32_t declared=0u;
        // headers_ owns only headers after the already-classified first line.
        while(at<headerLength_) {
            size_t end=at;
            while(end+1u<headerLength_ &&
                  !(headers_[end]=='\r'&&headers_[end+1u]=='\n'))++end;
            if(end+1u>=headerLength_)return false;
            if(end==at) {
                if(end+2u!=headerLength_)return false;
                break; // validate Host and Content-Length BEFORE accepting.
            }
            if(count==kMaxHeaderCount || end-at>768u)return false;
            size_t colon=at;
            while(colon<end && headers_[colon]!=':')++colon;
            if(colon==at || colon==end || colon-at>40u)return false;
            for(size_t i=at;i<colon;++i)if(!token(headers_[i]))return false;
            Span name{headers_.data()+at,colon-at};
            for(size_t i=0u;i<count;++i)
                if(equalName(names[i],name))return false;
            names[count++]=name;
            size_t valueStart=colon+1u,valueEnd=end;
            while(valueStart<valueEnd &&
                  (headers_[valueStart]==' '||headers_[valueStart]=='\t'))++valueStart;
            while(valueStart<valueEnd &&
                  (headers_[valueEnd-1u]==' '||headers_[valueEnd-1u]=='\t'))--valueEnd;
            for(size_t i=valueStart;i<valueEnd;++i) {
                const unsigned char c=static_cast<unsigned char>(headers_[i]);
                if(c<32u || c>=127u)return false;
            }
            Span value{headers_.data()+valueStart,valueEnd-valueStart};
            if(equalName(name,Span{"host",4u})) {
                if(!match(value,"192.168.4.1"))return false;
                host=true;
            } else if(equalName(name,Span{"content-length",14u})) {
                if(!decimal(value,declared))return false;
                gotLength=true;
            } else if(equalName(name,Span{"content-type",12u})) {
                gotType=match(value,"application/json");
                if(!gotType)return false;
            } else if(equalName(name,Span{"cookie",6u})) {
                // Store bounded source span for host-only session rule testing.
                // A value >256 is still well-framed HTTP but won't be trusted
                // by the separate legacy read-session parser.
                cookiePresent_=true;
                cookieStart_=valueStart;
                cookieLength_=value.n;
            } else if(equalName(name,Span{"transfer-encoding",17u}) ||
                      equalName(name,Span{"expect",6u}) ||
                      equalName(name,Span{"content-encoding",16u}) ||
                      equalName(name,Span{"trailer",7u}) ||
                      equalName(name,Span{"upgrade",7u}))
                return false;
            at=end+2u;
        }
        if(!host)return false;
        if(classification_.plan==Port80Plan::LegacyMetricsPost) {
            if(!gotLength||!gotType)return false;
            bodyExpected_=declared;
        } else {
            if(gotLength&&declared!=0u)return false;
            if(gotType)return false;
            bodyExpected_=0u;
        }
        // Scan complete header terminator, not merely the first empty line.
        return headerLength_>=4u && headers_[headerLength_-4u]=='\r' &&
               headers_[headerLength_-3u]=='\n' &&
               headers_[headerLength_-2u]=='\r' &&
               headers_[headerLength_-1u]=='\n';
    }
    bool reject(SingleIngressRefusal reason) {
        phase_=SingleIngressReviewPhase::Rejected;
        refusal_=reason;
        for(auto& byte:boundedMetrics_)byte=0u;
        bodyLength_=0u;
        return false;
    }
    uint32_t startedMs_=0u,lastReadMs_=0u;
    Port80Classification classification_{};
    SingleIngressReviewPhase phase_=SingleIngressReviewPhase::FirstLine;
    SingleIngressRefusal refusal_=SingleIngressRefusal::None;
    std::array<char,kFirstLineBytes> firstLine_{};
    std::array<char,kHeaderBytes> headers_{};
    std::array<uint8_t,kLegacyMetricsBytes> boundedMetrics_{};
    size_t lineLength_=0u,headerLength_=0u;
    size_t cookieStart_=0u,cookieLength_=0u;
    bool cookiePresent_=false;
    uint32_t bodyLength_=0u,bodyExpected_=0u;
};
} // namespace ShinoNativeOta
