// M3-C cryptographic HOST evidence, real OpenSSL HMAC/SHA256.
// No socket, credential store, test device, firmware, flash or installed LINK.
#include "M3CAuthenticatedIngress.h"
#include <openssl/evp.h>
#include <openssl/hmac.h>
#include "../link_m3l_incremental/M3LHostOpenSslFragments.h"
#include <openssl/sha.h>
#include <cassert>
#include <cstdlib>
#include <cstring>
#include <iostream>
#include <string>
#include <vector>

using ShinoM3C::Gate;
using ShinoM3C::Phase;
using ShinoM3C::Identity;
constexpr const char* HOST = "192.168.1.46";
constexpr const char* DEVICE = "1234567890abcdef";
constexpr const char* BOOT = "1234567890abcdef1234567890abcdef";
constexpr const char* TX = "00000000000000000000000000000001";
const Identity ID{HOST,DEVICE,BOOT};
const uint8_t KEY[32] = {
    1,2,3,4,5,6,7,8,9,10,11,12,13,14,15,16,
    17,18,19,20,21,22,23,24,25,26,27,28,29,30,31,32
};

struct RealCrypto {
    static bool hmacFragments(const uint8_t key[32],
                               const char* const* parts,size_t count,
                               uint8_t out[32]) {
        return ShinoM3LHost::hmacFragments(key,parts,count,out);
    }
    static bool hmac(const uint8_t* key, const uint8_t* src,
                     size_t len, uint8_t out[32]) {
        unsigned length=0;
        return HMAC(EVP_sha256(),key,32,src,len,out,&length)!=nullptr
            && length==32;
    }
    static bool sha256(const uint8_t* src,size_t n,uint8_t out[32]) {
        return SHA256(src,n,out)!=nullptr;
    }
};

static std::string hex(const uint8_t* buf,size_t n) {
    static constexpr char hexdigits[]="0123456789abcdef";
    std::string result(n*2u,'0');
    for(size_t i=0u;i<n;++i) {
        result[2u*i]=hexdigits[buf[i]>>4u];
        result[2u*i+1u]=hexdigits[buf[i]&15u];
    }
    return result;
}
static std::string body(const char* mode="MUSIC",unsigned revision=0,
                        const char* transaction=TX) {
    return std::string("{\"boot\":\"")+BOOT+"\",\"device\":\""+DEVICE+
        "\",\"mode\":\""+mode+"\",\"protocol\":\"shino-display-control-1\","
        "\"revision\":"+std::to_string(revision)+",\"tx\":\""+transaction+"\"}";
}
struct Packet{std::string header,body,hash,mac;};
static Packet packet(const char* mode="MUSIC",unsigned revision=0,
                     const char* transaction=TX) {
    const std::string raw=body(mode,revision,transaction);
    uint8_t digest[32]{},proof[32]{};
    assert(RealCrypto::sha256(reinterpret_cast<const uint8_t*>(raw.data()),
                              raw.size(),digest));
    const std::string digestHex=hex(digest,32u);
    const std::string sign=std::string("SHINO-M3-CONTROL-1\nPOST\n/api/v1/display/mode\n")
        +HOST+"\n"+DEVICE+"\n"+BOOT+"\n"+std::to_string(revision)
        +"\n"+mode+"\n"+transaction+"\n"+std::to_string(raw.size())
        +"\n"+digestHex;
    assert(RealCrypto::hmac(KEY,
               reinterpret_cast<const uint8_t*>(sign.data()),sign.size(),proof));
    const std::string macHex=hex(proof,32u);
    std::string header=
        std::string("POST /api/v1/display/mode HTTP/1.1\r\n")
        +"Host: "+HOST+"\r\n"
        +"Content-Type: application/json\r\n"
        +"Content-Length: "+std::to_string(raw.size())+"\r\n"
        +"Connection: close\r\n"
        +"X-Shino-Device: "+DEVICE+"\r\n"
        +"X-Shino-Boot: "+BOOT+"\r\n"
        +"X-Shino-Revision: "+std::to_string(revision)+"\r\n"
        +"X-Shino-Mode: "+mode+"\r\n"
        +"X-Shino-Tx: "+transaction+"\r\n"
        +"X-Shino-Body-Sha256: "+digestHex+"\r\n"
        +"X-Shino-Proof: "+macHex+"\r\n\r\n";
    return Packet{header,raw,digestHex,macHex};
}
static void ensure(bool cond,const char* error) {
    if(!cond) {std::cerr<<"M3C_CASE_FAIL "<<error<<"\n";std::abort();}
}
static std::string replace(std::string input,const std::string& before,
                           const std::string& after) {
    size_t index=input.find(before);
    ensure(index!=std::string::npos,"replace anchor");
    input.replace(index,before.size(),after);
    return input;
}
static Phase feedHeader(Gate& gate,const std::string& input,
                        uint32_t elapsed=50u,const uint8_t* key=KEY) {
    Phase result=gate.phase();
    for(char c:input) {
        result=gate.headerByte<RealCrypto>(c,elapsed,key);
        if(result!=Phase::Header) break;
    }
    return result;
}
static Phase feedBody(Gate& gate,const std::string& bytes,uint32_t ms=100u) {
    Phase result=gate.phase();
    for(unsigned char c:bytes) {
        result=gate.bodyByte<RealCrypto>(c,ms);
        if(result!=Phase::AuthenticatedHeader) break;
    }
    return result;
}
static void successAndCrossLanguageVector() {
    const Packet p=packet();
    ensure(p.body.size()==176u,"wire length");
    ensure(p.hash=="114d655a0bae76a903cb0a00090f898250efd8eddd2124ca28667032695951c6",
           "independent Python sha256");
    ensure(p.mac=="e1bbbcf0bcb54d301398431fe6ceddd75da80cf1c2a91e419559b17defb92d16",
           "independent Python HMAC");
    Gate g(ID,0);
    ensure(feedHeader(g,p.header+p.body)==Phase::AuthenticatedHeader,
           "authenticated actual header");
    ensure(g.consumedHeaders()==p.header.size(),"body not prefetched");
    ensure(g.consumedBody()==0u,"body count prior proof");
    ensure(g.bodyReadingAllowed(),"body only after proof");
    ensure(feedBody(g,p.body)==Phase::BodyDigestMatched,"digest-matched body");
    ensure(!g.verifiedNoSideEffect(),"cannot commit before FIN");
    ensure(g.finishAfterExactFraming(true,0u,150u)==Phase::VerifiedFrame,
           "verified frame and clean FIN");
    ensure(g.verifiedNoSideEffect(),"verified review only after FIN");
    ensure(g.resultForOfflineReview().mode==ShinoM3C::Mode::Music,"mode bind");
    ensure(g.resultForOfflineReview().revision==0u,"revision bind");
    ensure(std::strcmp(g.resultForOfflineReview().transaction,TX)==0,"tx bind");
    ensure(g.headerByte<RealCrypto>('!',500u,KEY)==Phase::VerifiedFrame,
           "terminal state unchanged"); // real transport must reject trailing bytes
}
static void invalidHeaders() {
    const Packet p=packet();
    std::vector<std::string> bad{
        replace(p.header,"POST /api/v1/display/mode","GET /api/v1/display/mode"),
        replace(p.header,"POST /api/v1/display/mode","POST /api/v1/bridge/metrics"),
        replace(p.header,"POST /api/v1/display/mode","POST /api/v1/display/mode?x=1"),
        replace(p.header,"HTTP/1.1","HTTP/1.0"),
        replace(p.header,"Host: 192.168.1.46","Host: 192.168.1.47"),
        replace(p.header,"Host: 192.168.1.46","Host: 8.8.8.8"),
        replace(p.header,"X-Shino-Device: "+std::string(DEVICE),
                "X-Shino-Device: 1111111111111111"),
        replace(p.header,"X-Shino-Boot: "+std::string(BOOT),
                "X-Shino-Boot: abcdef1234567890abcdef1234567890"),
        replace(p.header,"X-Shino-Tx: "+std::string(TX),
                "X-Shino-Tx: 00000000000000000000000000000002"),
        replace(p.header,"X-Shino-Mode: MUSIC","X-Shino-Mode: AUTO"),
        replace(p.header,"X-Shino-Mode: MUSIC","X-Shino-Mode: REBOOT"),
        replace(p.header,"X-Shino-Revision: 0","X-Shino-Revision: 1"),
        replace(p.header,"X-Shino-Revision: 0","X-Shino-Revision: -1"),
        replace(p.header,"X-Shino-Proof: "+p.mac,"X-Shino-Proof: "+std::string(64,'a')),
        replace(p.header,"X-Shino-Proof: "+p.mac,"X-Shino-Proof: "+std::string(64,'0')),
        replace(p.header,"X-Shino-Proof: "+p.mac,"X-Shino-Proof: "+std::string(64,'A')),
        replace(p.header,"X-Shino-Body-Sha256: "+p.hash,
                "X-Shino-Body-Sha256: "+std::string(64,'b')),
        replace(p.header,"Content-Length: 176","Content-Length: 177"),
        replace(p.header,"Content-Length: 176","Content-Length: 241"),
        replace(p.header,"Content-Length: 176","Content-Length: 0176"),
        replace(p.header,"Connection: close","Connection: keep-alive"),
        replace(p.header,"\r\nConnection: close",
                "\r\nTransfer-Encoding: chunked\r\nConnection: close"),
        replace(p.header,"\r\nConnection: close",
                "\r\nExpect: 100-continue\r\nConnection: close"),
        replace(p.header,"\r\nConnection: close",
                "\r\nContent-Encoding: gzip\r\nConnection: close"),
        replace(p.header,"\r\nConnection: close",
                "\r\nContent-Length: 176\r\nConnection: close"),
        replace(p.header,"\r\nConnection: close",
                "\r\nhost: 192.168.1.46\r\nConnection: close"),
        replace(p.header,"\r\nConnection: close",
                "\r\nX-Shino-Tx: "+std::string(TX)+"\r\nConnection: close"),
        replace(p.header,"\r\nConnection: close",
                "\r\nCookie: authenticated=yes\r\nConnection: close"),
        replace(p.header,"Content-Type: application/json",
                "Content-Type: text/plain"),
        replace(p.header,"\r\nConnection: close",
                "\r\nConnection: close \r\n"),
        replace(p.header,"HTTP/1.1\r\n","HTTP/1.1\n")
    };
    for(size_t i=0u;i<bad.size();++i) {
        Gate g(ID,0);
        if(feedHeader(g,bad[i])!=Phase::Reject)
            {std::cerr<<"case "<<i<<"\n";std::abort();}
        ensure(!g.bodyReadingAllowed(),"reject disallows body");
        ensure(g.consumedBody()==0u,"reject zero body");
    }
    Gate stale(ID,1u);
    ensure(feedHeader(stale,p.header)==Phase::Reject,"expected revision CAS");
    uint8_t zeros[32]{};
    Gate withoutKey(ID,0u);
    ensure(feedHeader(withoutKey,p.header,50u,zeros)==Phase::Reject,"zero key");
    Gate noKey(ID,0u);
    ensure(feedHeader(noKey,p.header,50u,nullptr)==Phase::Reject,"missing key");
    Gate late(ID,0u);
    ensure(feedHeader(late,p.header,1001u)==Phase::Reject,"header absolute clock");
    Gate partial(ID,0u);
    ensure(feedHeader(partial,p.header.substr(0,p.header.size()-1u))==Phase::Header,
           "short header not ready");
    ensure(partial.closeOrTimeout()==Phase::Reject,"closed partial header");
    Gate huge(ID,0u);
    ensure(feedHeader(huge,std::string(1025,'x'))==Phase::Reject,"header bound");
}
static void invalidOrInterruptedBody() {
    const Packet p=packet();
    {
        Gate g(ID,0u);
        ensure(feedHeader(g,p.header)==Phase::AuthenticatedHeader,"setup");
        std::string damaged=p.body;damaged[50]='Z';
        ensure(feedBody(g,damaged)==Phase::Reject,"body SHA mismatch");
        ensure(!g.verifiedNoSideEffect(),"SHA must not verify");
    }
    {
        Gate g(ID,0u);
        ensure(feedHeader(g,p.header)==Phase::AuthenticatedHeader,"setup");
        ensure(feedBody(g,p.body.substr(0,p.body.size()-1u))==Phase::AuthenticatedHeader,
               "incomplete body");
        ensure(g.closeOrTimeout()==Phase::Reject,"FIN incomplete");
    }
    {
        Gate g(ID,0u);
        ensure(feedHeader(g,p.header)==Phase::AuthenticatedHeader,"setup");
        ensure(feedBody(g,p.body,2001u)==Phase::Reject,"body deadline");
    }
    {
        Gate g(ID,0u);
        ensure(g.bodyByte<RealCrypto>('A',0u)==Phase::Reject,"prebody is denied");
    }
    // A cryptographically valid body with no clean FIN or queued bytes is
    // not yet a commit-eligible record.
    for (unsigned caseIndex=0u;caseIndex<3u;++caseIndex) {
        Gate g(ID,0u);
        ensure(feedHeader(g,p.header)==Phase::AuthenticatedHeader,"setup");
        ensure(feedBody(g,p.body)==Phase::BodyDigestMatched,"digest match");
        const Phase outcome=caseIndex==0u
            ?g.finishAfterExactFraming(false,0u,150u)
            :caseIndex==1u
             ?g.finishAfterExactFraming(true,1u,150u)
             :g.finishAfterExactFraming(true,0u,2001u);
        ensure(outcome==Phase::Reject,"clean FIN must be proven");
    }
    // No state mutation anywhere in gate: it only yields an offline result.
}
static void replayAfterVerifiedFinRefusedByOfflineLedger() {
    ShinoM3C::OfflineCasLedger ledger;
    const Packet a=packet();
    Gate first(ID,0u);
    ensure(feedHeader(first,a.header)==Phase::AuthenticatedHeader,"first auth");
    ensure(feedBody(first,a.body)==Phase::BodyDigestMatched,"first digest");
    ensure(!ledger.acceptVerifiedForLab(first),"no commit before FIN");
    ensure(first.finishAfterExactFraming(true,0u,150u)==Phase::VerifiedFrame,
           "first complete");
    ensure(ledger.acceptVerifiedForLab(first),"first CAS accepted");
    ensure(ledger.revision()==1u,"first revision increment");
    ensure(!ledger.acceptVerifiedForLab(first),"replay same verified frame rejected");

    Gate concurrentOld(ID,0u);
    ensure(feedHeader(concurrentOld,a.header)==Phase::AuthenticatedHeader,"old auth");
    ensure(feedBody(concurrentOld,a.body)==Phase::BodyDigestMatched,"old digest");
    ensure(concurrentOld.finishAfterExactFraming(true,0u,150u)==Phase::VerifiedFrame,
           "old complete");
    ensure(!ledger.acceptVerifiedForLab(concurrentOld),"stale CAS rejected");

    const char* NEW_TX="00000000000000000000000000000002";
    const Packet sameTxNextRev=packet("MUSIC",1u);
    Gate sameId(ID,1u);
    ensure(feedHeader(sameId,sameTxNextRev.header)==Phase::AuthenticatedHeader,"same tx auth");
    ensure(feedBody(sameId,sameTxNextRev.body)==Phase::BodyDigestMatched,"same tx digest");
    ensure(sameId.finishAfterExactFraming(true,0u,150u)==Phase::VerifiedFrame,
           "same tx complete");
    ensure(!ledger.acceptVerifiedForLab(sameId),"same tx new revision rejected");

    const Packet next=packet("MONITORING",1u,NEW_TX);
    Gate fresh(ID,1u);
    ensure(feedHeader(fresh,next.header)==Phase::AuthenticatedHeader,"next auth");
    ensure(feedBody(fresh,next.body)==Phase::BodyDigestMatched,"next digest");
    ensure(fresh.finishAfterExactFraming(true,0u,150u)==Phase::VerifiedFrame,
           "next complete");
    ensure(ledger.acceptVerifiedForLab(fresh),"fresh tx+CAS accepted");
    ensure(ledger.revision()==2u,"next revision increment");
}


static void exactCanonicalSigningLengthBoundary() {
    // These inputs are intentionally valid Host header values for their
    // externally bound fixture identity. The old 350-byte snprintf accepts
    // 349 signed bytes and rejects 350 even when the HMAC is valid.
    for(size_t hostLength: {size_t(144),size_t(145)}) {
        std::string host(hostLength,'a');
        const Packet p=packet();
        const std::string signedText=std::string("SHINO-M3-CONTROL-1\\nPOST\\n")
            +"/api/v1/display/mode\\n"+host+"\\n"+DEVICE+"\\n"+BOOT
            +"\\n0\\nMUSIC\\n"+TX+"\\n"+std::to_string(p.body.size())
            +"\\n"+p.hash;
        ensure(signedText.size()==hostLength+205u,"canonical count fixture");
        uint8_t proof[32]{};
        ensure(RealCrypto::hmac(KEY,reinterpret_cast<const uint8_t*>(
                  signedText.data()),signedText.size(),proof),
               "independent single-buffer HMAC oracle");
        std::string header=replace(p.header,
                "Host: "+std::string(HOST),"Host: "+host);
        header=replace(header,"X-Shino-Proof: "+p.mac,
                       "X-Shino-Proof: "+hex(proof,32u));
        const Identity local{host.c_str(),DEVICE,BOOT};
        Gate gate(local,0u);
        const Phase result=feedHeader(gate,header);
        if(hostLength==144u) {
            ensure(signedText.size()==349u,"349 exact expected");
            ensure(result==Phase::AuthenticatedHeader,
                   "349-byte original canonical HMAC frame accepted");
            ensure(feedBody(gate,p.body)==Phase::BodyDigestMatched,
                   "349-byte signed header original SHA body intact");
            ensure(gate.finishAfterExactFraming(true,0u,150u)
                   ==Phase::VerifiedFrame,"349-byte signed FIN");
        } else {
            ensure(signedText.size()==350u,"350 exact expected");
            ensure(result==Phase::Reject,
                   "350-byte signed input is rejected before body");
            ensure(gate.consumedBody()==0u,
                   "overlimit must never read body");
        }
    }
}

int main() {
    exactCanonicalSigningLengthBoundary();
    replayAfterVerifiedFinRefusedByOfflineLedger();
    successAndCrossLanguageVector();
    invalidHeaders();
    invalidOrInterruptedBody();
    std::cout<<"M3C_REAL_HMAC_PREBODY_AND_SHA256_BODY_HOST_PASS_NO_NETWORK\n";
}
