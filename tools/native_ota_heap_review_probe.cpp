// SPDX-License-Identifier: GPL-3.0-or-later
// Deterministic HOST ONLY regression of the disconnected heap observation
// model; no ESP, network, device access, real measurement or firmware writer.
#include "boot/NativeOtaHeapReview.h"
#include <array>
#include <cstddef>
#include <cstdint>
#include <iostream>
using namespace ShinoNativeOta;
#define CHECK(x) do {if(!(x)){std::cerr<<"FAIL "<<__LINE__<<": "<<#x<<"\n";return 1;}}while(0)

struct FakeSource {
    const NativeOtaHeapSample* values=nullptr;
    size_t count=0u,at=0u;
    bool read(uint32_t& freeBytes,uint32_t& largest,uint8_t& frag) {
        if(at>=count)return false;
        const auto s=values[at++];
        freeBytes=s.freeBytes;largest=s.largestFreeBlockBytes;
        frag=s.fragmentationPercent;
        return true;
    }
};
struct ConstantSource {
    bool read(uint32_t& freeBytes,uint32_t& largest,uint8_t& frag) {
        freeBytes=30000u;largest=22000u;frag=25u;
        return true;
    }
};

int main() {
    static_assert(NativeOtaHeapReview<FakeSource>::kMaxSamples==1024u,
                  "Only a bounded sample count may be retained");
    static_assert(sizeof(NativeOtaHeapReview<FakeSource>)<=64u,
                  "Host review model unexpectedly expanded");
    {
        constexpr std::array<NativeOtaHeapSample,4> samples{{
            {32184u,30000u,8u},{32016u,27000u,12u},
            {31960u,24000u,18u},{32128u,28000u,10u}
        }};
        FakeSource source{samples.data(),samples.size(),0u};
        NativeOtaHeapReview<FakeSource> review(source);
        for(size_t i=0;i<samples.size();++i)CHECK(review.capture());
        const auto result=review.summary();
        CHECK(result.samples==4u);
        CHECK(result.first.freeBytes==32184u);
        CHECK(result.latest.freeBytes==32128u);
        CHECK(result.lowestObservedFreeBytes==31960u);
        CHECK(result.lowestObservedLargestBlockBytes==24000u);
        CHECK(result.highestObservedFragmentationPercent==18u);
        CHECK(!review.capture()); // exhausted sensor cannot synthesize sample
        CHECK(review.summary().samples==4u);
    }
    {
        // Entire invalid observation is ignored, including a missing sample,
        // not coerced to zero or turned into a fictitious minimum.
        constexpr std::array<NativeOtaHeapSample,7> observations{{
            {0u,0u,0u},{30000u,0u,0u},{30000u,30001u,0u},
            {30000u,20000u,101u},{262145u,20000u,10u},
            {30000u,20000u,25u},{29000u,19000u,35u}
        }};
        FakeSource source{observations.data(),observations.size(),0u};
        NativeOtaHeapReview<FakeSource> review(source);
        for(size_t i=0u;i<5u;++i) {
            CHECK(!review.capture());
            CHECK(review.summary().samples==0u);
        }
        CHECK(review.capture());
        CHECK(review.capture());
        CHECK(review.summary().samples==2u);
        CHECK(review.summary().first.freeBytes==30000u);
        CHECK(review.summary().lowestObservedFreeBytes==29000u);
        CHECK(review.summary().lowestObservedLargestBlockBytes==19000u);
        CHECK(review.summary().highestObservedFragmentationPercent==35u);
        CHECK(!review.capture());
        CHECK(review.summary().samples==2u);
    }
    {
        ConstantSource source{};
        NativeOtaHeapReview<ConstantSource> review(source);
        for(size_t i=0u;i<NativeOtaHeapReview<ConstantSource>::kMaxSamples;++i)
            CHECK(review.capture());
        CHECK(!review.capture());
        const auto sum=review.summary();
        CHECK(sum.samples==1024u && sum.lowestObservedFreeBytes==30000u);
        CHECK(sum.lowestObservedLargestBlockBytes==22000u);
        CHECK(sum.highestObservedFragmentationPercent==25u);
    }
    std::cout<<"PASS: real bounded host C++ heap review, minimum OBSERVED only, "
                "fragmentation/max block and invalid-source refusal, "
                "HOST ONLY NO ROUTES NO DEVICE NO FLASH\n";
    return 0;
}
