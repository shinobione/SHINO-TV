// SPDX-License-Identifier: GPL-3.0-or-later
// Actual pure C++ pump tested with a fake WiFiClient-compatible reader.
// Not an application upload, not a TCP listener and not an Updater test.
#include "boot/NativeOtaNetworkPump.h"
#include <algorithm>
#include <cstdint>
#include <iostream>
#include <vector>
using ShinoNativeOta::NativeOtaNetworkPump;
using ShinoNativeOta::NetworkPumpResult;
#define CHECK(x) do {if(!(x)){std::cerr<<"FAIL line "<<__LINE__<<": "<<#x<<"\n";return 1;}}while(0)

struct FakeClient {
    std::vector<uint8_t> source;
    size_t offset=0u;
    size_t maxPerAvailable=2048u;
    bool disconnectWhenDrained=true;
    bool deliberatelyDisconnected=false;
    bool failRead=false;
    bool failAvailable=false;
    unsigned readCalls=0u,stopCalls=0u;
    size_t highestRequest=0u;
    explicit FakeClient(size_t n) {
        source.resize(n);
        for(size_t i=0;i<n;++i) source[i]=static_cast<uint8_t>((i*39u+i/13u+11u)&255u);
    }
    int available() const {
        if(failAvailable)return -1;
        return static_cast<int>(std::min(maxPerAvailable,source.size()-offset));
    }
    int read(uint8_t* into,size_t n) {
        ++readCalls;
        highestRequest=std::max(highestRequest,n);
        if(failRead)return -1;
        const size_t count=std::min(n,std::min(maxPerAvailable,source.size()-offset));
        for(size_t i=0;i<count;++i)into[i]=source[offset+i];
        offset+=count;
        return static_cast<int>(count);
    }
    bool connected() const {
        return !deliberatelyDisconnected &&
            (!disconnectWhenDrained || offset!=source.size());
    }
    void stop() {++stopCalls;deliberatelyDisconnected=true;}
};
struct MockReview {
    size_t expected;
    size_t received=0u,largestChunk=0u;
    unsigned feedCalls=0u,finishCalls=0u,disconnectCalls=0u,tickCalls=0u;
    bool failFeed=false,failFinish=false,failTick=false;
    explicit MockReview(size_t n):expected(n){}
    bool tick(uint32_t) {++tickCalls;return !failTick;}
    bool feed(const uint8_t* bytes,size_t n,uint32_t) {
        ++feedCalls;largestChunk=std::max(largestChunk,n);
        if(!bytes || n==0u || n>4096u || failFeed || received+n>expected)return false;
        received+=n;
        return true;
    }
    bool finishAfterExactFraming(uint32_t) {
        ++finishCalls;
        return !failFinish && received==expected;
    }
    void disconnect(){++disconnectCalls;}
};
using Pump=NativeOtaNetworkPump<FakeClient,MockReview>;

int happy(size_t size,size_t fragmented) {
    FakeClient client(size);
    client.maxPerAvailable=fragmented;
    MockReview review(size);
    Pump pump;
    NetworkPumpResult status=NetworkPumpResult::Pending;
    for(unsigned i=0;i<1500u;++i) {
        status=pump.poll(client,review,i);
        if(status!=NetworkPumpResult::Pending)break;
    }
    CHECK(status==NetworkPumpResult::BytesReviewedOnly);
    CHECK(review.received==size && client.offset==size);
    CHECK(client.highestRequest<=Pump::kReadBytes);
    CHECK(client.stopCalls==1u);
    CHECK(review.finishCalls==1u && review.disconnectCalls==0u);
    CHECK(pump.poll(client,review,2000u)==NetworkPumpResult::BytesReviewedOnly);
    CHECK(client.stopCalls==1u && review.finishCalls==1u);
    return 0;
}
int wrongSizes() {
    {
        FakeClient c(999u);MockReview r(1000u);Pump p;
        CHECK(p.poll(c,r,1u)==NetworkPumpResult::Rejected);
        CHECK(r.finishCalls==1u && r.disconnectCalls==1u && c.stopCalls==1u);
        CHECK(p.poll(c,r,2u)==NetworkPumpResult::Rejected);
        CHECK(c.stopCalls==1u);
    }
    {
        FakeClient c(1001u);MockReview r(1000u);Pump p;
        CHECK(p.poll(c,r,1u)==NetworkPumpResult::Rejected);
        CHECK(r.finishCalls==0u && r.disconnectCalls==1u);
    }
    return 0;
}
int connectionAndTimeouts() {
    {
        FakeClient c(1000u);c.disconnectWhenDrained=false;
        MockReview r(1000u);Pump p;
        CHECK(p.poll(c,r,1u)==NetworkPumpResult::Pending);
        CHECK(r.received==1000u && r.finishCalls==0u); // Must await TCP FIN.
        r.failTick=true;
        CHECK(p.poll(c,r,15002u)==NetworkPumpResult::Rejected);
        CHECK(r.finishCalls==0u && c.stopCalls==1u);
    }
    {
        FakeClient c(1000u);c.maxPerAvailable=1u;
        MockReview r(1000u);Pump p;
        CHECK(p.poll(c,r,1u)==NetworkPumpResult::Pending);
        c.deliberatelyDisconnected=true; // FIN with unread queued bytes must drain.
        for(unsigned i=2u;i<1100u;++i) {
            auto state=p.poll(c,r,i);
            if(state!=NetworkPumpResult::Pending){
                CHECK(state==NetworkPumpResult::BytesReviewedOnly);
                CHECK(r.received==1000u);break;
            }
        }
        CHECK(p.result()==NetworkPumpResult::BytesReviewedOnly);
    }
    {
        FakeClient c(1000u);c.maxPerAvailable=1u;
        MockReview r(1000u);Pump p;
        CHECK(p.poll(c,r,1u)==NetworkPumpResult::Pending);
        p.cancel(c,r);
        CHECK(p.result()==NetworkPumpResult::Rejected);
        CHECK(c.stopCalls==1u && r.disconnectCalls==1u);
        p.cancel(c,r);CHECK(c.stopCalls==1u);
    }
    return 0;
}
int failureMatrix() {
    {
        FakeClient c(1000u);c.failRead=true;MockReview r(1000u);Pump p;
        CHECK(p.poll(c,r,1u)==NetworkPumpResult::Rejected);
        CHECK(c.stopCalls==1u && r.finishCalls==0u);
    }
    {
        FakeClient c(1000u);c.failAvailable=true;MockReview r(1000u);Pump p;
        CHECK(p.poll(c,r,1u)==NetworkPumpResult::Rejected);
        CHECK(c.stopCalls==1u && r.finishCalls==0u);
    }
    {
        FakeClient c(1000u);MockReview r(1000u);r.failFeed=true;Pump p;
        CHECK(p.poll(c,r,1u)==NetworkPumpResult::Rejected);
        CHECK(c.stopCalls==1u && r.finishCalls==0u);
    }
    {
        FakeClient c(1000u);MockReview r(1000u);r.failFinish=true;Pump p;
        CHECK(p.poll(c,r,1u)==NetworkPumpResult::Rejected);
        CHECK(c.stopCalls==1u && r.finishCalls==1u);
    }
    return 0;
}
int boundedCooperation() {
    FakeClient c(5000u);MockReview r(5000u);Pump p;
    CHECK(p.poll(c,r,1u)==NetworkPumpResult::Pending);
    CHECK(c.readCalls<=2u && c.highestRequest<=512u);
    CHECK(r.received<=1024u && c.stopCalls==0u);
    return 0;
}
int main() {
    for(size_t size : {size_t(600u),size_t(64260u),size_t(494404u)}) {
        for(size_t chunks : {size_t(1u),size_t(73u),size_t(512u),size_t(2048u)}) {
            if(size>1000u && chunks<73u)continue;
            if(size>100000u && chunks<512u)continue;
            if(happy(size,chunks))return 1;
        }
    }
    if(wrongSizes()||connectionAndTimeouts()||failureMatrix()||boundedCooperation())return 1;
    std::cout<<"PASS: cooperative bounded ESP8266-style WiFiClient reader; exact TCP FIN, "
                "short/extra, cancel, error, timeout and NO DEVICE WRITER.\n";
    return 0;
}
