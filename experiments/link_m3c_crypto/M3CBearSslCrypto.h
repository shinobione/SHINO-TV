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
