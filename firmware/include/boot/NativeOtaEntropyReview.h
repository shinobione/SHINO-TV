// SPDX-License-Identifier: GPL-3.0-or-later
#pragma once
// RESEARCH ONLY, pure one-attempt wrapper around an externally supplied entropy
// source. It does not prove actual RF entropy, socket identity, nonce uniqueness
// across process resets, authentication or permission to flash firmware.
// EntropySource contract:
//   static bool privateApReady();       // future trusted device-side AP check
//   static bool fill(uint8_t*, size_t);  // fill exactly 32 fresh bytes or fail
// Never connect this preview to FirstBootBridge without a separate security gate.
#include "boot/NativeOtaDigestChallengeReview.h"
#include <array>
#include <cstddef>
#include <cstdint>

namespace ShinoNativeOta {

template<class EntropySource>
class NativeOtaEntropyReview final {
public:
    NativeOtaEntropyReview()=default;
    NativeOtaEntropyReview(const NativeOtaEntropyReview&)=delete;
    NativeOtaEntropyReview& operator=(const NativeOtaEntropyReview&)=delete;

    // One attempt, whether it passes or fails. This never issues a live HTTP
    // response; the caller must separately bind the result to its one-use
    // peer/method/route-specific StrictOtaDigestGate challenge.
    bool preview(DigestChallengePreview& out) {
        out=DigestChallengePreview{};
        if(attempted_) return false;
        attempted_=true;
        if(!EntropySource::privateApReady()) return false;
        std::array<uint8_t,32> entropy{};
        if(!EntropySource::fill(entropy.data(),entropy.size())) {
            clear(entropy);
            return false;
        }
        std::array<uint8_t,16> nonce{},opaque{};
        for(size_t i=0;i<16u;++i) {
            nonce[i]=entropy[i];
            opaque[i]=entropy[i+16u];
        }
        const bool ok=NativeOtaDigestChallengeReview::fromExternalEntropy(
            nonce,opaque,out);
        clear(entropy);
        clear(nonce);
        clear(opaque);
        return ok;
    }
private:
    template<size_t N>
    static void clear(std::array<uint8_t,N>& bytes) {
        for(auto& b:bytes) b=0u;
    }
    bool attempted_=false;
};

} // namespace ShinoNativeOta
