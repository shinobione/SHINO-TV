// SPDX-License-Identifier: GPL-3.0-or-later
// Host-only typed session/telemetry regression vs FirstBootBridge/FslessMetrics.
// In all scenarios digestPassed is simulated, fresh token is fixture entropy,
// and only an independent RAM fixture changes (NOT real ESP/Windows/LCD).
#include "boot/NativeOtaLegacySessionReview.h"
#include "boot/NativeOtaLegacyTelemetryReview.h"
#include <array>
#include <cmath>
#include <cstdint>
#include <iostream>
#include <limits>
#include <string>
using namespace ShinoNativeOta;
#define CHECK(x) do{if(!(x)){std::cerr<<"FAIL "<<__LINE__<<" "<<#x<<"\n";return 1;}}while(0)
constexpr uint32_t PEER=0xC0A80403u,OTHER_PEER=0xC0A80404u;
constexpr std::array<uint8_t,16> NONCE_A{{1,2,3,4,5,6,7,8,9,10,11,12,13,14,15,16}};
constexpr std::array<uint8_t,16> NONCE_B{{2,2,3,4,5,6,7,8,9,10,11,12,13,14,15,16}};
constexpr std::array<uint8_t,16> NONCE_C{{3,2,3,4,5,6,7,8,9,10,11,12,13,14,15,16}};
using D=LegacySessionDecision;
using P=Port80Plan;

LegacyDecision access(NativeOtaLegacySessionReview& s,P p,bool digest,
                      const std::string& cookie="",uint32_t peer=PEER,
                      uint32_t now=100u,
                      const std::array<uint8_t,16>& entropy=NONCE_A) {
    return s.decide(p,digest,cookie.data(),cookie.size(),peer,now,entropy);
}
std::string cookieFor(NativeOtaLegacySessionReview& s,size_t index) {
    char token[33]{};
    if(!s.tokenForHostTestOnly(index,token))throw 1;
    return std::string("SHINO_READ_SESSION=")+token;
}
int sessions() {
    NativeOtaLegacySessionReview state;
    CHECK(access(state,P::LegacyMetricsGet,true).decision==
          D::BackgroundForbiddenNoChallenge); // no Chrome Digest prompt storm
    CHECK(access(state,P::LegacyDashboardGet,false).decision==D::DigestChallengeOnly);
    auto d=access(state,P::LegacyDashboardGet,true);
    CHECK(d.decision==D::WouldIssueReadSession && d.wouldIssueCookie &&
          !d.actualDigestChecked && !d.requestActuallyDispatched);
    const auto cookie=cookieFor(state,0u);
    CHECK(cookie.size()==51u);
    d=access(state,P::LegacyDashboardGet,false,cookie);
    CHECK(d.decision==D::ReadAllowed && d.readCookieUsed && !d.wouldIssueCookie);
    for(auto route:{P::LegacyJavascriptGet,P::LegacyMetricsGet,P::LegacyCapabilitiesGet}) {
        d=access(state,route,false,cookie);
        CHECK(d.decision==D::ReadAllowed && d.readCookieUsed);
    }
    CHECK(access(state,P::LegacyMetricsGet,true,"").decision==
          D::BackgroundForbiddenNoChallenge);
    CHECK(access(state,P::LegacyJavascriptGet,true).decision==D::ReadAllowed);
    CHECK(access(state,P::LegacyCapabilitiesGet,true).decision==D::ReadAllowed);
    for(auto route:{P::LegacyStatusGet,P::LegacyFsPlanGet,P::LegacyFactoryReturnGet}) {
        CHECK(access(state,route,false,cookie).decision==D::DigestChallengeOnly);
        CHECK(access(state,route,true,cookie).decision==D::ReadAllowed);
    }
    CHECK(access(state,P::LegacyMetricsPost,false,cookie).decision==D::DigestChallengeOnly);
    d=access(state,P::LegacyMetricsPost,true,cookie);
    CHECK(d.decision==D::WouldAcceptMetricsPost && !d.readCookieUsed &&
          !d.metricsMutationPerformed && !d.flashWriterPresent);
    CHECK(access(state,P::LegacyFactoryReturnPost,true,cookie).decision==D::FactoryPostDisabled);
    CHECK(access(state,P::OtaReservedUpload,true,cookie).decision==D::FactoryPostDisabled);
    CHECK(access(state,P::LegacyAuthenticatedNotFound,false,cookie).decision==D::DigestChallengeOnly);
    CHECK(access(state,P::LegacyAuthenticatedNotFound,true,cookie).decision==
          D::UnknownRequiresDigestThen404);
    CHECK(access(state,P::LegacyMetricsGet,false,cookie,OTHER_PEER).decision==
          D::BackgroundForbiddenNoChallenge);
    for(const auto& malformed:{
        std::string("SHINO_READ_SESSION=abc"),
        cookie+"; SHINO_READ_SESSION=not-the-same-token-anymore",
        std::string("OTHER=0; ")+cookie+"; "+cookie,
        std::string(257u,'x'),
        std::string("SHINO_READ_SESSION=")+std::string(32u,'f')}) {
        CHECK(access(state,P::LegacyMetricsGet,false,malformed).decision==
              D::BackgroundForbiddenNoChallenge);
    }
    CHECK(access(state,P::LegacyMetricsGet,false,"OTHER=x; "+cookie+"; ignored=y")
             .decision==D::ReadAllowed);
    CHECK(access(state,P::LegacyMetricsGet,false,cookie,PEER,100u+7200000u).decision==
          D::BackgroundForbiddenNoChallenge); // exact 2h boundary expires
    CHECK(access(state,P::LegacyDashboardGet,true,"",PEER,100u+7200000u,NONCE_B)
             .decision==D::WouldIssueReadSession);
    const auto renewed=cookieFor(state,0u);
    CHECK(renewed!=cookie);
    CHECK(access(state,P::LegacyMetricsGet,false,cookie,PEER,100u+7200001u).decision==
          D::BackgroundForbiddenNoChallenge);
    CHECK(access(state,P::LegacyMetricsGet,false,renewed,PEER,100u+7200001u).decision==
          D::ReadAllowed);
    // Two RAM slots: replacing the older live token cannot authorize replay.
    NativeOtaLegacySessionReview slots;
    CHECK(access(slots,P::LegacyDashboardGet,true,"",PEER,100u,NONCE_A).wouldIssueCookie);
    const auto first=cookieFor(slots,0u);
    CHECK(access(slots,P::LegacyDashboardGet,true,"",PEER,200u,NONCE_B).wouldIssueCookie);
    const auto second=cookieFor(slots,1u);
    CHECK(access(slots,P::LegacyDashboardGet,true,"",PEER,300u,NONCE_C).wouldIssueCookie);
    CHECK(access(slots,P::LegacyMetricsGet,false,first,PEER,301u).decision==
          D::BackgroundForbiddenNoChallenge);
    CHECK(access(slots,P::LegacyMetricsGet,false,second,PEER,301u).decision==D::ReadAllowed);
    // Wrap-safe unsigned millis age still accepts a newly issued session.
    NativeOtaLegacySessionReview wrap;
    CHECK(access(wrap,P::LegacyDashboardGet,true,"",PEER,0xfffffff0u).wouldIssueCookie);
    CHECK(access(wrap,P::LegacyMetricsGet,false,cookieFor(wrap,0u),PEER,0x40u).decision==
          D::ReadAllowed);
    return 0;
}
LegacyNumericField number(double n){return {true,n};}
LegacyTelemetryInput valid() {
    LegacyTelemetryInput x{};
    x.objectPresent=true;x.okIsBoolean=true;x.ok=true;
    x.gpuAvailableIsBoolean=true;x.gpuAvailable=true;
    x.cpuUsage=number(22.5);x.gpuUsage=number(34.5);
    x.memoryUsedGb=number(8.0);x.gpuVramMb=number(2048.0);
    x.gpuTempC=number(56.0);x.gpuPower=number(120.0);
    return x;
}
int telemetry() {
    NativeOtaLegacyTelemetryReview state;
    CHECK(state.stale(0u));
    auto x=valid();
    CHECK(state.applyFixture(x,100u)==LegacyTelemetryResult::AcceptedIntoHostFixtureRamOnly);
    const auto s=state.snapshotForHostTestOnly();
    CHECK(s.received && s.cpu==22.5f && s.gpu==34.5f &&
          s.memoryGb==8.0f && s.gpuTempC==56.0f && s.vramMb==2048.0f);
    CHECK(!state.memoryTotalAvailable()); // old companion: unknown denominator
    CHECK(!state.stale(6100u) && state.stale(6101u)); // strictly >6000ms
    x.memoryTotalPresent=true;x.memoryTotalGb=number(16.0);
    CHECK(state.applyFixture(x,7000u)==LegacyTelemetryResult::AcceptedIntoHostFixtureRamOnly);
    CHECK(state.memoryTotalAvailable() && state.snapshotForHostTestOnly().memoryTotalGb==16.0f);
    const auto original=state.snapshotForHostTestOnly();
    for(int v=0;v<16;++v) {
        auto bad=x;
        if(v==0)bad.ok=false;
        else if(v==1)bad.okIsBoolean=false;
        else if(v==2)bad.gpuAvailableIsBoolean=false;
        else if(v==3)bad.objectPresent=false;
        else if(v==4)bad.cpuUsage=number(-1);
        else if(v==5)bad.cpuUsage=number(101);
        else if(v==6)bad.gpuUsage={false,22.0}; // JSON "22" or true
        else if(v==7)bad.memoryUsedGb=number(257.0);
        else if(v==8)bad.gpuVramMb=number(65537.0);
        else if(v==9)bad.gpuTempC=number(-41.0);
        else if(v==10)bad.gpuTempC=number(131.0);
        else if(v==11)bad.gpuPower=number(1201.0);
        else if(v==12)bad.cpuUsage=number(std::numeric_limits<double>::quiet_NaN());
        else if(v==13)bad.gpuPower=number(std::numeric_limits<double>::infinity());
        else if(v==14)bad.memoryTotalGb=number(0.0);
        else bad.memoryTotalGb=number(7.0);
        CHECK(state.applyFixture(bad,9000u)!=
              LegacyTelemetryResult::AcceptedIntoHostFixtureRamOnly);
        const auto unchanged=state.snapshotForHostTestOnly();
        CHECK(unchanged.lastReceivedMs==original.lastReceivedMs &&
              unchanged.cpu==original.cpu && unchanged.memoryGb==original.memoryGb &&
              unchanged.memoryTotalGb==original.memoryTotalGb);
    }
    x=valid();x.gpuAvailable=false; // numeric fields still mandatory even when unavailable
    CHECK(state.applyFixture(x,10000u)==LegacyTelemetryResult::AcceptedIntoHostFixtureRamOnly);
    CHECK(!state.snapshotForHostTestOnly().gpuAvailable);
    CHECK(!state.realDeviceMetricsChanged() && !state.fourLcdCardsActuallyRepainted());
    NativeOtaLegacyTelemetryReview wrap;
    CHECK(wrap.applyFixture(valid(),0xfffffff0u)==
          LegacyTelemetryResult::AcceptedIntoHostFixtureRamOnly);
    CHECK(!wrap.stale(0x50u));
    return 0;
}
int main() {
    if(sessions()||telemetry())return 1;
    std::cout<<"PASS: HOST synthetic 2-slot GET-only peer-bound session/403/no Digest storm; "
                "full genuine 4-metric telemetry typed contract and stale rollback; "
                "NO real auth/server/LCD/OTA/flash.\n";
    return 0;
}
