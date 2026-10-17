// SPDX-License-Identifier: GPL-3.0-or-later
// M3-G HOST-ONLY: real unchanged FslessMetrics.cpp and ArduinoJson 7.4.3
// behind the existing synthetic legacy TCP / MD5 Digest review fixture.
// IMPORTANT: metrics RAM mutations occur ONLY in host process, not device.
// Digest still authenticates AFTER bounded body buffering, not pre-body.
// HOST-ONLY INTEGRATED NONWRITING HTTP FIXTURE. One 127.0.0.1 ephemeral
// listener; exact native shadow ingress -> actual incoming legacy MD5 Digest
// proof (OpenSSL with disposable fixtures) -> existing legacy session and
// response PREVIEW objects. Not ESP8266WebServer, production authentication,
// firmware LCD, OTA, Wi-Fi or device deployment. Unlike the predecessor,
// this HOST binary DOES decode arbitrary bounded telemetry JSON and DOES
// serve the byte-for-byte original HTML/JS assets from firmware headers.
// The pinned nonce and cookie entropy are deliberately deterministic HOST
// test vectors, NEVER a pattern for a real challenge/session issuer.
#include "boot/NativeOtaSingleIngressShadow.h"
#include "boot/NativeOtaLegacySessionReview.h"
#include "boot/NativeOtaLegacyResponsePreview.h"
// Actual product dashboard header uses PROGMEM; the HOST-only shim has no
// flash address space. Do not add this macro to any firmware source.
#ifndef PROGMEM
#define PROGMEM
#endif
#include "boot/FslessWebUI.h"
#include "boot/FslessMetrics.h"
#include "../link_m3c_crypto/M3CAuthenticatedIngress.h"
#include <ArduinoJson.h>
#include <openssl/evp.h>
#include <openssl/hmac.h>
#include <openssl/sha.h>
#include <poll.h>
#include <cstring>
#include <arpa/inet.h>
#include <netinet/in.h>
#include <sys/socket.h>
#include <unistd.h>
#include <cerrno>
#include <chrono>
#include <cstdint>
#include <cstdlib>
#include <array>
#include <iostream>
#include <map>
#include <string>
using namespace ShinoNativeOta;
static_assert(ARDUINOJSON_VERSION_MAJOR==7 && ARDUINOJSON_VERSION_MINOR==4 &&
              ARDUINOJSON_VERSION_REVISION==3,"M3G requires pinned real ArduinoJson 7.4.3");
static uint32_t hostSampleClock=100u;
uint32_t millis() {return hostSampleClock;} // HOST Arduino.h stub only
namespace {
constexpr uint32_t PEER_FIXTURE=0xC0A80403u; // NOT the real accepted socket peer.

constexpr std::array<uint8_t,16> COOKIE_ENTROPY{{1,2,3,4,5,6,7,8,9,10,11,12,13,14,15,16}};
constexpr char USER[]="shino";
constexpr char PASSWORD[]="disposable-only-never-owner-password";
constexpr char REALM[]="SHINO-FirstBoot";
constexpr char NONCE[]="0123456789abcdef0123456789abcdef";
uint32_t nowMs(const std::chrono::steady_clock::time_point& start) {
    return 101u+static_cast<uint32_t>(std::chrono::duration_cast<std::chrono::milliseconds>(
        std::chrono::steady_clock::now()-start).count());
}
bool md5(const std::string& value,std::string& hex) {
    unsigned char digest[EVP_MAX_MD_SIZE]{};
    unsigned int len=0u;
    if(EVP_Digest(value.data(),value.size(),digest,&len,EVP_md5(),nullptr)!=1 ||
       len!=16u)return false;
    static constexpr char chars[]="0123456789abcdef";
    hex.clear();hex.reserve(32u);
    for(size_t i=0;i<16u;++i) {
        hex+=chars[digest[i]>>4u];
        hex+=chars[digest[i]&0x0fu];
    }
    return true;
}
bool readDigestFields(const char* value,size_t n,std::map<std::string,std::string>& fields) {
    if(!value || n<8u || n>768u || std::string(value,7u)!="Digest ")return false;
    size_t i=7u;
    while(i<n) {
        while(i<n && value[i]==' ')++i;
        const size_t begin=i;
        while(i<n && ((value[i]>='a'&&value[i]<='z') ||
                      (value[i]>='A'&&value[i]<='Z')||value[i]=='-'))++i;
        if(i==begin || i>=n || value[i]!='=')return false;
        const std::string key(value+begin,i-begin);
        ++i;
        std::string field;
        if(i<n && value[i]=='"') {
            ++i;const size_t first=i;
            while(i<n && value[i]!='"') {
                if(value[i]=='\\' || static_cast<unsigned char>(value[i])<32u ||
                   static_cast<unsigned char>(value[i])>=127u)return false;
                ++i;
            }
            if(i==n)return false;
            field.assign(value+first,i-first);
            ++i;
        } else {
            const size_t first=i;
            while(i<n && value[i]!=',' && value[i]!=' ') {
                if(static_cast<unsigned char>(value[i])<33u ||
                   static_cast<unsigned char>(value[i])>=127u)return false;
                ++i;
            }
            if(i==first)return false;
            field.assign(value+first,i-first);
        }
        if(!fields.emplace(key,field).second)return false; // duplicates
        while(i<n && value[i]==' ')++i;
        if(i==n)break;
        if(value[i]!=',')return false;
        ++i;if(i==n)return false;
    }
    return fields.size()==9u; // exact expected qop=auth fixture fields.
}
bool isLegacyProof(const char* value,size_t length,const char* method,
                   const char* path) {
    std::map<std::string,std::string> f;
    if(!readDigestFields(value,length,f))return false;
    const auto match=[&](const char* key,const char* want){
        const auto it=f.find(key);
        return it!=f.end() && it->second==want;
    };
    if(!match("username",USER) || !match("realm",REALM) || !match("nonce",NONCE) ||
       !match("uri",path) || !match("algorithm","MD5") || !match("qop","auth") ||
       !match("nc","00000001"))return false;
    const auto c=f.find("cnonce"),r=f.find("response");
    if(c==f.end()||r==f.end()||c->second.size()<8u||c->second.size()>64u||
       r->second.size()!=32u)return false;
    for(char v:c->second)
        if(!((v>='a'&&v<='z')||(v>='A'&&v<='Z')||(v>='0'&&v<='9')||
             v=='-'||v=='_'||v=='+'||v=='/'||v=='='))return false;
    for(char v:r->second)
        if(!((v>='0'&&v<='9')||(v>='a'&&v<='f')))return false;
    std::string ha1,ha2,want;
    if(!md5(std::string(USER)+":"+REALM+":"+PASSWORD,ha1) ||
       !md5(std::string(method)+":"+path,ha2) ||
       !md5(ha1+":"+NONCE+":"+f["nc"]+":"+c->second+":auth:"+ha2,want))return false;
    unsigned char diff=0u;
    for(size_t i=0;i<32u;++i)
        diff|=static_cast<unsigned char>(want[i]^r->second[i]);
    return diff==0u; // verifies actual raw Authorization bytes, not argv mode.
}
bool sendFully(int fd,const std::string& text) {
    size_t at=0u;
    while(at<text.size()) {
        const ssize_t n=::send(fd,text.data()+at,text.size()-at,MSG_NOSIGNAL);
        if(n<=0)return false;
        at+=static_cast<size_t>(n);
    }
    return true;
}
const char* routePath(Port80Plan route) {
    switch(route) {
    case Port80Plan::LegacyDashboardGet:return "/";
    case Port80Plan::LegacyJavascriptGet:return "/ui.js";
    case Port80Plan::LegacyMetricsGet:
    case Port80Plan::LegacyMetricsPost:return "/api/v1/bridge/metrics";
    case Port80Plan::LegacyCapabilitiesGet:return "/api/v1/bridge/ota/capabilities";
    case Port80Plan::LegacyStatusGet:return "/api/v1/bridge/status";
    case Port80Plan::LegacyFsPlanGet:return "/api/v1/bridge/fs-plan";
    case Port80Plan::LegacyFactoryReturnGet:return "/api/v1/bridge/factory-return";
    case Port80Plan::LegacyAuthenticatedNotFound:return "/unknown-fixture";
    default:return "";
    }
}
const char* reason(int status) {
    switch(status) {
    case 200:return "OK";
    case 401:return "Unauthorized";
    case 403:return "Forbidden";
    case 404:return "Not Found";
    case 413:return "Payload Too Large";
    case 422:return "Unprocessable Content";
    default:return "Fixture Error";
    }
}

// M3-I INERT HOST integration: this gate is dispatched only on the *exact*
// first-line route after reading one byte at a time, and BEFORE any request
// header/body beyond that first line has been pulled from the socket.
// The public 01..20 vector is NOT a device credential and MUST NEVER ship.
// Only LAB CAS revision changes; no renderer, actual ACK, flash or OTA.
constexpr char LAB_DEVICE[]="1234567890abcdef";
constexpr char LAB_BOOT[]="1234567890abcdef1234567890abcdef";
constexpr char LAB_HOST[]="192.168.4.1";
constexpr uint8_t PUBLIC_M3_KEY[32]{
    1,2,3,4,5,6,7,8,9,10,11,12,13,14,15,16,
    17,18,19,20,21,22,23,24,25,26,27,28,29,30,31,32
};
struct HostM3Crypto final {
    static bool hmac(const uint8_t* key,const uint8_t* bytes,
                     size_t n,uint8_t out[32]) {
        unsigned written=0;
        return HMAC(EVP_sha256(),key,32,bytes,n,out,&written)!=nullptr
            && written==32u;
    }
    static bool sha256(const uint8_t* bytes,size_t n,uint8_t out[32]) {
        return SHA256(bytes,n,out)!=nullptr;
    }
};
enum class ByteStatus { Data, Closed, Timeout, Error };
ByteStatus readByte(int fd, const std::chrono::steady_clock::time_point& since,
                    uint32_t deadlineMs,uint8_t& out) {
    for(;;) {
        const auto elapsed=std::chrono::duration_cast<std::chrono::milliseconds>(
            std::chrono::steady_clock::now()-since).count();
        if(elapsed>=deadlineMs) return ByteStatus::Timeout;
        pollfd p{fd,POLLIN,0};
        const int wait=static_cast<int>(deadlineMs-elapsed);
        const int n=::poll(&p,1,wait);
        if(n==0) return ByteStatus::Timeout;
        if(n<0){if(errno==EINTR)continue;return ByteStatus::Error;}
        if(p.revents&(POLLERR|POLLNVAL))return ByteStatus::Error;
        const ssize_t bytes=::recv(fd,&out,1u,0);
        if(bytes==1)return ByteStatus::Data;
        if(bytes==0)return ByteStatus::Closed;
        if(errno==EINTR||errno==EAGAIN)continue;
        return ByteStatus::Error;
    }
}
bool firstLineOnly(int fd,std::string& line,
                   std::chrono::steady_clock::time_point since) {
    line.clear();
    line.reserve(128u);
    for(size_t i=0u;i<128u;++i) {
        uint8_t b=0u;
        if(readByte(fd,since,1000u,b)!=ByteStatus::Data)return false;
        if(b=='\0'||(b=='\n'&&(line.empty()||line.back()!='\r')))return false;
        line.push_back(static_cast<char>(b));
        if(line.size()>=2u && line[line.size()-2u]=='\r' && b=='\n')
            return true;
    }
    return false;
}
void replyM3(int fd,int status,const char* body) {
    const char* reason=status==202?"Accepted":status==408?"Request Timeout":
        status==409?"Conflict":"Forbidden";
    std::string header=std::string("HTTP/1.1 ")+std::to_string(status)+" "+reason+
       "\r\nContent-Type: application/json\r\nCache-Control: no-store\r\n"+
       "Connection: close\r\nX-Shino-Host-Fixture: M3I_ONLY_NO_DEVICE\r\n"+
       "Content-Length: "+std::to_string(std::strlen(body))+"\r\n\r\n";
    (void)sendFully(fd,header+body);
}
void handleM3(int fd,const std::string& line,ShinoM3C::OfflineCasLedger& ledger) {
    // Separate from M3-G Digest/ArduinoJson path on the SAME host listener.
    // Read-order MUST be: first line, headers, HMAC, then one body byte.
    const ShinoM3C::Identity id{LAB_HOST,LAB_DEVICE,LAB_BOOT};
    ShinoM3C::Gate gate(id,ledger.revision());
    const auto begin=std::chrono::steady_clock::now();
    for(char c:line) {
        if(gate.headerByte<HostM3Crypto>(c,0u,PUBLIC_M3_KEY)==ShinoM3C::Phase::Reject) {
            replyM3(fd,403,"{\"lab\":\"M3_AUTH_REJECTED\",\"applied\":false}");
            return;
        }
    }
    uint8_t byte=0u;
    while(gate.phase()==ShinoM3C::Phase::Header) {
        const ByteStatus got=readByte(fd,begin,1000u,byte);
        if(got!=ByteStatus::Data) {
            replyM3(fd,got==ByteStatus::Timeout?408:403,
                    "{\"lab\":\"M3_HEADER_INCOMPLETE\",\"applied\":false}");
            return;
        }
        if(gate.headerByte<HostM3Crypto>(
            static_cast<char>(byte),nowMs(begin)-101u,PUBLIC_M3_KEY)
            ==ShinoM3C::Phase::Reject) {
            replyM3(fd,403,"{\"lab\":\"M3_AUTH_REJECTED\",\"applied\":false}");
            return;
        }
    }
    if(gate.phase()!=ShinoM3C::Phase::AuthenticatedHeader) {
        replyM3(fd,403,"{\"lab\":\"M3_AUTH_REJECTED\",\"applied\":false}");
        return;
    }
    const auto bodyStart=std::chrono::steady_clock::now();
    while(gate.phase()==ShinoM3C::Phase::AuthenticatedHeader) {
        const ByteStatus got=readByte(fd,bodyStart,2000u,byte);
        if(got!=ByteStatus::Data) {
            replyM3(fd,got==ByteStatus::Timeout?408:403,
                    "{\"lab\":\"M3_BODY_INCOMPLETE\",\"applied\":false}");
            return;
        }
        if(gate.bodyByte<HostM3Crypto>(
                byte,nowMs(bodyStart)-101u)==ShinoM3C::Phase::Reject) {
            replyM3(fd,403,"{\"lab\":\"M3_BODY_REJECTED\",\"applied\":false}");
            return;
        }
    }
    if(gate.phase()!=ShinoM3C::Phase::BodyDigestMatched) {
        replyM3(fd,403,"{\"lab\":\"M3_BODY_REJECTED\",\"applied\":false}");
        return;
    }
    // Dedicated client calls shutdown(SHUT_WR). Conventional clients that
    // wait for a response without a half-close get a bounded 408 refusal.
    // Any extra bytes before FIN cause refusal, never pipelining/keep-alive.
    const ByteStatus end=readByte(fd,bodyStart,2000u,byte);
    if(end!=ByteStatus::Closed) {
        replyM3(fd,end==ByteStatus::Timeout?408:403,
                "{\"lab\":\"M3_FRAMING_REJECTED\",\"applied\":false}");
        return;
    }
    if(gate.finishAfterExactFraming(true,0u,nowMs(bodyStart)-101u)
       !=ShinoM3C::Phase::VerifiedFrame ||
       !ledger.acceptVerifiedForLab(gate)) {
        replyM3(fd,409,"{\"lab\":\"M3_CAS_REJECTED\",\"applied\":false}");
        return;
    }
    replyM3(fd,202,"{\"lab\":\"M3_CRYPTO_VERIFIED_ONLY\",\"applied\":false}");
}

} // namespace

int main(int argc,char** argv) {
    if(argc!=2)return 2;
    const int requests=std::atoi(argv[1]);
    if(requests<1 || requests>24)return 2;
    const int listener=::socket(AF_INET,SOCK_STREAM,0);
    if(listener<0)return 2;
    sockaddr_in address{};
    address.sin_family=AF_INET;
    address.sin_addr.s_addr=htonl(INADDR_LOOPBACK);
    address.sin_port=htons(0u);
    if(::bind(listener,reinterpret_cast<const sockaddr*>(&address),sizeof(address))!=0 ||
       ::listen(listener,4)!=0) {::close(listener);return 2;}
    socklen_t addrlen=sizeof(address);
    if(::getsockname(listener,reinterpret_cast<sockaddr*>(&address),&addrlen)!=0) {
        ::close(listener);return 2;
    }
    std::cout<<"INTEGRATED_FIXTURE_PORT "<<ntohs(address.sin_port)<<std::endl;
    NativeOtaLegacySessionReview sessions;
    ShinoM3C::OfflineCasLedger m3LabLedger; // same process, one connection at a time
    int acceptedProofs=0,issuedReadCookies=0,acceptedPostPreviews=0,refusals=0;
    const auto start=std::chrono::steady_clock::now();
    for(int count=0;count<requests;++count) {
        const int fd=::accept(listener,nullptr,nullptr);
        if(fd<0){::close(listener);return 2;}
        timeval timeout{};timeout.tv_sec=2;timeout.tv_usec=0;
        (void)::setsockopt(fd,SOL_SOCKET,SO_RCVTIMEO,&timeout,sizeof(timeout));
        const auto requestStarted=std::chrono::steady_clock::now();
        std::string firstLine;
        if(!firstLineOnly(fd,firstLine,requestStarted)) {
            replyM3(fd,408,"{\"lab\":\"FIRST_LINE_REFUSED\",\"applied\":false}");
            ::close(fd);
            continue;
        }
        if(firstLine=="POST /api/v1/display/mode HTTP/1.1\r\n") {
            handleM3(fd,firstLine,m3LabLedger);
            ::close(fd);
            continue;
        }
        // Source-executed legacy path still runs on the same listener.
        // Never pass an already pre-read M3 body into a legacy parser.
        NativeOtaSingleIngressShadow ingress(nowMs(start));
        bool denied=!ingress.feed(reinterpret_cast<const uint8_t*>(
            firstLine.data()),firstLine.size(),nowMs(start)),ready=false;
        uint8_t buffer[512]{};
        for(;;) {
            const ssize_t got=::recv(fd,buffer,sizeof(buffer),0);
            const auto time=nowMs(start);
            if(got>0) {
                if(!ingress.feed(buffer,static_cast<size_t>(got),time)) {
                    denied=true;break;
                }
                if(ingress.result().phase==SingleIngressReviewPhase::AwaitExactClose) {
                    ready=true;break;
                }
            } else if(got==0) {
                ready=ingress.result().phase==SingleIngressReviewPhase::AwaitExactClose;
                if(!ready)denied=true;
                break;
            } else if(errno==EINTR)continue;
            else if(errno==EAGAIN||errno==EWOULDBLOCK) {
                if(!ingress.tick(time)){denied=true;break;}
            } else {denied=true;break;}
        }
        if(!denied && (!ready ||
           !ingress.finishOnExactMessageBoundaryForHostReviewOnly(nowMs(start))))
            denied=true;
        if(denied)ingress.disconnect();
        const auto parsed=ingress.result();
        LegacyHttpPreview reply{};
        bool proof=false;
        if(!denied && parsed.phase==SingleIngressReviewPhase::LegacyRequestReviewedOnly) {
            size_t authorizationLength=0u,cookieLength=0u;
            const char* authorization=ingress.authorizationValueForHostReviewOnly(
                authorizationLength);
            const char* cookie=ingress.cookieValueForHostReviewOnly(cookieLength);
            const bool post=parsed.route==Port80Plan::LegacyMetricsPost;
            proof=isLegacyProof(authorization,authorizationLength,
                                post?"POST":"GET",routePath(parsed.route));
            if(proof)++acceptedProofs;
            LegacyDecision decision=sessions.decide(
                parsed.route,proof,cookie,cookieLength,PEER_FIXTURE,nowMs(start),
                COOKIE_ENTROPY);
            if(decision.wouldIssueCookie)++issuedReadCookies;
            // Only the verified disposable Digest and independently reviewed
            // session decision allow *real* ArduinoJson decoding and applying
            // the UNMODIFIED FslessMetrics.cpp to this HOST process RAM.
            // The existing ingress collects <=384 body bytes before Digest:
            // this does NOT demonstrate pre-body authentication.
            bool parsedJson=false;
            LegacyTelemetryResult applied=LegacyTelemetryResult::InvalidNumbers;
            if(post && decision.decision==LegacySessionDecision::WouldAcceptMetricsPost &&
               parsed.bodyBytes>=16u && parsed.bodyBytes<=384u) {
                const auto* body=ingress.boundedMetricsBodyForTestOnly();
                if(body) {
                    JsonDocument payload;
                    const DeserializationError err=deserializeJson(
                        payload,reinterpret_cast<const char*>(body),parsed.bodyBytes);
                    if(!err) {
                        parsedJson=true;
                        hostSampleClock=nowMs(start);
                        String validationError;
                        if(FslessMetrics::apply(payload.as<JsonVariantConst>(),validationError))
                            applied=LegacyTelemetryResult::AcceptedIntoHostFixtureRamOnly;
                    }
                }
            }
            reply=NativeOtaLegacyResponsePreview::decide(
                parsed.route,decision,parsed.bodyBytes,parsedJson,applied);
            if(post && reply.status==200)++acceptedPostPreviews;
        } else {
            reply.status=403;
            reply.body="{\"error\":\"HOST_ONLY_INGRESS_REJECTED_NO_WRITER\"}";
        }
        if(reply.status!=200)++refusals;
        // Original firmware dashboard assets are served after fixture auth;
        // original FslessMetrics::describe() supplies real HOST RAM values.
        // No device, LCD, filesystem, firmware process or installed LINK.
        const bool sendRealPage=reply.status==200 &&
            parsed.route==Port80Plan::LegacyDashboardGet;
        const bool sendRealScript=reply.status==200 &&
            parsed.route==Port80Plan::LegacyJavascriptGet;
        std::string originalMetricsJson;
        if(reply.status==200 && parsed.route==Port80Plan::LegacyMetricsGet) {
            JsonDocument liveMetrics;
            hostSampleClock=nowMs(start);
            FslessMetrics::describe(liveMetrics);
            liveMetrics["host_fixture_only"]=true;
            char serialized[1024]{};
            const size_t written=serializeJson(liveMetrics,serialized,sizeof(serialized));
            if(written==0u || written>=sizeof(serialized)) {
                ::close(fd);::close(listener);return 2;
            }
            originalMetricsJson.assign(serialized,written);
        }
        const std::string body=sendRealPage?std::string(FslessWebUI::PAGE):
            (sendRealScript?std::string(FslessWebUI::SCRIPT):
             (originalMetricsJson.empty()?std::string(reply.body):originalMetricsJson));
        std::string header=std::string("HTTP/1.1 ")+std::to_string(reply.status)+
            " "+reason(reply.status)+"\r\nConnection: close\r\n"
            "Cache-Control: no-store\r\nX-Content-Type-Options: nosniff\r\n"
            "X-Shino-Host-Fixture: real-unmodified-metrics-host-ram-only\r\n"
            "Content-Type: "+reply.contentType+"\r\n";
        if(reply.wouldChallengeDigest)
            header+=std::string("WWW-Authenticate: Digest realm=\"")+REALM+
                "\", nonce=\""+NONCE+"\", algorithm=MD5, qop=\"auth\"\r\n";
        if(reply.wouldUseDashboardCsp)
            header+="Content-Security-Policy: default-src 'none'; style-src 'unsafe-inline'; "
                    "script-src 'self'; connect-src 'self'; base-uri 'none'; form-action 'none'\r\n";
        if(reply.wouldIssueCookie) {
            char token[33]{};
            // This token was created ONLY after independently verified proof,
            // never on an unverified or read-cookie-only POST.
            if(sessions.tokenForHostTestOnly(0u,token))
                header+=std::string("Set-Cookie: SHINO_READ_SESSION=")+token+
                    "; Path=/; Max-Age=7200; HttpOnly; SameSite=Strict\r\n";
        }
        header+="Content-Length: "+std::to_string(body.size())+"\r\n\r\n";
        const bool sent=sendFully(fd,header+body);
        ::close(fd);
        if(!sent){::close(listener);return 2;}
    }
    ::close(listener);
    // Deliberately output only counts. Never log password, Digest values,
    // nonce, cookie or telemetry body.
    std::cout<<"ACTUAL_FIXTURE_PROOFS "<<acceptedProofs
             <<" READ_COOKIES "<<issuedReadCookies
             <<" POST_PREVIEWS "<<acceptedPostPreviews
             <<" DENIED_OR_CHALLENGED "<<refusals
             <<" REAL_LEGACY_DISPATCH 0 DEVICE_WRITER 0 HOST_RAM_METRICS_ONLY"
             <<" M3HMAC_REVIEW_ONLY_NO_SCENE 1"<<std::endl;
    return 0;
}
