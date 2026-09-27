// SPDX-License-Identifier: GPL-3.0-or-later
// HOST ONLY: response STATUS/body preview, never a web handler/real Digest/
// ArduinoJson decoder/device acknowledgement. Do not ship test fixture 200s.
#include "boot/NativeOtaLegacyResponsePreview.h"
#include <array>
#include <cstring>
#include <iostream>
#include <string>
using namespace ShinoNativeOta;
#define CHECK(x) do{if(!(x)){std::cerr<<"FAIL "<<__LINE__<<" "<<#x<<"\n";return 1;}}while(0)
constexpr uint32_t PEER=0xC0A80403u;
constexpr std::array<uint8_t,16> ENTROPY{{1,2,3,4,5,6,7,8,9,10,11,12,13,14,15,16}};
using P=Port80Plan;
using S=LegacySessionDecision;
using T=LegacyTelemetryResult;
LegacyDecision auth(NativeOtaLegacySessionReview& sessions,P path,bool fixtureDigest,
                    const std::string& cookie="",uint32_t now=100u) {
    return sessions.decide(path,fixtureDigest,cookie.data(),cookie.size(),PEER,now,ENTROPY);
}
LegacyHttpPreview preview(P path,const LegacyDecision& decision,size_t n=0u,
                          bool fixtureJsonParsed=false,T validation=T::InvalidEnvelope) {
    return NativeOtaLegacyResponsePreview::decide(
        path,decision,n,fixtureJsonParsed,validation);
}
bool safe(const LegacyHttpPreview& v) {
    return v.hasNoStore && v.hasNoSniff && !v.actualAuthChecked &&
           !v.actualHandlerDispatched && !v.wouldApplyTelemetry &&
           !v.otaWriterPresent;
}
int main() {
    NativeOtaLegacySessionReview sessions;
    {
        const auto r=preview(P::LegacyDashboardGet,auth(sessions,P::LegacyDashboardGet,false));
        CHECK(r.status==401 && r.wouldChallengeDigest && !r.wouldIssueCookie && safe(r));
    }
    const auto welcome=preview(P::LegacyDashboardGet,auth(sessions,P::LegacyDashboardGet,true));
    CHECK(welcome.status==200 && welcome.wouldIssueCookie && welcome.wouldUseDashboardCsp);
    CHECK(std::string(welcome.contentType)=="text/html; charset=utf-8");
    CHECK(std::string(welcome.body)=="HOST_FIXTURE_DASHBOARD_HTML_NOT_SERVED");
    CHECK(safe(welcome));
    char token[33]{};
    CHECK(sessions.tokenForHostTestOnly(0u,token));
    const std::string cookie=std::string("SHINO_READ_SESSION=")+token;
    {
        const auto r=preview(P::LegacyDashboardGet,
                             auth(sessions,P::LegacyDashboardGet,false,cookie));
        CHECK(r.status==200 && !r.wouldIssueCookie && !r.wouldChallengeDigest && safe(r));
    }
    {
        const auto r=preview(P::LegacyJavascriptGet,
                             auth(sessions,P::LegacyJavascriptGet,false,cookie));
        CHECK(r.status==200 && std::string(r.contentType)=="application/javascript; charset=utf-8");
        CHECK(!r.wouldIssueCookie && safe(r));
    }
    {
        const auto r=preview(P::LegacyMetricsGet,
                             auth(sessions,P::LegacyMetricsGet,false,cookie));
        CHECK(r.status==200 && !r.wouldChallengeDigest);
        CHECK(std::string(r.body).find("\"real_device_sample_read\":false")!=std::string::npos);
        CHECK(safe(r));
    }
    for(const auto& invalidCookie:{std::string(""),std::string("SHINO_READ_SESSION=invalid")}) {
        const auto r=preview(P::LegacyMetricsGet,
                             auth(sessions,P::LegacyMetricsGet,true,invalidCookie));
        CHECK(r.status==403 && !r.wouldChallengeDigest && !r.wouldIssueCookie && safe(r));
        CHECK(std::string(r.body)=="{\"error\":\"Browser session expired; reopen / and authenticate\"}");
    }
    {
        const auto r=preview(P::LegacyMetricsGet,
                             auth(sessions,P::LegacyMetricsGet,false,cookie,7200100u));
        CHECK(r.status==403 && !r.wouldChallengeDigest && safe(r));
    }
    // GET-only cookie cannot authenticate a Windows metrics write.
    {
        const auto r=preview(P::LegacyMetricsPost,
                             auth(sessions,P::LegacyMetricsPost,false,cookie));
        CHECK(r.status==401 && r.wouldChallengeDigest && safe(r));
    }
    const auto digestPost=auth(sessions,P::LegacyMetricsPost,true,cookie);
    CHECK(digestPost.decision==S::WouldAcceptMetricsPost && !digestPost.actualDigestChecked);
    for(const size_t length : {size_t(0u),size_t(15u),size_t(385u),size_t(494404u)}) {
        const auto r=preview(P::LegacyMetricsPost,digestPost,length,true,
                             T::AcceptedIntoHostFixtureRamOnly);
        CHECK(r.status==413 && safe(r));
        CHECK(std::string(r.body)=="{\"error\":\"Invalid bounded telemetry payload length\"}");
    }
    constexpr char goodJson[]=
        R"({"ok":true,"gpu_available":true,"cpu_usage":22.5,"gpu_usage":34.5,"memory_used_gb":8,"memory_total_gb":16,"gpu_vram_mb":2048,"gpu_temp_c":56,"gpu_power":120})";
    constexpr size_t goodLength=sizeof(goodJson)-1u;
    CHECK(goodLength>=16u && goodLength<=384u);
    {
        const auto r=preview(P::LegacyMetricsPost,digestPost,goodLength,false,
                             T::AcceptedIntoHostFixtureRamOnly);
        CHECK(r.status==422 && std::string(r.body)=="{\"error\":\"Invalid JSON telemetry\"}");
        CHECK(safe(r));
    }
    for(T invalid:{T::InvalidEnvelope,T::InvalidNumbers,T::InvalidTotalRam}) {
        const auto r=preview(P::LegacyMetricsPost,digestPost,goodLength,true,invalid);
        CHECK(r.status==422 && safe(r));
        CHECK(std::string(r.body)=="{\"error\":\"Invalid, missing or out-of-range telemetry fields\"}");
    }
    {
        NativeOtaLegacyTelemetryReview ramFixture;
        LegacyTelemetryInput input{};
        input.objectPresent=input.okIsBoolean=input.ok=
            input.gpuAvailableIsBoolean=input.gpuAvailable=true;
        input.cpuUsage={true,22.5};input.gpuUsage={true,34.5};
        input.memoryUsedGb={true,8.0};input.memoryTotalPresent=true;
        input.memoryTotalGb={true,16.0};input.gpuVramMb={true,2048.0};
        input.gpuTempC={true,56.0};input.gpuPower={true,120.0};
        const T status=ramFixture.applyFixture(input,200u);
        CHECK(status==T::AcceptedIntoHostFixtureRamOnly);
        const auto r=preview(P::LegacyMetricsPost,digestPost,goodLength,true,status);
        CHECK(r.status==200 && safe(r));
        CHECK(std::string(r.body)=="{\"status\":\"RAM_SAMPLE_ACCEPTED\",\"persisted\":false}");
        CHECK(!ramFixture.realDeviceMetricsChanged());
    }
    for(P path:{P::LegacyStatusGet,P::LegacyFsPlanGet,P::LegacyFactoryReturnGet}) {
        const auto without=preview(path,auth(sessions,path,false,cookie));
        CHECK(without.status==401 && without.wouldChallengeDigest && safe(without));
        const auto with=preview(path,auth(sessions,path,true,cookie));
        CHECK(with.status==200 && safe(with) &&
              std::string(with.body).find("\"host_fixture_only\":true")!=std::string::npos);
    }
    {
        const auto r=preview(P::LegacyCapabilitiesGet,
                             auth(sessions,P::LegacyCapabilitiesGet,false,cookie));
        CHECK(r.status==200 && safe(r));
        CHECK(std::string(r.body).find("\"native_ota_upload_route_registered\":false")!=std::string::npos);
    }
    {
        const auto denied=preview(P::LegacyAuthenticatedNotFound,
                                  auth(sessions,P::LegacyAuthenticatedNotFound,false,cookie));
        const auto hidden=preview(P::LegacyAuthenticatedNotFound,
                                  auth(sessions,P::LegacyAuthenticatedNotFound,true,cookie));
        CHECK(denied.status==401 && hidden.status==404 && safe(denied) && safe(hidden));
        CHECK(std::string(hidden.body)=="{\"error\":\"No arbitrary update, erase or filesystem route exists\"}");
    }
    for(P forbidden:{P::OtaReservedArm,P::OtaReservedUpload,P::OtaReservedReject,
                     P::LegacyFactoryReturnPost}) {
        const auto r=preview(forbidden,auth(sessions,forbidden,true,cookie));
        CHECK(r.status==403 && safe(r));
        CHECK(std::string(r.body).find("NO_FLASH")!=std::string::npos);
    }
    std::cout<<"PASS: source-grounded HOST HTTP status previews 200/401/403/404/413/422, "
                "synthetic session/no Chrome poll challenge and exact PC JSON response strings; "
                "NO REAL DIGEST/ROUTE/DISPATCH/LCD/FLASH.\n";
    return 0;
}
