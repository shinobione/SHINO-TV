// SPDX-License-Identifier: GPL-3.0-or-later
// HOST-only deterministic virtual-clock proof of disconnected heap cadence.
#include "boot/NativeOtaHeapSampleCadence.h"
#include <cstdint>
#include <iostream>
using namespace ShinoNativeOta;
#define CHECK(x) do {if(!(x)){std::cerr<<"FAIL "<<__LINE__<<": "<<#x<<"\n";return 1;}}while(0)

int main() {
    static_assert(NativeOtaHeapSampleCadence::kIntervalMs==1000u,
                  "Heap review cadence drifted from audited 1 Hz maximum");
    {
        NativeOtaHeapSampleCadence cadence(100u);
        CHECK(cadence.due(100u));   // first cooperative opportunity only
        CHECK(!cadence.due(100u));
        CHECK(!cadence.due(1099u));
        CHECK(cadence.due(1100u));
        CHECK(!cadence.due(1101u));
        CHECK(cadence.due(2100u));
    }
    {
        // A long stalled loop does NOT cause catch-up samples.
        NativeOtaHeapSampleCadence cadence(500u);
        CHECK(cadence.due(500u));
        CHECK(cadence.due(10500u)); // exactly one attempt after 10 s gap
        CHECK(!cadence.due(10500u));
        CHECK(!cadence.due(11499u));
        CHECK(cadence.due(11500u));
    }
    {
        // Unsigned elapsed arithmetic remains correct across millis wrap.
        const uint32_t start=UINT32_MAX-500u;
        NativeOtaHeapSampleCadence cadence(start);
        CHECK(cadence.due(start));
        CHECK(!cadence.due(start+999u));
        CHECK(cadence.due(start+1000u));
        CHECK(!cadence.due(start+1001u));
    }
    std::cout<<"PASS: disconnected 1Hz heap cadence, no catch-up bursts, "
                "wrap-safe HOST ONLY NO TIMER NO DEVICE NO FLASH\n";
    return 0;
}
