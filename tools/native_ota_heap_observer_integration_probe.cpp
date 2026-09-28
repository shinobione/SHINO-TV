// SPDX-License-Identifier: GPL-3.0-or-later
// HOST ONLY integration of prospective cadence + bounded heap accumulator.
// The fake source count proves no sensor read occurs between due() events.
// No ESP, network, timer, endpoint, persistence, device or flash.
#include "boot/NativeOtaHeapReview.h"
#include "boot/NativeOtaHeapSampleCadence.h"
#include <cstdint>
#include <iostream>
using namespace ShinoNativeOta;
#define CHECK(x) do {if(!(x)){std::cerr<<"FAIL "<<__LINE__<<": "<<#x<<"\n";return 1;}}while(0)

struct CountingSource {
    uint32_t reads=0u;
    bool read(uint32_t& freeBytes,uint32_t& largest,uint8_t& frag) {
        ++reads;
        freeBytes=32000u-(reads*10u);
        largest=28000u-(reads*20u);
        frag=static_cast<uint8_t>(10u+reads);
        return true;
    }
};

int main() {
    CountingSource source{};
    NativeOtaHeapReview<CountingSource> review(source);
    NativeOtaHeapSampleCadence cadence(100u);

    auto poll=[&](uint32_t now) {
        if(cadence.due(now))
            return review.capture();
        return false;
    };

    CHECK(poll(100u));
    CHECK(source.reads==1u && review.summary().samples==1u);

    // Hundreds of cooperative loop calls within the same second MUST NOT
    // touch the heap sensor or mutate the observation summary.
    for(uint32_t now=101u;now<1100u;++now)
        CHECK(!poll(now));
    CHECK(source.reads==1u && review.summary().samples==1u);

    CHECK(poll(1100u));
    CHECK(source.reads==2u && review.summary().samples==2u);

    // Ten seconds of scheduler stall -> exactly one read when loop resumes.
    CHECK(poll(11100u));
    CHECK(source.reads==3u && review.summary().samples==3u);
    CHECK(!poll(11100u));
    CHECK(source.reads==3u);

    const auto sum=review.summary();
    CHECK(sum.first.freeBytes==31990u);
    CHECK(sum.latest.freeBytes==31970u);
    CHECK(sum.lowestObservedFreeBytes==31970u);
    CHECK(sum.lowestObservedLargestBlockBytes==27940u);
    CHECK(sum.highestObservedFragmentationPercent==13u);

    std::cout<<"PASS: cadence gates every heap source read; no subsecond reads, "
                "no catch-up burst, observed-only summary HOST ONLY NO DEVICE NO FLASH\n";
    return 0;
}
