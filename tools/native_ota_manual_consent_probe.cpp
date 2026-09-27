// SPDX-License-Identifier: GPL-3.0-or-later
// Host-only fixture. Digest result is SIMULATED; no genuine HTTP session or writer.
#include "boot/NativeOtaManualConsentGate.h"
#include "boot/NativeOtaRawHeaderGate.h"
#include "boot/NativeOtaRequestPolicy.h"
#include <array>
#include <cstdint>
#include <iostream>
#include <string>
using namespace ShinoNativeOta;
#define CHECK(x) do{if(!(x)){std::cerr<<"FAIL "<<__LINE__<<": "<<#x<<"\n";return 1;}}while(0)
constexpr uint32_t PEER=0xC0A80403u;
constexpr uint32_t OTHER_PEER=0xC0A80404u;
constexpr uint32_t SIZE=494404u;
constexpr std::array<uint8_t,16> TOKEN{{1,2,3,4,5,6,7,8,9,10,11,12,13,14,15,16}};
constexpr std::array<uint8_t,16> WRONG_TOKEN{{1,2,3,4,5,6,7,8,9,10,11,12,13,14,15,17}};
constexpr std::array<uint8_t,16> EMPTY_TOKEN{{}};
constexpr std::array<uint8_t,32> DIGEST{{1,2,3,4,5,6,7,8,9,10,11,12,13,14,15,16,
                                         17,18,19,20,21,22,23,24,25,26,27,28,29,30,31,32}};
constexpr std::array<uint8_t,32> WRONG_DIGEST{{1,2,3,4,5,6,7,8,9,10,11,12,13,14,15,16,
                                         17,18,19,20,21,22,23,24,25,26,27,28,29,30,31,33}};
constexpr std::array<uint8_t,32> EMPTY_DIGEST{{}};
constexpr auto OEM=IntendedPackage::SignedExactOem;
constexpr auto SHINO=IntendedPackage::SignedShino;

int happyAndReplay() {
    ManualConsentGate g;
    CHECK(g.offer(true,true,true,PEER,OEM,SIZE,TOKEN,DIGEST,100u));
    CHECK(g.phase()==ConsentPhase::Offered);
    CHECK(g.checkTimeout(200u));
    CHECK(g.consume(true,true,PEER,OEM,SIZE,TOKEN,DIGEST,201u));
    CHECK(g.phase()==ConsentPhase::ConsumedForReviewOnly);
    CHECK(!g.consume(true,true,PEER,OEM,SIZE,TOKEN,DIGEST,202u));
    CHECK(!g.offer(true,true,true,PEER,OEM,SIZE,WRONG_TOKEN,DIGEST,203u));
    return 0;
}
int failClosedOffer() {
    {
        ManualConsentGate g;
        CHECK(!g.offer(false,true,true,PEER,OEM,SIZE,TOKEN,DIGEST,100u));
        CHECK(g.phase()==ConsentPhase::Aborted);
        CHECK(!g.offer(true,true,true,PEER,OEM,SIZE,TOKEN,DIGEST,101u));
    }
    for(int variant=0;variant<8;++variant) {
        ManualConsentGate g;
        const bool ok=g.offer(true,variant!=0,variant!=1,
            variant!=2?PEER:0u,OEM,variant!=3?SIZE:SIZE-1u,
            variant!=4?TOKEN:EMPTY_TOKEN,
            variant!=5?DIGEST:EMPTY_DIGEST,100u);
        if(variant<=5) CHECK(!ok);
        else CHECK(ok);
    }
    {
        ManualConsentGate g;
        CHECK(!g.offer(true,true,true,PEER,
                       static_cast<IntendedPackage>(99),SIZE,TOKEN,DIGEST,100u));
    }
    {
        ManualConsentGate g;
        CHECK(!g.offer(true,true,true,PEER,SHINO,64000u,TOKEN,DIGEST,100u));
        CHECK(g.phase()==ConsentPhase::Aborted);
    }
    {
        ManualConsentGate g;
        CHECK(g.offer(true,true,true,PEER,SHINO,64260u,TOKEN,DIGEST,100u));
        CHECK(g.consume(true,true,PEER,SHINO,64260u,TOKEN,DIGEST,200u));
    }
    return 0;
}
int failClosedConsume() {
    for(int variant=0;variant<8;++variant) {
        ManualConsentGate g;
        CHECK(g.offer(true,true,true,PEER,OEM,SIZE,TOKEN,DIGEST,100u));
        bool ok=g.consume(variant!=0,variant!=1,
                          variant!=2?PEER:OTHER_PEER,
                          variant!=3?OEM:SHINO,
                          variant!=4?SIZE:SIZE-1u,
                          variant!=5?TOKEN:WRONG_TOKEN,
                          variant!=6?DIGEST:WRONG_DIGEST,
                          variant!=7?200u:60100u);
        CHECK(!ok);
        CHECK(g.phase()==ConsentPhase::Aborted);
        CHECK(!g.consume(true,true,PEER,OEM,SIZE,TOKEN,DIGEST,202u));
        CHECK(!g.offer(true,true,true,PEER,OEM,SIZE,TOKEN,DIGEST,202u));
    }
    return 0;
}
int timeoutAbortWrap() {
    {
        ManualConsentGate g;
        CHECK(g.offer(true,true,true,PEER,OEM,SIZE,TOKEN,DIGEST,0u));
        CHECK(g.checkTimeout(59999u));
        CHECK(!g.checkTimeout(60000u));
        CHECK(g.phase()==ConsentPhase::Aborted);
    }
    {
        ManualConsentGate g;
        CHECK(g.offer(true,true,true,PEER,OEM,SIZE,TOKEN,DIGEST,0xfffffff0u));
        CHECK(g.consume(true,true,PEER,OEM,SIZE,TOKEN,DIGEST,0x00000040u));
    }
    {
        ManualConsentGate g;
        CHECK(g.offer(true,true,true,PEER,OEM,SIZE,TOKEN,DIGEST,100u));
        g.abort();
        CHECK(g.phase()==ConsentPhase::Aborted);
        CHECK(!g.consume(true,true,PEER,OEM,SIZE,TOKEN,DIGEST,101u));
    }
    return 0;
}
int parseVsAuth() {
    const std::string t="0102030405060708090a0b0c0d0e0f10";
    const std::string hdr="POST /api/v1/bridge/ota/upload HTTP/1.1\r\n"
        "Host: 192.168.4.1\r\nOrigin: http://192.168.4.1\r\n"
        "Content-Type: application/octet-stream\r\nContent-Length: 494404\r\n"
        "Authorization: Digest example\r\n"
        "Cookie: SHINO_READ_SESSION=only-a-GET-cookie\r\n"
        "X-Shino-Intent: "+t+"\r\n\r\n";
    RawOtaHeaderResult r{};
    CHECK(RawOtaHeaderGate::inspect(hdr.data(),hdr.size(),r));
    CHECK(r.digestHeaderPresent && r.readCookiePresent);
    CHECK(t==r.intentToken);
    RequestEnvelope policy{};
    policy.readCookiePresent=r.readCookiePresent;
    policy.reachedFromPrivateAp=true;
    policy.peerIpv4NetworkOrder=PEER;
    policy.method="POST";
    policy.host="192.168.4.1";
    policy.origin="http://192.168.4.1";
    policy.contentType="application/octet-stream";
    policy.contentLength=r.contentLength;
    policy.digestAuthenticated=false; // Syntactic Digest header is NOT proof.
    CHECK(!PrivilegedRequestPolicy::preliminaryAccept(policy,PrivilegedRequestKind::SignedTransport));
    policy.digestAuthenticated=true; // HOST FIXTURE; production must verify the real Digest.
    CHECK(PrivilegedRequestPolicy::preliminaryAccept(policy,PrivilegedRequestKind::SignedTransport));
    ManualConsentGate g;
    CHECK(g.offer(true,true,true,PEER,OEM,SIZE,TOKEN,DIGEST,100u));
    CHECK(g.consume(true,true,PEER,OEM,r.contentLength,TOKEN,DIGEST,101u));
    return 0;
}
int main() {
    if(happyAndReplay()||failClosedOffer()||failClosedConsume()||
       timeoutAbortWrap()||parseVsAuth()) return 1;
    std::cout<<"PASS: manual consent single-use/60s/peer/package/token/digest, "
                "raw syntax NEVER authenticates Digest or GET cookie; HOST ONLY NO WRITER.\n";
    return 0;
}
