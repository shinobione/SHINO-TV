// SPDX-License-Identifier: GPL-3.0-or-later
// SINGLE HOST-ONLY TCP OWNER on literal 127.0.0.1:0. Every request reaches
// the SAME bounded parser. This intentionally has NO legacy route handler,
// no production authentication, no OTA review/flash writer or real device
// connectivity. Even recognized legacy requests receive HTTP 501, not 200.
#include "boot/NativeOtaSingleIngressShadow.h"
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

uint32_t nowMs(const std::chrono::steady_clock::time_point& start) {
    return static_cast<uint32_t>(std::chrono::duration_cast<std::chrono::milliseconds>(
        std::chrono::steady_clock::now()-start).count())+100u;
}
int main() {
    const int listener=::socket(AF_INET,SOCK_STREAM,0);
    if(listener<0)return 2;
    sockaddr_in addr{};
    addr.sin_family=AF_INET;
    addr.sin_addr.s_addr=htonl(INADDR_LOOPBACK);
    addr.sin_port=htons(0);
    if(::bind(listener,reinterpret_cast<const sockaddr*>(&addr),sizeof(addr))!=0 ||
       ::listen(listener,1)!=0){::close(listener);return 2;}
    socklen_t len=sizeof(addr);
    if(::getsockname(listener,reinterpret_cast<sockaddr*>(&addr),&len)!=0){
        ::close(listener);return 2;
    }
    std::cout<<"SHADOW_PORT "<<ntohs(addr.sin_port)<<std::endl;
    const int conn=::accept(listener,nullptr,nullptr);
    ::close(listener);
    if(conn<0)return 2;
    timeval timeout{};timeout.tv_sec=1;timeout.tv_usec=0;
    (void)::setsockopt(conn,SOL_SOCKET,SO_RCVTIMEO,&timeout,sizeof(timeout));

    const auto began=std::chrono::steady_clock::now();
    NativeOtaSingleIngressShadow ingress(100u);
    bool rejected=false;
    uint8_t buffer[512]{};
    for(;;) {
        const ssize_t n=::recv(conn,buffer,sizeof(buffer),0);
        const uint32_t now=nowMs(began);
        if(n>0) {
            if(!ingress.feed(buffer,static_cast<size_t>(n),now)) {
                rejected=true;break;
            }
        } else if(n==0) {
            break;
        } else if(errno==EINTR) {
            continue;
        } else if(errno==EAGAIN || errno==EWOULDBLOCK) {
            if(!ingress.tick(now)) {rejected=true;break;}
        } else {rejected=true;ingress.disconnect();break;}
    }
    if(!rejected && !ingress.finishOnExactTransportClose(nowMs(began)))
        rejected=true;
    if(rejected)ingress.disconnect();

    const auto r=ingress.result();
    const std::string text=rejected ? "SHADOW_REJECTED_NO_WRITER" :
                                    "SHADOW_CLASSIFIED_ONLY_NO_DISPATCH";
    const std::string response=std::string(rejected ?
        "HTTP/1.1 403 Forbidden\r\n" : "HTTP/1.1 501 Not Implemented\r\n")+
        "Content-Type: text/plain\r\nCache-Control: no-store\r\n"
        "Connection: close\r\nContent-Length: "+std::to_string(text.size())+
        "\r\n\r\n"+text;
    (void)::send(conn,response.data(),response.size(),MSG_NOSIGNAL);
    ::close(conn);
    std::cout<<"ROUTE "<<static_cast<int>(r.route)
             <<" PHASE "<<static_cast<int>(r.phase)
             <<" REFUSAL "<<static_cast<int>(r.refusal)
             <<" BODY_BYTES "<<r.bodyBytes
             <<" NO_AUTH_NO_LEGACY_HANDLER_NO_WRITER"<<std::endl;
    return rejected?1:0; // Unit tests expect 1 for rejected malformed/OTA input.
}
