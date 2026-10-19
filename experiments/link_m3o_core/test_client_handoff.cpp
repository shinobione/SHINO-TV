// M3-O by-value reference lifecycle HOST test.
// Simulates Core CLIENT_IS_GIVEN ownership transition, not real lwIP transfer.
// Never reads a request body and never interprets this as an LCD ACK.
#include "M3OClientSlot.h"
#include <cassert>
#include <cstdio>
#include <memory>
#include <string>
namespace {
struct Counters {
    int stop=0,reads=0;
    bool connected=true;
};
struct FakeWiFiClient {
    std::shared_ptr<Counters> reference;
    FakeWiFiClient()=default;
    explicit FakeWiFiClient(std::shared_ptr<Counters> r):reference(r) {}
    explicit operator bool()const{return reference&&reference->connected;}
    void stop() {if(reference){++reference->stop;reference->connected=false;}}
    int read() {if(reference)++reference->reads;return -1;}
};
enum ClientFuture { CONTINUE, STOP, GIVEN };
template<typename Slot>
ClientFuture firstHook(Slot& slot,const char* method,const char* url,
                       FakeWiFiClient* borrowed,bool verifiedPeer,uint32_t now) {
    // HOST cannot establish actual WiFiClient IP identity.
    if(std::string(url)!="/api/v1/display/mode")return CONTINUE;
    if(std::string(method)!="POST"||!verifiedPeer||slot.busy())return STOP;
    return slot.take(borrowed,now)?GIVEN:STOP;
}
}
int main(){
    using ShinoM3O::ClientSlot; using ShinoM3O::Result;
    auto shared=std::make_shared<Counters>();
    FakeWiFiClient original(shared);
    ClientSlot<FakeWiFiClient> slot;
    assert(!slot.busy());
    assert(firstHook(slot,"GET","/api/v1/bridge/metrics",&original,true,10)==CONTINUE);
    assert(!slot.busy());
    assert(firstHook(slot,"POST","/api/v1/display/mode",&original,false,10)==STOP);
    assert(firstHook(slot,"GET","/api/v1/display/mode",&original,true,10)==STOP);
    assert(!slot.busy() && shared->stop==0);
    assert(firstHook(slot,"POST","/api/v1/display/mode",&original,true,11)==GIVEN);
    // Core releases currentClient reference rather than stopping on GIVEN.
    original=FakeWiFiClient();
    assert(slot.busy());
    assert(shared.use_count()>=2u); // local shared + copied owned slot
    assert(firstHook(slot,"POST","/api/v1/display/mode",&original,true,12)==STOP);
    assert(slot.denyAndRelease(12)==Result::Denied);
    assert(!slot.busy()&&shared->stop==1&&shared->reads==0);
    assert(slot.denyAndRelease(50)==Result::Idle);
    auto second=std::make_shared<Counters>();
    FakeWiFiClient fresh(second);
    assert(slot.take(&fresh,UINT32_MAX-100u));
    assert(slot.denyAndRelease(2000u)==Result::Expired);
    assert(second->stop==1&&second->reads==0);
    assert(!slot.take(nullptr,0));
    FakeWiFiClient null{};
    assert(!slot.take(&null,0));
    auto third=std::make_shared<Counters>();
    {
        ClientSlot<FakeWiFiClient> owner;
        FakeWiFiClient c(third);
        assert(owner.take(&c,3));
        c=FakeWiFiClient();
    }
    assert(third->stop==1&&third->reads==0);
    std::puts("M3O_CLIENT_IS_GIVEN_HOST_SLOT_LIFECYCLE_PASS");
}
