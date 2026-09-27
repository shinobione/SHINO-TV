// SPDX-License-Identifier: GPL-3.0-or-later
#pragma once
// V2.1 PORT-80 MIGRATION PLAN ONLY, NOT AN ACTIVE CONNECTION DEMULTIPLEXER.
// This is a pure bounded first-line classifier for documenting/test-running
// a future single-owner raw port-80 server. It does NOT listen, read a socket,
// process headers, transfer consumed bytes to ESP8266WebServer, authenticate,
// accept a firmware upload, call Update, or enable a second listener.
//
// IMPORTANT: ESP8266WebServer 3.1.2 privately owns WiFiServer and calls
// _server.accept() within handleClient(). It has NO reviewed API here for
// handing it a WiFiClient after consuming bytes. A future production change
// needs a separately audited single-owner server with full legacy route,
// GET session and bounded metrics POST parity; this classifier alone cannot
// preserve the active dashboard. So FirstBootBridge remains unchanged.
#include <cstddef>
#include <cstdint>

namespace ShinoNativeOta {
enum class Port80Plan : uint8_t {
    Incomplete,
    Invalid,
    LegacyDashboardGet,
    LegacyJavascriptGet,
    LegacyMetricsGet,
    LegacyMetricsPost,
    LegacyStatusGet,
    LegacyFsPlanGet,
    LegacyCapabilitiesGet,
    LegacyFactoryReturnGet,
    LegacyFactoryReturnPost, // only registered if SHINO_ENABLE_FACTORY_RESTORE=1
    LegacyAuthenticatedNotFound, // existing server's protected 404
    OtaReservedArm,
    OtaReservedUpload,
    OtaReservedReject
};
struct Port80Classification {
    Port80Plan plan = Port80Plan::Invalid;
    bool requiresIndependentPrivilegedPost = false;
    bool mayUseBrowserReadCookie = false; // only when a future legacy adapter independently validates it
    bool currentlyRegisteredInFirstBootBridge = false;
};
class NativeOtaPort80Plan final {
public:
    static constexpr size_t kMaxFirstLineBytes = 128u;
    // Feed at most the complete request line. Do not consume a body or other
    // headers. Caller must retain any consumed preface for its own parser.
    static Port80Classification inspect(const char* raw,size_t length,
                                        bool factoryRestoreCompiled=false) {
        Port80Classification result{};
        if (!raw || length==0u || length>kMaxFirstLineBytes) return result;
        bool hasLineEnd=false;
        for(size_t i=0;i<length;++i) {
            const unsigned char c=static_cast<unsigned char>(raw[i]);
            if(c=='\r') {
                if(i+1u!=length-1u || raw[i+1u]!='\n')return result;
                hasLineEnd=true;
                ++i; // consume paired LF; standalone LF remains forbidden.
            } else if(c=='\n' || c==0u || c<32u || c>=127u) {
                return result; // no folding, LF-only, controls or non-ASCII
            }
        }
        if(!hasLineEnd){
            result.plan=length==kMaxFirstLineBytes?Port80Plan::Invalid:Port80Plan::Incomplete;
            return result;
        }
        const size_t payloadLength=length-2u;
        size_t firstSpace=payloadLength;
        for(size_t i=0;i<payloadLength;++i)
            if(raw[i]==' ') {firstSpace=i;break;}
        if(firstSpace==payloadLength || firstSpace==0u)return result;
        size_t secondSpace=payloadLength;
        for(size_t i=firstSpace+1u;i<payloadLength;++i)
            if(raw[i]==' ') {secondSpace=i;break;}
        if(secondSpace==payloadLength || secondSpace==firstSpace+1u)return result;
        for(size_t i=secondSpace+1u;i<payloadLength;++i)
            if(raw[i]==' ')return result;
        if(!eq(raw+secondSpace+1u,payloadLength-secondSpace-1u,"HTTP/1.1"))
            return result;
        const View method{raw,firstSpace};
        const View route{raw+firstSpace+1u,secondSpace-firstSpace-1u};
        const bool get=equal(method,"GET");
        const bool post=equal(method,"POST");
        if(route.n==0u || route.p[0]!='/')return result;
        for(size_t i=0;i<route.n;++i) {
            const char c=route.p[i];
            // Reject request-target query/fragment and percent encoding in
            // this migration design. Today's dashboard uses exact routes.
            // Preserving arbitrary old query semantics is a separate gate.
            if(c=='?' || c=='#' || c=='%' || c=='\\')return result;
        }
        // Strictly reserve the entire OTA namespace BEFORE any future generic
        // HTTP parser can buffer a 494-KiB POST. Capabilities is the EXISTING
        // GET-only read-only route and must remain reachable via legacy auth.
        if(starts(route,"/api/v1/bridge/ota/") &&
           !equal(route,"/api/v1/bridge/ota/capabilities")) {
            result.requiresIndependentPrivilegedPost=true;
            if(post && equal(route,"/api/v1/bridge/ota/arm"))
                result.plan=Port80Plan::OtaReservedArm;
            else if(post && equal(route,"/api/v1/bridge/ota/upload"))
                result.plan=Port80Plan::OtaReservedUpload;
            else result.plan=Port80Plan::OtaReservedReject;
            // RESERVATION is NOT a live install route or permission.
            result.currentlyRegisteredInFirstBootBridge=false;
            return result;
        }
        if(!get && !post) {
            result.plan=Port80Plan::LegacyAuthenticatedNotFound;
            return result;
        }
        if(get && equal(route,"/"))result.plan=Port80Plan::LegacyDashboardGet;
        else if(get && equal(route,"/ui.js"))result.plan=Port80Plan::LegacyJavascriptGet;
        else if(get && equal(route,"/api/v1/bridge/metrics"))result.plan=Port80Plan::LegacyMetricsGet;
        else if(post && equal(route,"/api/v1/bridge/metrics"))result.plan=Port80Plan::LegacyMetricsPost;
        else if(get && equal(route,"/api/v1/bridge/status"))result.plan=Port80Plan::LegacyStatusGet;
        else if(get && equal(route,"/api/v1/bridge/fs-plan"))result.plan=Port80Plan::LegacyFsPlanGet;
        else if(get && equal(route,"/api/v1/bridge/ota/capabilities"))result.plan=Port80Plan::LegacyCapabilitiesGet;
        else if(get && equal(route,"/api/v1/bridge/factory-return"))result.plan=Port80Plan::LegacyFactoryReturnGet;
        else if(post && equal(route,"/api/v1/bridge/factory-return"))result.plan=Port80Plan::LegacyFactoryReturnPost;
        else result.plan=Port80Plan::LegacyAuthenticatedNotFound;
        result.currentlyRegisteredInFirstBootBridge=
            result.plan!=Port80Plan::LegacyAuthenticatedNotFound &&
            (result.plan!=Port80Plan::LegacyFactoryReturnPost || factoryRestoreCompiled);
        result.requiresIndependentPrivilegedPost=
            result.plan==Port80Plan::LegacyMetricsPost ||
            result.plan==Port80Plan::LegacyFactoryReturnPost;
        result.mayUseBrowserReadCookie=
            result.plan==Port80Plan::LegacyDashboardGet ||
            result.plan==Port80Plan::LegacyJavascriptGet ||
            result.plan==Port80Plan::LegacyMetricsGet ||
            result.plan==Port80Plan::LegacyCapabilitiesGet;
        return result;
    }
private:
    struct View{const char* p;size_t n;};
    static bool eq(const char* p,size_t n,const char* literal) {
        size_t i=0u;
        while(i<n && literal[i] && p[i]==literal[i])++i;
        return i==n && literal[i]=='\0';
    }
    static bool equal(View v,const char* expected){return eq(v.p,v.n,expected);}
    static bool starts(View v,const char* prefix){
        size_t i=0u;
        while(prefix[i]) {
            if(i>=v.n || v.p[i]!=prefix[i])return false;
            ++i;
        }
        return true;
    }
};
} // namespace ShinoNativeOta
