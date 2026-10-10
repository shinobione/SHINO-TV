// Host-only paired scheduler: actual StageA handlers + unwired transfer state.
// Native Core/RSA is qualified separately; this adapter writes only host RAM.
#pragma once
#include "../include/M9SignedTransfer.h"
#include <fstream>
#include <vector>
#ifdef _WIN32
#include <bcrypt.h>
#else
#include <openssl/sha.h>
#endif
namespace Mixed {
struct Hash {
    std::vector<uint8_t> bytes;
    void begin(){bytes.clear();}
    void add(const uint8_t* p,size_t n){bytes.insert(bytes.end(),p,p+n);}
    void end(uint8_t* out){
#ifdef _WIN32
        BCRYPT_ALG_HANDLE algorithm=nullptr;BCRYPT_HASH_HANDLE hash=nullptr;
        if(BCryptOpenAlgorithmProvider(&algorithm,BCRYPT_SHA256_ALGORITHM,nullptr,0)<0 ||
           BCryptCreateHash(algorithm,&hash,nullptr,0,nullptr,0,0)<0 ||
           BCryptHashData(hash,bytes.data(),ULONG(bytes.size()),0)<0 || BCryptFinishHash(hash,out,32,0)<0)
            throw std::runtime_error("host SHA256 fixture");
        BCryptDestroyHash(hash);BCryptCloseAlgorithmProvider(algorithm,0);
#else
        SHA256(bytes.data(),bytes.size(),out);
#endif
    }
};
inline M9Signed::Digest digest(const std::vector<uint8_t>& b){Hash h;M9Signed::Digest d;h.begin();h.add(b.data(),b.size());h.end(d.data());return d;}
struct DigestHash {static bool hex(const char* p,size_t n,char* out){
    Hash h;M9Signed::Digest d;h.begin();h.add(reinterpret_cast<const uint8_t*>(p),n);h.end(d.data());
    const char* alphabet="0123456789abcdef";for(size_t i=0;i<32;++i){out[i*2]=alphabet[d[i]>>4];out[i*2+1]=alphabet[d[i]&15];}out[64]=0;return true;}};
struct Adapter {
    std::vector<uint8_t> staging;bool scheduled=false,poisoned=false;
    bool begin(const M9Signed::Release&,const M9Signed::Layout&){return !poisoned;}
    size_t write(uint8_t* p,size_t n){if(poisoned)return 0;staging.insert(staging.end(),p,p+n);return n;}
    bool precommit(const M9Signed::Release& r,const M9Signed::Layout&){return digest(staging)==r.packageHash;}
    bool commit(){scheduled=true;return true;}void poison(){poisoned=true;}
};
inline Adapter adapter;inline std::vector<uint8_t> package;
inline std::unique_ptr<M9Signed::Transfer<Hash,DigestHash,Adapter>> transfer;
inline unsigned chunks=0,streamGets=0,streamPosts=0,lastGets=0,lastPosts=0;
inline const char* nonce="23456789abcdef0123456789abcdef01";
inline const char* opaque="cdef0123456789abcdef0123456789ab";
inline const char* token="abcdefabcdefabcdefabcdefabcdefab";
inline const M9Signed::Budget budget{60000,50000,0,4096};
inline std::string header(bool arm,const std::string& ha1){
    std::string path=arm?"/api/v1/bridge/ota/arm":"/api/v1/bridge/ota/upload";
    char ha2[65],proof[65];std::string input="POST:"+path;DigestHash::hex(input.data(),input.size(),ha2);
    input=ha1+":"+nonce+":00000001:inertcnonce:auth:"+ha2;DigestHash::hex(input.data(),input.size(),proof);
    return "POST "+path+" HTTP/1.1\r\nHost: 192.168.4.1\r\nOrigin: http://192.168.4.1\r\nContent-Type: "+
       (arm?"application/json":"application/octet-stream")+"\r\nContent-Length: "+std::to_string(arm?16:package.size())+
       "\r\nAuthorization: Digest username=\"shino\", realm=\"SHINO-OTA\", nonce=\""+nonce+"\", opaque=\""+opaque+
       "\", uri=\""+path+"\", algorithm=SHA-256, qop=auth, nc=00000001, cnonce=\"inertcnonce\", response=\""+proof+
       "\"\r\n"+(arm?"":std::string("X-Shino-Intent: ")+token+"\r\n")+"\r\n";
}
inline void start(const char* path){
    std::ifstream file(path,std::ios::binary);package={std::istreambuf_iterator<char>(file),{}};
    if(package.size()!=100260)throw std::runtime_error("public mixed fixture missing");
    std::vector<uint8_t> raw(package.begin(),package.end()-260),key{1};
    M9Signed::Release release{uint32_t(raw.size()),digest(raw),digest(package),digest(key)};
    transfer=std::make_unique<M9Signed::Transfer<Hash,DigestHash,Adapter>>(release,399264,adapter);
    ShinoNativeOta::StrictOtaDigestGate<DigestHash> arm,upload;char ha1[65];
    DigestHash::hex("shino:SHINO-OTA:PUBLIC-INERT",sizeof("shino:SHINO-OTA:PUBLIC-INERT")-1,ha1);
    arm.challenge(0xc0a80402,ShinoNativeOta::RawOtaRequestKind::Arm,nonce,opaque,host_ms);
    upload.challenge(0xc0a80402,ShinoNativeOta::RawOtaRequestKind::SignedTransport,nonce,opaque,host_ms);
    auto ah=header(true,ha1),uh=header(false,ha1);
    if(!transfer->arm(ah.data(),ah.size(),reinterpret_cast<const uint8_t*>("{\"confirm\":true}"),16,
       0xc0a80402,true,true,token,arm,"shino",ha1,host_ms,budget) ||
       !transfer->begin(uh.data(),uh.size(),0xc0a80402,true,upload,"shino",ha1,host_ms,budget))
        throw std::runtime_error("mixed arm gate");
}
inline void step(){
    if(transfer->phase()!=M9Signed::Phase::Streaming)return;
    streamGets+=gets-lastGets;streamPosts+=posts-lastPosts;lastGets=gets;lastPosts=posts;
    uint32_t at=transfer->received();size_t n=std::min(size_t(512),package.size()-at);
    if(!transfer->add(package.data()+at,n,at,host_ms,budget))throw std::runtime_error("mixed state upload");++chunks;
    if(transfer->phase()==M9Signed::Phase::Complete && !transfer->finish(host_ms,budget))throw std::runtime_error("mixed finish");
}
inline void report(){std::cout<<"\n{\"model_chunks\":"<<chunks<<",\"stream_gets\":"<<streamGets<<",\"stream_posts\":"<<streamPosts
    <<",\"scheduled_model\":"<<(adapter.scheduled?"true":"false")<<",\"listeners_added\":0,\"native_rsa_here\":false}";}
}
