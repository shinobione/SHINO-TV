// SPDX-License-Identifier: GPL-3.0-or-later
// HOST LOOPBACK ONLY: prove one bounded HTTP message can be answered without
// requiring TCP FIN. It intentionally returns only 501/403, with no Digest,
// no real legacy handler, no OTA writer, no device sockets or credentials.
#include "boot/NativeOtaSingleIngressShadow.h"
#include <arpa/inet.h>
#include <netinet/in.h>
#include <sys/socket.h>
#include <unistd.h>
#include <cerrno>
#include <chrono>
#include <cstdint>
#include <iostream>
#include <string>
using namespace ShinoNativeOta;

static uint32_t nowMs(const std::chrono::steady_clock::time_point& start) {
    return 100u+static_cast<uint32_t>(std::chrono::duration_cast<std::chrono::milliseconds>(
        std::chrono::steady_clock::now()-start).count());
}
static bool sendAll(int fd,const std::string& response) {
    size_t offset=0u;
    while(offset<response.size()) {
        const ssize_t n=::send(fd,response.data()+offset,response.size()-offset,MSG_NOSIGNAL);
        if(n<=0)return false;
        offset+=static_cast<size_t>(n);
    }
    return true;
}
int main() {
    const int listener=::socket(AF_INET,SOCK_STREAM,0);
    if(listener<0)return 2;
    sockaddr_in addr{};
    addr.sin_family=AF_INET;
    addr.sin_addr.s_addr=htonl(INADDR_LOOPBACK);
    addr.sin_port=htons(0);
    if(::bind(listener,reinterpret_cast<const sockaddr*>(&addr),sizeof(addr))!=0 ||
       ::listen(listener,1)!=0) {::close(listener);return 2;}
    socklen_t len=sizeof(addr);
    if(::getsockname(listener,reinterpret_cast<sockaddr*>(&addr),&len)!=0) {
        ::close(listener);return 2;
    }
    std::cout<<"MESSAGE_BOUNDARY_PORT "<<ntohs(addr.sin_port)<<std::endl;
    const int peer=::accept(listener,nullptr,nullptr);
    ::close(listener);
    if(peer<0)return 2;
    timeval timeout{};timeout.tv_sec=1;timeout.tv_usec=0;
    (void)::setsockopt(peer,SOL_SOCKET,SO_RCVTIMEO,&timeout,sizeof(timeout));
    NativeOtaSingleIngressShadow ingress(100u);
    const auto started=std::chrono::steady_clock::now();
    bool rejected=false,ready=false;
    uint8_t buffer[512]{};
    for(;;) {
        const ssize_t n=::recv(peer,buffer,sizeof(buffer),0);
        const uint32_t now=nowMs(started);
        if(n>0) {
            if(!ingress.feed(buffer,static_cast<size_t>(n),now)) {
                rejected=true;break;
            }
            if(ingress.result().phase==SingleIngressReviewPhase::AwaitExactClose) {
                // An exact HTTP/1.1 message is complete even when the sender
                // has not performed TCP shutdown(SHUT_WR).
                ready=true;break;
            }
        } else if(n==0) {
            // EOF before exact body completion must not succeed.
            ready=ingress.result().phase==SingleIngressReviewPhase::AwaitExactClose;
            if(!ready)rejected=true;
            break;
        } else if(errno==EINTR)continue;
        else if(errno==EAGAIN || errno==EWOULDBLOCK) {
            if(!ingress.tick(now)){rejected=true;break;}
        } else {rejected=true;break;}
    }
    if(!rejected && (!ready ||
       !ingress.finishOnExactMessageBoundaryForHostReviewOnly(nowMs(started))))
        rejected=true;
    if(rejected)ingress.disconnect();

    // One response and then close. Pipelined bytes cannot be dispatched as
    // subsequent requests; extra bytes within the same feed() are rejected.
    const std::string body=rejected?"MESSAGE_BOUNDARY_REJECTED_NO_WRITER":
                                    "MESSAGE_BOUNDARY_REVIEW_ONLY_NO_DISPATCH";
    const std::string wire=std::string(rejected?
        "HTTP/1.1 403 Forbidden\r\n":"HTTP/1.1 501 Not Implemented\r\n")+
        "Connection: close\r\nCache-Control: no-store\r\n"
        "X-Shino-Host-Fixture: no-auth-no-device-no-writer\r\n"
        "Content-Type: text/plain\r\nContent-Length: "+
        std::to_string(body.size())+"\r\n\r\n"+body;
    const bool sent=sendAll(peer,wire);
    ::close(peer);
    std::cout<<"MESSAGE_READY "<<ready<<" REJECTED "<<rejected
             <<" LEGACY_DISPATCH 0 WRITER 0 HTTP_ONLY_LOOPBACK"<<std::endl;
    return sent?0:2;
}
