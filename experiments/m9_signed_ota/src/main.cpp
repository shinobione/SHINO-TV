// SPDX-License-Identifier: GPL-3.0-or-later
#include <Arduino.h>
#ifdef M9_SIGNED_COMPILE_PROOF
#include "M9SignedCore.h"
namespace {
// No key, credentials, release, AP, HTTP listener or executable call site.
// Function address retention proves a real linked native API chain. setup/loop
// never invoke it. All adapter/network-intent symbols have internal linkage.
__attribute__((noinline)) bool unwiredProof(const uint8_t* der,
    size_t bytes,const M9Signed::Release& release,char* header,size_t headerBytes,
    uint8_t* body,size_t bodyBytes,const char* nonce,const char* opaque,
    const char* token,const char* user,const char* ha1,uint32_t now,M9Signed::Budget budget){
    M9Signed::NativeAdapter adapter(der,bytes);
    M9Signed::Transfer<M9Signed::Sha256,M9Signed::DigestHash,M9Signed::NativeAdapter> transfer(release,399264,adapter);
    ShinoNativeOta::StrictOtaDigestGate<M9Signed::DigestHash> arm,upload;
    arm.challenge(0xc0a80402,ShinoNativeOta::RawOtaRequestKind::Arm,nonce,opaque,now);
    upload.challenge(0xc0a80402,ShinoNativeOta::RawOtaRequestKind::SignedTransport,nonce,opaque,now);
    if(!transfer.arm(header,headerBytes,body,bodyBytes,0xc0a80402,true,true,token,arm,user,ha1,now,budget))return false;
    if(!transfer.begin(header,headerBytes,0xc0a80402,true,upload,user,ha1,now,budget))return false;
    if(!transfer.add(body,bodyBytes,0,now,budget))return false;
    return transfer.finish(now,budget);
}
using Proof = decltype(&unwiredProof);
Proof volatile retainedProof = &unwiredProof;
}
#endif
void setup(){
#ifdef M9_SIGNED_COMPILE_PROOF
    // Volatile address read retains linker evidence; no indirect invocation.
    const auto pointer=retainedProof;(void)pointer;
#endif
}
void loop(){}
