// M3-L HOST-only: EVP_MAC OpenSSL 3 truly incremental HMAC-SHA256.
// No complete canonical message concatenation or key material logging.
#pragma once
#include <openssl/evp.h>
#include <openssl/core_names.h>
#include <openssl/params.h>
#include <cstddef>
#include <cstdint>
#include <cstring>
namespace ShinoM3LHost {
inline bool hmacFragments(const uint8_t key[32],
                          const char* const* parts,size_t count,
                          uint8_t out[32]) {
    if(!key||!parts||!count||!out)return false;
    EVP_MAC* algorithm=EVP_MAC_fetch(nullptr,"HMAC",nullptr);
    if(!algorithm)return false;
    EVP_MAC_CTX* ctx=EVP_MAC_CTX_new(algorithm);
    EVP_MAC_free(algorithm);
    if(!ctx)return false;
    char digest[]="SHA256";
    OSSL_PARAM params[]={
        OSSL_PARAM_construct_utf8_string(OSSL_MAC_PARAM_DIGEST,digest,0),
        OSSL_PARAM_construct_end()
    };
    bool okay=EVP_MAC_init(ctx,key,32u,params)==1;
    for(size_t i=0u;i<count&&okay;++i) {
        if(!parts[i]){okay=false;break;}
        const size_t len=std::strlen(parts[i]);
        okay=EVP_MAC_update(ctx,
            reinterpret_cast<const unsigned char*>(parts[i]),len)==1;
    }
    size_t bytes=0u;
    if(okay) okay=EVP_MAC_final(ctx,out,&bytes,32u)==1&&bytes==32u;
    EVP_MAC_CTX_free(ctx);
    return okay;
}
}
