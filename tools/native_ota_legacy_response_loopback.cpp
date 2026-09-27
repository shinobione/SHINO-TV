// SPDX-License-Identifier: GPL-3.0-or-later
// LOCALHOST SINGLE-REQUEST HTTP RESPONSE FIXTURE ONLY. NEVER an owner-device
// listener. Auth success comes ONLY from argv scenario, NOT Authorization
// bytes; COOKIE success uses a preissued disposable fixture token and the
// exact bounded raw Cookie value from NativeOtaSingleIngressShadow.
// JSON recognition is limited to TWO frozen synthetic strings: this does
// NOT replace ArduinoJson, native Digest, legacy handler, LCD or flash.
#include "boot/NativeOtaSingleIngressShadow.h"
#include "boot/NativeOtaLegacySessionReview.h"
#include "boot/NativeOtaLegacyResponsePreview.h"
#include <arpa/inet.h>
#include <netinet/in.h>
#include <sys/socket.h>
#include <unistd.h>
#include <cerrno>
#include <chrono>
#include <cstdint>
#include <cstring>
#include <iostream>
#include <string>
using namespace ShinoNativeOta;
constexpr uint32_t PEER_FIXTURE=0xC0A80403u;
constexpr std::array<uint8_t,16> TOKEN_FIXTURE{{1,2,3,4,5,6,7,8,9,10,11,12,13,14,15,16}};
constexpr const char* GOOD_JSON=
    R"({"ok":true,"gpu_available":true,"cpu_usage":22.5,"gpu_usage":34.5,"memory_used_gb":8,"memory_total_gb":16,"gpu_vram_mb":2048,"gpu_temp_c":56,"gpu_power":120})";
constexpr const char* BAD_NUMERIC_JSON=
    R"({"ok":true,"gpu_available":true,"cpu_usage":999,"gpu_usage":34.5,"memory_used_gb":8,"memory_total_gb":16,"gpu_vram_mb":2048,"gpu_temp_c":56,"gpu_power":120})";
static uint32_t nowMs(const std::chrono::steady_clock::time_point& start){
    return 101u+static_cast<uint32_t>(std::chrono::duration_cast<std::chrono::milliseconds>(
        std::chrono::steady_clock::now()-start).count());
}
static bool sendFully(int socket,const std::string& response) {
    size_t at=0u;
    while(at<response.size()) {
        const ssize_t n=::send(socket,response.data()+at,response.size()-at,MSG_NOSIGNAL);
        if(n<=0)return false;
        at+=static_cast<size_t>(n);
    }
    return true;
}
int main(int argc,char** argv) {
    if(argc!=2)return 2;
    const std::string mode(argv[1]);
    const bool digestFixture=mode=="digest_fixture";
    const bool cookieFixture=mode=="cookie_fixture"||mode=="expired_cookie_fixture";
    if(!digestFixture && !cookieFixture && mode!="anonymous")return 2;

    // Real OS listener is restricted to this host's 127.0.0.1, never port80.
    const int listener=::socket(AF_INET,SOCK_STREAM,0);
    if(listener<0)return 2;
    sockaddr_in address{};
    address.sin_family=AF_INET;
    address.sin_addr.s_addr=htonl(INADDR_LOOPBACK);
    address.sin_port=htons(0u);
    if(::bind(listener,reinterpret_cast<const sockaddr*>(&address),sizeof(address))!=0 ||
       ::listen(listener,1)!=0) {::close(listener);return 2;}
    socklen_t addrlen=sizeof(address);
    if(::getsockname(listener,reinterpret_cast<sockaddr*>(&address),&addrlen)!=0) {
        ::close(listener);return 2;
    }
    std::cout<<"FIXTURE_PORT "<<ntohs(address.sin_port)<<std::endl;
    const int connection=::accept(listener,nullptr,nullptr);
    ::close(listener);
    if(connection<0)return 2;
    timeval timeout{};timeout.tv_sec=1;timeout.tv_usec=0;
    (void)::setsockopt(connection,SOL_SOCKET,SO_RCVTIMEO,&timeout,sizeof(timeout));

    NativeOtaSingleIngressShadow shadow(101u);
    const auto began=std::chrono::steady_clock::now();
    bool rejected=false;
    bool messageReady=false;
    uint8_t buf[512]{};
    while(true) {
        const ssize_t n=::recv(connection,buf,sizeof(buf),0);
        const uint32_t when=nowMs(began);
        if(n>0) {
            if(!shadow.feed(buf,static_cast<size_t>(n),when)) {
                rejected=true;break;
            }
            if(shadow.result().phase==SingleIngressReviewPhase::AwaitExactClose) {
                // End at the exact HTTP message boundary: normal clients do
                // not have to half-close their TCP write side before a reply.
                messageReady=true;break;
            }
        } else if(n==0) {
            messageReady=shadow.result().phase==SingleIngressReviewPhase::AwaitExactClose;
            if(!messageReady)rejected=true;
            break;
        } else if(errno==EINTR)continue;
        else if(errno==EAGAIN || errno==EWOULDBLOCK) {
            if(!shadow.tick(when)) {rejected=true;break;}
        } else {rejected=true;break;}
    }
    if(!rejected && (!messageReady ||
       !shadow.finishOnExactMessageBoundaryForHostReviewOnly(nowMs(began))))
        rejected=true;
    if(rejected)shadow.disconnect();

    LegacyHttpPreview reply{};
    const auto parsed=shadow.result();
    // Even an oversized declared Windows POST is NOT read into RAM. The
    // source's 413 is a post-Digest response: the host fixture retains only
    // bounded header metadata and authenticates its synthetic decision first.
    const bool boundedOversize=
        rejected && parsed.route==Port80Plan::LegacyMetricsPost &&
        parsed.refusal==SingleIngressRefusal::LegacyMetricsLengthOutsideBounds;
    if((!rejected &&
        parsed.phase==SingleIngressReviewPhase::LegacyRequestReviewedOnly) ||
       boundedOversize) {
        NativeOtaLegacySessionReview sessions;
        if(cookieFixture) {
            // Explicitly prepare one synthetic prior Digest-successful GET /.
            // This is NOT derived from a header or real Digest/owner secret.
            (void)sessions.decide(Port80Plan::LegacyDashboardGet,true,nullptr,0u,
                                  PEER_FIXTURE,100u,TOKEN_FIXTURE);
        }
        size_t rawCookieLen=0u;
        const char* rawCookie=shadow.cookieValueForHostReviewOnly(rawCookieLen);
        const uint32_t consentTime=mode=="expired_cookie_fixture"?7200101u:101u;
        const LegacyDecision d=sessions.decide(parsed.route,digestFixture,
            rawCookie,rawCookieLen,PEER_FIXTURE,consentTime,TOKEN_FIXTURE);
        bool knownValid=false,knownBadNumeric=false;
        if(parsed.route==Port80Plan::LegacyMetricsPost) {
            const auto* p=shadow.boundedMetricsBodyForTestOnly();
            if(p) {
                const std::string body(reinterpret_cast<const char*>(p),parsed.bodyBytes);
                knownValid=body==GOOD_JSON;
                knownBadNumeric=body==BAD_NUMERIC_JSON;
            }
        }
        // A tiny frozen synthetic dictionary is intentionally NOT a JSON
        // parser. Unexpected JSON receives the malformed-fixture branch.
        reply=NativeOtaLegacyResponsePreview::decide(
            parsed.route,d,boundedOversize?parsed.declaredBodyBytes:parsed.bodyBytes,
            knownValid||knownBadNumeric,
            knownValid?LegacyTelemetryResult::AcceptedIntoHostFixtureRamOnly:
                       LegacyTelemetryResult::InvalidNumbers);
    } else {
        reply.status=403;
        reply.body="{\"error\":\"HOST_FIXTURE_INGRESS_REJECTED_NO_FLASH\"}";
    }

    const char* phrase=reply.status==200?"OK":
                       reply.status==401?"Unauthorized":
                       reply.status==403?"Forbidden":
                       reply.status==404?"Not Found":
                       reply.status==413?"Payload Too Large":
                       reply.status==422?"Unprocessable Content":"Fixture Error";
    std::string header="HTTP/1.1 "+std::to_string(reply.status)+" "+phrase+
        "\r\nConnection: close\r\nCache-Control: no-store\r\n"
        "X-Content-Type-Options: nosniff\r\n"
        "X-Shino-Host-Fixture: synthetic-no-owner-auth-no-device-writer\r\n"
        "Content-Type: "+reply.contentType+"\r\n";
    if(reply.wouldChallengeDigest)
        header+="X-Shino-Fixture-Digest-Challenge: required-but-NOT-generated\r\n";
    if(reply.wouldUseDashboardCsp)
        header+="Content-Security-Policy: default-src 'none'; style-src 'unsafe-inline'; "
                "script-src 'self'; connect-src 'self'; base-uri 'none'; form-action 'none'\r\n";
    if(reply.wouldIssueCookie) {
        char token[33]{};
        // Never show an actual owner cookie. Disposable test token from argv
        // fixture-only entropy, never ESP.random() nor stored credentials.
        NativeOtaLegacySessionReview fixtureSession;
        (void)fixtureSession.decide(Port80Plan::LegacyDashboardGet,true,nullptr,0u,
                                    PEER_FIXTURE,101u,TOKEN_FIXTURE);
        if(fixtureSession.tokenForHostTestOnly(0u,token)) {
            header+="Set-Cookie: SHINO_READ_SESSION="+std::string(token)+
                "; Path=/; Max-Age=7200; HttpOnly; SameSite=Strict\r\n";
        }
    }
    const std::string body(reply.body);
    header+="Content-Length: "+std::to_string(body.size())+"\r\n\r\n";
    const bool sent=sendFully(connection,header+body);
    ::close(connection);
    std::cout<<"FIXTURE_RESULT "<<reply.status
             <<" WOULD_CHALLENGE "<<reply.wouldChallengeDigest
             <<" WOULD_ISSUE_COOKIE "<<reply.wouldIssueCookie
             <<" REAL_DISPATCH "<<reply.actualHandlerDispatched
             <<" DEVICE_WRITER "<<reply.otaWriterPresent
             <<" PREVIEW_ONLY_NO_FLASH"<<std::endl;
    return sent?0:2;
}
