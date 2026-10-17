// Host execution: real StageA/parser, explicit inert identity/interface seams.
#pragma once
#include "M9StageAHttp.h"
#include "../../m9_signed_ota/host/M9SignedMixed.h"
namespace Wire {
struct Policy {
    std::string test;
    uint32_t now()const{return millis();}
    uint32_t peer(WiFiClient&)const{return test=="peer"?0x7f000001:0xc0a80402;}
    bool privateAp(WiFiClient&)const{return test!="interface";}
    bool ownerConfirmed()const{return test!="consent";}
    const char* user()const{return "shino";}
    const char* token()const{return "abcdefabcdefabcdefabcdefabcdefab";}
    const char* ha1()const{return "a6ba08aff2b5e9d74b7a39d2a5c54d01c8aaafe189f36ef6183269ed7ffecd79";}
    M9Signed::Budget budget()const{return test=="budget"?M9Signed::Budget{30224,30008,1,3248}:M9Signed::Budget{60000,50000,0,4096};}
};
struct Adapter {
    std::vector<uint8_t> stage;unsigned begins=0,writes=0,commits=0;bool poisoned=false;std::string test;
    bool begin(const M9Signed::Release&,const M9Signed::Layout&){++begins;return !poisoned && test!="allocator";}
    size_t write(uint8_t* p,size_t n){++writes;if(poisoned || test=="write")return 0;stage.insert(stage.end(),p,p+n);return n;}
    bool precommit(const M9Signed::Release& release,const M9Signed::Layout&){
        if(test=="corrupt" && !stage.empty())stage[42]^=1;
        return Mixed::digest(stage)==release.packageHash;
    }
    bool commit(){++commits;return true;}void poison(){poisoned=true;}
};
inline M9Signed::Digest hex(const char* s){M9Signed::Digest out;for(unsigned i=0;i<32;++i){auto digit=[](char c){return c<='9'?c-'0':c-'a'+10;};out[i]=uint8_t(digit(s[2*i])*16+digit(s[2*i+1]));}return out;}
inline Adapter adapter;inline Policy policy;
using Http=M9StageA::Http<Mixed::Hash,Mixed::DigestHash,Adapter,Policy>;
inline std::unique_ptr<Http> http;
inline unsigned pumpCalls=0,maxStreamStep=0;
inline void start(ESP8266WebServer& server,const char* test) {
    policy.test=adapter.test=test;
    if(policy.test=="wrap")host_ms=0xfffff000u;
    const M9Signed::Release release{100000,
        hex("5c6605d32ad0efd4b5a7f7ba9675a1111d765695afd3d41da5290ba3fc8defb6"),
        hex("fba6f824ac53cdc12ac6cbbd55ca983802b1c65764c68180d6a6f0d81986738e"),
        hex("aac999d99e0474a27a9124d8013c65ca51554699184edae9bfdedbce53a31ece")};
    http=std::make_unique<Http>(release,399264,adapter,policy);
    const char* nonce="23456789abcdef0123456789abcdef01";const char* opaque="cdef0123456789abcdef0123456789ab";
    http->armHeaderAuth.challenge(0xc0a80402,ShinoNativeOta::RawOtaRequestKind::Arm,nonce,opaque,millis());
    http->armAuth.challenge(0xc0a80402,ShinoNativeOta::RawOtaRequestKind::Arm,nonce,opaque,millis());
    http->uploadAuth.challenge(0xc0a80402,ShinoNativeOta::RawOtaRequestKind::SignedTransport,"3456789abcdef0123456789abcdef012",opaque,millis());
    server.setStageARawHook([](const String& line,WiFiClient* client,uint32_t started){return http->claim(line,client,started);});
}
inline void pump(){++pumpCalls;auto before=http->phase();auto received=http->received();http->pump();maxStreamStep=std::max(maxStreamStep,unsigned(http->received()-received));if(before!=http->phase())std::cerr<<"ota_phase="<<unsigned(http->phase())<<" bytes="<<http->received()<<" clock="<<millis()<<" begins="<<adapter.begins<<" writes="<<adapter.writes<<'\n';}
inline void report(){std::cout<<"\n{\"begins\":"<<adapter.begins<<",\"writes\":"<<adapter.writes<<",\"commits\":"<<adapter.commits
    <<",\"received\":"<<http->received()<<",\"chunks\":"<<http->chunks<<",\"rejects\":"<<http->rejects
    <<",\"phase\":"<<unsigned(http->phase())<<",\"poisoned\":"<<(adapter.poisoned?"true":"false")
    <<",\"pump_calls\":"<<pumpCalls<<",\"watchdog_feeds\":"<<ESP.feeds<<",\"max_stream_step\":"<<maxStreamStep<<"}";}
}
