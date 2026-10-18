// SPDX-License-Identifier: GPL-3.0-or-later
#pragma once
// M3-M isolated handler seam: executes unchanged B5.3 FslessMetrics.cpp.
// No WiFiServer, route registration, port, key, flash, LCD or HTTP writer.
// Caller must provide a VERIFIED legacy authorization policy; the production
// B5.3 Digest/cookie/IP/Origin verifier is NOT yet transferred. No default
// permit-all option; an isolated Xtensa proof injects DenyAll.
#include "boot/FslessMetrics.h"
#include "boot/HomeLanPolicy.h"
#include <ArduinoJson.h>
#include <cstddef>
#include <cstdint>
#include <cstring>

namespace ShinoM3M {
enum class Verb : uint8_t { Get, Post };
enum class Network : uint8_t { ProtectedAp, HomeSta };
struct Request {
    Verb method=Verb::Get;
    Network network=Network::HomeSta;
    const char* path=nullptr;
    const uint8_t* body=nullptr;
    size_t bodySize=0;
    size_t declaredLength=0;
    const char* contentType=nullptr;
    bool hasTransferEncoding=false;
    bool exactEndOfBody=false;
};
// Caller-owned response buffer: prevents allocating up to 896 bytes
// on the limited ESP8266 continuation stack inside this handler.
struct Response {
    int status=500;
    size_t written=0;
};
struct DenyAll final {
    bool permit(Verb, Network, const char*) const {return false;}
};

class ActualMetricsHandler final {
public:
    static constexpr size_t kMaxBody=384u;
    static constexpr size_t kMinBody=16u;
    static constexpr size_t kMinReply=896u;
    static constexpr const char* kPath="/api/v1/bridge/metrics";

    template<class VerifiedLegacyAuthorization>
    static Response handle(const Request& req,
                           const VerifiedLegacyAuthorization& verifier,
                           char* output,size_t capacity) {
        if(!output||capacity<kMinReply) return {500,0};
        output[0]='\0';
        // These checks are NOT a replacement for the original B5.3
        // network authority, Digest nonce or browser cookie verifier.
        if(!req.path||std::strcmp(req.path,kPath)!=0 ||
           !HomeLan::endpoint(req.network==Network::ProtectedAp,req.path))
            return message(404,"{\"error\":\"ROUTE_HOLD\"}",output,capacity);
        // MUST check authority before touching body bytes or requesting
        // the JsonDocument heap allocation. A false verifier is terminal.
        if(!verifier.permit(req.method,req.network,req.path))
            return message(403,"{\"error\":\"AUTHORIZATION_REQUIRED\"}",output,capacity);
        if(req.method==Verb::Get) {
            // GET must not become an implicit POST or accept request content.
            if(req.body||req.bodySize||req.declaredLength||req.hasTransferEncoding)
                return message(400,"{\"error\":\"INVALID_GET_FRAMING\"}",output,capacity);
            JsonDocument doc;
            FslessMetrics::describe(doc);
            const size_t required=measureJson(doc);
            if(required>=capacity) return {500,0};
            const size_t n=serializeJson(doc,output,capacity);
            if(n!=required)return {500,0};
            return {200,n};
        }
        if(req.method!=Verb::Post || !req.exactEndOfBody ||
           req.hasTransferEncoding || !req.contentType ||
           std::strcmp(req.contentType,"application/json")!=0 ||
           req.declaredLength!=req.bodySize || req.bodySize<kMinBody ||
           req.bodySize>kMaxBody || !req.body)
            return message(400,"{\"error\":\"METRICS_FRAMING\"}",output,capacity);
        JsonDocument doc;
        if(deserializeJson(doc,req.body,req.bodySize))
            return message(422,"{\"error\":\"INVALID_JSON\"}",output,capacity);
        String reason;
        if(!FslessMetrics::apply(doc.as<JsonVariantConst>(),reason))
            return message(422,"{\"error\":\"INVALID_TELEMETRY\"}",output,capacity);
        // The real FirstBootBridge additionally sets telemetryNeedsRedraw.
        // This isolated adapter cannot claim any LCD repaint.
        return message(200,"{\"status\":\"RAM_SAMPLE_ACCEPTED\",\"persisted\":false}",
                       output,capacity);
    }
private:
    static Response message(int status,const char* body,char* out,size_t cap) {
        const size_t n=std::strlen(body);
        if(n>=cap)return {500,0};
        std::memcpy(out,body,n+1u);
        return {status,n};
    }
};
} // namespace ShinoM3M
