// SPDX-License-Identifier: GPL-3.0-or-later
// Pure host probe: canonical RFC7616 SHA-256 Digest challenge shape joins the
// already-disconnected strict verifier. Fixture entropy/credentials ONLY.
// Not a Chrome test, HTTP listener, device RNG or firmware installation.
#include "boot/NativeOtaDigestChallengeReview.h"
#include "boot/NativeOtaStrictDigestGate.h"
#include <openssl/evp.h>
#include <array>
#include <cstdint>
#include <iostream>
#include <stdexcept>
#include <string>
using namespace ShinoNativeOta;
#define CHECK(x) do { if(!(x)) { std::cerr<<"FAIL "<<__LINE__<<": "<<#x<<"\n"; return 1; } } while(0)

struct HostSha256 final {
    static bool hex(const char* s,size_t n,char out[65]) {
        EVP_MD_CTX* ctx=EVP_MD_CTX_new();
        if(!ctx)return false;
        uint8_t hash[32]{};
        unsigned int len=0;
        const bool ok=EVP_DigestInit_ex(ctx,EVP_sha256(),nullptr)==1 &&
            EVP_DigestUpdate(ctx,s,n)==1 &&
            EVP_DigestFinal_ex(ctx,hash,&len)==1 && len==32u;
        EVP_MD_CTX_free(ctx);
        if(!ok)return false;
        static constexpr char h[]="0123456789abcdef";
        for(size_t i=0;i<32u;++i) {
            out[2u*i]=h[hash[i]>>4u];
            out[2u*i+1u]=h[hash[i]&15u];
        }
        out[64]='\0';
        return true;
    }
};
std::string sha(const std::string& s) {
    char out[65]{};
    if(!HostSha256::hex(s.data(),s.size(),out))throw std::runtime_error("fixture SHA failure");
    return out;
}
int main() {
    std::array<uint8_t,16> nonce{},opaque{},zero{};
    for(size_t i=0;i<16u;++i) {
        nonce[i]=static_cast<uint8_t>(i+1u);
        opaque[i]=static_cast<uint8_t>(i+33u);
    }
    DigestChallengePreview p{};
    CHECK(!NativeOtaDigestChallengeReview::fromExternalEntropy(zero,opaque,p));
    CHECK(p.wwwAuthenticate[0]=='\0');
    CHECK(!NativeOtaDigestChallengeReview::fromExternalEntropy(nonce,zero,p));
    CHECK(!NativeOtaDigestChallengeReview::fromExternalEntropy(nonce,nonce,p));
    CHECK(NativeOtaDigestChallengeReview::fromExternalEntropy(nonce,opaque,p));
    CHECK(std::string(p.nonce.data())=="0102030405060708090a0b0c0d0e0f10");
    CHECK(std::string(p.opaque.data())=="2122232425262728292a2b2c2d2e2f30");
    CHECK(std::string(p.wwwAuthenticate.data()) ==
        "Digest realm=\"SHINO-OTA\", nonce=\"0102030405060708090a0b0c0d0e0f10\", "
        "opaque=\"2122232425262728292a2b2c2d2e2f30\", algorithm=SHA-256, qop=\"auth\"");
    constexpr uint32_t peer=0xC0A80403u;
    constexpr auto kind=RawOtaRequestKind::Arm;
    constexpr const char* route="/api/v1/bridge/ota/arm";
    const std::string user="owner-fixture", password="non-owner-fixture-secret";
    const std::string ha1=sha(user+":SHINO-OTA:"+password);
    const std::string ha2=sha(std::string("POST:")+route);
    const std::string cnonce="clientnonce123";
    const std::string response=sha(ha1+":"+p.nonce.data()+":00000001:"+
                                  cnonce+":auth:"+ha2);
    const std::string authorization=
        "Digest username=\""+user+"\", realm=\"SHINO-OTA\", nonce=\""+
        p.nonce.data()+"\", uri=\""+route+"\", response=\""+response+
        "\", opaque=\""+p.opaque.data()+"\", qop=auth, nc=00000001, cnonce=\""+
        cnonce+"\", algorithm=SHA-256";
    {
        StrictOtaDigestGate<HostSha256> gate;
        CHECK(gate.challenge(peer,kind,p.nonce.data(),p.opaque.data(),100u));
        CHECK(gate.verify(peer,kind,authorization.data(),authorization.size(),
                          user.c_str(),ha1.c_str(),101u));
        CHECK(gate.phase()==StrictDigestPhase::VerifiedForReviewOnly);
        CHECK(!gate.verify(peer,kind,authorization.data(),authorization.size(),
                           user.c_str(),ha1.c_str(),102u)); // one shot
    }
    {
        StrictOtaDigestGate<HostSha256> gate;
        CHECK(gate.challenge(peer,kind,p.nonce.data(),p.opaque.data(),100u));
        CHECK(!gate.verify(peer,RawOtaRequestKind::SignedTransport,
                           authorization.data(),authorization.size(),
                           user.c_str(),ha1.c_str(),101u)); // exact route binding
        CHECK(gate.phase()==StrictDigestPhase::Aborted);
    }
    {
        StrictOtaDigestGate<HostSha256> gate;
        CHECK(gate.challenge(peer,kind,p.nonce.data(),p.opaque.data(),100u));
        CHECK(!gate.verify(peer+1u,kind,authorization.data(),authorization.size(),
                           user.c_str(),ha1.c_str(),101u)); // peer binding
    }
    std::cout<<"PASS: external-entropy challenge format plus actual OpenSSL-backed "
                "strict proof, replay/route/peer rejection. HOST ONLY NO HTTP/FLASH.\n";
    return 0;
}
