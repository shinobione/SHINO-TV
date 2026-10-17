#pragma once
#include <Updater.h>
#include <bearssl.h>
#include <cstring>
#include <vector>
#include <StackThunk.h>
namespace BearSSL {
// Host API seam: real pinned BearSSL DER decoder supplies this owned key.
// Target compilation uses the actual Core PublicKey declaration/constructor.
class PublicKey {
public:
    br_rsa_public_key rsa{};
    PublicKey(const uint8_t* der,size_t bytes){
        br_pkey_decoder_context context;br_pkey_decoder_init(&context);
        if(!der || !bytes)return;
        br_pkey_decoder_push(&context,der,bytes);
        const auto key=br_pkey_decoder_get_rsa(&context);
        if(br_pkey_decoder_last_error(&context)!=0 || !key)return;
        n.assign(key->n,key->n+key->nlen);e.assign(key->e,key->e+key->elen);
        rsa={n.data(),n.size(),e.data(),e.size()};
    }
    bool isRSA()const{return rsa.n!=nullptr;}bool isEC()const{return false;}
    const br_rsa_public_key* getRSA()const{return &rsa;}
    const br_ec_public_key* getEC()const{return nullptr;}
private:std::vector<uint8_t> n,e;
};
class HashSHA256 : public UpdaterHashClass {
public:
    void begin()override;void add(const void*,uint32_t)override;void end()override;
    int len()override;const void* hash()override;const unsigned char* oid()override;
private:br_sha256_context _cc;unsigned char _sha256[32];
};
class SigningVerifier : public UpdaterVerifyClass {
public:
    explicit SigningVerifier(PublicKey* k):_pubKey(k){stack_thunk_add_ref();}
    ~SigningVerifier(){stack_thunk_del_ref();}
    uint32_t length()override;bool verify(UpdaterHashClass*,const void*,uint32_t)override;
private:PublicKey* _pubKey;
};
}
