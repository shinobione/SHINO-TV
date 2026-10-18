// Source-execute unchanged B5.3 FslessMetrics.cpp with real ArduinoJson 7.4.3.
// Authorization objects are HOST TEST FIXTURES, not real Digest/Cookie.
// This test NEVER starts the installed LINK, any socket or a device.
#include "M3MActualMetricsHandler.h"
#include <cstdio>
#include <cstdlib>
#include <cstring>
#include <string>
using namespace ShinoM3M;
namespace {
uint32_t timeMs=100u;
char reply[ActualMetricsHandler::kMinReply]{}; // global, not CONT stack
void check(bool ok,const char* cause) {
    if(!ok){std::fprintf(stderr,"FAIL: %s\n",cause);std::exit(3);}
}
struct LabAuth {
    bool read=false,write=false;
    mutable unsigned checks=0;
    bool permit(Verb v,Network net,const char* path)const {
        ++checks;
        return path && net==Network::HomeSta &&
            (v==Verb::Get?read:write);
    }
};
constexpr const char* body=
    R"({"ok":true,"gpu_available":true,"cpu_usage":22.5,"gpu_usage":34.5,"memory_used_gb":8.0,"memory_total_gb":16.0,"gpu_vram_mb":2048.0,"gpu_temp_c":56.0,"gpu_power":120.0})";
Request get() {
    Request r;
    r.method=Verb::Get;r.network=Network::HomeSta;
    r.path=ActualMetricsHandler::kPath;
    return r;
}
Request post(const char* value) {
    auto r=get();r.method=Verb::Post;
    r.body=reinterpret_cast<const uint8_t*>(value);
    r.bodySize=std::strlen(value);
    r.declaredLength=r.bodySize;
    r.contentType="application/json";
    r.exactEndOfBody=true;
    return r;
}
template<class Auth>
Response call(const Request& r,const Auth& auth,size_t capacity=sizeof(reply)) {
    return ActualMetricsHandler::handle(r,auth,reply,capacity);
}
}
uint32_t millis(){return timeMs;}
int main() {
    DenyAll deny;
    auto r=post(body);
    const auto forbidden=call(r,deny);
    check(forbidden.status==403,"no actual auth -> deny POST");
    check(!FslessMetrics::snapshot().received,"unauthorized post did not alter RAM");
    check(call(get(),deny).status==403,"no actual auth -> deny GET");
    LabAuth cookie{true,false};
    check(call(r,cookie).status==403,"read cookie never writes");
    check(!FslessMetrics::snapshot().received,"read cookie rejected safely");
    check(call(get(),cookie).status==200,"cookie permits GET");
    check(std::strstr(reply,"\"received\":false")!=nullptr,"initial no sample");
    LabAuth digest{true,true};
    check(call(r,digest).status==200,"Digest fixture permits POST");
    check(std::strcmp(reply,"{\"status\":\"RAM_SAMPLE_ACCEPTED\",\"persisted\":false}")==0,
          "true original B5.3 POST response contract");
    check(FslessMetrics::snapshot().received,"original C++ sample actually stored");
    check(call(get(),cookie).status==200,"independent cookie read after POST");
    check(std::strstr(reply,"\"cpu_usage\":22.5")!=nullptr,
          "GET is true original FslessMetrics describe");
    check(std::strstr(reply,"\"gpu_temp_c\":56")!=nullptr,
          "original temp accessible");
    check(std::strstr(reply,"\"ttl_seconds\":6")!=nullptr,"B5.3 TTL6 invariant");

    // Malformed and dangerous values must never overwrite the last good RAM.
    auto invalid=post(R"({"ok":true,"gpu_available":true,"cpu_usage":102,"gpu_usage":34,"memory_used_gb":8,"memory_total_gb":16,"gpu_vram_mb":2048,"gpu_temp_c":56,"gpu_power":120})");
    check(call(invalid,digest).status==422,"real FslessMetrics rejects 102%");
    check(FslessMetrics::snapshot().cpu==22.5f,"out of range retains previous");
    auto malformed=post(R"({"ok":true,"gpu_available":tru})");
    check(call(malformed,digest).status==422,"invalid JSON rejected");
    check(FslessMetrics::snapshot().cpu==22.5f,"bad JSON retains previous");

    auto wrongType=post(body);
    wrongType.contentType="text/plain";
    check(call(wrongType,digest).status==400,"content type restricted");
    auto shortBody=post(body);shortBody.declaredLength--;
    check(call(shortBody,digest).status==400,"Content-Length exactness");
    auto te=post(body);te.hasTransferEncoding=true;
    check(call(te,digest).status==400,"no transfer-encoding ambiguity");
    auto absentFin=post(body);absentFin.exactEndOfBody=false;
    check(call(absentFin,digest).status==400,"no implicit partial body acceptance");
    auto excess=post(body);excess.bodySize=385;excess.declaredLength=385;
    check(call(excess,digest).status==400,"oversized body rejected before decode");
    check(FslessMetrics::snapshot().cpu==22.5f,"framing refusals preserve RAM");

    auto getBody=get();getBody.body=reinterpret_cast<const uint8_t*>(body);
    getBody.bodySize=1;
    check(call(getBody,digest).status==400,"GET request body forbidden");
    auto forbiddenRoute=get();forbiddenRoute.path="/api/v1/display/mode";
    const auto authChecksBefore=digest.checks;
    check(call(forbiddenRoute,digest).status==404,"M3 route never falls to metrics adapter");
    check(digest.checks==authChecksBefore,"no auth checked on wrong route");
    auto invalidRoute=get();invalidRoute.path=nullptr;
    check(call(invalidRoute,digest).status==404,"null route denied");
    const auto deniedTiny=call(get(),digest,32u);
    check(deniedTiny.status==500&&deniedTiny.written==0,
          "caller must provide real bounded response memory");
    // Existing SDK TTL behavior: read-only, no writer and no reboot.
    timeMs=6101u;
    check(call(get(),digest).status==200,"GET after TTL");
    check(std::strstr(reply,"\"stale\":true")!=nullptr,"TTL still expires as before");
    std::puts("M3M_REAL_FSLESSMETRICS_AUTHORIZED_ONLY_SOURCE_EXECUTED_PASS");
}
