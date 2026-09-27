// SPDX-License-Identifier: GPL-3.0-or-later
// HOST-ONLY bounded TWO-SLOT TCP fairness fixture, 127.0.0.1:ephemeral.
// ONE listener and one nonblocking poll loop; ONE <=256-byte read per slot
// per turn, max two ingress parsers, immediate 503 when both are busy.
// No authentication, real handlers, HTML, metric mutation, OTA, device,
// filesystem, production listener, firmware writer or flash.
// The host uses unique_ptr to manage fixture slots; this is NOT a measured
// ESP8266 heap budget or an implementation of the production HTTP server.
#include "boot/NativeOtaSingleIngressShadow.h"
#include <arpa/inet.h>
#include <netinet/in.h>
#include <poll.h>
#include <sys/socket.h>
#include <unistd.h>
#include <array>
#include <cerrno>
#include <chrono>
#include <cstdint>
#include <cstdlib>
#include <iostream>
#include <memory>
#include <string>
using namespace ShinoNativeOta;
namespace {
constexpr size_t kSlots=2u;
constexpr size_t kReadPerSlotPerTurn=256u;
constexpr int kPollMs=50;
struct Slot {
    int fd=-1;
    std::unique_ptr<NativeOtaSingleIngressShadow> parser{};
};
uint32_t ms(const std::chrono::steady_clock::time_point& t) {
    return 100u+static_cast<uint32_t>(
        std::chrono::duration_cast<std::chrono::milliseconds>(
            std::chrono::steady_clock::now()-t).count());
}
bool sendAll(int fd,const std::string& value) {
    size_t at=0u;
    while(at<value.size()) {
        const ssize_t n=::send(fd,value.data()+at,value.size()-at,MSG_NOSIGNAL);
        if(n<=0)return false;
        at+=static_cast<size_t>(n);
    }
    return true;
}
void replyAndClose(int fd,int code) {
    const char* phrase=code==501?"Not Implemented":
                       code==503?"Service Unavailable":"Forbidden";
    const char* body=code==501?"HOST_CONCURRENT_REVIEW_ONLY_NO_DISPATCH":
                     code==503?"HOST_CONCURRENT_BUSY_NO_WRITER":
                               "HOST_CONCURRENT_DENIED_NO_WRITER";
    const std::string b(body);
    const std::string header="HTTP/1.1 "+std::to_string(code)+" "+phrase+
        "\r\nConnection: close\r\nCache-Control: no-store\r\n"
        "X-Shino-Host-Fixture: two-slot-no-auth-no-device-no-writer\r\n"
        "Content-Type: text/plain\r\nContent-Length: "+
        std::to_string(b.size())+"\r\n\r\n";
    (void)sendAll(fd,header+b);
    ::close(fd);
}
size_t active(const std::array<Slot,kSlots>& slots) {
    size_t count=0u;
    for(const auto& s:slots)if(s.fd>=0)++count;
    return count;
}
void closeSlot(std::array<Slot,kSlots>& slots,size_t i,int code,
               int& accepted, int& denied) {
    if(code==501)++accepted;
    else ++denied;
    replyAndClose(slots[i].fd,code);
    slots[i].fd=-1;
    slots[i].parser.reset();
    std::cout<<"CLOSED_SLOT "<<i<<" RESULT "<<code<<" ACTIVE "<<active(slots)
             <<std::endl;
}
} // namespace

int main(int argc,char** argv) {
    if(argc!=2)return 2;
    const int expected=std::atoi(argv[1]);
    if(expected<1||expected>12)return 2;
    const int listener=::socket(AF_INET,SOCK_STREAM,0);
    if(listener<0)return 2;
    sockaddr_in address{};
    address.sin_family=AF_INET;
    address.sin_addr.s_addr=htonl(INADDR_LOOPBACK);
    address.sin_port=htons(0);
    if(::bind(listener,reinterpret_cast<const sockaddr*>(&address),
              sizeof(address))!=0 || ::listen(listener,4)!=0) {
        ::close(listener);return 2;
    }
    socklen_t addrLen=sizeof(address);
    if(::getsockname(listener,reinterpret_cast<sockaddr*>(&address),&addrLen)!=0) {
        ::close(listener);return 2;
    }
    std::cout<<"HOST_FAIRNESS_PORT "<<ntohs(address.sin_port)<<std::endl;
    const auto started=std::chrono::steady_clock::now();
    std::array<Slot,kSlots> slots{};
    int seen=0,busy=0,accepted=0,denied=0;
    size_t peakActive=0u;
    for(;;) {
        if(seen>=expected && active(slots)==0u)break;
        if(ms(started)>20000u) {
            for(auto& s:slots)if(s.fd>=0){::close(s.fd);s.fd=-1;s.parser.reset();}
            ::close(listener);return 3; // HOST fixture watchdog, not a device claim
        }
        // Each active parser gets a deadline check, including an idle socket
        // with no POLLIN. Slow clients cannot reset the ABSOLUTE body limit.
        for(size_t i=0u;i<kSlots;++i) {
            if(slots[i].fd>=0 && !slots[i].parser->tick(ms(started)))
                closeSlot(slots,i,403,accepted,denied);
        }
        std::array<pollfd,1u+kSlots> polls{};
        polls[0].fd=seen<expected?listener:-1;
        polls[0].events=POLLIN;
        for(size_t i=0u;i<kSlots;++i) {
            polls[i+1u].fd=slots[i].fd;
            polls[i+1u].events=POLLIN;
        }
        const int got=::poll(polls.data(),static_cast<nfds_t>(polls.size()),kPollMs);
        if(got<0){if(errno==EINTR)continue;::close(listener);return 2;}
        if(polls[0].fd>=0 && (polls[0].revents&POLLIN)) {
            const int fd=::accept(listener,nullptr,nullptr);
            if(fd<0){::close(listener);return 2;}
            ++seen;
            size_t index=0u;
            while(index<kSlots && slots[index].fd>=0)++index;
            if(index==kSlots) {
                ++busy;
                replyAndClose(fd,503);
                std::cout<<"REFUSED_BUSY ACTIVE "<<active(slots)<<std::endl;
            } else {
                slots[index].fd=fd;
                slots[index].parser.reset(new NativeOtaSingleIngressShadow(ms(started)));
                if(active(slots)>peakActive)peakActive=active(slots);
                std::cout<<"ADMITTED_SLOT "<<index<<" ACTIVE "<<active(slots)
                         <<std::endl;
            }
        }
        for(size_t i=0u;i<kSlots;++i) {
            // Don't use an event computed for a different accepted socket:
            // a slot may have changed since poll() above.
            if(polls[i+1u].fd<0 || polls[i+1u].fd!=slots[i].fd)continue;
            if(slots[i].fd<0 || !(polls[i+1u].revents&(POLLIN|POLLHUP|POLLERR)))continue;
            std::array<uint8_t,kReadPerSlotPerTurn> chunk{};
            const ssize_t n=::recv(slots[i].fd,chunk.data(),chunk.size(),0);
            if(n>0) {
                if(!slots[i].parser->feed(chunk.data(),static_cast<size_t>(n),
                                          ms(started))) {
                    closeSlot(slots,i,403,accepted,denied);
                } else if(slots[i].parser->result().phase==
                          SingleIngressReviewPhase::AwaitExactClose) {
                    const bool complete=slots[i].parser->
                        finishOnExactMessageBoundaryForHostReviewOnly(ms(started));
                    closeSlot(slots,i,complete?501:403,accepted,denied);
                }
            } else if(n==0) {
                // Only a COMPLETE framed message can be accepted at EOF.
                const bool complete=slots[i].parser->result().phase==
                   SingleIngressReviewPhase::AwaitExactClose &&
                   slots[i].parser->
                       finishOnExactMessageBoundaryForHostReviewOnly(ms(started));
                if(!complete)slots[i].parser->disconnect();
                closeSlot(slots,i,complete?501:403,accepted,denied);
            } else if(errno!=EINTR && errno!=EAGAIN && errno!=EWOULDBLOCK) {
                slots[i].parser->disconnect();
                closeSlot(slots,i,403,accepted,denied);
            }
        }
    }
    ::close(listener);
    std::cout<<"FAIRNESS_SUMMARY ACCEPTED "<<accepted<<" DENIED "<<denied
             <<" BUSY "<<busy<<" PEAK_SLOTS "<<peakActive
             <<" ACTIVE "<<active(slots)
             <<" DISPATCH 0 WRITER 0 DEVICE 0"<<std::endl;
    return 0;
}
