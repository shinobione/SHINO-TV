// SPDX-License-Identifier: GPL-3.0-or-later
// Host-only security-envelope probe: no firmware device/HTTP socket/flash.
#include "boot/NativeOtaRequestPolicy.h"
#include <cstdint>
#include <iostream>
using ShinoNativeOta::RequestEnvelope;
using ShinoNativeOta::PrivilegedRequestKind;
using ShinoNativeOta::PrivilegedRequestPolicy;
#define CHECK(value) do { if (!(value)) { std::cerr << "FAIL " << __LINE__ << ": " #value "\n"; return 1; } } while(0)

constexpr uint32_t kMinSigned = 64000u+256u+4u;
constexpr uint32_t kMaxSigned = 494144u+256u+4u;

RequestEnvelope arm() {
    RequestEnvelope r{};
    r.digestAuthenticated = true;
    r.reachedFromPrivateAp = true;
    r.peerIpv4NetworkOrder = 0xC0A80403u;
    r.method = "POST";
    r.host = "192.168.4.1";
    r.origin = "http://192.168.4.1";
    r.contentType = "application/json";
    r.contentLength = 200;
    return r;
}
bool accepts(const RequestEnvelope& e, PrivilegedRequestKind kind=PrivilegedRequestKind::Arm) {
    return PrivilegedRequestPolicy::preliminaryAccept(e,kind);
}
int main() {
    // Correct envelope is still merely eligible for later independent checks.
    { auto r=arm(); CHECK(accepts(r)); r.readCookiePresent=true; CHECK(accepts(r)); }
    { auto r=arm(); r.digestAuthenticated=false; r.readCookiePresent=true; CHECK(!accepts(r)); }
    { auto r=arm(); r.digestAuthenticated=false; CHECK(!accepts(r)); }
    { auto r=arm(); r.reachedFromPrivateAp=false; CHECK(!accepts(r)); }
    for (uint32_t ip : {0u,0xC0A80400u,0xC0A80401u,0xC0A804FFu,0xC0A80103u,0x7F000001u,0x0A000003u}) {
        auto r=arm(); r.peerIpv4NetworkOrder=ip; CHECK(!accepts(r));
    }
    { auto r=arm(); r.peerIpv4NetworkOrder=0xC0A80402u; CHECK(accepts(r));
      r.peerIpv4NetworkOrder=0xC0A804FEu; CHECK(accepts(r)); }
    for (auto value : {"GET","PUT","OPTIONS","HEAD","post","","POST POST"}) {
        auto r=arm(); r.method=value; CHECK(!accepts(r));
    }
    { auto r=arm(); r.method=nullptr; CHECK(!accepts(r)); }
    for (auto value : {"localhost","192.168.4.1:81","192.168.4.1:80","192.168.1.70",
                       "192.168.4.1.attacker.invalid","","192.168.4.1, evil.test"}) {
        auto r=arm(); r.host=value; CHECK(!accepts(r));
    }
    { auto r=arm(); r.host=nullptr; CHECK(!accepts(r)); }
    for (auto value : {"http://192.168.1.70","https://192.168.4.1",
                       "http://192.168.4.1:81","http://192.168.4.1/",
                       "null","http://localhost","http://evil.test",
                       "http://192.168.4.1.evil.test",""}) {
        auto r=arm(); r.origin=value; CHECK(!accepts(r));
    }
    { auto r=arm(); r.origin=nullptr; CHECK(!accepts(r)); }
    for (auto value : {"application/json; charset=utf-8","text/plain",
                       "application/octet-stream","multipart/form-data",
                       "application/json,application/octet-stream",""}) {
        auto r=arm(); r.contentType=value; CHECK(!accepts(r));
    }
    { auto r=arm(); r.contentType=nullptr; CHECK(!accepts(r)); }
    for(uint32_t len : {0u,1u,15u,385u,1024u,0xFFFFFFFFu}) {
        auto r=arm(); r.contentLength=len; CHECK(!accepts(r));
    }
    for(uint32_t len : {16u,384u}) {
        auto r=arm(); r.contentLength=len; CHECK(accepts(r));
    }
    { auto r=arm(); r.contentType="application/octet-stream";
      r.contentLength=kMinSigned; CHECK(accepts(r,PrivilegedRequestKind::SignedTransport));
      r.contentLength=kMaxSigned; CHECK(accepts(r,PrivilegedRequestKind::SignedTransport)); }
    for(uint32_t len : {0u,1u,kMinSigned-1,kMaxSigned+1,0xFFFFFFFFu}) {
        auto r=arm(); r.contentType="application/octet-stream";
        r.contentLength=len; CHECK(!accepts(r,PrivilegedRequestKind::SignedTransport));
    }
    { auto r=arm(); r.contentLength=kMinSigned;
      CHECK(!accepts(r,PrivilegedRequestKind::SignedTransport));
      r.contentType="application/octet-stream"; CHECK(!accepts(r,PrivilegedRequestKind::Arm)); }
    { auto r=arm(); CHECK(!accepts(r,static_cast<PrivilegedRequestKind>(99))); }
    std::cout<<"PASS: privilege request policy rejects cookie-only, non-AP, cross-origin, "
                "wrong host/method/content type/length; NO HTTP route or writer.\n";
    return 0;
}
