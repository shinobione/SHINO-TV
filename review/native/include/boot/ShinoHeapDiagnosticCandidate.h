// SPDX-License-Identifier: GPL-3.0-or-later
#pragma once
// Opt-in, read-only INSTRUMENTED CANDIDATE for a separately authorized build.
// Not compiled into default esp12e, not an OTA component or update authority.
// One cooperative heap-stat read at most per second, after ordinary bridge work.
// No timer, second listener, allocation, persistence, filesystem or flash API.
#include <Arduino.h>
#include <ArduinoJson.h>
#include "boot/NativeOtaHeapReview.h"
#include "boot/NativeOtaHeapSampleCadence.h"

namespace ShinoHeapDiagnostic {

struct EspHeapSource final {
    bool read(uint32_t& freeBytes,uint32_t& largestFreeBlockBytes,
              uint8_t& fragmentationPercent) {
        // Core 3.1.2 32-bit largest-block overload, independently compiled
        // in NativeOtaDevicePumpCompileProbe.cpp before candidate activation.
        ESP.getHeapStats(&freeBytes,&largestFreeBlockBytes,&fragmentationPercent);
        return true;
    }
};

class Candidate final {
public:
    Candidate():cadence_(0u),review_(source_) {}
    Candidate(const Candidate&)=delete;
    Candidate& operator=(const Candidate&)=delete;

    // Only call at the end of an ordinary loop iteration, AFTER legacy HTTP,
    // LCD and existing factory tick. Never call in a handler, ISR or paintCard.
    void pollAfterExistingWork(uint32_t nowMs) {
        if(cadence_.due(nowMs)) (void)review_.capture();
    }

    // Only the EXISTING Digest-protected GET /api/v1/bridge/status may call
    // this. Do NOT collect a new sample while serializing JSON: the response
    // itself allocates heap and the sample must have a clear prior time.
    void appendReadOnlyStatus(JsonDocument& doc) const {
        const ShinoNativeOta::NativeOtaHeapSummary summary=review_.summary();
        JsonObject observation=doc["heap_observation"].to<JsonObject>();
        observation["schema"]="OBSERVED_HEAP_V1";
        observation["sampling_interval_ms"]=ShinoNativeOta::NativeOtaHeapSampleCadence::kIntervalMs;
        observation["sample_count"]=summary.samples;
        observation["max_samples"]=ShinoNativeOta::NativeOtaHeapReview<EspHeapSource>::kMaxSamples;
        observation["state"]=summary.samples==0u ? "NO_SAMPLES" :
            summary.samples==ShinoNativeOta::NativeOtaHeapReview<EspHeapSource>::kMaxSamples ?
                "SATURATED" : "SAMPLING";
        if(summary.samples==0u)return; // Missing data is never represented as zero.
        observation["first_free_heap_bytes"]=summary.first.freeBytes;
        observation["latest_free_heap_bytes"]=summary.latest.freeBytes;
        observation["latest_largest_free_block_bytes"]=summary.latest.largestFreeBlockBytes;
        observation["latest_fragmentation_percent"]=summary.latest.fragmentationPercent;
        observation["lowest_observed_free_heap_bytes"]=summary.lowestObservedFreeBytes;
        observation["lowest_observed_largest_free_block_bytes"]=summary.lowestObservedLargestBlockBytes;
        observation["highest_observed_fragmentation_percent"]=summary.highestObservedFragmentationPercent;
    }

private:
    EspHeapSource source_{};
    ShinoNativeOta::NativeOtaHeapSampleCadence cadence_;
    ShinoNativeOta::NativeOtaHeapReview<EspHeapSource> review_;
};

static_assert(ShinoNativeOta::NativeOtaHeapSampleCadence::kIntervalMs==1000u,
              "Read-only candidate observation rate changed; re-audit.");
static_assert(sizeof(Candidate)<=96u,
              "Candidate's fixed static observation context became unexpectedly large.");

} // namespace ShinoHeapDiagnostic
