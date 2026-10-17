// SPDX-License-Identifier: GPL-3.0-or-later
#pragma once
// M3-E: pure closed route inventory for the inspected B5.3 *source*.
// INERT. No WiFiServer, ESP8266WebServer, WiFiClient, route registration,
// Digest verifier, handler delegation, body read, mode application or OTA.
//
// Importantly, matching a listed route does NOT authorize dispatch. The
// existing active FirstBootBridge/HomeLan behavior has not been recreated.
// Any future native migration requires separate route-by-route parity tests.
#include <cstddef>
#include <cstdint>
#include <cstring>

namespace ShinoM3E {

enum class Kind : uint8_t {
    Closed = 0, UnsafeOtaReserved,
    DashboardGet, JavascriptGet,
    MetricsGet, MetricsPost, StatusGet, FsPlanGet,
    OtaCapabilitiesGet, FactoryReturnGet, FactoryReturnPost,
    WifiRecoveryPost, WifiIntentGet, WifiConfigurePost,
    FsProbeStatusGet,
    DisplayModeCandidate, DisplayCapabilitiesCandidate, DisplayStatusCandidate
};

enum class Peer : uint8_t { AccessPoint, HomeLan };
struct Options {
    bool homeLanCompiled = true;
    bool factoryRestoreCompiled = false;
    bool fsProbeProfile = false;
};
struct Classification {
    Kind kind = Kind::Closed;
    bool routePresentInInspectedSource = false;
    bool requestAllowedByKnownStaPathList = false;
    bool requiresPrivilegedIndependentGate = true;
    bool allowedToDispatch = false; // ALWAYS false: no native parity yet.
};

class LegacyRouteGate final {
public:
    static constexpr size_t kMaxMethodBytes = 4u;
    static constexpr size_t kMaxTargetBytes = 96u;

    static Classification inspect(const char* method, const char* target,
                                  Peer peer, Options options = {}) {
        Classification result{};
        if (!valid(method,kMaxMethodBytes) || !valid(target,kMaxTargetBytes)
            || target[0]!='/' || (std::strcmp(method,"GET")!=0
                                  && std::strcmp(method,"POST")!=0))
            return result;
        // No percent decoding, queries, fragments, traversal, path aliases or
        // HTTP method override. Explicit exact targets only.
        for (const char* p=target;*p;++p) {
            if (*p=='%' || *p=='?' || *p=='#' || *p=='\\'
                || *p==' ' || *p=='\r' || *p=='\n')
                return result;
        }
        const bool get = std::strcmp(method,"GET")==0;
        const bool post = !get;
        const bool sta = peer==Peer::HomeLan;
        // These paths come from HomeLanPolicy::endpoint() in B5.3, NOT
        // guesses about which LAN routes a future application should allow.
        const bool staListed =
            equal(target,"/") || equal(target,"/ui.js") ||
            equal(target,"/api/v1/bridge/metrics") ||
            equal(target,"/api/v1/bridge/status") ||
            equal(target,"/api/v1/bridge/wifi/recovery") ||
            equal(target,"/api/v1/bridge/ota/capabilities");
        result.requestAllowedByKnownStaPathList = !sta || (
            options.homeLanCompiled && staListed);
        if (sta && !result.requestAllowedByKnownStaPathList) return result;

        if (under(target,"/api/v1/bridge/ota/") &&
            !equal(target,"/api/v1/bridge/ota/capabilities")) {
            result.kind=Kind::UnsafeOtaReserved;
            return result; // NEVER a write registration.
        }
        if (get&&equal(target,"/")) result.kind=Kind::DashboardGet;
        else if (get&&equal(target,"/ui.js")) result.kind=Kind::JavascriptGet;
        else if (get&&equal(target,"/api/v1/bridge/metrics")) result.kind=Kind::MetricsGet;
        else if (post&&equal(target,"/api/v1/bridge/metrics")) result.kind=Kind::MetricsPost;
        else if (get&&equal(target,"/api/v1/bridge/status")) result.kind=Kind::StatusGet;
        else if (get&&equal(target,"/api/v1/bridge/fs-plan")) result.kind=Kind::FsPlanGet;
        else if (get&&equal(target,"/api/v1/bridge/ota/capabilities"))
            result.kind=Kind::OtaCapabilitiesGet;
        else if (get&&equal(target,"/api/v1/bridge/factory-return"))
            result.kind=Kind::FactoryReturnGet;
        else if (post&&options.factoryRestoreCompiled&&
                 equal(target,"/api/v1/bridge/factory-return"))
            result.kind=Kind::FactoryReturnPost;
        else if (options.homeLanCompiled&&post&&
                 equal(target,"/api/v1/bridge/wifi/recovery"))
            result.kind=Kind::WifiRecoveryPost;
        else if (options.homeLanCompiled&&get&&
                 equal(target,"/api/v1/bridge/wifi/intent"))
            result.kind=Kind::WifiIntentGet;
        else if (options.homeLanCompiled&&post&&
                 equal(target,"/api/v1/bridge/wifi"))
            result.kind=Kind::WifiConfigurePost;
        else if (options.fsProbeProfile&&get&&
                 equal(target,"/api/v1/m9/fs-probe/status"))
            result.kind=Kind::FsProbeStatusGet;
        else if (post&&equal(target,"/api/v1/display/mode"))
            result.kind=Kind::DisplayModeCandidate;
        else if (get&&equal(target,"/api/v1/display/capabilities"))
            result.kind=Kind::DisplayCapabilitiesCandidate;
        else if (get&&equal(target,"/api/v1/display/status"))
            result.kind=Kind::DisplayStatusCandidate;

        result.routePresentInInspectedSource =
            result.kind!=Kind::Closed &&
            result.kind!=Kind::UnsafeOtaReserved &&
            result.kind!=Kind::DisplayModeCandidate &&
            result.kind!=Kind::DisplayCapabilitiesCandidate &&
            result.kind!=Kind::DisplayStatusCandidate;
        // Intentional invariant: NONE of these classifications can dispatch.
        return result;
    }

private:
    static bool equal(const char* a,const char* b) {
        return std::strcmp(a,b)==0;
    }
    static bool under(const char* path,const char* prefix) {
        return std::strncmp(path,prefix,std::strlen(prefix))==0;
    }
    static bool valid(const char* p,size_t maximum) {
        if (!p) return false;
        size_t used=0u;
        while (used<=maximum && p[used]) ++used;
        return used>0u&&used<=maximum;
    }
};

} // namespace ShinoM3E
