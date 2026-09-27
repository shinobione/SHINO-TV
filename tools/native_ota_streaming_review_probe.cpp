// SPDX-License-Identifier: GPL-3.0-or-later
// HOST ONLY. Entire "upload" stays inside a mock RAM sink; no device, socket,
// private credentials, firmware updater, signature acceptance or flash.
#include "boot/NativeOtaStreamingReview.h"
#include <openssl/evp.h>
#include <array>
#include <cstddef>
#include <cstdint>
#include <iostream>
#include <string>
#include <vector>
using namespace ShinoNativeOta;
#define CHECK(x) do { if(!(x)){ std::cerr<<"FAIL "<<__LINE__<<": "<<#x<<"\n";return 1; } } while(0)

struct HostSha256 final {
    EVP_MD_CTX* ctx=EVP_MD_CTX_new();
    HostSha256(){if(!ctx)throw 1;}
    HostSha256(const HostSha256&)=delete;
    HostSha256& operator=(const HostSha256&)=delete;
    ~HostSha256(){EVP_MD_CTX_free(ctx);}
    void begin(){if(EVP_DigestInit_ex(ctx,EVP_sha256(),nullptr)!=1)throw 1;}
    void add(const uint8_t* bytes,size_t n) {
        if(EVP_DigestUpdate(ctx,bytes,n)!=1)throw 1;
    }
    void end(uint8_t out[32]) {
        unsigned int n=0u;
        if(EVP_DigestFinal_ex(ctx,out,&n)!=1 || n!=32u)throw 1;
    }
    static bool hex(const char* p,size_t n,char out[65]) {
        unsigned char raw[32]{};unsigned int length=0u;
        EVP_MD_CTX* h=EVP_MD_CTX_new();
        if(!h)return false;
        const bool success=EVP_DigestInit_ex(h,EVP_sha256(),nullptr)==1 &&
            EVP_DigestUpdate(h,p,n)==1 && EVP_DigestFinal_ex(h,raw,&length)==1 &&
            length==32u;
        EVP_MD_CTX_free(h);
        if(!success)return false;
        const char* digits="0123456789abcdef";
        for(size_t i=0;i<32u;++i) {out[2u*i]=digits[raw[i]>>4u];out[2u*i+1u]=digits[raw[i]&15u];}
        out[64]='\0';return true;
    }
};
std::string hash(const std::string& s) {
    char out[65]{};if(!HostSha256::hex(s.data(),s.size(),out))throw 1;
    return out;
}
std::array<uint8_t,32> digestOf(const std::vector<uint8_t>& input) {
    HostSha256 h;h.begin();h.add(input.data(),input.size());
    std::array<uint8_t,32> result{};h.end(result.data());return result;
}
struct RamOnlyReviewSink final {
    bool rejectBegin=false,rejectChunk=false,rejectComplete=false;
    unsigned beginCalls=0u,writeCalls=0u,completeCalls=0u,abortCalls=0u;
    uint32_t expected=0u;
    std::vector<uint8_t> data{};
    bool beginForReview(uint32_t count) {
        ++beginCalls;
        if(rejectBegin)return false;
        expected=count;return true;
    }
    bool acceptForReview(const uint8_t* ptr,size_t count) {
        ++writeCalls;
        if(rejectChunk || !ptr || count==0u ||
            count>4096u || data.size()+count>expected)return false;
        data.insert(data.end(),ptr,ptr+count);return true;
    }
    bool completeForReview() {
        ++completeCalls;
        return !rejectComplete && data.size()==expected;
    }
    void abortReview(){++abortCalls;data.clear();}
};
using Gate=NativeOtaStreamingReview<HostSha256,HostSha256,RamOnlyReviewSink>;
using DGate=StrictOtaDigestGate<HostSha256>;
constexpr uint32_t PEER=0xC0A80403u;
constexpr uint32_t OTHER_PEER=0xC0A80404u;
constexpr uint32_t MINIMUM=64260u;
constexpr uint32_t MAXIMUM=494404u;
constexpr std::array<uint8_t,16> TOKEN{{1,2,3,4,5,6,7,8,9,10,11,12,13,14,15,16}};
const std::string TOKEN_HEX="0102030405060708090a0b0c0d0e0f10";
const char* NONCE="0123456789abcdef0123456789abcdef";
const char* OPAQUE="fedcba9876543210fedcba9876543210";
const char* USER="host-only-owner-fixture";
const char* PASS="never-a-production-secret";
const char* ROUTE="/api/v1/bridge/ota/upload";
const char* CNONCE="abcdef0123456789";
std::string ha1(){return hash(std::string(USER)+":SHINO-OTA:"+PASS);}
std::string authorization(const std::string& uri=ROUTE) {
    const auto a1=ha1();
    const auto a2=hash("POST:"+uri);
    const auto proof=hash(a1+":"+NONCE+":00000001:"+CNONCE+":auth:"+a2);
    return std::string("Digest username=\"")+USER+"\", realm=\"SHINO-OTA\", nonce=\""+
        NONCE+"\", uri=\""+uri+"\", response=\""+proof+"\", opaque=\""+OPAQUE+
        "\", qop=auth, nc=00000001, cnonce=\""+CNONCE+"\", algorithm=SHA-256";
}
std::vector<uint8_t> synthetic(size_t n) {
    std::vector<uint8_t> result(n);
    for(size_t i=0u;i<n;++i)result[i]=static_cast<uint8_t>((i*73u + i/19u + 7u)&255u);
    return result;
}
std::string wireHeaders(uint32_t bytes,const std::string& auth=authorization(),
                        const std::string& extra="") {
    return "POST /api/v1/bridge/ota/upload HTTP/1.1\r\n"
      "Host: 192.168.4.1\r\nOrigin: http://192.168.4.1\r\n"
      "Content-Type: application/octet-stream\r\nContent-Length: "+
      std::to_string(bytes)+"\r\nAuthorization: "+auth+
      "\r\nX-Shino-Intent: "+TOKEN_HEX+"\r\n"+extra+"\r\n";
}
struct Fixture {
    DGate proof{};
    ManualConsentGate consent{};
    RamOnlyReviewSink sink{};
    Gate stream{proof,consent,sink};
    const std::string ha1Value=ha1();
    std::vector<uint8_t> payload;
    std::array<uint8_t,32> approvedHash{};
    explicit Fixture(uint32_t count=MINIMUM):payload(synthetic(count)),
        approvedHash(digestOf(payload)) {}
    bool prepare(uint32_t now=100u,bool ownerConfirmed=true,bool realAp=true,
                 IntendedPackage kind=IntendedPackage::SignedShino,
                 uint32_t peer=PEER) {
        if(!proof.challenge(PEER,RawOtaRequestKind::SignedTransport,NONCE,OPAQUE,now))
            return false;
        if(!consent.offer(true,true,ownerConfirmed,PEER,kind,
                          static_cast<uint32_t>(payload.size()),TOKEN,approvedHash,now))
            return false;
        return stream.start(peer,realAp,kind,approvedHash,USER,ha1Value.c_str(),now);
    }
    std::string header(const std::string& auth=authorization(),const std::string& extra="")const{
        return wireHeaders(static_cast<uint32_t>(payload.size()),auth,extra);
    }
    bool headerOnly(const std::string& h,uint32_t now=101u) {
        return stream.feed(reinterpret_cast<const uint8_t*>(h.data()),h.size(),now);
    }
    bool send(size_t chunk=4096u,uint32_t now=102u) {
        for(size_t i=0;i<payload.size();i+=chunk){
            size_t n=payload.size()-i<chunk?payload.size()-i:chunk;
            if(!stream.feed(payload.data()+i,n,now))return false;
        }
        return true;
    }
    bool finalized(uint32_t now=103u) {
        return stream.finishAfterExactFraming(now);
    }
};
int successModes() {
    for(size_t size : {size_t(MINIMUM),size_t(MAXIMUM)}) {
        for(size_t chunks : {size_t(1),size_t(7),size_t(1024),size_t(4096),size_t(8192)}) {
            // Avoid half a million host calls for repeated segmentation variants.
            if(size==MAXIMUM && chunks<4096u)continue;
            Fixture f(static_cast<uint32_t>(size));CHECK(f.prepare());
            const auto head=f.header();
            // Header may arrive one byte at a time, and final header+body
            // may share a single TCP packet. No body is forwarded before auth.
            if(chunks==1u) {
                for(char c:head) {
                    const uint8_t byte=static_cast<uint8_t>(c);
                    CHECK(f.stream.feed(&byte,1u,101u));
                }
            } else {
                CHECK(f.headerOnly(head));
            }
            CHECK(f.sink.beginCalls==1u && f.sink.writeCalls==0u);
            CHECK(f.send(chunks));
            CHECK(f.stream.phase()==StreamReviewPhase::BodyCompleteAwaitingReview);
            CHECK(f.sink.data==f.payload);
            CHECK(f.finalized());
            CHECK(f.stream.phase()==StreamReviewPhase::BytesAcceptedForOfflineReviewOnly);
            CHECK(f.sink.completeCalls==1u);
            CHECK(!f.finalized()); CHECK(!f.stream.start(PEER,true,
                IntendedPackage::SignedShino,f.approvedHash,USER,f.ha1Value.c_str(),104u));
        }
    }
    {
        Fixture f;CHECK(f.prepare());
        const auto head=f.header();
        std::vector<uint8_t> combined(head.begin(),head.end());
        combined.insert(combined.end(),f.payload.begin(),f.payload.begin()+100u);
        CHECK(f.stream.feed(combined.data(),combined.size(),101u));
        CHECK(f.sink.beginCalls==1u && f.sink.data.size()==100u);
        CHECK(f.stream.feed(f.payload.data()+100u,f.payload.size()-100u,102u));
        CHECK(f.finalized());
    }
    return 0;
}
int rejectBeforeBody() {
    {
        Fixture f;CHECK(f.prepare());
        const auto h=f.header(authorization("/api/v1/bridge/ota/arm"));
        CHECK(!f.headerOnly(h));CHECK(f.sink.beginCalls==0u);
        CHECK(f.stream.phase()==StreamReviewPhase::Aborted);
    }
    for(const auto& extra: {
        std::string("Host: 192.168.4.1\r\n"),
        std::string("Transfer-Encoding: chunked\r\n"),
        std::string("Origin: http://evil.invalid\r\n"),
        std::string("X-Shino-Intent: ")+TOKEN_HEX+"\r\n",
        std::string("Content-Length: 64260\r\n",
        std::string("Expect: 100-continue\r\n")}) {
        Fixture f;CHECK(f.prepare());
        CHECK(!f.headerOnly(f.header(authorization(),extra)));
        CHECK(f.sink.beginCalls==0u);
    }
    {
        Fixture f;CHECK(f.prepare());
        CHECK(!f.headerOnly(f.header("Digest username=\"fake\"")));
        CHECK(f.sink.beginCalls==0u);
    }
    {
        Fixture f;CHECK(f.prepare());
        auto h=f.header();h.replace(h.find(TOKEN_HEX),TOKEN_HEX.size(),
                                 "ffffffffffffffffffffffffffffffff");
        CHECK(!f.headerOnly(h));CHECK(f.sink.beginCalls==0u);
    }
    {
        Fixture f;CHECK(f.prepare());
        auto h=f.header();h.replace(h.find("Content-Length: 64260"),21u,"Content-Length: 64261");
        CHECK(!f.headerOnly(h));CHECK(f.sink.beginCalls==0u);
    }
    {
        Fixture f;CHECK(f.prepare());
        auto h=f.header();h.replace(h.find("Content-Type: application/octet-stream"),38u,
                                 "Content-Type: multipart/form-data");
        CHECK(!f.headerOnly(h));CHECK(f.sink.beginCalls==0u);
    }
    {
        Fixture f;CHECK(f.prepare());auto h=f.header();
        CHECK(f.stream.feed(reinterpret_cast<const uint8_t*>(h.data()),5u,101u));
        f.stream.disconnect();CHECK(f.stream.phase()==StreamReviewPhase::Aborted);
        CHECK(f.sink.beginCalls==0u);
        CHECK(!f.headerOnly(h));
    }
    {
        Fixture f;CHECK(f.prepare());auto h=f.header();
        CHECK(!f.stream.feed(reinterpret_cast<const uint8_t*>(h.data()),5u,10101u));
        CHECK(f.sink.beginCalls==0u);
    }
    return 0;
}
int rejectAfterBodyStart() {
    {
        Fixture f;CHECK(f.prepare());CHECK(f.headerOnly(f.header()));
        CHECK(f.stream.feed(f.payload.data(),100u,102u));
        CHECK(!f.finalized());CHECK(f.stream.phase()==StreamReviewPhase::Aborted);
        CHECK(f.sink.completeCalls==0u);
    }
    {
        Fixture f;CHECK(f.prepare());CHECK(f.headerOnly(f.header()));
        CHECK(f.stream.feed(f.payload.data(),2000u,102u));
        f.stream.disconnect();CHECK(f.stream.phase()==StreamReviewPhase::Aborted);
        CHECK(!f.stream.feed(f.payload.data()+2000u,1u,103u));
    }
    {
        Fixture f;CHECK(f.prepare());CHECK(f.headerOnly(f.header()));
        CHECK(f.stream.feed(f.payload.data(),1u,102u));
        CHECK(!f.stream.tick(15102u));CHECK(f.stream.phase()==StreamReviewPhase::Aborted);
    }
    {
        Fixture f;CHECK(f.prepare());CHECK(f.headerOnly(f.header()));
        auto corrupted=f.payload;corrupted[12345u]^=1u;
        CHECK(f.stream.feed(corrupted.data(),corrupted.size(),102u));
        CHECK(!f.finalized());CHECK(f.sink.completeCalls==0u);
        CHECK(f.stream.phase()==StreamReviewPhase::Aborted);
    }
    {
        Fixture f;CHECK(f.prepare());CHECK(f.headerOnly(f.header()));
        auto oversized=f.payload;oversized.push_back(1u);
        CHECK(!f.stream.feed(oversized.data(),oversized.size(),102u));
        CHECK(f.sink.completeCalls==0u);
    }
    {
        Fixture f;CHECK(f.prepare());CHECK(f.headerOnly(f.header()));
        CHECK(f.send());const uint8_t extra=42u;
        CHECK(!f.stream.feed(&extra,1u,103u));CHECK(!f.finalized());
    }
    {
        Fixture f;CHECK(f.prepare());
        f.sink.rejectBegin=true;CHECK(!f.headerOnly(f.header()));
        CHECK(f.sink.beginCalls==1u && f.sink.writeCalls==0u);
    }
    {
        Fixture f;CHECK(f.prepare());CHECK(f.headerOnly(f.header()));
        f.sink.rejectChunk=true;CHECK(!f.stream.feed(f.payload.data(),4096u,102u));
        CHECK(f.sink.completeCalls==0u);
    }
    {
        Fixture f;CHECK(f.prepare());CHECK(f.headerOnly(f.header()));
        f.sink.rejectComplete=true;CHECK(f.send());CHECK(!f.finalized());
        CHECK(f.stream.phase()==StreamReviewPhase::Aborted);
    }
    {
        Fixture f;CHECK(f.prepare());
        const auto h=f.header();
        std::vector<uint8_t> oversized(h.begin(),h.end());
        oversized.insert(oversized.end(),f.payload.begin(),f.payload.end());
        oversized.push_back(7u);
        CHECK(!f.stream.feed(oversized.data(),oversized.size(),101u));
        CHECK(f.sink.completeCalls==0u);
    }
    return 0;
}
int main() {
    if(successModes() || rejectBeforeBody() || rejectAfterBodyStart())return 1;
    std::cout<<"PASS: streaming HTTP fragment/combined-frame, Digest+consent gates, SHA256, "
                "disconnect, timeout, replay, overflow, short sink; RAM REVIEW ONLY NO FLASH.\n";
    return 0;
}
