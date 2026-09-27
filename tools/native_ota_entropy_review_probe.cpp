// SPDX-License-Identifier: GPL-3.0-or-later
// Host-only deterministic negative testing of the one-attempt AP/entropy gate.
// These are NOT real device RF samples, authentication or network requests.
#include "boot/NativeOtaEntropyReview.h"
#include <cstddef>
#include <cstdint>
#include <iostream>
using namespace ShinoNativeOta;
#define CHECK(x) do { if(!(x)) { std::cerr<<"FAIL "<<__LINE__<<": "<<#x<<"\n"; return 1; } } while(0)

struct FixtureSource {
    static bool ap;
    static bool shouldFail;
    static unsigned int mode;
    static unsigned int fillCalls;
    static bool privateApReady() {return ap;}
    static bool fill(uint8_t* dest,size_t n) {
        ++fillCalls;
        if(shouldFail || !dest || n!=32u) return false;
        for(size_t i=0;i<n;++i) {
            if(mode==1u) dest[i]=0u; // all-zero
            else if(mode==2u) dest[i]=static_cast<uint8_t>((i%16u)+1u); // nonce == opaque
            else dest[i]=static_cast<uint8_t>(i+1u);
        }
        return true;
    }
};
bool FixtureSource::ap=false;
bool FixtureSource::shouldFail=false;
unsigned int FixtureSource::mode=0u;
unsigned int FixtureSource::fillCalls=0u;

using Gate=NativeOtaEntropyReview<FixtureSource>;

int main() {
    DigestChallengePreview p{};
    {
        FixtureSource::ap=false;
        Gate g;
        CHECK(!g.preview(p));
        CHECK(FixtureSource::fillCalls==0u);
        CHECK(p.wwwAuthenticate[0]=='\0');
        FixtureSource::ap=true;
        CHECK(!g.preview(p)); // fail permanently; never retry same gate
        CHECK(FixtureSource::fillCalls==0u);
    }
    {
        FixtureSource::ap=true;FixtureSource::shouldFail=true;
        Gate g;
        CHECK(!g.preview(p));
        CHECK(p.nonce[0]=='\0');
        CHECK(p.wwwAuthenticate[0]=='\0');
        CHECK(!g.preview(p));
        CHECK(FixtureSource::fillCalls==1u);
    }
    FixtureSource::shouldFail=false;
    for(unsigned int mode : {1u,2u}) {
        FixtureSource::mode=mode;
        Gate g;
        CHECK(!g.preview(p));
        CHECK(p.nonce[0]=='\0');
        CHECK(p.wwwAuthenticate[0]=='\0');
        CHECK(!g.preview(p));
    }
    {
        FixtureSource::mode=0u;
        Gate g;
        CHECK(g.preview(p));
        CHECK(std::string(p.nonce.data())=="0102030405060708090a0b0c0d0e0f10");
        CHECK(std::string(p.opaque.data())=="1112131415161718191a1b1c1d1e1f20");
        CHECK(std::string(p.wwwAuthenticate.data()).find(
            "algorithm=SHA-256, qop=\"auth\"")!=std::string::npos);
        CHECK(!g.preview(p));
        CHECK(p.wwwAuthenticate[0]=='\0'); // never reuse earlier output
    }
    std::cout<<"PASS: AP readiness before entropy, one attempt only, failed/zero/equal "
                "entropy denied, header preview only. HOST ONLY NO HTTP/FLASH.\n";
    return 0;
}
