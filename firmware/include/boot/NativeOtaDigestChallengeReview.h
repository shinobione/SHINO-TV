// SPDX-License-Identifier: GPL-3.0-or-later
#pragma once
// HOST-ONLY challenge serialization contract for a FUTURE privileged OTA Digest.
// The caller, not this class, MUST prove independent hardware CSPRNG entropy,
// nonce uniqueness, private-AP peer binding and real request authentication.
// No server, credential, listener, flash API, install permission or RNG here.
#include <array>
#include <cstddef>
#include <cstdint>
#include <cstdio>

namespace ShinoNativeOta {

struct DigestChallengePreview {
    std::array<char,33> nonce{};
    std::array<char,33> opaque{};
    std::array<char,192> wwwAuthenticate{}; // HEADER VALUE ONLY; not an HTTP response.
};

class NativeOtaDigestChallengeReview final {
public:
    static bool fromExternalEntropy(const std::array<uint8_t,16>& nonceBytes,
                                    const std::array<uint8_t,16>& opaqueBytes,
                                    DigestChallengePreview& out) {
        out=DigestChallengePreview{};
        uint8_t nonzeroNonce=0u, nonzeroOpaque=0u, difference=0u;
        for(size_t i=0;i<16u;++i) {
            nonzeroNonce|=nonceBytes[i];
            nonzeroOpaque|=opaqueBytes[i];
            difference|=nonceBytes[i]^opaqueBytes[i];
        }
        if(!nonzeroNonce || !nonzeroOpaque || !difference) return false;
        static constexpr char hex[]="0123456789abcdef";
        for(size_t i=0;i<16u;++i) {
            out.nonce[2u*i]=hex[nonceBytes[i]>>4u];
            out.nonce[2u*i+1u]=hex[nonceBytes[i]&15u];
            out.opaque[2u*i]=hex[opaqueBytes[i]>>4u];
            out.opaque[2u*i+1u]=hex[opaqueBytes[i]&15u];
        }
        const int n=std::snprintf(out.wwwAuthenticate.data(),
                                  out.wwwAuthenticate.size(),
                                  "Digest realm=\"SHINO-OTA\", nonce=\"%s\", opaque=\"%s\", "
                                  "algorithm=SHA-256, qop=\"auth\"",
                                  out.nonce.data(),out.opaque.data());
        if(n<0 || static_cast<size_t>(n)>=out.wwwAuthenticate.size()) {
            out=DigestChallengePreview{};
            return false;
        }
        return true; // NOT an issued challenge, real browser proof or authorization.
    }
};

} // namespace ShinoNativeOta
