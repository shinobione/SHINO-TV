// Offline compile-only candidate on the pinned ESP8266 Arduino Core 3.1.2.
// BearSSL library is part of that core. NO secret key provided or stored here.
#pragma once
#ifdef ESP8266
#include <bearssl/bearssl.h>
#else
#include <bearssl.h>
#endif
#include <cstddef>
#include <cstdint>
#include <cstring>
namespace ShinoM3C {
struct BearSslCrypto final {
    static bool sha256(const uint8_t* p, size_t n, uint8_t out[32]) {
        if ((!p && n) || !out) return false;
        br_sha256_context ctx;
        br_sha256_init(&ctx);
        br_sha256_update(&ctx,p,n);
        br_sha256_out(&ctx,out);
        return true;
    }
    // M3-L streaming HMAC: HMAC ipad/opad and SHA state belong only to
    // this call. Never materialize the signed canonical message, and never
    // downgrade to hashes of individually authenticated fragments.
    static bool hmacFragments(const uint8_t key[32],
                              const char* const* parts,
                              size_t count,uint8_t out[32]) {
        if(!key||!parts||!count||!out) return false;
        br_hmac_key_context keyContext;
        br_hmac_context ctx;
        br_hmac_key_init(&keyContext,&br_sha256_vtable,key,32u);
        br_hmac_init(&ctx,&keyContext,32u);
        bool valid=true;
        for(size_t i=0u;i<count;++i) {
            if(!parts[i]) {valid=false;break;}
            br_hmac_update(&ctx,parts[i],std::strlen(parts[i]));
        }
        const bool result=valid && br_hmac_out(&ctx,out)==32u;
        volatile uint8_t* p=reinterpret_cast<volatile uint8_t*>(&ctx);
        for(size_t i=0u;i<sizeof(ctx);++i) p[i]=0u;
        p=reinterpret_cast<volatile uint8_t*>(&keyContext);
        for(size_t i=0u;i<sizeof(keyContext);++i) p[i]=0u;
        return result;
    }
    static bool hmac(const uint8_t key[32], const uint8_t* data,
                     size_t n, uint8_t out[32]) {
        if (!key || (!data && n) || !out) return false;
        br_hmac_key_context keyContext;
        br_hmac_context ctx;
        br_hmac_key_init(&keyContext,&br_sha256_vtable,key,32);
        br_hmac_init(&ctx,&keyContext,32);
        br_hmac_update(&ctx,data,n);
        return br_hmac_out(&ctx,out)==32;
    }
};
} // namespace ShinoM3C
