// SPDX-License-Identifier: GPL-3.0-or-later
#pragma once
// DISCONNECTED V2.1 heap instrumentation contract. One sample is supplied by
// an independently audited Source; this type never invokes ESP/HTTP, allocates
// dynamic memory, stores secrets, creates a listener, changes flash or reboots.
// The minimum is only the LOWEST OBSERVED sample, not true in-flight peak usage.
#include <cstddef>
#include <cstdint>

namespace ShinoNativeOta {

struct NativeOtaHeapSample final {
    uint32_t freeBytes=0u;
    uint32_t largestFreeBlockBytes=0u;
    uint8_t fragmentationPercent=0u;
};

struct NativeOtaHeapSummary final {
    uint16_t samples=0u;
    NativeOtaHeapSample first{};
    NativeOtaHeapSample latest{};
    uint32_t lowestObservedFreeBytes=0u;
    uint32_t lowestObservedLargestBlockBytes=0u;
    uint8_t highestObservedFragmentationPercent=0u;
};

// Source must implement bool read(uint32_t& free, uint32_t& largest, uint8_t& frag).
// This is a prospective observation model; the existing FirstBootBridge never
// constructs or calls it. An explicit physical build and endpoint are NOT added.
template<class Source>
class NativeOtaHeapReview final {
public:
    static constexpr uint16_t kMaxSamples=1024u;

    explicit NativeOtaHeapReview(Source& source):source_(source) {}
    NativeOtaHeapReview(const NativeOtaHeapReview&)=delete;
    NativeOtaHeapReview& operator=(const NativeOtaHeapReview&)=delete;

    bool capture() {
        if(summary_.samples==kMaxSamples)return false;
        NativeOtaHeapSample next{};
        if(!source_.read(next.freeBytes,next.largestFreeBlockBytes,
                         next.fragmentationPercent))return false;
        // No 0, impossible max/free relationship, or corrupt fragmentation.
        // Do not make allocation/memory-safety assertions from these samples.
        if(next.freeBytes==0u || next.freeBytes>262144u ||
           next.largestFreeBlockBytes==0u ||
           next.largestFreeBlockBytes>next.freeBytes ||
           next.fragmentationPercent>100u)return false;
        if(summary_.samples==0u) {
            summary_.first=next;
            summary_.lowestObservedFreeBytes=next.freeBytes;
            summary_.lowestObservedLargestBlockBytes=next.largestFreeBlockBytes;
            summary_.highestObservedFragmentationPercent=next.fragmentationPercent;
        } else {
            if(next.freeBytes<summary_.lowestObservedFreeBytes)
                summary_.lowestObservedFreeBytes=next.freeBytes;
            if(next.largestFreeBlockBytes<summary_.lowestObservedLargestBlockBytes)
                summary_.lowestObservedLargestBlockBytes=next.largestFreeBlockBytes;
            if(next.fragmentationPercent>summary_.highestObservedFragmentationPercent)
                summary_.highestObservedFragmentationPercent=next.fragmentationPercent;
        }
        summary_.latest=next;
        ++summary_.samples;
        return true;
    }
    NativeOtaHeapSummary summary() const {return summary_;}
private:
    Source& source_;
    NativeOtaHeapSummary summary_{};
};

} // namespace ShinoNativeOta
