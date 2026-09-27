// SPDX-License-Identifier: GPL-3.0-or-later
// ESP8266 Arduino Core 3.1.2 COMPILE-ONLY proof: the bounded network reader,
// exact URI SHA256 Digest and stream-review templates compile against the real
// WiFiClient and native BearSSL implementation. This translation unit exposes
// NO callable entry point, creates NO WiFiServer/port listener, is NOT included
// by FirstBootBridge, and cannot receive or install a package.
#include <Arduino.h>
#include <ESP8266WiFi.h>
#include <bearssl/bearssl_hash.h>
#include "boot/NativeOtaNetworkPump.h"
#include "boot/NativeOtaPort80Plan.h"
#include "shino_private_policy.h"

static_assert(SHINO_ENABLE_NATIVE_SIGNED_OTA == 0,
              "Native OTA is still a non-installing source research gate.");
static_assert(ShinoNativeOta::NativeOtaPort80Plan::kMaxFirstLineBytes == 128u,
              "Port-80 routing research line cap must stay fixed and disconnected.");

namespace ShinoNativeOta {

struct NativeBearSslSha256 final {
    br_sha256_context context{};
    void begin() { br_sha256_init(&context); }
    void add(const uint8_t* bytes, size_t count) {
        br_sha256_update(&context, bytes, count);
    }
    void end(uint8_t out[32]) { br_sha256_out(&context, out); }

    static bool hex(const char* source, size_t length, char out[65]) {
        if (!source || !out) return false;
        br_sha256_context context{};
        uint8_t result[32]{};
        br_sha256_init(&context);
        br_sha256_update(&context, source, length);
        br_sha256_out(&context, result);
        static constexpr char DIGITS[] = "0123456789abcdef";
        for (size_t i=0; i<sizeof(result); ++i) {
            out[2u*i]=DIGITS[result[i] >> 4u];
            out[2u*i+1u]=DIGITS[result[i] & 15u];
            result[i]=0u;
        }
        out[64]='\0';
        return true;
    }
};

// Fail-closed compile fixture. It does not retain body bytes, has no device
// writer, and deliberately never permits a successful review. Never replace
// this with a flash sink without a separately approved implementation gate.
struct NativeRejectAllSink final {
    bool beginForReview(uint32_t) { return false; }
    bool acceptForReview(const uint8_t*, size_t) { return false; }
    bool completeForReview() { return false; }
    void abortReview() {}
};

using UnwiredDeviceReview =
    NativeOtaStreamingReview<NativeBearSslSha256, NativeBearSslSha256, NativeRejectAllSink>;

// Explicit instantiation type-checks every real method against ESP8266 3.1.2.
// No instance, listener, callback or startup action is declared or created.
template class StrictOtaDigestGate<NativeBearSslSha256>;
template class NativeOtaStreamingReview<
    NativeBearSslSha256, NativeBearSslSha256, NativeRejectAllSink>;
template class NativeOtaNetworkPump<WiFiClient, UnwiredDeviceReview>;

} // namespace ShinoNativeOta
