// Source-backed B5.3 legacy route identity tests. No sockets, no privileges.
#include "M3ELegacyRouteGate.h"
#include <cassert>
#include <cstdlib>
#include <cstring>
#include <iostream>
#include <string>
#include <vector>
using ShinoM3E::Kind;
using ShinoM3E::Peer;
using ShinoM3E::Options;
using ShinoM3E::LegacyRouteGate;

struct Case {
    const char* method;
    const char* uri;
    Kind expected;
    bool existing;
};
static void cases(Peer peer,Options opts,const std::vector<Case>& expected) {
    for(const Case& item:expected) {
        const auto result=LegacyRouteGate::inspect(item.method,item.uri,peer,opts);
        if(result.kind!=item.expected ||
           result.routePresentInInspectedSource!=item.existing ||
           result.allowedToDispatch || !result.requiresPrivilegedIndependentGate) {
            std::cerr<<"M3E_ROUTE_ASSERT_FAIL "<<item.method<<" "<<item.uri<<"\n";
            std::abort();
        }
    }
}
static void apiOnAp() {
    const Options full{true,true,true};
    cases(Peer::AccessPoint,full,{
        {"GET","/",Kind::DashboardGet,true},
        {"GET","/ui.js",Kind::JavascriptGet,true},
        {"GET","/api/v1/bridge/metrics",Kind::MetricsGet,true},
        {"POST","/api/v1/bridge/metrics",Kind::MetricsPost,true},
        {"GET","/api/v1/bridge/status",Kind::StatusGet,true},
        {"GET","/api/v1/bridge/fs-plan",Kind::FsPlanGet,true},
        {"GET","/api/v1/bridge/ota/capabilities",Kind::OtaCapabilitiesGet,true},
        {"GET","/api/v1/bridge/factory-return",Kind::FactoryReturnGet,true},
        {"POST","/api/v1/bridge/factory-return",Kind::FactoryReturnPost,true},
        {"GET","/api/v1/m9/fs-probe/status",Kind::FsProbeStatusGet,true},
        {"POST","/api/v1/bridge/wifi/recovery",Kind::WifiRecoveryPost,true},
        {"GET","/api/v1/bridge/wifi/intent",Kind::WifiIntentGet,true},
        {"POST","/api/v1/bridge/wifi",Kind::WifiConfigurePost,true},
        {"POST","/api/v1/display/mode",Kind::DisplayModeCandidate,false},
        {"GET","/api/v1/display/capabilities",Kind::DisplayCapabilitiesCandidate,false},
        {"GET","/api/v1/display/status",Kind::DisplayStatusCandidate,false},
        {"POST","/api/v1/bridge/ota/arm",Kind::UnsafeOtaReserved,false},
        {"POST","/api/v1/bridge/ota/upload",Kind::UnsafeOtaReserved,false},
        {"PUT","/api/v1/bridge/metrics",Kind::Closed,false},
        {"GET","/api/v1/bridge/ota/upload",Kind::UnsafeOtaReserved,false},
        {"POST","/api/v1/bridge/ota/capabilities",Kind::Closed,false},
        {"GET","/api/v1/bridge/wifi",Kind::Closed,false},
        {"POST","/api/v1/bridge/wifi/intent",Kind::Closed,false},
        {"POST","/ui.js",Kind::Closed,false},
        {"GET","/api/v1/bridge/status/",Kind::Closed,false},
        {"GET","/api/v1/bridge/%6detrics",Kind::Closed,false},
        {"GET","/api/v1/bridge/metrics?x=1",Kind::Closed,false},
        {"GET","//api/v1/bridge/status",Kind::Closed,false},
        {"GET","/api/v1/bridge/metrics/../status",Kind::Closed,false},
        {"GET","/api/v1/display/mode",Kind::Closed,false},
        {"GET","/api/v1/bridge/ota/capabilities/",Kind::UnsafeOtaReserved,false}
    });
    cases(Peer::AccessPoint,Options{true,false,false},{
        {"POST","/api/v1/bridge/factory-return",Kind::Closed,false},
        {"GET","/api/v1/m9/fs-probe/status",Kind::Closed,false}
    });
    cases(Peer::AccessPoint,Options{false,false,false},{
        {"GET","/",Kind::DashboardGet,true},
        {"POST","/api/v1/bridge/wifi",Kind::Closed,false},
        {"GET","/api/v1/bridge/wifi/intent",Kind::Closed,false},
        {"POST","/api/v1/bridge/wifi/recovery",Kind::Closed,false}
    });
}
static void homeLanIsMoreRestricted() {
    const Options options{true,true,true};
    cases(Peer::HomeLan,options,{
        {"GET","/",Kind::DashboardGet,true},
        {"GET","/ui.js",Kind::JavascriptGet,true},
        {"GET","/api/v1/bridge/metrics",Kind::MetricsGet,true},
        {"POST","/api/v1/bridge/metrics",Kind::MetricsPost,true},
        {"GET","/api/v1/bridge/status",Kind::StatusGet,true},
        {"GET","/api/v1/bridge/ota/capabilities",Kind::OtaCapabilitiesGet,true},
        {"POST","/api/v1/bridge/wifi/recovery",Kind::WifiRecoveryPost,true},
        {"GET","/api/v1/bridge/wifi/intent",Kind::Closed,false},
        {"POST","/api/v1/bridge/wifi",Kind::Closed,false},
        {"GET","/api/v1/bridge/fs-plan",Kind::Closed,false},
        {"GET","/api/v1/bridge/factory-return",Kind::Closed,false},
        {"POST","/api/v1/bridge/factory-return",Kind::Closed,false},
        {"POST","/api/v1/display/mode",Kind::Closed,false},
        {"GET","/api/v1/display/capabilities",Kind::Closed,false},
        {"GET","/api/v1/display/status",Kind::Closed,false},
        {"POST","/api/v1/bridge/ota/upload",Kind::Closed,false}
    });
}
static void malformedNeverDispatches() {
    std::string tooLong(97u,'x');tooLong[0]='/';
    for(const char* value:{"GET","get","POST","POST ","HEAD","PATCH","DELETE",""})
        assert(!LegacyRouteGate::inspect(value,"/").allowedToDispatch);
    for(const char* uri:{"","/api/v1/bridge/status#anything",
            "/api/v1/bridge/status%2f","/api/v1/bridge/status\r\n",
            "/api/v1/bridge/status\\evil","/api/v1/bridge/status abc"})
        assert(LegacyRouteGate::inspect("GET",uri).kind==Kind::Closed);
    assert(LegacyRouteGate::inspect("GET",tooLong.c_str()).kind==Kind::Closed);
    assert(LegacyRouteGate::inspect(nullptr,"/").kind==Kind::Closed);
    assert(LegacyRouteGate::inspect("GET",nullptr).kind==Kind::Closed);
}
int main() {
    apiOnAp();
    homeLanIsMoreRestricted();
    malformedNeverDispatches();
    std::cout<<"M3E_B53_SOURCE_ROUTE_INVENTORY_HOST_PASS_NO_DISPATCH\n";
}
