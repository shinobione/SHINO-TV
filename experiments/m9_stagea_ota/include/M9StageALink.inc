// Included only in a disposable copy of the actual StageA translation unit.
#include "M9SignedCore.h"
#include "M9StageAHttp.h"
namespace {
struct NativePolicy {
    const char *username,*credentialHa1,*intent;bool confirmed;
    uint32_t now()const{return millis();}
    uint32_t peer(WiFiClient& client)const{
        auto ip=client.remoteIP();return uint32_t(ip[0])<<24|uint32_t(ip[1])<<16|uint32_t(ip[2])<<8|ip[3];
    }
    bool privateAp(WiFiClient& client)const{
        return WiFi.getMode()==WIFI_AP && WiFi.softAPIP()==IPAddress(192,168,4,1) && client.localIP()==WiFi.softAPIP();
    }
    bool ownerConfirmed()const{return confirmed;}
    const char* user()const{return username;}const char* ha1()const{return credentialHa1;}const char* token()const{return intent;}
    M9Signed::Budget budget()const{
        uint32_t heap,block;uint8_t frag;ESP.getHeapStats(&heap,&block,&frag);
        return {heap,block,frag,ESP.getFreeContStack()};
    }
};
using NativeHttp=M9StageA::Http<M9Signed::Sha256,M9Signed::DigestHash,M9Signed::NativeAdapter,NativePolicy>;
// Reserve actual concurrent objects in the integrated ELF, instead of hiding
// persistent memory in a large proof-root frame. No constructor runs at boot.
alignas(M9Signed::NativeAdapter) uint8_t nativeStorage[sizeof(M9Signed::NativeAdapter)];
alignas(NativeHttp) uint8_t httpStorage[sizeof(NativeHttp)];
NativeHttp* nativeHttp=nullptr;bool constructed=false;
NativePolicy policyStorage{};
const uint32_t nativeCosts[] PROGMEM={sizeof(br_pkey_decoder_context),sizeof(BearSSL::SigningVerifier),sizeof(String)};
volatile uint32_t retainedCost=0;
__attribute__((noinline)) bool stageAUnwiredProof(const uint8_t* der,size_t bytes,
    const M9Signed::Release& release,NativePolicy& policy,const char* armNonce,
    const char* armOpaque,const char* uploadNonce,const char* uploadOpaque) {
    if(constructed || !policy.budget().safe())return false;constructed=true;
    policyStorage=policy;
    auto adapter=new(nativeStorage) M9Signed::NativeAdapter(der,bytes);
    nativeHttp=new(httpStorage) NativeHttp(release,ESP.getSketchSize(),*adapter,policyStorage);
    auto& server=M9NormalStageA::service.raw();
    server.setStageARawHook([](const String& line,WiFiClient* client,uint32_t started){return nativeHttp->claim(line,client,started);});
    const uint32_t peer=0xc0a80402,now=policy.now();
    return nativeHttp->armHeaderAuth.challenge(peer,ShinoNativeOta::RawOtaRequestKind::Arm,armNonce,armOpaque,now) &&
        nativeHttp->armAuth.challenge(peer,ShinoNativeOta::RawOtaRequestKind::Arm,armNonce,armOpaque,now) &&
        nativeHttp->uploadAuth.challenge(peer,ShinoNativeOta::RawOtaRequestKind::SignedTransport,uploadNonce,uploadOpaque,now);
}
__attribute__((noinline)) void stageAUnwiredPump(){if(nativeHttp)nativeHttp->pump();}
decltype(&stageAUnwiredProof) volatile retainedStageAProof=&stageAUnwiredProof;
decltype(&stageAUnwiredPump) volatile retainedStageAPump=&stageAUnwiredPump;
}
void retainM9StageAProof(){auto a=retainedStageAProof;auto b=retainedStageAPump;(void)a;(void)b;
    for(unsigned i=0;i<3;++i)retainedCost=pgm_read_dword(nativeCosts+i);
}
