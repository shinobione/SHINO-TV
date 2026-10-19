// Native pinned ESP8266 Core 3.1.2 BearSSL MD5 for EXISTING Digest only.
// Never use MD5 for new M3 display commands (they require HMAC SHA-256).
#pragma once
#include <bearssl/bearssl.h>
#include "M3NLegacyDigest.h"
namespace ShinoM3N {
class BearMd5 final {
    br_md5_context state_{};
public:
    ~BearMd5(){wipe(&state_,sizeof(state_));}
    void reset(){br_md5_init(&state_);}
    void add(const char* s,size_t n){br_md5_update(&state_,s,n);}
    void finish(uint8_t out[16]){br_md5_out(&state_,out);}
};
}
