// SPDX-License-Identifier: GPL-3.0-or-later
// ESP8266 Arduino Core 3.1.2 COMPILE-ONLY proof: the bounded network reader,
// exact URI SHA256 Digest and stream-review templates compile against the real
// WiFiClient and native BearSSL implementation. This translation unit exposes
// NO callable entry point, creates NO WiFiServer/port listener, is NOT included
// by FirstBootBridge, and cannot receive or install a package.
#include <Arduino.h>
#include <ArduinoJson.h>
#include <ESP8266WiFi.h>
#include <bearssl/bearssl_hash.h>
#include "boot/NativeOtaNetworkPump.h"
#include "boot/NativeOtaEntropyReview.h"
#include "boot/NativeOtaPort80Plan.h"
#include "boot/NativeOtaSingleIngressShadow.h"
#include "boot/NativeOtaLegacySessionReview.h"
#include "boot/NativeOtaHeapReview.h"
#include "boot/NativeOtaHeapSampleCadence.h"
#include "shino_private_policy.h"

static_assert(SHINO_ENABLE_NATIVE_SIGNED_OTA == 0,
              "Native OTA is still a non-installing source research gate.");
static_assert(ARDUINOJSON_VERSION_MAJOR == 7 &&
              ARDUINOJSON_VERSION_MINOR == 4 &&
              ARDUINOJSON_VERSION_REVISION == 3,
              "Live ESP8266 JSON library drifted from verified host parity version 7.4.3.");
static_assert(ShinoNativeOta::NativeOtaPort80Plan::kMaxFirstLineBytes == 128u,
              "Port-80 routing research line cap must stay fixed and disconnected.");
static_assert(ShinoNativeOta::NativeOtaSingleIngressShadow::kHeaderBytes == 2048u &&
              ShinoNativeOta::NativeOtaSingleIngressShadow::kLegacyMetricsBytes == 384u,
              "Source-only single-owner review buffers drifted; re-audit bounded framing.");
// Compile these SIZEOF limits with the ACTUAL pinned Xtensa ESP8266 toolchain,
// not just host x86 layout. They are TYPE-SIZE ceilings, not a measured free-
// heap / peak stack / live port-80 server budget. No object is constructed.
static_assert(sizeof(ShinoNativeOta::NativeOtaSingleIngressShadow) <= 3072u,
              "Unwired ingress would exceed 3 KiB of per-instance storage.");
static_assert(sizeof(ShinoNativeOta::NativeOtaLegacySessionReview) <= 256u,
              "Unwired 2-slot legacy session model exceeded its type-size envelope.");
// Illustrative two-client parser ceiling using the ACTUAL Xtensa layout,
// not live heap or TCP overhead. Both parsers remain wholly uninstantiated
// and disconnected from the active FirstBootBridge port-80 listener.
static_assert(2u*sizeof(ShinoNativeOta::NativeOtaSingleIngressShadow) <= 6144u,
              "Two prospective ingress contexts exceeded the 6 KiB parser-only cap.");


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

// UNWIRED entropy source TYPE CHECK ONLY. ESP8266 Core 3.1.2 documents that
// ESP.random() requires Wi-Fi RF enabled for entropy. AP mode and default
// private IP are necessary, NOT proof that RF entropy is healthy, WPA2 is
// provisioned or an incoming peer is authenticated. Never call from the
// active bridge without separate review.
struct NativeDeviceEntropySource final {
    static bool privateApReady() {
        return WiFi.getMode()==WIFI_AP &&
               WiFi.softAPIP()==IPAddress(192,168,4,1);
    }
    static bool fill(uint8_t* bytes,size_t length) {
        return bytes && length==32u && ESP.random(bytes,length)==bytes;
    }
};

// Actual pinned ESP8266 API TYPE CHECK ONLY, using the 32-bit max-block
// overload. It remains disconnected: no heap sampling occurs on the device,
// no endpoint or scheduler is registered and no runtime heap claim is made.
// Arduino Core 3.1.2 must expose these APIs under its pinned UMM_INFO build.
struct NativeDeviceHeapSource final {
    bool read(uint32_t& freeBytes,uint32_t& largestBlock,uint8_t& fragmentation) {
        ESP.getHeapStats(&freeBytes,&largestBlock,&fragmentation);
        return true;
    }
};
static_assert(sizeof(NativeOtaHeapReview<NativeDeviceHeapSource>) <= 64u,
              "Prospective non-running heap review exceeds bounded type budget.");
static_assert(NativeOtaHeapSampleCadence::kIntervalMs == 1000u,
              "Prospective heap sampling cadence drifted from 1 Hz maximum.");
static_assert(sizeof(NativeOtaHeapSampleCadence) <= 8u,
              "Prospective non-running heap cadence unexpectedly expanded.");
template class NativeOtaHeapReview<NativeDeviceHeapSource>;

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
template class NativeOtaEntropyReview<NativeDeviceEntropySource>;
template class StrictOtaDigestGate<NativeBearSslSha256>;
template class NativeOtaStreamingReview<
    NativeBearSslSha256, NativeBearSslSha256, NativeRejectAllSink>;
template class NativeOtaNetworkPump<WiFiClient, UnwiredDeviceReview>;

} // namespace ShinoNativeOta
