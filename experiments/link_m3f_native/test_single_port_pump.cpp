// M3-F: HOST fake WiFiClient/WiFiServer with the SAME transport API as the
// ESP8266 3.1.2 compiler fixture. No network socket, no filesystem writes.
#include "M3FSinglePortPump.h"
#include <openssl/evp.h>
#include <openssl/hmac.h>
#include "../link_m3l_incremental/M3LHostOpenSslFragments.h"
#include <openssl/sha.h>
#include <cassert>
#include <cstdlib>
#include <cstdint>
#include <deque>
#include <iostream>
#include <memory>
#include <string>
using namespace ShinoM3F;

constexpr const char* HOST="192.168.1.46";
constexpr const char* DEVICE="1234567890abcdef";
constexpr const char* BOOT="1234567890abcdef1234567890abcdef";
constexpr const char* TX1="00000000000000000000000000000001";
constexpr const char* TX2="00000000000000000000000000000002";
const ShinoM3C::Identity ID{HOST,DEVICE,BOOT};
const uint8_t PUBLIC_KEY[32] = {
  1,2,3,4,5,6,7,8,9,10,11,12,13,14,15,16,
  17,18,19,20,21,22,23,24,25,26,27,28,29,30,31,32
};
struct Crypto {
    static bool hmacFragments(const uint8_t key[32],
                               const char* const* parts,size_t count,
                               uint8_t out[32]) {
        return ShinoM3LHost::hmacFragments(key,parts,count,out);
    }
    static bool hmac(const uint8_t* key,const uint8_t* in,
                     size_t n,uint8_t out[32]){
        unsigned produced=0;
        return HMAC(EVP_sha256(),key,32,in,n,out,&produced)!=nullptr
            && produced==32u;
    }
    static bool sha256(const uint8_t* in,size_t n,uint8_t out[32]){
        return SHA256(in,n,out)!=nullptr;
    }
};
static std::string hex(const uint8_t* in,size_t n){
    const char* alphabet="0123456789abcdef";
    std::string s(n*2u,'0');
    for(size_t i=0u;i<n;++i){
        s[i*2u]=alphabet[in[i]>>4];
        s[i*2u+1u]=alphabet[in[i]&15u];
    }
    return s;
}
static std::string packet(unsigned revision=0u,const char* tx=TX1,
                          const char* mode="MUSIC"){
    const std::string payload=std::string("{\"boot\":\"")+BOOT+
        "\",\"device\":\""+DEVICE+"\",\"mode\":\""+mode+
        "\",\"protocol\":\"shino-display-control-1\",\"revision\":"+
        std::to_string(revision)+",\"tx\":\""+tx+"\"}";
    uint8_t hash[32]{},mac[32]{};
    assert(Crypto::sha256(reinterpret_cast<const uint8_t*>(payload.data()),
                          payload.size(),hash));
    const std::string hashHex=hex(hash,32u);
    const std::string signedText=std::string("SHINO-M3-CONTROL-1\nPOST\n")
        +"/api/v1/display/mode\n"+HOST+"\n"+DEVICE+"\n"+BOOT+"\n"
        +std::to_string(revision)+"\n"+mode+"\n"+tx+"\n"
        +std::to_string(payload.size())+"\n"+hashHex;
    assert(Crypto::hmac(PUBLIC_KEY,
       reinterpret_cast<const uint8_t*>(signedText.data()),
       signedText.size(),mac));
    return std::string("POST /api/v1/display/mode HTTP/1.1\r\n")
        +"Host: "+HOST+"\r\nContent-Type: application/json\r\n"
        +"Content-Length: "+std::to_string(payload.size())+"\r\n"
        +"Connection: close\r\n"
        +"X-Shino-Device: "+DEVICE+"\r\n"
        +"X-Shino-Boot: "+BOOT+"\r\n"
        +"X-Shino-Revision: "+std::to_string(revision)+"\r\n"
        +"X-Shino-Mode: "+mode+"\r\n"
        +"X-Shino-Tx: "+tx+"\r\n"
        +"X-Shino-Body-Sha256: "+hashHex+"\r\n"
        +"X-Shino-Proof: "+hex(mac,32u)+"\r\n\r\n"+payload;
}
struct Channel{
    std::string request,response;
    size_t index=0u;
    size_t bytesRead=0u;
    bool halfClosed=true,stopped=false,paused=false;
};
struct Client {
    std::shared_ptr<Channel> c;
    explicit operator bool() const {return bool(c);}
    int available() const {
        if(!c || c->stopped || c->paused)return 0;
        return static_cast<int>(c->request.size()-c->index);
    }
    bool connected() const {
        return c && !c->stopped &&
            (c->index<c->request.size() || !c->halfClosed);
    }
    int read(){
        if(available()<=0)return -1;
        c->bytesRead++;
        return static_cast<uint8_t>(c->request[c->index++]);
    }
    size_t write(const uint8_t* data,size_t n){
        if(!c || c->stopped)return 0u;
        c->response.append(reinterpret_cast<const char*>(data),n);
        return n;
    }
    void stop(){if(c)c->stopped=true;}
};
struct Server{
    std::deque<Client> queued;
    int acceptCalls=0;
    Client accept(){
        ++acceptCalls;
        if(queued.empty())return {};
        Client n=queued.front();queued.pop_front();return n;
    }
    std::shared_ptr<Channel> add(std::string request,bool fin=true){
        auto c=std::make_shared<Channel>();
        c->request=std::move(request);c->halfClosed=fin;
        queued.push_back(Client{c});
        return c;
    }
};
using Pump=SinglePortPump<Server,Client,Crypto>;

static Step runOne(Pump& pump,Server& server,std::shared_ptr<Channel> c,
                   uint32_t& clock){
    const int existingCalls=server.acceptCalls;
    for(int i=0;i<800;++i) {
        const size_t before=c->bytesRead;
        const Step step=pump.poll(clock);
        assert(c->bytesRead-before<=Pump::kMaxReadsPerPoll);
        // The owner scheduler gets a chance every single poll.
        clock+=5u;
        if(step!=Step::Pending && step!=Step::Idle)return step;
    }
    std::cerr<<"pump hung after "<<server.acceptCalls-existingCalls
             <<" accepts\n";
    std::abort();
}
static void testValidReplayAndCas(){
    Server server;
    Pump pump(server,ID,PUBLIC_KEY);
    uint32_t now=0u;
    auto a=server.add(packet());
    assert(runOne(pump,server,a,now)==Step::CryptoReviewedOnly);
    assert(a->response.find("202 Accepted")!=std::string::npos);
    assert(a->response.find("\"applied\":false")!=std::string::npos);
    assert(a->bytesRead==a->request.size());
    assert(!pump.busy());

    auto replay=server.add(packet());
    assert(runOne(pump,server,replay,now)==Step::Rejected);
    assert(replay->response.find("403 Forbidden")!=std::string::npos);
    assert(replay->bytesRead<replay->request.size()); // no body reads.

    auto b=server.add(packet(1u,TX2,"MONITORING"));
    assert(runOne(pump,server,b,now)==Step::CryptoReviewedOnly);
    assert(b->response.find("202 Accepted")!=std::string::npos);
    assert(pump.connectionCount()==3u);
}
static void testNoFinAndUnreadTrailingBytes(){
    Server server;
    Pump pump(server,ID,PUBLIC_KEY);
    uint32_t now=0u;
    auto withoutFin=server.add(packet(),false);
    assert(runOne(pump,server,withoutFin,now)==Step::Rejected);
    assert(withoutFin->response.find("408 Request Timeout")!=std::string::npos);
    assert(now<4000u);
    auto extra=server.add(packet()+"NEXT");
    assert(runOne(pump,server,extra,now)==Step::Rejected);
    assert(extra->response.find("403 Forbidden")!=std::string::npos);
    auto truncated=packet();truncated.pop_back();
    auto shortBody=server.add(truncated);
    assert(runOne(pump,server,shortBody,now)==Step::Rejected);
    assert(shortBody->response.find("403 Forbidden")!=std::string::npos);
}
static void testHeaderRejectionPrebodyAndLegacyHold(){
    Server server;
    Pump pump(server,ID,PUBLIC_KEY);
    uint32_t now=0u;
    std::string forged=packet();
    const auto at=forged.find("X-Shino-Mode: MUSIC");
    assert(at!=std::string::npos);
    forged.replace(at,std::strlen("X-Shino-Mode: MUSIC"),
                   "X-Shino-Mode: AUTO");
    auto bad=server.add(forged);
    assert(runOne(pump,server,bad,now)==Step::Rejected);
    assert(bad->bytesRead<bad->request.size());
    auto metrics=server.add("POST /api/v1/bridge/metrics HTTP/1.1\r\n"
                            "Host: 192.168.1.46\r\n\r\n{}");
    assert(runOne(pump,server,metrics,now)==Step::LegacyHeld);
    assert(metrics->response.find("503 Service Unavailable")!=std::string::npos);
    assert(metrics->bytesRead==std::strlen(
           "POST /api/v1/bridge/metrics HTTP/1.1\r\n"));
    auto dashboard=server.add("GET / HTTP/1.1\r\nHost: x\r\n\r\n");
    assert(runOne(pump,server,dashboard,now)==Step::LegacyHeld);
    auto ota=server.add("POST /api/v1/bridge/ota/upload HTTP/1.1\r\n"
                         "Host: x\r\n\r\n");
    assert(runOne(pump,server,ota,now)==Step::Rejected);
    assert(ota->response.find("404 Not Found")!=std::string::npos);
}
static void testBudgetAndDeadlineKeepSchedulerResponsive(){
    Server server;
    Pump pump(server,ID,PUBLIC_KEY);
    uint32_t now=0u;
    auto blocked=server.add(packet());
    blocked->paused=true;
    unsigned ticks=0;
    for(unsigned i=0u;i<210u;++i) {
        const Step result=pump.poll(now);
        ++ticks;now+=5u;
        if(result==Step::Rejected)break;
        assert(result==Step::Pending);
    }
    assert(ticks>0 && ticks<=202);
    assert(blocked->bytesRead==0u);
    assert(blocked->response.find("408 Request Timeout")!=std::string::npos);
    // Immediately after a timed-out client, the listener accepts a new
    // request on the same existing server, not a second listener.
    auto good=server.add(packet());
    assert(runOne(pump,server,good,now)==Step::CryptoReviewedOnly);
}
static void testConcurrentQueuedClientsSerialized(){
    Server server;
    Pump pump(server,ID,PUBLIC_KEY);
    uint32_t now=0u;
    auto first=server.add(packet());
    auto second=server.add(packet(1u,TX2,"AUTO"));
    const Step firstResult=runOne(pump,server,first,now);
    assert(firstResult==Step::CryptoReviewedOnly);
    assert(second->bytesRead==0u);
    assert(runOne(pump,server,second,now)==Step::CryptoReviewedOnly);
}
int main(){
    testValidReplayAndCas();
    testNoFinAndUnreadTrailingBytes();
    testHeaderRejectionPrebodyAndLegacyHold();
    testBudgetAndDeadlineKeepSchedulerResponsive();
    testConcurrentQueuedClientsSerialized();
    std::cout<<"M3F_BORROWED_ONE_SERVER_COOPERATIVE_HOST_PASS_LEGACY_HOLD\n";
}
