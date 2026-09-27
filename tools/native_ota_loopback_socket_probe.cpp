// SPDX-License-Identifier: GPL-3.0-or-later
// POSIX HOST TEST ONLY: binds 127.0.0.1:0, receives exactly one upload via
// real TCP recv() fragments into NativeOtaStreamingReview, and responds with
// an informational offline result. NO ESP8266, Wi-Fi, OTA, Updater or flash.
#include "boot/NativeOtaStreamingReview.h"
#include <openssl/evp.h>
#include <arpa/inet.h>
#include <netinet/in.h>
#include <sys/socket.h>
#include <unistd.h>
#include <cerrno>
#include <chrono>
#include <cstdio>
#include <cstdint>
#include <iostream>
#include <string>
#include <vector>

using namespace ShinoNativeOta;
constexpr uint32_t PEER=0xC0A80403u; // simulated private-AP peer, not loopback locator.
constexpr std::array<uint8_t,16> TOKEN{{1,2,3,4,5,6,7,8,9,10,11,12,13,14,15,16}};
constexpr const char* NONCE="0123456789abcdef0123456789abcdef";
constexpr const char* OPAQUE="fedcba9876543210fedcba9876543210";
constexpr const char* USER="synthetic-loopback-owner";
constexpr const char* PASS="synthetic-fixture-password-not-owner-secret";

struct OpenSslSha final {
    EVP_MD_CTX* ctx=EVP_MD_CTX_new();
    OpenSslSha(){if(!ctx)throw 1;}
    OpenSslSha(const OpenSslSha&)=delete;
    OpenSslSha& operator=(const OpenSslSha&)=delete;
    ~OpenSslSha(){EVP_MD_CTX_free(ctx);}
    void begin(){if(EVP_DigestInit_ex(ctx,EVP_sha256(),nullptr)!=1)throw 1;}
    void add(const uint8_t* b,size_t n) {
        if(EVP_DigestUpdate(ctx,b,n)!=1)throw 1;
    }
    void end(uint8_t out[32]) {
        unsigned int n=0u;
        if(EVP_DigestFinal_ex(ctx,out,&n)!=1 || n!=32u)throw 1;
    }
    static bool hex(const char* b,size_t n,char out[65]) {
        unsigned char digest[32]{};unsigned int size=0u;
        EVP_MD_CTX* ctx=EVP_MD_CTX_new();
        if(!ctx)return false;
        const bool ok=EVP_DigestInit_ex(ctx,EVP_sha256(),nullptr)==1 &&
            EVP_DigestUpdate(ctx,b,n)==1 &&
            EVP_DigestFinal_ex(ctx,digest,&size)==1 && size==32u;
        EVP_MD_CTX_free(ctx);
        if(!ok)return false;
        const char* h="0123456789abcdef";
        for(size_t i=0;i<32u;++i) {
            out[2u*i]=h[digest[i]>>4u];out[2u*i+1u]=h[digest[i]&15u];
        }
        out[64]='\0';return true;
    }
};
bool hexDigest(const char* b,size_t n,char (&out)[65]) {
    return OpenSslSha::hex(b,n,out);
}
bool parseHash(const char* h,std::array<uint8_t,32>& out) {
    if(!h)return false;
    for(size_t i=0;i<32u;++i) {
        const char a=h[2*i],b=h[2*i+1];
        const auto digit=[](char c)->int {
            if(c>='0'&&c<='9')return c-'0';
            if(c>='a'&&c<='f')return c-'a'+10;
            return -1;
        };
        const int hi=digit(a),lo=digit(b);
        if(hi<0||lo<0)return false;
        out[i]=static_cast<uint8_t>(hi*16+lo);
    }
    return h[64]=='\0';
}
struct RamSink final {
    uint32_t expected=0u;std::vector<uint8_t> bytes{};bool aborted=false;
    bool beginForReview(uint32_t count){expected=count;return true;}
    bool acceptForReview(const uint8_t* data,size_t n) {
        if(n==0u || n>4096u || bytes.size()+n>expected)return false;
        bytes.insert(bytes.end(),data,data+n);return true;
    }
    bool completeForReview(){return !aborted && bytes.size()==expected;}
    void abortReview(){aborted=true;bytes.clear();}
};
uint32_t clockMs(const std::chrono::steady_clock::time_point& started) {
    return static_cast<uint32_t>(std::chrono::duration_cast<std::chrono::milliseconds>(
        std::chrono::steady_clock::now()-started).count())+100u;
}

int main(int argc,char** argv) {
    // User-selected fixture SHA256 is untrusted in production; host-only
    // selected manifest is explicitly "owner confirmed" for test.
    if(argc!=3)return 2;
    std::array<uint8_t,32> digest{};
    if(!parseHash(argv[1],digest))return 2;
    const unsigned long size=std::stoul(argv[2]);
    if(size<64260u || size>494404u)return 2;
    int server=::socket(AF_INET,SOCK_STREAM,0);
    if(server<0)return 2;
    sockaddr_in local{};
    local.sin_family=AF_INET;
    local.sin_addr.s_addr=htonl(INADDR_LOOPBACK); // 127.0.0.1 ONLY.
    local.sin_port=htons(0u);                    // OS-assigned ephemeral port.
    if(::bind(server,reinterpret_cast<const sockaddr*>(&local),sizeof(local))!=0 ||
       ::listen(server,1)!=0){::close(server);return 2;}
    socklen_t n=sizeof(local);
    if(::getsockname(server,reinterpret_cast<sockaddr*>(&local),&n)!=0){
        ::close(server);return 2;
    }
    std::cout<<"LOOPBACK_PORT "<<ntohs(local.sin_port)<<std::endl;
    int client=::accept(server,nullptr,nullptr);
    ::close(server);
    if(client<0)return 2;
    timeval timeout{};
    timeout.tv_sec=1;timeout.tv_usec=0;
    ::setsockopt(client,SOL_SOCKET,SO_RCVTIMEO,&timeout,sizeof(timeout));

    char ha1[65]{};
    const std::string hInput=std::string(USER)+":SHINO-OTA:"+PASS;
    if(!hexDigest(hInput.data(),hInput.size(),ha1))return 2;
    StrictOtaDigestGate<OpenSslSha> proof;
    ManualConsentGate consent;
    RamSink sink;
    NativeOtaStreamingReview<OpenSslSha,OpenSslSha,RamSink> stream(proof,consent,sink);
    const auto begin=std::chrono::steady_clock::now();
    bool ready=proof.challenge(PEER,RawOtaRequestKind::SignedTransport,NONCE,OPAQUE,100u)
        && consent.offer(true,true,true,PEER,IntendedPackage::SignedShino,
                         static_cast<uint32_t>(size),TOKEN,digest,100u)
        && stream.start(PEER,true,IntendedPackage::SignedShino,digest,
                        USER,ha1,100u);
    bool bad=!ready;
    uint8_t segment[1536]{};
    if(ready) {
        while(true) {
            const ssize_t got=::recv(client,segment,sizeof(segment),0);
            const uint32_t now=clockMs(begin);
            if(got>0) {
                if(!stream.feed(segment,static_cast<size_t>(got),now)) {
                    bad=true;break;
                }
            } else if(got==0) {
                break; // clean TCP write-half-close required by HOST FIXTURE.
            } else if(errno==EINTR) {
                continue;
            } else if(errno==EAGAIN || errno==EWOULDBLOCK) {
                if(!stream.tick(now)){bad=true;break;}
            } else {bad=true;break;}
        }
    }
    const bool accepted=!bad && stream.finishAfterExactFraming(clockMs(begin));
    if(!accepted)stream.disconnect();
    const char* answer=accepted
        ? "HTTP/1.1 200 OK\r\nConnection: close\r\nContent-Length: 29\r\n\r\nOFFLINE_REVIEW_ONLY_NO_FLASH_OK"
        : "HTTP/1.1 422 Unprocessable Content\r\nConnection: close\r\nContent-Length: 16\r\n\r\nREJECTED_NO_FLASH";
    // Content-Length is fixture response framing, never a firmware result.
    ::send(client,answer,std::strlen(answer),MSG_NOSIGNAL);
    ::close(client);
    std::cout<<"RESULT "<<(accepted?"OFFLINE_REVIEW_ONLY":"REJECTED")
             <<" RAM_BYTES "<<sink.bytes.size()
             <<" NO_DEVICE_NO_FLASH"<<std::endl;
    return accepted?0:1; // Rejections are EXPECTED for malicious fixtures.
}
