// SPDX-License-Identifier: GPL-3.0-or-later
// HOST ONLY: emit a synthetic SHA-256 Digest challenge or validate an
// Authorization header CAPTURED FROM AN INDEPENDENT HTTP CLIENT.
// No live ESP8266 listener, production owner password, body sink or flash.
#include "boot/NativeOtaDigestChallengeReview.h"
#include "boot/NativeOtaStrictDigestGate.h"
#include <openssl/evp.h>
#include <array>
#include <cstdint>
#include <iostream>
#include <string>
using namespace ShinoNativeOta;

struct HostSha256 final {
    static bool hex(const char* s,size_t n,char out[65]) {
        if(!s || !out) return false;
        EVP_MD_CTX* ctx=EVP_MD_CTX_new();
        if(!ctx) return false;
        uint8_t bytes[32]{};
        unsigned int len=0u;
        const bool ok=EVP_DigestInit_ex(ctx,EVP_sha256(),nullptr)==1 &&
            EVP_DigestUpdate(ctx,s,n)==1 &&
            EVP_DigestFinal_ex(ctx,bytes,&len)==1 && len==32u;
        EVP_MD_CTX_free(ctx);
        if(!ok) return false;
        static constexpr char h[]="0123456789abcdef";
        for(size_t i=0;i<32u;++i) {
            out[2u*i]=h[bytes[i]>>4u];
            out[2u*i+1u]=h[bytes[i]&15u];
        }
        out[64]='\0';
        return true;
    }
};

bool preview(DigestChallengePreview& result) {
    std::array<uint8_t,16> n{},o{};
    for(size_t i=0;i<16u;++i) {
        n[i]=static_cast<uint8_t>(i+1u);
        o[i]=static_cast<uint8_t>(i+33u);
    }
    return NativeOtaDigestChallengeReview::fromExternalEntropy(n,o,result);
}

int main(int argc,char** argv) {
    if(argc!=2) return 2;
    DigestChallengePreview challenge{};
    if(!preview(challenge)) return 2;
    const std::string mode=argv[1];
    if(mode=="challenge") {
        std::cout<<challenge.wwwAuthenticate.data()<<"\n";
        return 0;
    }
    if(mode!="verify" && mode!="replay") return 2;
    std::string authorization;
    if(!std::getline(std::cin,authorization) ||
       authorization.size()>StrictOtaDigestGate<HostSha256>::kMaxAuthorizationBytes)
        return 3;
    static constexpr char username[]="owner-fixture";
    static constexpr char password[]="not-the-owner-password";
    static constexpr char ha1Prefix[]="owner-fixture:SHINO-OTA:not-the-owner-password";
    char ha1[65]{};
    if(!HostSha256::hex(ha1Prefix,sizeof(ha1Prefix)-1u,ha1)) return 2;
    StrictOtaDigestGate<HostSha256> gate;
    constexpr uint32_t peer=0xC0A80403u;
    constexpr auto kind=RawOtaRequestKind::Arm;
    if(!gate.challenge(peer,kind,challenge.nonce.data(),
                       challenge.opaque.data(),100u)) return 2;
    const bool accepted=gate.verify(peer,kind,authorization.data(),
                                    authorization.size(),username,ha1,101u);
    for(auto& c:ha1)c='\0';
    if(!accepted || gate.phase()!=StrictDigestPhase::VerifiedForReviewOnly) {
        std::cout<<"REJECTED_FOR_REVIEW\n";
        return 3;
    }
    if(mode=="replay" &&
       gate.verify(peer,kind,authorization.data(),authorization.size(),
                   username,ha1,102u)) return 4; // must reject the second use
    // Nothing here issues a real HTTP 200/202 or authorizes a device operation.
    std::cout<<"STRICT_DIGEST_VALID_FOR_HOST_REVIEW_ONLY\n";
    return 0;
}
