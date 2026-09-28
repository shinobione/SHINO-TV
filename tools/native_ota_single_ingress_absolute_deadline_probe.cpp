// SPDX-License-Identifier: GPL-3.0-or-later
// Pure HOST deterministic virtual-clock slow-client regression. No real sleep,
// socket, device, authorization, telemetry mutation or flash.
#include "boot/NativeOtaSingleIngressShadow.h"
#include <cstdint>
#include <iostream>
#include <string>
using namespace ShinoNativeOta;
#define CHECK(x) do {if(!(x)){std::cerr<<"FAIL "<<__LINE__<<": "<<#x<<"\n";return 1;}}while(0)

static constexpr char kHeaders[] =
    "POST /api/v1/bridge/metrics HTTP/1.1\r\n"
    "Host: 192.168.4.1\r\n"
    "Content-Type: application/json\r\n"
    "Content-Length: 16\r\n\r\n";
static constexpr char kBody[]="1234567890123456";
static bool send(NativeOtaSingleIngressShadow& reader,
                 const char* bytes,size_t count,uint32_t at) {
    return reader.feed(reinterpret_cast<const uint8_t*>(bytes),count,at);
}
static bool deniedDeadline(const NativeOtaSingleIngressShadow& r) {
    const auto s=r.result();
    return s.phase==SingleIngressReviewPhase::Rejected &&
           s.refusal==SingleIngressRefusal::Deadline &&
           s.bodyBytes==0u && !s.routeWasActuallyDispatched &&
           !s.otaWriterCompiled;
}
int main() {
    static_assert(NativeOtaSingleIngressShadow::kHeaderDeadlineMs==10000u,
                  "Header protection unexpectedly drifted");
    static_assert(NativeOtaSingleIngressShadow::kBodyIdleDeadlineMs==15000u,
                  "Body idle protection unexpectedly drifted");
    static_assert(NativeOtaSingleIngressShadow::kBodyTotalDeadlineMs==30000u,
                  "Body absolute limit must remain independently audited");
    static_assert(NativeOtaSingleIngressShadow::kLegacyMetricsBytes==384u,
                  "Only small bounded legacy telemetry accepted");
    {
        NativeOtaSingleIngressShadow r(100u);
        CHECK(send(r,kHeaders,sizeof(kHeaders)-1u,100u));
        CHECK(r.result().phase==SingleIngressReviewPhase::BoundedLegacyBody);
        CHECK(send(r,kBody,1u,101u));
        CHECK(send(r,kBody+1u,1u,14000u)); // resets idle, not absolute lifetime
        CHECK(send(r,kBody+2u,1u,28000u));
        CHECK(r.tick(30099u));             // 29,999ms after complete headers
        CHECK(!r.tick(30100u));           // 30,000ms absolute deadline
        CHECK(deniedDeadline(r));
        CHECK(!send(r,kBody+3u,13u,30101u));
        CHECK(!r.finishOnExactMessageBoundaryForHostReviewOnly(30101u));
    }
    {
        NativeOtaSingleIngressShadow r(100u);
        CHECK(send(r,kHeaders,sizeof(kHeaders)-1u,100u));
        CHECK(!r.tick(15100u));           // original 15s idle still works
        CHECK(deniedDeadline(r));
    }
    {
        NativeOtaSingleIngressShadow r(100u);
        CHECK(send(r,kHeaders,sizeof(kHeaders)-1u,100u));
        CHECK(send(r,kBody,16u,15099u)); // 14,999ms, still within BOTH gates
        CHECK(r.finishOnExactMessageBoundaryForHostReviewOnly(15100u));
        CHECK(r.result().phase==SingleIngressReviewPhase::LegacyRequestReviewedOnly);
        CHECK(r.result().bodyBytes==16u);
        CHECK(!r.result().routeWasActuallyDispatched);
    }
    {
        // unsigned elapsed time remains valid when millis() wraps.
        constexpr uint32_t start=UINT32_MAX-5000u;
        NativeOtaSingleIngressShadow r(start);
        CHECK(send(r,kHeaders,sizeof(kHeaders)-1u,start));
        CHECK(send(r,kBody,1u,start+1000u));
        CHECK(!r.tick(start+30000u));
        CHECK(deniedDeadline(r));
    }
    {
        // First-line/header deadline is independent of the body lifetime.
        NativeOtaSingleIngressShadow r(100u);
        static constexpr char incomplete[]="POST /api/v1/bridge/metrics HTTP/1.1\r\n";
        CHECK(send(r,incomplete,sizeof(incomplete)-1u,100u));
        CHECK(!r.tick(10100u));
        CHECK(deniedDeadline(r));
    }
    std::cout<<"PASS: total-body 30s cap, independent 15s idle/10s headers, "
                "wrap-safe, no post-deadline accept; HOST ONLY NO HTTP/FLASH.\n";
    return 0;
}
