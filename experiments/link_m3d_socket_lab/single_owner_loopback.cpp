// M3-D: loopback-only, one-listener, actual POSIX TCP read-order experiment.
// NOT an ESP8266 HTTP adapter. NOT a backend for SHINO LINK. NOT deployable.
// Legacy routes deliberately return 503, not fake successful telemetry.
// A test-only 01..20 HMAC key is public and must never be provisioned.
// Single connection at a time, bounded header/body deadlines, no threads.
#include "../link_m3c_crypto/M3CAuthenticatedIngress.h"
#include <openssl/evp.h>
#include <openssl/hmac.h>
#include <openssl/sha.h>
#include <sys/socket.h>
#include <netinet/in.h>
#include <poll.h>
#include <unistd.h>
#include <cerrno>
#include <chrono>
#include <cstdint>
#include <cstdlib>
#include <cstring>
#include <iostream>
#include <string>

namespace {
using Clock=std::chrono::steady_clock;
using namespace ShinoM3C;

constexpr uint32_t FIRST_LINE_MS=1000u;
constexpr uint32_t HEADER_MS=1000u;
constexpr uint32_t BODY_MS=2000u;
constexpr size_t FIRST_LINE_CAP=128u;
constexpr const char* VIRTUAL_HOST="192.168.1.46";
constexpr const char* DEVICE="1234567890abcdef";
constexpr const char* BOOT="1234567890abcdef1234567890abcdef";
const uint8_t PUBLIC_LAB_KEY[32] = {
  1,2,3,4,5,6,7,8,9,10,11,12,13,14,15,16,
  17,18,19,20,21,22,23,24,25,26,27,28,29,30,31,32
};
const Identity LAB_ID{VIRTUAL_HOST,DEVICE,BOOT};

struct RealCrypto {
    static bool hmac(const uint8_t* key,const uint8_t* bytes,size_t n,
                     uint8_t out[32]) {
        unsigned written=0;
        return HMAC(EVP_sha256(),key,32,bytes,n,out,&written)!=nullptr
            && written==32u;
    }
    static bool sha256(const uint8_t* bytes,size_t n,uint8_t out[32]) {
        return SHA256(bytes,n,out)!=nullptr;
    }
};

uint32_t elapsed(Clock::time_point start) {
    return static_cast<uint32_t>(std::chrono::duration_cast<
        std::chrono::milliseconds>(Clock::now()-start).count());
}
enum class Read { Byte, Fin, Timeout, Error };

Read one(int fd,uint32_t deadlineMs,Clock::time_point start,uint8_t& result) {
    while(true) {
        const uint32_t ms=elapsed(start);
        if(ms >= deadlineMs) return Read::Timeout;
        const int remaining=static_cast<int>(deadlineMs-ms);
        pollfd request{fd,POLLIN,0};
        const int ready=poll(&request,1,remaining);
        if(ready==0) return Read::Timeout;
        if(ready<0) {
            if(errno==EINTR) continue;
            return Read::Error;
        }
        if(request.revents & (POLLERR|POLLNVAL)) return Read::Error;
        // POLLHUP can coexist with POLLIN while data is buffered.
        const ssize_t n=recv(fd,&result,1,0);
        if(n==1) return Read::Byte;
        if(n==0) return Read::Fin;
        if(errno==EINTR||errno==EAGAIN) continue;
        return Read::Error;
    }
}

void respond(int fd,int status,const char* reason,const char* body) {
    // Keep the lab response tiny and connection-closing.
    const std::string response=
        std::string("HTTP/1.1 ")+std::to_string(status)+" "+reason+"\r\n"
        +"Content-Type: application/json\r\n"
        +"Content-Length: "+std::to_string(std::strlen(body))+"\r\n"
        +"Connection: close\r\n\r\n"+body;
    size_t at=0u;
    while(at<response.size()) {
        const ssize_t sent=send(fd,response.data()+at,response.size()-at,
                                MSG_NOSIGNAL);
        if(sent<=0) break;
        at+=static_cast<size_t>(sent);
    }
}
void reject(int fd,int status=403) {
    respond(fd,status,status==408?"Request Timeout":"Forbidden",
            "{\"lab\":\"REJECTED_NO_MUTATION\"}");
}

bool firstLine(int fd,std::string& line,Clock::time_point origin) {
    // Exact-size first-line cap before allocation/reading arbitrary headers.
    line.clear();
    line.reserve(FIRST_LINE_CAP);
    uint8_t byte=0;
    for(size_t i=0u;i<FIRST_LINE_CAP;++i) {
        if(one(fd,FIRST_LINE_MS,origin,byte)!=Read::Byte) return false;
        if(byte=='\0'||byte=='\n'&&(i==0u||line.back()!='\r')) return false;
        line.push_back(static_cast<char>(byte));
        if(line.size()>=2u&&line.substr(line.size()-2u)=="\r\n")
            return true;
    }
    return false;
}

bool isLegacyRead(const std::string& target) {
    return target=="GET /status HTTP/1.1\r\n"
        || target=="GET /api/v1/m9/normal/status HTTP/1.1\r\n"
        || target=="GET /api/v1/m9/normal/resources HTTP/1.1\r\n"
        || target=="GET /api/v1/bridge/metrics HTTP/1.1\r\n"
        || target=="POST /api/v1/bridge/metrics HTTP/1.1\r\n";
}

void oneConnection(int fd,OfflineCasLedger& ledger) {
    const Clock::time_point first=Clock::now();
    std::string line;
    if(!firstLine(fd,line,first)) {reject(fd,408);return;}
    if(line!="POST /api/v1/display/mode HTTP/1.1\r\n") {
        if(isLegacyRead(line)) {
            // Explicit FAIL-CLOSED: no real legacy service is invoked or cloned.
            respond(fd,503,"Service Unavailable",
                    "{\"lab\":\"LEGACY_PARITY_NOT_IMPLEMENTED\"}");
        } else {
            respond(fd,404,"Not Found","{\"lab\":\"CLOSED_ROUTE\"}");
        }
        return;
    }
    Gate gate(LAB_ID,ledger.revision());
    const Clock::time_point started=Clock::now();
    for(unsigned char ch:line)
        if(gate.headerByte<RealCrypto>(static_cast<char>(ch),elapsed(started),
                                       PUBLIC_LAB_KEY)==Phase::Reject) {
            reject(fd);return;
        }
    uint8_t byte=0;
    while(gate.phase()==Phase::Header) {
        const Read r=one(fd,HEADER_MS,started,byte);
        if(r!=Read::Byte) {reject(fd,r==Read::Timeout?408:403);return;}
        if(gate.headerByte<RealCrypto>(static_cast<char>(byte),elapsed(started),
                                       PUBLIC_LAB_KEY)==Phase::Reject) {
            reject(fd);return;
        }
    }
    // No socket body byte has been read before HMAC verification.
    if(gate.phase()!=Phase::AuthenticatedHeader) {reject(fd);return;}

    const Clock::time_point bodyStart=Clock::now();
    while(gate.phase()==Phase::AuthenticatedHeader) {
        const Read r=one(fd,BODY_MS,bodyStart,byte);
        if(r!=Read::Byte) {reject(fd,r==Read::Timeout?408:403);return;}
        if(gate.bodyByte<RealCrypto>(byte,elapsed(bodyStart))==Phase::Reject) {
            reject(fd);return;
        }
    }
    if(gate.phase()!=Phase::BodyDigestMatched) {reject(fd);return;}

    // Dedicated sender must half-close its write side. It may still receive
    // HTTP response normally. Detect and refuse *all* trailing bytes before
    // FIN. A conventional HTTP/1.1 client waiting for a response without
    // half-close times out and never commits. No keep-alive/pipelining.
    const Read remainder=one(fd,BODY_MS,bodyStart,byte);
    if(remainder!=Read::Fin) {
        reject(fd,remainder==Read::Timeout?408:403);
        return;
    }
    if(gate.finishAfterExactFraming(true,0u,elapsed(bodyStart))!=Phase::VerifiedFrame) {
        reject(fd);return;
    }
    if(!ledger.acceptVerifiedForLab(gate)) {
        respond(fd,409,"Conflict","{\"lab\":\"LAB_CAS_OR_REPLAY_REJECTED\"}");
        return;
    }
    // 202 NOT an ACK claiming that the display changed!
    respond(fd,202,"Accepted",
            "{\"lab\":\"CRYPTO_VERIFIED_BUT_NOT_APPLIED\",\"applied\":false}");
}
}

int main(int argc,char** argv) {
    if(argc!=2) return 2;
    char* end=nullptr;
    const long count=std::strtol(argv[1],&end,10);
    if(!end||*end||count<1||count>64) return 2;
    const int listener=socket(AF_INET,SOCK_STREAM,0);
    if(listener<0) return 3;
    const int opt=1;
    setsockopt(listener,SOL_SOCKET,SO_REUSEADDR,&opt,sizeof(opt));
    sockaddr_in address{};
    address.sin_family=AF_INET;
    address.sin_addr.s_addr=htonl(INADDR_LOOPBACK);
    address.sin_port=0;
    if(bind(listener,reinterpret_cast<const sockaddr*>(&address),sizeof(address))!=0
        ||listen(listener,4)!=0) {close(listener);return 4;}
    socklen_t n=sizeof(address);
    if(getsockname(listener,reinterpret_cast<sockaddr*>(&address),&n)!=0) {
        close(listener);return 5;
    }
    std::cout<<"M3D_LOOPBACK_PORT="<<ntohs(address.sin_port)<<std::endl;
    OfflineCasLedger ledger;
    for(long i=0;i<count;++i) {
        const int client=accept(listener,nullptr,nullptr);
        if(client<0) {close(listener);return 6;}
        oneConnection(client,ledger);
        shutdown(client,SHUT_RDWR);
        close(client);
    }
    close(listener);
    std::cout<<"M3D_LOOPBACK_SINGLE_LISTENER_DONE="<<count<<std::endl;
    return 0;
}
