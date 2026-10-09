// Real state transitions; fake deterministic proof intentionally tests only
// the authorization state machine, NOT the production BearSSL HMAC primitive.
#include "ShinoArmGate.h"
#include <cassert>
#include <cstring>
#include <cstdio>
static void mockMac(const uint8_t* key,const char* message,char* out){
    unsigned v=key[0];
    for(const char* p=message;*p;++p)v=(v*33u)^uint8_t(*p);
    for(unsigned i=0;i<64;++i){out[i]="0123456789abcdef"[(v>>(i%8*4))&15];}out[64]=0;
}
int main(){
    using namespace ShinoInstall;
    ArmGate gate(mockMac);
    const char* id="0123456789abcdef";
    const char* build="aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa";
    const char* key="1111111111111111111111111111111111111111111111111111111111111111";
    assert(!gate.configure(id,build,"invalid"));
    assert(gate.configure(id,build,key));
    uint8_t random[16];for(unsigned i=0;i<16;++i)random[i]=i+1;
    char nonce[33],message[170],proof[65],bad[65];
    assert(gate.challenge(random,16,1,nonce,sizeof(nonce)));
    std::snprintf(message,sizeof(message),"SHINO_ARM_1 %s %s %s PROBE",id,build,nonce);
    uint8_t nativeKey[32];std::memset(nativeKey,0x11,sizeof(nativeKey));
    mockMac(nativeKey,message,proof);
    std::strcpy(bad,proof);bad[0]=bad[0]=='0'?'1':'0';
    assert(!gate.arm(true,bad,100,true,true));
    assert(!gate.arm(true,proof,100,true,true)); // replay fails
    assert(gate.challenge(random,16,200,nonce,sizeof(nonce)));
    assert(!gate.arm(true,proof,15200,true,true)); // expired
    assert(gate.challenge(random,16,300,nonce,sizeof(nonce)));
    assert(!gate.arm(true,proof,350,false,true)); // not in normal mode
    assert(gate.challenge(random,16,400,nonce,sizeof(nonce)));
    assert(gate.arm(true,proof,450,true,true));
    ArmRequest req;
    assert(gate.consume(req) && req.ready && req.dryRun && req.key);
    assert(!gate.consume(req));
    // Install is refused, even with genuine proof, until a separate probe passes.
    assert(gate.challenge(random,16,600,nonce,sizeof(nonce)));
    std::snprintf(message,sizeof(message),"SHINO_ARM_1 %s %s %s INSTALL",id,build,nonce);
    mockMac(nativeKey,message,proof);
    assert(!gate.arm(false,proof,650,true,true));
    gate.setProbeResult(true);
    assert(gate.challenge(random,16,700,nonce,sizeof(nonce)));
    assert(gate.arm(false,proof,750,true,true));
    assert(gate.consume(req)&&!req.dryRun);
    gate.invalidate();
    assert(!gate.probeQualified());
    return 0;
}
