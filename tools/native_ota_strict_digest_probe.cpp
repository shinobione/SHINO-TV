// SPDX-License-Identifier: GPL-3.0-or-later
// Host-only synthetic RFC7616 SHA-256 Digest verifier negative tests.
// NO device/AP/real owner credentials, no body upload, no firmware writer.
#include "boot/NativeOtaStrictDigestGate.h"
#include <openssl/evp.h>
#include <cstdio>
#include <iostream>
#include <string>
using namespace ShinoNativeOta;
#define CHECK(x) do{if(!(x)){std::cerr<<"FAIL "<<__LINE__<<": "<<#x<<"\n";return 1;}}while(0)
struct HostSha256 final {
    static bool hex(const char* p,size_t n,char out[65]) {
        unsigned char bytes[32]{};unsigned int count=0u;
        EVP_MD_CTX* ctx=EVP_MD_CTX_new();
        if(!ctx)return false;
        const bool ok=EVP_DigestInit_ex(ctx,EVP_sha256(),nullptr)==1 &&
           EVP_DigestUpdate(ctx,p,n)==1 &&
           EVP_DigestFinal_ex(ctx,bytes,&count)==1 && count==32u;
        EVP_MD_CTX_free(ctx);
        if(!ok)return false;
        const char hexdigits[]="0123456789abcdef";
        for(size_t i=0;i<32u;++i) {
            out[2*i]=hexdigits[bytes[i]>>4];
            out[2*i+1]=hexdigits[bytes[i]&15u];
        }
        out[64]='\0';return true;
    }
};
using Gate=StrictOtaDigestGate<HostSha256>;
constexpr uint32_t PEER=0xC0A80403u;
constexpr uint32_t OTHER_PEER=0xC0A80404u;
const char* NONCE="0123456789abcdef0123456789abcdef";
const char* OPAQUE="fedcba9876543210fedcba9876543210";
const char* USER="owner-fixture";
const char* PASS="not-the-owner-password";
const char* ROUTE="/api/v1/bridge/ota/upload";
const char* ARM_ROUTE="/api/v1/bridge/ota/arm";
const char* CNONCE="abc123def456";
std::string hash(const std::string& s) {
    char out[65]{};if(!HostSha256::hex(s.data(),s.size(),out))throw 1;return out;
}
std::string ownerHa1(){return hash(std::string(USER)+":SHINO-OTA:"+PASS);}
std::string responseFor(const std::string& uri=ROUTE,const std::string& ha1=ownerHa1(),
                        const std::string& cnonce=CNONCE) {
    const auto ha2=hash(std::string("POST:")+uri);
    return hash(ha1+":"+NONCE+":00000001:"+cnonce+":auth:"+ha2);
}
std::string auth(const std::string& uri=ROUTE,const std::string& response=responseFor(),
                 const std::string& cnonce=CNONCE) {
    return std::string("Digest username=\"")+USER+"\", realm=\"SHINO-OTA\", nonce=\""+
        NONCE+"\", uri=\""+uri+"\", response=\""+response+"\", opaque=\""+OPAQUE+
        "\", qop=auth, nc=00000001, cnonce=\""+cnonce+"\", algorithm=SHA-256";
}
bool verify(Gate& g,const std::string& request,
            const std::string& ha1=ownerHa1(),
            uint32_t peer=PEER,
            RawOtaRequestKind kind=RawOtaRequestKind::SignedTransport,
            uint32_t now=101u) {
    return g.verify(peer,kind,request.data(),request.size(),USER,ha1.c_str(),now);
}
// Non-copyable gate: construct each scope locally, no reuse/rearm.
int reject(const std::string& request, const std::string& ha1=ownerHa1(),
           uint32_t peer=PEER,
           RawOtaRequestKind kind=RawOtaRequestKind::SignedTransport) {
    Gate g;CHECK(g.challenge(PEER,RawOtaRequestKind::SignedTransport,NONCE,OPAQUE,100u));
    CHECK(!verify(g,request,ha1,peer,kind));
    CHECK(g.phase()==StrictDigestPhase::Aborted);
    CHECK(!verify(g,auth()));
    CHECK(!g.challenge(PEER,RawOtaRequestKind::SignedTransport,NONCE,OPAQUE,102u));
    return 0;
}
int main() {
    {
        Gate g;CHECK(g.challenge(PEER,RawOtaRequestKind::SignedTransport,NONCE,OPAQUE,100u));
        CHECK(verify(g,auth()));
        CHECK(g.phase()==StrictDigestPhase::VerifiedForReviewOnly);
        CHECK(!verify(g,auth())); // nonce-count/nonce cannot be reused
        CHECK(!g.challenge(PEER,RawOtaRequestKind::SignedTransport,NONCE,OPAQUE,200u));
    }
    {
        Gate g;CHECK(g.challenge(PEER,RawOtaRequestKind::SignedTransport,NONCE,OPAQUE,100u));
        CHECK(!verify(g,auth(),ownerHa1(),PEER,RawOtaRequestKind::Arm)); // URI binding
        CHECK(g.phase()==StrictDigestPhase::Aborted);
    }
    {
        Gate g;CHECK(g.challenge(PEER,RawOtaRequestKind::SignedTransport,NONCE,OPAQUE,100u));
        CHECK(!verify(g,auth(),ownerHa1(),OTHER_PEER)); // AP peer binding
    }
    {
        // RFC7616 quoted cnonce may use Base64 including +, /, =.
        const std::string base64Cnonce="abc+def/ghijklmnop=";
        Gate g;CHECK(g.challenge(PEER,RawOtaRequestKind::SignedTransport,
                                 NONCE,OPAQUE,100u));
        CHECK(verify(g,auth(ROUTE,responseFor(ROUTE,ownerHa1(),base64Cnonce),
                            base64Cnonce)));
        CHECK(g.phase()==StrictDigestPhase::VerifiedForReviewOnly);
    }
    CHECK(!reject(auth(ARM_ROUTE,responseFor(ARM_ROUTE))));
    CHECK(!reject(auth(ROUTE,std::string(64u,'0'))));
    CHECK(!reject(auth(),hash("wrong-private-credential")));
    {
        auto v=auth();const auto x=v.find("nc=00000001");
        v.replace(x,11u,"nc=00000002");CHECK(!reject(v));
    }
    for(const auto& replacement : {"qop=auth-int","qop=\"auth-int\"","algorithm=MD5",
                                    "algorithm=\"SHA-512-256\"",
                                    "uri=\"/api/v1/bridge/ota/arm\"",
                                    "realm=\"Other\"","username=\"intruder\"",
                                    "cnonce=\"a\"","cnonce=\"abc:defghi\"","cnonce=\"abc,defghi\"","opaque=\"00000000000000000000000000000000\""}) {
        auto v=auth();std::string needle;
        if(std::string(replacement).find("qop=")==0)needle="qop=auth";
        else if(std::string(replacement).find("algorithm=")==0)needle="algorithm=SHA-256";
        else if(std::string(replacement).find("uri=")==0)needle=std::string("uri=\"")+ROUTE+"\"";
        else if(std::string(replacement).find("realm=")==0)needle="realm=\"SHINO-OTA\"";
        else if(std::string(replacement).find("username=")==0)needle=std::string("username=\"")+USER+"\"";
        else if(std::string(replacement).find("cnonce=")==0)needle="cnonce=\"abc123def456\"";
        else needle=std::string("opaque=\"")+OPAQUE+"\"";
        const auto at=v.find(needle);
        CHECK(at!=std::string::npos);
        v.replace(at,needle.size(),replacement);CHECK(!reject(v));
    }
    {
        auto v=auth()+", username=\"owner-fixture\"";CHECK(!reject(v)); // duplicate parameter
        v=auth()+", bogus=123";CHECK(!reject(v));
        v=auth()+",";CHECK(!reject(v));
        v=auth();v.replace(0,7,"Basic  ");CHECK(!reject(v));
        v=auth();v+="\r\nX-Injected: true";CHECK(!reject(v));
        v=auth();v.insert(v.find("cnonce=\"")+8u, "\\");CHECK(!reject(v));
    }
    {
        Gate g;CHECK(g.challenge(PEER,RawOtaRequestKind::SignedTransport,NONCE,OPAQUE,100u));
        CHECK(g.checkTimeout(59999u));
        CHECK(!g.checkTimeout(60100u));CHECK(g.phase()==StrictDigestPhase::Aborted);
    }
    {
        Gate g;CHECK(g.challenge(PEER,RawOtaRequestKind::SignedTransport,NONCE,OPAQUE,0xfffffff0u));
        CHECK(verify(g,auth(),ownerHa1(),PEER,RawOtaRequestKind::SignedTransport,0x00000040u));
    }
    {
        Gate g;CHECK(!g.challenge(PEER,RawOtaRequestKind::SignedTransport,
            "00000000000000000000000000000000",OPAQUE,100u));
        CHECK(g.phase()==StrictDigestPhase::Aborted);
    }
    {
        Gate g;CHECK(g.challenge(PEER,RawOtaRequestKind::SignedTransport,NONCE,OPAQUE,100u));
        g.abort();CHECK(g.phase()==StrictDigestPhase::Aborted);
        CHECK(!verify(g,auth()));
    }
    std::cout<<"PASS: dedicated SHA-256 Digest qop-auth exactly binds POST route, "
                "one-shot nonce, peer, nc and real OpenSSL proof. HOST ONLY NO HTTP/FLASH.\n";
    return 0;
}
