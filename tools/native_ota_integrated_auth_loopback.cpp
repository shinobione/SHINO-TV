// SPDX-License-Identifier: GPL-3.0-or-later
// HOST-ONLY INTEGRATED NONWRITING HTTP FIXTURE. One 127.0.0.1 ephemeral
// listener; exact native shadow ingress -> actual incoming legacy MD5 Digest
// proof (OpenSSL with disposable fixtures) -> existing legacy session and
// response PREVIEW objects. Not ESP8266WebServer, production authentication,
// a general JSON decoder, live HTML/JS, LCD, OTA or device deployment.
// The pinned nonce and cookie entropy are deliberately deterministic HOST
// test vectors, NEVER a pattern for a real challenge/session issuer.
#include "boot/NativeOtaSingleIngressShadow.h"
#include "boot/NativeOtaLegacySessionReview.h"
#include "boot/NativeOtaLegacyResponsePreview.h"
#include "boot/FslessWebUI.h"
#include <openssl/evp.h>
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
namespace {
constexpr uint32_t PEER_FIXTURE=0xC0A80403u; // NOT the real accepted socket peer.
constexpr std::array<uint8_t,16> COOKIE_ENTROPY{{1,2,3,4,5,6,7,8,9,10,11,12,13,14,15,16}};
constexpr char USER[]="shino";
constexpr char PASSWORD[]="disposable-only-never-owner-password";
constexpr char REALM[]="SHINO-FirstBoot";
constexpr char NONCE[]="0123456789abcdef0123456789abcdef";
constexpr char GOOD_JSON[]=
 R"({"ok":true,"cpu_usage":22.5,"gpu_usage":34.5,"memory_used_gb":8.0,"memory_total_gb":16.0,"gpu_vram_mb":2048.0,"gpu_temp_c":56.0,"gpu_power":120.0,"gpu_available":true})";
constexpr char BAD_JSON[]=
 R"({"ok":true,"cpu_usage":999.0,"gpu_usage":34.5,"memory_used_gb":8.0,"memory_total_gb":16.0,"gpu_vram_mb":2048.0,"gpu_temp_c":56.0,"gpu_power":120.0,"gpu_available":true})";
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
    int acceptedProofs=0,issuedReadCookies=0,acceptedPostPreviews=0,refusals=0;
    const auto start=std::chrono::steady_clock::now();
    for(int count=0;count<requests;++count) {
        const int fd=::accept(listener,nullptr,nullptr);
        if(fd<0){::close(listener);return 2;}
        timeval timeout{};timeout.tv_sec=2;timeout.tv_usec=0;
        (void)::setsockopt(fd,SOL_SOCKET,SO_RCVTIMEO,&timeout,sizeof(timeout));
        NativeOtaSingleIngressShadow ingress(nowMs(start));
        bool denied=false,ready=false;
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
            bool good=false,bad=false;
            if(post && parsed.bodyBytes!=0u) {
                const auto* data=ingress.boundedMetricsBodyForTestOnly();
                if(data) {
                    const std::string body(reinterpret_cast<const char*>(data),
                                           parsed.bodyBytes);
                    good=body==GOOD_JSON;
                    bad=body==BAD_JSON;
                }
            }
            reply=NativeOtaLegacyResponsePreview::decide(
                parsed.route,decision,parsed.bodyBytes,good||bad,
                good?LegacyTelemetryResult::AcceptedIntoHostFixtureRamOnly:
                     LegacyTelemetryResult::InvalidNumbers);
            if(post && reply.status==200)++acceptedPostPreviews;
        } else {
            reply.status=403;
            reply.body="{\"error\":\"HOST_ONLY_INGRESS_REJECTED_NO_WRITER\"}";
        }
        if(reply.status!=200)++refusals;
        // On the HOST fixture only, use the byte-for-byte ORIGINAL firmware
        // PROGMEM assets instead of placeholder HTML/JS. All authorization
        // and request framing still happen BEFORE serving these GET assets.
        // This is NOT a runtime ESP8266WebServer handler and cannot mutate
        // RAM metrics, any filesystem or flash.
        const bool sendRealPage=reply.status==200 &&
            parsed.route==Port80Plan::LegacyDashboardGet;
        const bool sendRealScript=reply.status==200 &&
            parsed.route==Port80Plan::LegacyJavascriptGet;
        const std::string body=sendRealPage?std::string(FslessWebUI::PAGE):
            (sendRealScript?std::string(FslessWebUI::SCRIPT):std::string(reply.body));
        std::string header=std::string("HTTP/1.1 ")+std::to_string(reply.status)+
            " "+reason(reply.status)+"\r\nConnection: close\r\n"
            "Cache-Control: no-store\r\nX-Content-Type-Options: nosniff\r\n"
            "X-Shino-Host-Fixture: real-fixture-proof-no-real-handler-no-writer\r\n"
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
             <<" REAL_LEGACY_DISPATCH 0 DEVICE_WRITER 0 HOST_ONLY"<<std::endl;
    return 0;
}
