// SPDX-License-Identifier: GPL-3.0-or-later
#pragma once
// M3-C: disconnected, fixed-allocation, source-executed two-gate cryptographic
// experiment. This file MUST NOT be registered with ESP8266WebServer, WiFiServer,
// shino_link, OTA, LittleFS, renderer or the installed device.
//
// Real HMAC-SHA256 over the exact target, binding, revision, mode, transaction,
// content length and declared body SHA-256 is verified BEFORE reading body.
// Body SHA-256 and the exact canonical JSON frame are checked AFTER reading.
//
// CryptoProvider contract:
// static bool hmac(const uint8_t key[32], const uint8_t* bytes, size_t n,
//                  uint8_t out[32]);
// static bool sha256(const uint8_t* bytes, size_t n, uint8_t out[32]);
//
// No production key custody or CSPRNG claim. The key and expected boot/device
// are externally supplied by the caller, never learned from client headers.
#include <cstddef>
#include <cstdint>
#include <cstdio>
#include <cstring>

namespace ShinoM3C {

enum class Phase : uint8_t { Header, AuthenticatedHeader, BodyDigestMatched, VerifiedFrame, Reject };
enum class Mode : uint8_t { Auto, ClockWeather, Monitoring, Music };
struct Result {
    Mode mode = Mode::Auto;
    uint32_t revision = 0u;
    char transaction[33]{};
};
struct Identity {
    const char* host;
    const char* device;
    const char* boot;
};
class Gate final {
public:
    static constexpr size_t kHeaderMax = 1024u;
    static constexpr size_t kLineMax = 320u;
    static constexpr size_t kBodyMax = 240u;
    static constexpr unsigned kFields = 11u;
    static constexpr uint32_t kHeaderDeadlineMs = 1000u; // injected lab clock only
    static constexpr uint32_t kBodyDeadlineMs = 2000u;   // injected lab clock only
    static constexpr const char* kRoute = "/api/v1/display/mode";
    static constexpr const char* kProtocol = "shino-display-control-1";

    Gate(const Identity& id, uint32_t expectedRevision)
        : id_(id), expectedRevision_(expectedRevision) {}

    // Feed EXACTLY ONE BYTE at a time. Do not use an upstream bulk read that
    // already pulled unauthenticated body bytes from the socket.
    template<class Crypto>
    Phase headerByte(char b, uint32_t elapsedMs, const uint8_t key[32]) {
        if (phase_ != Phase::Header) return phase_;
        if (elapsedMs > kHeaderDeadlineMs || !key || headerUsed_ >= kHeaderMax ||
            b == '\0') return deny();
        header_[headerUsed_++] = b;
        if (b == '\n') {
            if (headerUsed_ < 2u || header_[headerUsed_-2u] != '\r') return deny();
            const size_t lineLen = headerUsed_ - lineStart_ - 2u;
            if (lineLen > kLineMax) return deny();
            lineStart_ = headerUsed_;
            if (lineLen == 0u) {
                if (!parseHeader() || !authenticateHeader<Crypto>(key))
                    return deny();
                phase_ = Phase::AuthenticatedHeader;
                return phase_;
            }
        } else if (headerUsed_ - lineStart_ > kLineMax + 2u) return deny();
        return phase_;
    }

    // Body must be read only when phase()==AuthenticatedHeader.
    template<class Crypto>
    Phase bodyByte(uint8_t b, uint32_t elapsedMs) {
        if (phase_ != Phase::AuthenticatedHeader) return deny();
        if (elapsedMs > kBodyDeadlineMs || bodyUsed_ >= declaredLength_
            || bodyUsed_ >= kBodyMax) return deny();
        body_[bodyUsed_++] = b;
        if (bodyUsed_ != declaredLength_) return phase_;
        uint8_t got[32]{};
        const bool hashOk = Crypto::sha256(body_, bodyUsed_, got);
        const bool sameHash = constantTime(got, declaredBodyHash_, 32u);
        clear(got, sizeof(got));
        if (!hashOk || !sameHash || !exactCanonicalBody()) return deny();
        phase_ = Phase::BodyDigestMatched;
        return phase_;
    }

    Phase finishAfterExactFraming(bool peerClosed, size_t pendingBytes,
                                  uint32_t elapsedMs) {
        // A HASH-MATCHED body is not an applied command. Explicit FIN
        // and zero unread queued bytes are required before further review.
        if (phase_ != Phase::BodyDigestMatched || !peerClosed ||
            pendingBytes != 0u || elapsedMs > kBodyDeadlineMs) return deny();
        phase_ = Phase::VerifiedFrame;
        return phase_;
    }
    Phase closeOrTimeout() {
        // Any other EOF/cancellation without a verified frame is terminal.
        if (phase_ != Phase::VerifiedFrame) return deny();
        return phase_;
    }

    Phase phase() const { return phase_; }
    size_t consumedHeaders() const { return headerUsed_; }
    size_t consumedBody() const { return bodyUsed_; }
    bool bodyReadingAllowed() const { return phase_==Phase::AuthenticatedHeader; }
    bool verifiedNoSideEffect() const { return phase_==Phase::VerifiedFrame; }
    const Result& resultForOfflineReview() const { return candidate_; }

private:
    struct Span {const char* p; size_t n;};
    enum Field : uint8_t {
        Host = 0, Type = 1, Length = 2, Connection = 3, Device = 4,
        Boot = 5, Revision = 6, ModeField = 7, Tx = 8, BodyHash = 9, Proof = 10
    };
#if defined(SHINO_M3C_INCREMENTAL_HMAC) && SHINO_M3C_INCREMENTAL_HMAC == 1 && \
    defined(SHINO_M3C_STACK_MEMBER_SCRATCH) && SHINO_M3C_STACK_MEMBER_SCRATCH == 1
#error "M3-L incremental HMAC and M3-K member scratch are mutually exclusive"
#endif
    // Eleven exact headers, no unknown fields.
    static constexpr uint16_t kRequiredMask = (1u<<11u)-1u;
    const Identity id_;
    uint32_t expectedRevision_ = 0u;
    char header_[kHeaderMax]{};
    uint8_t body_[kBodyMax]{};
    uint8_t declaredBodyHash_[32]{};
    char proofHex_[65]{};
#if defined(SHINO_M3C_STACK_MEMBER_SCRATCH) && SHINO_M3C_STACK_MEMBER_SCRATCH == 1
    // M3-K experimental trade-off only: place the exactly same 350-byte
    // canonical HMAC message scratch on the *Gate instance* instead of CONT
    // stack. The owner MUST provide one serialized Gate per connection.
    // Persistent secret-bearing scratch is wiped after each HMAC operation;
    // it must never be a function-local static shared across connections.
    char signedFieldsScratch_[350]{};
#endif
    size_t headerUsed_ = 0u, lineStart_ = 0u, bodyUsed_ = 0u;
    uint16_t declaredLength_ = 0u;
    uint16_t seen_ = 0u;
    Phase phase_ = Phase::Header;
    Result candidate_{};
    const char* modeLiteral_ = nullptr;

    static void clear(void* p, size_t n) {
        volatile uint8_t* out = static_cast<volatile uint8_t*>(p);
        for (size_t i=0u;i<n;++i) out[i]=0u;
    }
    Phase deny() {
        clear(body_, sizeof(body_));
        clear(declaredBodyHash_, sizeof(declaredBodyHash_));
        clear(proofHex_, sizeof(proofHex_));
        candidate_ = Result{};
        modeLiteral_ = nullptr;
        phase_ = Phase::Reject;
        return phase_;
    }
    static bool exact(Span s, const char* literal, bool insensitive=false) {
        if (!literal) return false;
        size_t at=0u;
        while (literal[at]) {
            if (at>=s.n) return false;
            char a=s.p[at], b=literal[at];
            if (insensitive) {
                if (a>='A' && a<='Z') a = static_cast<char>(a+32);
                if (b>='A' && b<='Z') b = static_cast<char>(b+32);
            }
            if (a!=b) return false;
            ++at;
        }
        return at==s.n;
    }
    static bool safeFieldName(Span s) {
        if (!s.n || s.n>32u) return false;
        for (size_t i=0u;i<s.n;++i) {
            const char c=s.p[i];
            if (!((c>='a'&&c<='z')||(c>='A'&&c<='Z')||
                  (c>='0'&&c<='9')||c=='-'))
                return false;
        }
        return true;
    }
    static int nibble(char c) {
        if (c>='0'&&c<='9') return c-'0';
        if (c>='a'&&c<='f') return c-'a'+10;
        return -1;
    }
    static bool decodeHex(Span s, uint8_t* out, size_t n) {
        if (s.n != n*2u) return false;
        uint8_t nonzero=0u;
        for(size_t i=0u;i<n;++i) {
            int a=nibble(s.p[i*2u]),b=nibble(s.p[i*2u+1u]);
            if (a<0||b<0) return false;
            out[i]=static_cast<uint8_t>((a<<4)|b);
            nonzero |= out[i];
        }
        return nonzero!=0u;
    }
    static bool saveHex(Span s, char* out, size_t n) {
        if (s.n!=n) return false;
        bool nonzero=false;
        for(size_t i=0u;i<n;++i) {
            if(nibble(s.p[i])<0) return false;
            out[i]=s.p[i];
            nonzero |= out[i]!='0';
        }
        out[n]='\0';
        return nonzero;
    }
    static bool decimal(Span s, uint32_t max, uint32_t& out) {
        if (!s.n || s.n>10u || (s.n>1u && s.p[0]=='0')) return false;
        uint32_t value=0u;
        for(size_t i=0u;i<s.n;++i) {
            if(s.p[i]<'0'||s.p[i]>'9') return false;
            const uint32_t digit=static_cast<uint32_t>(s.p[i]-'0');
            if(value>(max-digit)/10u) return false;
            value=value*10u+digit;
        }
        out=value;
        return true;
    }
    static bool constantTime(const uint8_t* a,const uint8_t* b,size_t n) {
        uint8_t mismatch=0u;
        for(size_t i=0u;i<n;++i) mismatch |= static_cast<uint8_t>(a[i]^b[i]);
        return mismatch==0u;
    }
    static const char* literalFor(Span s, Mode& mode) {
        if (exact(s,"AUTO")) {mode=Mode::Auto;return "AUTO";}
        if (exact(s,"CLOCK_WEATHER")) {mode=Mode::ClockWeather;return "CLOCK_WEATHER";}
        if (exact(s,"MONITORING")) {mode=Mode::Monitoring;return "MONITORING";}
        if (exact(s,"MUSIC")) {mode=Mode::Music;return "MUSIC";}
        return nullptr;
    }
    bool parseHeader() {
        if (!id_.host || !id_.device || !id_.boot) return false;
        size_t start=0u, end=0u;
        bool first=true;
        uint16_t seen=0u;
        for (;;) {
            end=start;
            while(end+1u<headerUsed_ && !(header_[end]=='\r'&&header_[end+1u]=='\n')) ++end;
            if (end+1u>=headerUsed_) return false;
            if (first) {
                if(!exact(Span{header_,end},"POST /api/v1/display/mode HTTP/1.1"))
                    return false;
                first=false;
                start=end+2u;
                continue;
            }
            if(end==start) {
                if(end+2u!=headerUsed_ || seen!=kRequiredMask) return false;
                seen_=seen;
                return true;
            }
            if(end-start>kLineMax) return false;
            size_t colon=start;
            while(colon<end && header_[colon]!=':') ++colon;
            if(colon==start || colon==end || !safeFieldName(Span{header_+start,colon-start}))
                return false;
            size_t valStart=colon+1u;
            if(valStart<end && header_[valStart]==' ') ++valStart;
            if(valStart==end || header_[valStart]==' ' || header_[valStart]=='\t'
               || header_[end-1u]==' ') return false;
            for(size_t j=valStart;j<end;++j) {
                unsigned char c=static_cast<unsigned char>(header_[j]);
                if(c<33u || c>=127u) return false;
            }
            Span name{header_+start,colon-start},value{header_+valStart,end-valStart};
            Field field;
            if(exact(name,"Host",true))field=Host;
            else if(exact(name,"Content-Type",true))field=Type;
            else if(exact(name,"Content-Length",true))field=Length;
            else if(exact(name,"Connection",true))field=Connection;
            else if(exact(name,"X-Shino-Device",true))field=Device;
            else if(exact(name,"X-Shino-Boot",true))field=Boot;
            else if(exact(name,"X-Shino-Revision",true))field=Revision;
            else if(exact(name,"X-Shino-Mode",true))field=ModeField;
            else if(exact(name,"X-Shino-Tx",true))field=Tx;
            else if(exact(name,"X-Shino-Body-Sha256",true))field=BodyHash;
            else if(exact(name,"X-Shino-Proof",true))field=Proof;
            else return false; // no TE/CL ambiguity, no proxies, no unknowns
            const uint16_t bit=uint16_t(1u<<field);
            if(seen & bit) return false;
            seen=uint16_t(seen|bit);
            switch(field) {
                case Host:
                    if(!exact(value,id_.host)) return false;
                    break;
                case Type:
                    if(!exact(value,"application/json")) return false;
                    break;
                case Length: {
                    uint32_t n=0u;
                    if(!decimal(value,kBodyMax,n)||n==0u) return false;
                    declaredLength_=static_cast<uint16_t>(n);break;
                }
                case Connection:
                    if(!exact(value,"close",true)) return false;
                    break;
                case Device:
                    if(!exact(value,id_.device)||value.n!=16u)return false;
                    for(size_t i=0u;i<value.n;++i) if(nibble(value.p[i])<0)return false;
                    break;
                case Boot:
                    if(!exact(value,id_.boot)||value.n!=32u)return false;
                    for(size_t i=0u;i<value.n;++i) if(nibble(value.p[i])<0)return false;
                    break;
                case Revision: {
                    uint32_t n=0u;
                    if(!decimal(value,0xffffffffu,n)||n!=expectedRevision_||
                       n==0xffffffffu) return false;
                    candidate_.revision=n;break;
                }
                case ModeField:
                    modeLiteral_=literalFor(value,candidate_.mode);
                    if(!modeLiteral_) return false;
                    break;
                case Tx:
                    if(!saveHex(value,candidate_.transaction,32u)) return false;
                    break;
                case BodyHash:
                    if(!decodeHex(value,declaredBodyHash_,32u)) return false;
                    break;
                case Proof:
                    if(!saveHex(value,proofHex_,64u)) return false;
                    break;
                default:return false;
            }
            start=end+2u;
        }
    }
    template<class Crypto>
    bool authenticateHeader(const uint8_t key[32]) {
        // This key MUST be provisioned out of band, unique to display control.
        // The lab rejects all-zero keys, but cannot prove secrecy/rotation.
        uint8_t keybits=0u;
        for(size_t i=0u;i<32u;++i)keybits |= key[i];
        if(!keybits || !modeLiteral_)return false;
        static constexpr char hex[]="0123456789abcdef";
        char hash[65]{};
        for(size_t i=0u;i<32u;++i) {
            hash[i*2u]=hex[declaredBodyHash_[i]>>4];
            hash[i*2u+1u]=hex[declaredBodyHash_[i]&15u];
        }
#if defined(SHINO_M3C_INCREMENTAL_HMAC) && SHINO_M3C_INCREMENTAL_HMAC == 1
        // M3-L: immutable canonical wire sequence, delivered in bounded
        // NUL-terminated segments straight into HMAC update. No full
        // canonical message exists on stack, heap or persistent Gate RAM.
        // Numeric decimal spellings must match the original snprintf.
        char revisionDigits[11]{},lengthDigits[4]{};
        const int revisionSize=std::snprintf(revisionDigits,sizeof(revisionDigits),
            "%lu",static_cast<unsigned long>(candidate_.revision));
        const int lengthSize=std::snprintf(lengthDigits,sizeof(lengthDigits),
            "%u",static_cast<unsigned>(declaredLength_));
        const bool lengthsOk=revisionSize>0 &&
            static_cast<size_t>(revisionSize)<sizeof(revisionDigits) &&
            lengthSize>0 &&
            static_cast<size_t>(lengthSize)<sizeof(lengthDigits);
        const char* const parts[]{
            "SHINO-M3-CONTROL-1\nPOST\n",kRoute,"\n",id_.host,"\n",
            id_.device,"\n",id_.boot,"\n",revisionDigits,"\n",
            modeLiteral_,"\n",candidate_.transaction,"\n",
            lengthDigits,"\n",hash
        };
        uint8_t actual[32]{},expected[32]{};
        const bool decoded=decodeHex(Span{proofHex_,64u},expected,32u);
        const bool computed=lengthsOk && decoded &&
            Crypto::hmacFragments(key,parts,sizeof(parts)/sizeof(parts[0]),
                                  actual);
        const bool accepted=computed && constantTime(actual,expected,32u);
        clear(hash,sizeof(hash));
        clear(revisionDigits,sizeof(revisionDigits));
        clear(lengthDigits,sizeof(lengthDigits));
        clear(actual,sizeof(actual));clear(expected,sizeof(expected));
        clear(proofHex_,sizeof(proofHex_));
        return accepted;
#else
        static constexpr size_t kSignedFieldBytes=350u;
#if defined(SHINO_M3C_STACK_MEMBER_SCRATCH) && SHINO_M3C_STACK_MEMBER_SCRATCH == 1
        char* const signedFields=signedFieldsScratch_;
        clear(signedFields,kSignedFieldBytes);
#else
        char signedFields[kSignedFieldBytes]{};
#endif
        const int n=std::snprintf(signedFields,kSignedFieldBytes,
            "SHINO-M3-CONTROL-1\nPOST\n%s\n%s\n%s\n%s\n%lu\n%s\n%s\n%u\n%s",
            kRoute,id_.host,id_.device,id_.boot,
            static_cast<unsigned long>(candidate_.revision),
            modeLiteral_,candidate_.transaction,
            static_cast<unsigned>(declaredLength_),hash);
        clear(hash,sizeof(hash));
        if(n<=0 || static_cast<size_t>(n)>=kSignedFieldBytes) {
            clear(signedFields,kSignedFieldBytes);return false;
        }
        uint8_t actual[32]{},expected[32]{};
        const bool decoded=decodeHex(Span{proofHex_,64u},expected,32u);
        const bool computed=decoded && Crypto::hmac(key,
            reinterpret_cast<const uint8_t*>(signedFields),
            static_cast<size_t>(n),actual);
        const bool accepted=computed && constantTime(actual,expected,32u);
        clear(signedFields,kSignedFieldBytes);
        clear(actual,sizeof(actual));clear(expected,sizeof(expected));
        clear(proofHex_,sizeof(proofHex_));
        return accepted;
#endif
    }
    bool exactCanonicalBody() const {
        char expected[kBodyMax+1u]{};
        const int n=std::snprintf(expected,sizeof(expected),
            "{\"boot\":\"%s\",\"device\":\"%s\",\"mode\":\"%s\","
            "\"protocol\":\"%s\",\"revision\":%lu,\"tx\":\"%s\"}",
            id_.boot,id_.device,modeLiteral_,kProtocol,
            static_cast<unsigned long>(candidate_.revision),
            candidate_.transaction);
        return n>0 && static_cast<size_t>(n)==bodyUsed_
            && constantTime(reinterpret_cast<const uint8_t*>(expected),body_,bodyUsed_);
    }
};

// In-memory transaction lab only; no renderer, filesystem or owner authority.
// The caller MUST serialize application, bind the same verified boot and
// revalidate the current revision without a concurrent writer. This class
// does not provide either cross-thread exclusion or reboot persistence.
class OfflineCasLedger final {
public:
    explicit OfflineCasLedger(uint32_t startRevision = 0u)
        : revision_(startRevision) {}
    bool acceptVerifiedForLab(const Gate& gate) {
        if (!gate.verifiedNoSideEffect() || revision_ == 0xffffffffu)
            return false;
        const Result& candidate = gate.resultForOfflineReview();
        if (candidate.revision != revision_ || !candidate.transaction[0])
            return false;
        uint8_t differs = 0u;
        for (size_t i=0u;i<32u;++i)
            differs |= static_cast<uint8_t>(
                candidate.transaction[i]^lastTransaction_[i]);
        if (!differs) return false;
        for (size_t i=0u;i<33u;++i)
            lastTransaction_[i]=candidate.transaction[i];
        ++revision_;
        return true;
    }
    uint32_t revision() const { return revision_; }
private:
    uint32_t revision_ = 0u;
    char lastTransaction_[33]{};
};

} // namespace ShinoM3C
