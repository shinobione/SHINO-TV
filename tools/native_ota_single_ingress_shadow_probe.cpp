// SPDX-License-Identifier: GPL-3.0-or-later
// One future port owner, HOST-ONLY route/framing proof. No credentials,
// dashboard HTML, telemetry handler, OTA writer or real network listener.
#include "boot/NativeOtaSingleIngressShadow.h"
#include <iostream>
#include <string>
#include <vector>
using namespace ShinoNativeOta;
#define CHECK(x) do{if(!(x)){std::cerr<<"FAIL line "<<__LINE__<<": "<<#x<<"\n";return 1;}}while(0)

std::string request(const char* method,const char* path,
                    const std::string& extra="",const std::string& body="") {
    return std::string(method)+" "+path+" HTTP/1.1\r\nHost: 192.168.4.1\r\n"+
        extra+"\r\n"+body;
}
std::string sampleMetrics(){
    return R"({"cpu":22,"gpu":35,"memoryGb":8.2,"memoryTotalGb":16,"gpuTempC":55})";
}
SingleIngressReviewResult send(const std::string& payload,size_t perRead,
                                bool finish=true,uint32_t now=101u) {
    NativeOtaSingleIngressShadow shadow(100u);
    for(size_t i=0u;i<payload.size();i+=perRead) {
        const size_t n=payload.size()-i<perRead?payload.size()-i:perRead;
        if(!shadow.feed(reinterpret_cast<const uint8_t*>(payload.data()+i),n,now))
            return shadow.result();
    }
    if(finish)shadow.finishOnExactTransportClose(now+1u);
    return shadow.result();
}
int legacyParity(){
    struct Row{const char* method;const char* path;Port80Plan expected;};
    const Row rows[]={
        {"GET","/",Port80Plan::LegacyDashboardGet},
        {"GET","/ui.js",Port80Plan::LegacyJavascriptGet},
        {"GET","/api/v1/bridge/metrics",Port80Plan::LegacyMetricsGet},
        {"GET","/api/v1/bridge/status",Port80Plan::LegacyStatusGet},
        {"GET","/api/v1/bridge/fs-plan",Port80Plan::LegacyFsPlanGet},
        {"GET","/api/v1/bridge/ota/capabilities",Port80Plan::LegacyCapabilitiesGet},
        {"GET","/api/v1/bridge/factory-return",Port80Plan::LegacyFactoryReturnGet},
    };
    for(const auto& row:rows){
        const auto wire=request(row.method,row.path);
        for(size_t chunk:{size_t(1),size_t(7),size_t(4096)}) {
            auto r=send(wire,chunk);
            CHECK(r.phase==SingleIngressReviewPhase::LegacyRequestReviewedOnly);
            CHECK(r.route==row.expected);
            CHECK(r.refusal==SingleIngressRefusal::None);
            CHECK(r.bodyBytes==0u && r.requiresExistingLegacyAuthentication);
            CHECK(!r.routeWasActuallyDispatched && !r.otaWriterCompiled);
        }
    }
    const auto json=sampleMetrics();
    const auto wire=request("POST","/api/v1/bridge/metrics",
        "Content-Type: application/json\r\nContent-Length: "+std::to_string(json.size())+"\r\n",json);
    for(size_t chunk:{size_t(1),size_t(3),size_t(17),size_t(2000)}) {
        const auto r=send(wire,chunk);
        CHECK(r.phase==SingleIngressReviewPhase::LegacyRequestReviewedOnly);
        CHECK(r.route==Port80Plan::LegacyMetricsPost && r.bodyBytes==json.size());
        CHECK(r.requiresExistingLegacyAuthentication && !r.browserGetCookieMayBeConsidered);
    }
    return 0;
}
int denials(){
    for(const auto& path:{
        "/api/v1/bridge/ota/arm","/api/v1/bridge/ota/upload",
        "/api/v1/bridge/ota/install","/api/v1/bridge/ota/capabilities",
        "/api/v1/bridge/ota" }) {
        auto wire=request("POST",path,"Content-Length: 494404\r\n");
        const auto r=send(wire,1u);
        CHECK(r.phase==SingleIngressReviewPhase::Rejected);
        CHECK(r.refusal==SingleIngressRefusal::OtaReservedNoWriter);
        CHECK(r.bodyBytes==0u && !r.routeWasActuallyDispatched && !r.otaWriterCompiled);
    }
    {
        const auto r=send(request("POST","/api/v1/bridge/factory-return",
                                  "Content-Length: 30\r\n"),4096u);
        CHECK(r.refusal==SingleIngressRefusal::FactoryWriteDisabled);
    }
    {
        const auto r=send(request("GET","/update"),4096u);
        CHECK(r.refusal==SingleIngressRefusal::UnsupportedMethodOrPath);
    }
    {
        const auto r=send(request("GET","/api/v1/bridge/metrics",
            "hOst: 192.168.4.1\r\n"),4096u);
        CHECK(r.refusal==SingleIngressRefusal::InvalidFraming);
    }
    {
        const auto r=send(std::string("GET / HTTP/1.1\r\n\r\n"),4096u);
        CHECK(r.refusal==SingleIngressRefusal::InvalidFraming);
    }
    {
        const auto r=send(request("POST","/api/v1/bridge/metrics",
            "Content-Type: application/json\r\nContent-Length: 20\r\n"
            "CONTENT-LENGTH: 20\r\n",std::string(20u,'x')),4096u);
        CHECK(r.refusal==SingleIngressRefusal::InvalidFraming);
    }
    for(const auto& extra:{
        "Transfer-Encoding: chunked\r\n","Expect: 100-continue\r\n",
        "Content-Encoding: gzip\r\n","Upgrade: websocket\r\n",
        "Trailer: auth\r\n","X-Obs: a\r\n continuation\r\n",
        "Bad_Name: thing\r\n"}) {
        auto r=send(request("GET","/",extra),4096u);
        CHECK(r.refusal==SingleIngressRefusal::InvalidFraming);
    }
    for(const auto& body:{std::string("x"),std::string(494404u,'x')}) {
        auto r=send(request("GET","/","",body),4096u);
        CHECK(r.refusal==SingleIngressRefusal::InvalidFraming);
    }
    const auto json=sampleMetrics();
    const auto good=request("POST","/api/v1/bridge/metrics",
        "Content-Type: application/json\r\nContent-Length: "+std::to_string(json.size())+"\r\n",json);
    {
        auto r=send(good+"X",4096u);
        CHECK(r.refusal==SingleIngressRefusal::InvalidFraming);
    }
    {
        auto r=send(good.substr(0,good.size()-1u),4096u);
        CHECK(r.refusal==SingleIngressRefusal::InvalidFraming);
    }
    {
        auto r=send(request("POST","/api/v1/bridge/metrics",
            "Content-Type: application/json\r\nContent-Length: 385\r\n",std::string(385u,'x')),4096u);
        CHECK(r.refusal==SingleIngressRefusal::InvalidFraming);
    }
    {
        NativeOtaSingleIngressShadow shadow(100u);
        auto cut=good.substr(0,12u);
        CHECK(shadow.feed(reinterpret_cast<const uint8_t*>(cut.data()),cut.size(),101u));
        CHECK(!shadow.tick(10100u));
        CHECK(shadow.result().refusal==SingleIngressRefusal::Deadline);
    }
    {
        NativeOtaSingleIngressShadow shadow(100u);
        CHECK(shadow.feed(reinterpret_cast<const uint8_t*>(good.data()),good.size(),101u));
        shadow.disconnect();
        CHECK(shadow.result().phase==SingleIngressReviewPhase::Rejected);
    }
    {
        auto wire=request("GET","/api/v1/bridge/ota/capabilities");
        CHECK(send(wire+"x",1u).phase==SingleIngressReviewPhase::Rejected);
    }
    return 0;
}
int main(){
    if(legacyParity()||denials())return 1;
    std::cout<<"PASS: one-owner HTTP shadow legacy route metadata and <=384B metrics, "
                "reserved OTA refused before body, NO legacy dispatch/auth/flash.\n";
    return 0;
}
