// SPDX-License-Identifier: GPL-3.0-or-later
#pragma once
// DISCONNECTED prospective heap sampling cadence. This helper has no ESP,
// network, timer interrupt, allocation, persistence, endpoint or device caller.
// A future owner-approved build may call due(nowMs) cooperatively from loop().
// It deliberately NEVER catches up missed periods with a burst of samples.
#include <cstdint>

namespace ShinoNativeOta {

class NativeOtaHeapSampleCadence final {
public:
    static constexpr uint32_t kIntervalMs=1000u;

    explicit NativeOtaHeapSampleCadence(uint32_t startedMs)
        : lastAttemptMs_(startedMs), firstPending_(true) {}

    NativeOtaHeapSampleCadence(const NativeOtaHeapSampleCadence&)=delete;
    NativeOtaHeapSampleCadence& operator=(const NativeOtaHeapSampleCadence&)=delete;

    bool due(uint32_t nowMs) {
        if(firstPending_) {
            firstPending_=false;
            lastAttemptMs_=nowMs;
            return true;
        }
        if(static_cast<uint32_t>(nowMs-lastAttemptMs_)<kIntervalMs)
            return false;
        // Schedule from the actual attempt time, not from a nominal timeline:
        // after a stalled loop there is one sample, never a catch-up burst.
        lastAttemptMs_=nowMs;
        return true;
    }

private:
    uint32_t lastAttemptMs_=0u;
    bool firstPending_=true;
};

} // namespace ShinoNativeOta
