#pragma once
#include <Updater.h>
#include <bearssl.h>
#include <cstring>
#include <StackThunk.h>
namespace BearSSL {
// Public DER parsing is independently checked by OpenSSL. This seam binds
// fixture modulus/exponent to the ACTUAL pinned BearSSL RSA verifier.
class PublicKey {
public:
    br_rsa_public_key rsa{};
    bool isRSA()const{return rsa.n!=nullptr;}bool isEC()const{return false;}
    const br_rsa_public_key* getRSA()const{return &rsa;}
    const br_ec_public_key* getEC()const{return nullptr;}
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
