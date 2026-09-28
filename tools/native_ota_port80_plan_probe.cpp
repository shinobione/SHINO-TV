// SPDX-License-Identifier: GPL-3.0-or-later
// Compile/run bounded source-only plan. No socket, no body, no active server.
#include "boot/NativeOtaPort80Plan.h"
#include <iostream>
#include <string>
using namespace ShinoNativeOta;
#define CHECK(x) do{if(!(x)){std::cerr<<"FAIL line "<<__LINE__<<": "<<#x<<"\n";return 1;}}while(0)
Port80Classification route(const std::string& request) {
    return NativeOtaPort80Plan::inspect(request.data(),request.size());
}
std::string request(const std::string& method,const std::string& path) {
    return method+" "+path+" HTTP/1.1\r\n";
}
int main() {
    struct Scenario{const char* method;const char* path;Port80Plan plan;bool cookie;bool privileged;};
    const Scenario legacy[]={
        {"GET","/",Port80Plan::LegacyDashboardGet,true,false},
        {"GET","/ui.js",Port80Plan::LegacyJavascriptGet,true,false},
        {"GET","/api/v1/bridge/metrics",Port80Plan::LegacyMetricsGet,true,false},
        {"POST","/api/v1/bridge/metrics",Port80Plan::LegacyMetricsPost,false,true},
        {"GET","/api/v1/bridge/status",Port80Plan::LegacyStatusGet,false,false},
        {"GET","/api/v1/bridge/fs-plan",Port80Plan::LegacyFsPlanGet,false,false},
        {"GET","/api/v1/bridge/ota/capabilities",Port80Plan::LegacyCapabilitiesGet,true,false},
        {"GET","/api/v1/bridge/factory-return",Port80Plan::LegacyFactoryReturnGet,false,false},
        {"POST","/api/v1/bridge/factory-return",Port80Plan::LegacyFactoryReturnPost,false,true},
    };
    for(const auto& x:legacy) {
        const auto d=route(request(x.method,x.path));
        CHECK(d.plan==x.plan);
        CHECK(d.mayUseBrowserReadCookie==x.cookie);
        CHECK(d.requiresIndependentPrivilegedPost==x.privileged);
        CHECK(d.currentlyRegisteredInFirstBootBridge==(d.plan!=Port80Plan::LegacyFactoryReturnPost));
    }
    {
        const auto line=request("POST","/api/v1/bridge/factory-return");
        const auto factory=NativeOtaPort80Plan::inspect(line.data(),line.size(),true);
        CHECK(factory.plan==Port80Plan::LegacyFactoryReturnPost);
        CHECK(factory.currentlyRegisteredInFirstBootBridge &&
              factory.requiresIndependentPrivilegedPost &&
              !factory.mayUseBrowserReadCookie);
    }
    for(const auto& method:{"GET","POST","PUT","HEAD","OPTIONS","PATCH","DELETE","post"}) {
        for(const auto& path:{
            "/api/v1/bridge/ota/arm","/api/v1/bridge/ota/upload",
            "/api/v1/bridge/ota/install","/api/v1/bridge/ota/new",
            "/api/v1/bridge/ota/"}) {
            auto d=route(request(method,path));
            CHECK(d.requiresIndependentPrivilegedPost);
            CHECK(!d.currentlyRegisteredInFirstBootBridge && !d.mayUseBrowserReadCookie);
            if(std::string(method)=="POST" && std::string(path)=="/api/v1/bridge/ota/arm")
                CHECK(d.plan==Port80Plan::OtaReservedArm);
            else if(std::string(method)=="POST" && std::string(path)=="/api/v1/bridge/ota/upload")
                CHECK(d.plan==Port80Plan::OtaReservedUpload);
            else CHECK(d.plan==Port80Plan::OtaReservedReject);
        }
    }
    for(const auto& method:{"POST","PUT","HEAD","OPTIONS","DELETE"}) {
        for(const auto& reserved:{"/api/v1/bridge/ota/capabilities","/api/v1/bridge/ota"}) {
            const auto d=route(request(method,reserved));
            CHECK(d.plan==Port80Plan::OtaReservedReject);
            CHECK(d.requiresIndependentPrivilegedPost &&
                  !d.currentlyRegisteredInFirstBootBridge && !d.mayUseBrowserReadCookie);
        }
    }
    for(const auto& path:{
        "/api/v1/bridge/metrics2","/update","/api/v1/bridge/ota",
        "/api/v1/bridge/status/","/api/v1/bridge/ota/capabilities-extra"}) {
        const auto d=route(request("GET",path));
        CHECK(d.plan==Port80Plan::LegacyAuthenticatedNotFound ||
              d.plan==Port80Plan::OtaReservedReject);
        CHECK(!d.mayUseBrowserReadCookie);
    }
    {
        const auto d=route(request("HEAD","/api/v1/bridge/metrics"));
        CHECK(d.plan==Port80Plan::LegacyAuthenticatedNotFound);
    }
    for(const auto& bad:{
        "","G","GET / HTTP/1.0\r\n","get / HTTP/2\r\n",
        "GET  / HTTP/1.1\r\n","GET /  HTTP/1.1\r\n",
        "GET / HTTP/1.1\n","GET / HTTP/1.1\r",
        "GET / HTTP/1.1\r\nX", "GET /\tHTTP/1.1\r\n",
        "GET /%2f HTTP/1.1\r\n","GET /?x=1 HTTP/1.1\r\n",
        "POST http://192.168.4.1/api/v1/bridge/ota/upload HTTP/1.1\r\n",
        "POST /api/v1/bridge/ota/upload HTTP/1.1\r\n\r\n",
        "POST /api/v1/bridge/ota/upload HTTP/1.1\r\nX: y\r\n"}) {
        auto d=route(bad);
        CHECK(d.plan==Port80Plan::Invalid || d.plan==Port80Plan::Incomplete);
        CHECK(!d.requiresIndependentPrivilegedPost && !d.mayUseBrowserReadCookie);
    }
    {
        const auto d=route(std::string("GET / HTTP/1.1\r\n",16u));
        CHECK(d.plan==Port80Plan::LegacyDashboardGet);
        CHECK(route("GET /").plan==Port80Plan::Incomplete);
    }
    {
        const std::string overlong(130,'x');
        CHECK(route(overlong).plan==Port80Plan::Invalid);
    }
    {
        // Construct explicitly to preserve the NUL byte.
        std::string s="GET /";s.push_back('\0');s+=" HTTP/1.1\r\n";
        CHECK(route(s).plan==Port80Plan::Invalid);
    }
    std::cout<<"PASS: source-only port80 route parity dashboard/PC metrics/factory/capabilities, "
                "OTA namespace reserved even odd methods, NO listener or upload writer.\n";
    return 0;
}
