// M3-N source test: REAL OpenSSL MD5 Digest + unchanged B5.3 FslessMetrics
// through the new, auth-required M3-M handler. ALL credentials are public
// artificial TEST values. No sockets, SmallTV, OTA, clock or Wi-Fi calls.
#include "M3NMetricsAuthority.h"
#include <openssl/evp.h>
#include <array>
#include <cstdio>
#include <cstdlib>
#include <cstring>
#include <string>
using namespace ShinoM3N;
namespace {
uint32_t hostTime=100;
char reply[ShinoM3M::ActualMetricsHandler::kMinReply]{};
constexpr char USER[]="test-user";
constexpr char PASS[]="public-fixture-not-device-password";
constexpr char ROUTE[]="/api/v1/bridge/metrics";
const Peer PEER{0xc0a80132u,0xc0a8012eu};
struct HostMd5 {
    EVP_MD_CTX* ctx=EVP_MD_CTX_new();
    HostMd5(){if(!ctx)std::abort();}
    ~HostMd5(){EVP_MD_CTX_free(ctx);}
    void reset(){if(EVP_DigestInit_ex(ctx,EVP_md5(),nullptr)!=1)std::abort();}
    void add(const char* p,size_t n){
        if(EVP_DigestUpdate(ctx,p,n)!=1)std::abort();
    }
    void finish(uint8_t result[16]) {
        unsigned n=0;
        if(EVP_DigestFinal_ex(ctx,result,&n)!=1||n!=16)std::abort();
    }
};
void check(bool ok,const char* why) {
    if(!ok){std::fprintf(stderr,"M3N FAIL %s\n",why);std::exit(2);}
}
std::string md5(std::string raw) {
    HostMd5 md;uint8_t digest[16]{};char hex[33]{};
    md.reset();md.add(raw.data(),raw.size());md.finish(digest);
    toHex(digest,16,hex);wipe(digest,sizeof(digest));
    return hex;
}
std::string auth(const DigestState& st,const std::string& verb,
                 const std::string& route,unsigned nc=1,
                 const std::string& user=USER,
                 const std::string& realm="SHINO-FirstBoot",
                 const std::string& qop="auth",
                 const std::string& opaqueOverride="",
                 bool includeAlgorithm=true) {
    char ncHex[9]{};
    std::snprintf(ncHex,sizeof(ncHex),"%08x",nc);
    const std::string cnonce="abcdefABCDEF12";
    const std::string ha1=md5(user+":"+realm+":"+PASS);
    const std::string ha2=md5(verb+":"+route);
    const std::string proof=md5(ha1+":"+st.nonce()+":"+ncHex+":"+cnonce+":auth:"+ha2);
    return "Digest username=\""+user+"\", realm=\""+realm+
      "\", nonce=\""+st.nonce()+"\", uri=\""+route+
      "\", response=\""+proof+"\", opaque=\""+
      (opaqueOverride.empty()?st.opaque():opaqueOverride)+
      "\", qop="+qop+", nc="+ncHex+", cnonce=\""+cnonce+"\""+
      (includeAlgorithm?", algorithm=MD5":"");
}
std::string sample(unsigned cpu) {
    return R"({"ok":true,"gpu_available":true,"cpu_usage":)"+
       std::to_string(cpu)+
       R"(,"gpu_usage":34.5,"memory_used_gb":8.0,"memory_total_gb":16.0,"gpu_vram_mb":2048.0,"gpu_temp_c":56.0,"gpu_power":120.0})";
}
ShinoM3M::Request req(ShinoM3M::Verb verb,const std::string& sampleData) {
    ShinoM3M::Request r{};
    r.method=verb;r.network=ShinoM3M::Network::HomeSta;
    r.path=ROUTE;
    if(verb==ShinoM3M::Verb::Post){
       r.body=reinterpret_cast<const uint8_t*>(sampleData.data());
       r.bodySize=sampleData.size();
       r.declaredLength=sampleData.size();
       r.contentType="application/json";
       r.exactEndOfBody=true;
    }
    return r;
}
template<class Auth>
int execute(const ShinoM3M::Request& request,const Auth& verifier){
   auto response=ShinoM3M::ActualMetricsHandler::handle(
        request,verifier,reply,sizeof(reply));
   return response.status;
}
}
uint32_t millis(){return hostTime;}
int main(){
    DigestState digest;
    BrowserReadSessions cookies;
    uint8_t challengeEntropy[32]{};
    for(unsigned i=0;i<32;++i)challengeEntropy[i]=static_cast<uint8_t>(i+1);
    check(digest.issue(challengeEntropy,PEER,100),"strong injected challenge");
    char challenge[176]{};
    check(digest.challenge(challenge,sizeof(challenge)),"challenge bounded");
    check(std::strstr(challenge,"Digest realm=\"SHINO-FirstBoot\", qop=\"auth\"")!=nullptr,
          "core 3.1.2 compatible qop realm header");
    check(std::strstr(challenge,digest.nonce())!=nullptr&&
          std::strstr(challenge,digest.opaque())!=nullptr,"challenge nonce opaque");

    const auto json=sample(22u);
    const auto getRequest=req(ShinoM3M::Verb::Get,json);
    const auto postRequest=req(ShinoM3M::Verb::Post,json);
    NetworkContext net{PEER,0xffffff00u,false,false,true,true,
                       "192.168.1.46","192.168.1.46",""};
    std::string currentAuth=auth(digest,"POST",ROUTE);
    const auto permit=[&](const NetworkContext& context,
                          const std::string& proof,const char* cookie,
                          size_t cookieLen, uint32_t now) {
        return MetricsAuthority<HostMd5>(context,digest,cookies,
            proof.data(),proof.size(),cookie,cookieLen,USER,PASS,now);
    };
    check(execute(postRequest,permit(net,"",nullptr,0,110))==403,
          "cannot POST without Digest");
    check(execute(postRequest,permit(net,currentAuth,nullptr,0,110))==200,
          "source-executed real Digest MD5 verified before metrics write");
    check(FslessMetrics::snapshot().cpu==22.0f,"source C++ really applied");
    check(execute(postRequest,permit(net,currentAuth,nullptr,0,110))==403,
          "replay nc=1 rejected");
    check(execute(getRequest,permit(net,"",nullptr,0,110))==403,
          "unauthorized GET denied");

    uint8_t cookieEntropy[16]{};
    for(unsigned i=0;i<16;++i)cookieEntropy[i]=static_cast<uint8_t>(i+42u);
    char token[33]{};
    check(cookies.issue(cookieEntropy,PEER,110,token),"issue owner read cookie");
    std::string browserCookie="theme=dark; SHINO_READ_SESSION="+
        std::string(token)+" ; example=1";
    check(execute(getRequest,permit(net,"",browserCookie.data(),
          browserCookie.size(),110))==200,"cookie authorizes GET only");
    check(execute(postRequest,permit(net,"",browserCookie.data(),
          browserCookie.size(),110))==403,"cookie never authorizes POST");
    const auto duplicateCookie=browserCookie+"; SHINO_READ_SESSION="+token;
    check(execute(getRequest,permit(net,"",duplicateCookie.data(),
         duplicateCookie.size(),110))==403,"duplicate cookie denied");
    const auto alien=Peer{0xc0a80133u,PEER.local};
    NetworkContext alienNet=net;alienNet.peer=alien;
    check(execute(getRequest,permit(alienNet,"",browserCookie.data(),
         browserCookie.size(),110))==403,"cookie cannot transfer to another peer");
    check(execute(postRequest,permit(alienNet,auth(digest,"POST",ROUTE,2),
         nullptr,0,110))==403,"Digest nonce bound to client");

    std::string second=auth(digest,"POST",ROUTE,2);
    NetworkContext invalid=net; invalid.origin="http://evil.example";
    check(execute(postRequest,permit(invalid,second,nullptr,0,110))==403,
          "origin enforced by actual HomeLan authority policy");
    invalid=net; invalid.host="192.168.1.99";
    check(execute(postRequest,permit(invalid,second,nullptr,0,110))==403,
          "Host strict local authority");
    invalid=net; invalid.onStaInterface=false;
    check(execute(postRequest,permit(invalid,second,nullptr,0,110))==403,
          "radio interface guard");
    invalid=net;invalid.subnet=0u;
    check(execute(postRequest,permit(invalid,second,nullptr,0,110))==403,
          "no unknown subnet fail open");
    check(execute(postRequest,permit(net,second,nullptr,0,110))==200,
          "rejected wrong-peer/origin did not consume nonce counter");

    const auto bad=sample(102u);
    const auto badRequest=req(ShinoM3M::Verb::Post,bad);
    check(execute(badRequest,permit(net,auth(digest,"POST",ROUTE,3),
          nullptr,0,110))==422,"source C++ rejects invalid numeric");
    check(FslessMetrics::snapshot().cpu==22.0f,"invalid sample keeps previous");
    const auto current=auth(digest,"POST",ROUTE,4);
    const auto tampered=current.substr(0,current.find("response=\""))+
        "response=\""+std::string(32,'0')+"\", opaque=\""+
        digest.opaque()+"\", qop=auth, nc=00000004, cnonce=\"abcdefABCDEF12\"";
    check(execute(postRequest,permit(net,tampered,nullptr,0,110))==403,
          "invalid MD5 proof rejects");
    const auto forgedNonce=auth(digest,"POST",ROUTE,4,USER,"SHINO-FirstBoot",
                                "auth","00000000000000000000000000000000");
    check(execute(postRequest,permit(net,forgedNonce,nullptr,0,110))==403,
          "wrong opaque refused");
    const auto wrongQop=auth(digest,"POST",ROUTE,4,USER,"SHINO-FirstBoot","auth-int");
    check(execute(postRequest,permit(net,wrongQop,nullptr,0,110))==403,
          "qop downgrade refused");
    const auto wrongUser=auth(digest,"POST",ROUTE,4,"another-user");
    check(execute(postRequest,permit(net,wrongUser,nullptr,0,110))==403,
          "username is bound");
    check(execute(postRequest,permit(net,second+", nc=00000005",nullptr,0,110))==403,
          "duplicate Digest field denied");
    check(execute(postRequest,permit(net,std::string("Basic abc"),nullptr,0,110))==403,
          "Basic cannot fall back through native Digest");
    check(execute(postRequest,permit(net,auth(digest,"POST",ROUTE,4),nullptr,0,
          30101))==403,"expired nonce denied");
    check(execute(getRequest,permit(net,"",browserCookie.data(),
          browserCookie.size(),7200111u))==403,"expired cookie denied");

    DigestState missing;
    const uint8_t zeros[32]{};
    check(!missing.issue(zeros,PEER,100),"no deterministic all-zero challenge");
    digest.invalidate();cookies.invalidate();
    check(execute(getRequest,permit(net,"",browserCookie.data(),
          browserCookie.size(),120))==403,"session invalidation on network change");
    std::puts("M3N_REAL_MD5_AUTH_AND_ORIGINAL_METRICS_SOURCE_PASS");
}
