// M3-R HOST-only signed real HMAC and single-parser socket simulation.
// Use the existing exact M3-C profile. No Wi-Fi, device or display writer.
#include "M3RSingleParser.h"
#include "../link_m3l_incremental/M3LHostOpenSslFragments.h"
#include <openssl/evp.h>
#include <openssl/hmac.h>
#include <openssl/sha.h>
#include <cstdint>
#include <cstdlib>
#include <iostream>
#include <string>

using ShinoM3C::Gate;
using ShinoM3C::Identity;
using ShinoM3C::Phase;
static constexpr const char* HOST="192.168.1.46";
static constexpr const char* DEV="1234567890abcdef";
static constexpr const char* BOOT="1234567890abcdef1234567890abcdef";
static constexpr const char* TX="00000000000000000000000000000001";
static const Identity ID{HOST,DEV,BOOT};
static const uint8_t KEY[32]={
    1,2,3,4,5,6,7,8,9,10,11,12,13,14,15,16,
    17,18,19,20,21,22,23,24,25,26,27,28,29,30,31,32
};
struct Crypto {
    static bool hmac(const uint8_t* key,const uint8_t* bytes,size_t n,
                     uint8_t output[32]) {
        unsigned len=0;
        return HMAC(EVP_sha256(),key,32,bytes,n,output,&len)!=nullptr &&
               len==32u;
    }
    static bool hmacFragments(const uint8_t key[32],const char* const* chunks,
                              size_t count,uint8_t out[32]) {
        return ShinoM3LHost::hmacFragments(key,chunks,count,out);
    }
    static bool sha256(const uint8_t* source,size_t n,uint8_t out[32]) {
        return SHA256(source,n,out)!=nullptr;
    }
};
static std::string hx(const uint8_t* bytes,size_t n) {
    static const char digits[]="0123456789abcdef";
    std::string out(n*2u,'0');
    for(size_t i=0;i<n;++i) {
        out[2*i]=digits[bytes[i]>>4];
        out[2*i+1]=digits[bytes[i]&15];
    }
    return out;
}
static void need(bool x,const char* label) {
    if(!x) {std::cerr<<"M3R_FAIL "<<label<<"\n";std::abort();}
}
struct Packet {std::string headers,body;};
static Packet signedPacket() {
    const std::string b=std::string("{\"boot\":\"")+BOOT+"\",\"device\":\""+DEV+
        "\",\"mode\":\"MUSIC\",\"protocol\":\"shino-display-control-1\","
        "\"revision\":0,\"tx\":\""+TX+"\"}";
    uint8_t digest[32]{},proof[32]{};
    need(Crypto::sha256(reinterpret_cast<const uint8_t*>(b.data()),b.size(),digest),
         "sha fixture");
    const std::string bodyHash=hx(digest,32);
    const std::string signedText=std::string("SHINO-M3-CONTROL-1\nPOST\n")
        +"/api/v1/display/mode\n"+HOST+"\n"+DEV+"\n"+BOOT+"\n0\nMUSIC\n"
        +TX+"\n"+std::to_string(b.size())+"\n"+bodyHash;
    need(Crypto::hmac(KEY,reinterpret_cast<const uint8_t*>(
        signedText.data()),signedText.size(),proof),"HMAC fixture");
    need(b.size()==176u,"M3C body length");
    need(bodyHash=="114d655a0bae76a903cb0a00090f898250efd8eddd2124ca28667032695951c6",
         "exact SHA from M3C vector");
    need(hx(proof,32)=="e1bbbcf0bcb54d301398431fe6ceddd75da80cf1c2a91e419559b17defb92d16",
         "exact HMAC from M3C vector");
    std::string header=std::string(ShinoM3R::kValidatedFirstLine)
        +"Host: "+HOST+"\r\nContent-Type: application/json\r\n"
        +"Content-Length: "+std::to_string(b.size())+"\r\n"
        +"Connection: close\r\nX-Shino-Device: "+DEV+"\r\n"
        +"X-Shino-Boot: "+BOOT+"\r\nX-Shino-Revision: 0\r\n"
        +"X-Shino-Mode: MUSIC\r\nX-Shino-Tx: "+TX+"\r\n"
        +"X-Shino-Body-Sha256: "+bodyHash+"\r\n"
        +"X-Shino-Proof: "+hx(proof,32)+"\r\n\r\n";
    return Packet{header,b};
}
struct Peer {
    std::string wire;
    size_t exposed=0u,pos=0u;
    bool closed=false;
    size_t calls=0u;
    explicit Peer(std::string w,bool fragments=false)
        : wire(std::move(w)),exposed(fragments?0u:wire.size()) {}
    int available() const {return static_cast<int>(exposed-pos);}
    bool connected() const {return !closed && pos<wire.size();}
    int read() {
        ++calls;
        if(pos>=exposed)return -1;
        int result=static_cast<unsigned char>(wire[pos++]);
        if(pos==wire.size())closed=true;
        return result;
    }
    void drip() {if(exposed<wire.size())++exposed;}
};
static std::string tail(const Packet& p) {
    const std::string lead=ShinoM3R::kValidatedFirstLine;
    need(p.headers.compare(0,lead.size(),lead)==0,"first line fixture");
    return p.headers.substr(lead.size());
}
static Phase read(Gate& gate,Peer& peer,uint32_t& now,uint32_t started,
                  bool fragment=false,const uint8_t* key=KEY) {
    return ShinoM3R::readAuthenticatedHeaders<Crypto>(
        peer,gate,key,[&]{return now;},[&]{++now;if(fragment)peer.drip();},
        started);
}
static Phase frame(Gate& gate,Peer& peer,uint32_t& now,uint32_t started,
                   bool fragment=false) {
    return ShinoM3R::verifyFrameWithoutSideEffect<Crypto>(
        peer,gate,[&]{return now;},[&]{++now;if(fragment)peer.drip();},
        started);
}
static void positiveAndBodyBoundaries() {
    const auto p=signedPacket();
    for(bool fragment:{false,true}) {
        Gate gate(ID,0u);
        Peer peer(tail(p)+p.body,fragment);
        uint32_t clock=1000u;
        if(fragment)clock=500u;
        const uint32_t start=clock;
        need(read(gate,peer,clock,start,fragment)==Phase::AuthenticatedHeader,
             "authenticated using single parser");
        need(peer.pos==tail(p).size(),"never read body before HMAC");
        need(gate.consumedBody()==0u,"zero unauthenticated body");
        need(gate.bodyReadingAllowed(),"only authenticated header gives body");
        need(frame(gate,peer,clock,start,fragment)==Phase::VerifiedFrame,
             "real SHA + FIN after authenticated header");
        need(gate.verifiedNoSideEffect(),"cryptographic offline frame valid");
        need(gate.resultForOfflineReview().mode==ShinoM3C::Mode::Music,
             "MUSIC authenticated mode");
    }
}
static void negativeCases() {
    const auto p=signedPacket();
    const std::string ok=tail(p);
    const auto broken=[&](std::string headers,const char* label) {
        Gate gate(ID,0u);
        Peer peer(headers+p.body);
        uint32_t now=0;
        need(read(gate,peer,now,0u)==Phase::Reject,label);
        need(peer.pos<=headers.size(),"never read body on invalid auth");
        need(gate.consumedBody()==0u,"no body on auth rejection");
    };
    auto change=[&](std::string what,std::string into,const char* why) {
        auto bytes=ok;const auto at=bytes.find(what);
        need(at!=std::string::npos,"fixture patch anchor");
        bytes.replace(at,what.size(),into);
        broken(bytes,why);
    };
    change("Host: 192.168.1.46","Host: 192.168.1.47","host binding");
    change("X-Shino-Mode: MUSIC","X-Shino-Mode: AUTO","HMAC mode binding");
    change("X-Shino-Proof: ","X-Shino-Proof: f","proof invalid");
    change("Connection: close","Connection: keep-alive","keepalive rejected");
    change("Connection: close","Transfer-Encoding: chunked","TE rejected");
    change("Host: ","Host: \r\nHost: ","duplicate header");
    change("Content-Length: 176","Content-Length: 0176","ambiguous length");
    change("Host: ","Host: \t","control byte header");
    change("Host: ","Host: \n","bare LF header");
    broken(ok.substr(0,ok.size()-1u),"interrupted headers");
    broken(std::string(961u,'A'),"headers bounded before heap");
    {
        Gate gate(ID,0u);Peer peer(ok+p.body);uint32_t now=1000u;
        need(read(gate,peer,now,0u)==Phase::Reject,"elapsed deadline");
        need(peer.pos==0,"timeout no socket body");
    }
    {
        Gate gate(ID,0u);Peer peer(ok+p.body,true);
        uint32_t now=UINT32_MAX-500u;const uint32_t started=now;
        need(read(gate,peer,now,started,true)==Phase::AuthenticatedHeader,
             "millis wraps safely with slow fragmentation");
        need(peer.pos==ok.size(),"no body after clock wrap");
    }
    {
        Gate gate(ID,0u);Peer peer(ok+p.body);uint32_t now=0;
        uint8_t zero[32]{};
        need(read(gate,peer,now,0u,false,zero)==Phase::Reject,
             "zero HMAC key rejected");
        need(peer.pos==ok.size(),"denied after header proof");
    }
    {
        Gate gate(ID,0u);Peer peer(ok+p.body);uint32_t now=0;
        need(read(gate,peer,now,0u)==Phase::AuthenticatedHeader,"setup");
        peer.wire.push_back('X'); peer.exposed=peer.wire.size();peer.closed=false;
        need(frame(gate,peer,now,0u)==Phase::Reject,
             "trailing extra bytes fail even after SHA matched");
    }
    {
        Gate gate(ID,0u);Peer peer(ok+p.body.substr(0,p.body.size()-1u));
        uint32_t now=0;
        need(read(gate,peer,now,0u)==Phase::AuthenticatedHeader,"setup truncation");
        need(frame(gate,peer,now,0u)==Phase::Reject,"missing body EOF denied");
    }
    {
        Gate gate(ID,0u);auto body=p.body;body[20]='!';
        Peer peer(ok+body);uint32_t now=0;
        need(read(gate,peer,now,0u)==Phase::AuthenticatedHeader,"setup tamper");
        need(frame(gate,peer,now,0u)==Phase::Reject,"tampered body sha rejected");
    }
}
int main() {
    positiveAndBodyBoundaries();
    negativeCases();
    std::cout<<"M3R_SINGLE_M3C_PARSER_REAL_OPENSSL_HOST_PASS_NO_DEVICE\n";
}
