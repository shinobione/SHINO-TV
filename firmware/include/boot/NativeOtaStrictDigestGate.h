// SPDX-License-Identifier: GPL-3.0-or-later
#pragma once
// SHINO V2.1: pure, disconnected, HOST-TESTED dedicated SHA-256 HTTP Digest
// one-shot proof contract. NO HTTP listener, nonce generator, owner credential,
// updater writer, filesystem or persistent session.
//
// Do not use the pinned core-3.1.2 ESP8266WebServer::authenticateDigest()
// to authorize firmware writes: its Digest calculation uses client-provided
// uri without explicitly matching the real requested URI, and does not track
// nonce-count reuse. This strict contract requires Digest algorithm SHA-256
// (RFC 7616 qop=auth), actual method POST and EXACT route, dedicated realm,
// one-time nonce, opaque, nc=00000001 and independently derived secret HA1.
// HashProvider contract: static bool hex(const char*, size_t, char out[65]).
// The upstream browser's SHA-256 challenge behavior MUST be tested separately
// before connecting a privileged route; host proof is not live HTTP auth.
#include "boot/NativeOtaRawHeaderGate.h"
#include <cstddef>
#include <cstdint>
#include <cstdio>

namespace ShinoNativeOta {

enum class StrictDigestPhase : uint8_t { Idle, Challenged, VerifiedForReviewOnly, Aborted };

template<class HashProvider>
class StrictOtaDigestGate final {
public:
    static constexpr uint32_t kLifetimeMs = 60'000u;
    static constexpr size_t kMaxAuthorizationBytes = 640u;

    StrictOtaDigestGate()=default;
    StrictOtaDigestGate(const StrictOtaDigestGate&)=delete;
    StrictOtaDigestGate& operator=(const StrictOtaDigestGate&)=delete;

    // Both nonce and opaque must come from independently audited CSPRNG.
    // Caller must create a fresh gate for each distinct privileged request.
    bool challenge(uint32_t privateApPeer, RawOtaRequestKind exactKind,
                   const char* unpredictableNonce32,
                   const char* unpredictableOpaque32, uint32_t nowMs) {
        if (phase_!=StrictDigestPhase::Idle) return false;
        if (privateApPeer==0u || !lowerHexN(unpredictableNonce32,32u) ||
            !lowerHexN(unpredictableOpaque32,32u) ||
            allZero(unpredictableNonce32,32u) || allZero(unpredictableOpaque32,32u) ||
            (exactKind!=RawOtaRequestKind::Arm &&
             exactKind!=RawOtaRequestKind::SignedTransport))
            return fail();
        peer_=privateApPeer;
        kind_=exactKind;
        copy32(nonce_,unpredictableNonce32);
        copy32(opaque_,unpredictableOpaque32);
        issuedAt_=nowMs;
        phase_=StrictDigestPhase::Challenged;
        return true;
    }

    // The exact URI and method are determined ONLY from a separately
    // validated raw request, not copied from the Authorization header.
    // expectedHa1Sha256 = SHA256(username:SHINO-OTA:owner-private-password);
    // it MUST be generated from private build credentials, never request JSON.
    bool verify(uint32_t actualPeer,RawOtaRequestKind actualKind,
                const char* rawAuthorization,size_t authorizationLength,
                const char* exactOwnerUsername,const char* expectedHa1Sha256,
                uint32_t nowMs) {
        if (phase_!=StrictDigestPhase::Challenged) return false;
        if (actualPeer!=peer_ || actualKind!=kind_ ||
            static_cast<uint32_t>(nowMs-issuedAt_)>=kLifetimeMs ||
            !lowerHexN(expectedHa1Sha256,64u) || !exactOwnerUsername ||
            boundedLength(exactOwnerUsername,65u)==0u ||
            boundedLength(exactOwnerUsername,65u)>64u)
            return fail();
        Fields f{};
        if (!parse(rawAuthorization,authorizationLength,f)) return fail();
        const char* route=kind_==RawOtaRequestKind::Arm
            ? "/api/v1/bridge/ota/arm" : "/api/v1/bridge/ota/upload";
        if (!equals(f.username,exactOwnerUsername) ||
            !equals(f.realm,"SHINO-OTA") ||
            !equals(f.uri,route) ||
            !equals(f.qop,"auth") ||
            !equals(f.algorithm,"SHA-256") ||
            !equals(f.nc,"00000001") ||
            !same32(f.nonce,nonce_) || !same32(f.opaque,opaque_) ||
            !lowerHexSpan(f.response,64u) ||
            f.cnonce.n<8u || f.cnonce.n>64u)
            return fail();
        for(size_t i=0;i<f.cnonce.n;++i) {
            const char c=f.cnonce.p[i];
            if (!((c>='a'&&c<='z')||(c>='A'&&c<='Z')||
                  (c>='0'&&c<='9')||c=='-'||c=='_')) return fail();
        }
        char ha2[65]{};
        char message[96]{};
        int n=std::snprintf(message,sizeof(message),"POST:%s",route);
        if (n<0 || static_cast<size_t>(n)>=sizeof(message) ||
            !HashProvider::hex(message,static_cast<size_t>(n),ha2)) return fail();
        // One-shot nonce-count "00000001" plus qop=auth disallows replay.
        char responseMessage[300]{};
        n=std::snprintf(responseMessage,sizeof(responseMessage),
                        "%s:%s:00000001:%.*s:auth:%s",
                        expectedHa1Sha256,nonce_,static_cast<int>(f.cnonce.n),
                        f.cnonce.p,ha2);
        if (n<0 || static_cast<size_t>(n)>=sizeof(responseMessage)) return fail();
        char computed[65]{};
        if (!HashProvider::hex(responseMessage,static_cast<size_t>(n),computed))
            return fail();
        uint8_t mismatch=0u;
        for(size_t i=0;i<64u;++i)
            mismatch|=static_cast<uint8_t>(computed[i]^f.response.p[i]);
        for(auto& c:computed)c='\0';
        for(auto& c:ha2)c='\0';
        for(auto& c:message)c='\0';
        for(auto& c:responseMessage)c='\0';
        if (mismatch) return fail();
        wipe();
        phase_=StrictDigestPhase::VerifiedForReviewOnly;
        return true;
    }

    bool checkTimeout(uint32_t nowMs) {
        if (phase_!=StrictDigestPhase::Challenged) return false;
        if (static_cast<uint32_t>(nowMs-issuedAt_)>=kLifetimeMs) return fail();
        return true;
    }
    void abort() {
        if (phase_==StrictDigestPhase::Challenged) fail();
    }
    StrictDigestPhase phase() const {return phase_;}

private:
    struct Span {const char* p=nullptr;size_t n=0u;};
    struct Fields {
        Span username,realm,nonce,uri,response,opaque,qop,nc,cnonce,algorithm;
    };
    static size_t boundedLength(const char* p,size_t limit) {
        if (!p) return 0u;
        for(size_t i=0;i<limit;++i) if(p[i]=='\0')return i;
        return limit+1u;
    }
    static bool lowerHexN(const char* p,size_t n) {
        if (!p || boundedLength(p,n+1u)!=n) return false;
        for(size_t i=0;i<n;++i)
            if (!((p[i]>='0'&&p[i]<='9')||(p[i]>='a'&&p[i]<='f'))) return false;
        return true;
    }
    static bool allZero(const char* p,size_t n) {
        uint8_t x=0u;
        for(size_t i=0;i<n;++i)x|=static_cast<uint8_t>(p[i]!='0');
        return x==0u;
    }
    static bool equals(Span a,const char* b) {
        if(!a.p || !b) return false;
        size_t i=0u;
        while(i<a.n && b[i] && a.p[i]==b[i]) ++i;
        return i==a.n && b[i]=='\0';
    }
    static bool same32(Span a,const char* b) {
        if(a.n!=32u || !a.p) return false;
        uint8_t d=0u;
        for(size_t i=0;i<32u;++i)d|=static_cast<uint8_t>(a.p[i]^b[i]);
        return d==0u;
    }
    static bool lowerHexSpan(Span a,size_t n) {
        if(a.n!=n || !a.p) return false;
        for(size_t i=0;i<n;++i)
            if (!((a.p[i]>='0'&&a.p[i]<='9')||
                  (a.p[i]>='a'&&a.p[i]<='f')))return false;
        return true;
    }
    static void copy32(char (&dst)[33],const char* src) {
        for(size_t i=0;i<32u;++i)dst[i]=src[i];
        dst[32u]='\0';
    }
    static bool keyIs(const char* p,size_t n,const char* literal) {
        size_t i=0u;
        while(i<n && literal[i] && p[i]==literal[i])++i;
        return i==n && literal[i]=='\0';
    }
    static bool parse(const char* d,size_t n,Fields& f) {
        if (!d || n<15u || n>kMaxAuthorizationBytes) return false;
        static constexpr char prefix[]="Digest ";
        for(size_t i=0;i<7u;++i)if(d[i]!=prefix[i])return false;
        size_t pos=7u;
        uint16_t used=0u;
        unsigned items=0u;
        while(pos<n) {
            while(pos<n && d[pos]==' ')++pos;
            if(pos>=n || items==10u)return false;
            const size_t start=pos;
            while(pos<n && ((d[pos]>='a'&&d[pos]<='z')||d[pos]=='-'))++pos;
            const size_t klen=pos-start;
            if(klen==0u || pos>=n || d[pos++]!='=')return false;
            const bool quoted=pos<n && d[pos]=='"';
            if(quoted)++pos;
            const size_t valueStart=pos;
            if(quoted) {
                while(pos<n && d[pos]!='"') {
                    const char c=d[pos];
                    if(c=='\\' || static_cast<unsigned char>(c)<33u ||
                       static_cast<unsigned char>(c)>126u)return false;
                    ++pos;
                }
                if(pos>=n)return false;
            } else {
                while(pos<n && d[pos]!=',' && d[pos]!=' ') {
                    if(static_cast<unsigned char>(d[pos])<33u ||
                       static_cast<unsigned char>(d[pos])>126u ||
                       d[pos]=='"' || d[pos]=='\\')return false;
                    ++pos;
                }
            }
            const Span value{d+valueStart,pos-valueStart};
            if(value.n==0u)return false;
            if(quoted)++pos;
            Span* target=nullptr;
            uint16_t bit=0u;
            if(keyIs(d+start,klen,"username"))      {target=&f.username;bit=1u<<0;}
            else if(keyIs(d+start,klen,"realm"))     {target=&f.realm;bit=1u<<1;}
            else if(keyIs(d+start,klen,"nonce"))     {target=&f.nonce;bit=1u<<2;}
            else if(keyIs(d+start,klen,"uri"))       {target=&f.uri;bit=1u<<3;}
            else if(keyIs(d+start,klen,"response"))  {target=&f.response;bit=1u<<4;}
            else if(keyIs(d+start,klen,"opaque"))    {target=&f.opaque;bit=1u<<5;}
            else if(keyIs(d+start,klen,"qop"))       {target=&f.qop;bit=1u<<6;}
            else if(keyIs(d+start,klen,"nc"))        {target=&f.nc;bit=1u<<7;}
            else if(keyIs(d+start,klen,"cnonce"))    {target=&f.cnonce;bit=1u<<8;}
            else if(keyIs(d+start,klen,"algorithm")) {target=&f.algorithm;bit=1u<<9;}
            else return false;
            if(used & bit)return false; // duplicate Digest parameter: fail closed
            used|=bit;*target=value;++items;
            while(pos<n && d[pos]==' ')++pos;
            if(pos<n) {
                if(d[pos++]!=',' || pos==n)return false;
            }
        }
        return used==static_cast<uint16_t>((1u<<10u)-1u);
    }
    void wipe() {
        for(auto& c:nonce_)c='\0';
        for(auto& c:opaque_)c='\0';
        peer_=0u;
    }
    bool fail() {
        wipe();
        phase_=StrictDigestPhase::Aborted;
        return false;
    }
    StrictDigestPhase phase_=StrictDigestPhase::Idle;
    RawOtaRequestKind kind_=RawOtaRequestKind::Arm;
    uint32_t peer_=0u, issuedAt_=0u;
    char nonce_[33]{},opaque_[33]{};
};

} // namespace ShinoNativeOta
