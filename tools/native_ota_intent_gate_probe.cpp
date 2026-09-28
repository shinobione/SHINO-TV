// SPDX-License-Identifier: GPL-3.0-or-later
// Pure-host unit probe: this NEVER links Arduino, ESP8266WebServer or Update.
#include "boot/NativeOtaIntentGate.h"
#include <array>
#include <cstdint>
#include <iostream>
#include <type_traits>

using ShinoNativeOta::IntentGate;
using ShinoNativeOta::TransferPhase;

#define CHECK(cond) do { if (!(cond)) { \
    std::cerr << "FAIL line " << __LINE__ << ": " #cond "\\n"; return 1; \
} } while (0)

constexpr uint32_t kPeer = 0xC0A80403;
constexpr uint32_t kOtherPeer = 0xC0A80404;
constexpr uint32_t kSize = 64'000 + 256 + 4;
constexpr std::array<uint8_t,16> kToken{{1,2,3,4,5,6,7,8,9,10,11,12,13,14,15,16}};
constexpr std::array<uint8_t,16> kOtherToken{{1,2,3,4,5,6,7,8,9,10,11,12,13,14,15,17}};
constexpr std::array<uint8_t,16> kEmptyToken{{}};
static_assert(!std::is_copy_constructible<IntentGate>::value, "single-use gate must not be cloned");
static_assert(!std::is_copy_assignable<IntentGate>::value, "single-use gate must not be copied");

int happyPath() {
    IntentGate gate;
    CHECK(gate.phase() == TransferPhase::Idle);
    CHECK(gate.arm(kPeer,kToken,kSize,100));
    CHECK(gate.phase() == TransferPhase::Armed);
    CHECK(!gate.arm(kPeer,kOtherToken,kSize,100)); // no second concurrent arm
    CHECK(gate.start(kPeer,kToken,kSize,101));
    uint8_t sample[4096]{};
    uint32_t offset=0;
    while (offset<kSize) {
        const size_t count = (kSize-offset > sizeof(sample)) ? sizeof(sample) : kSize-offset;
        CHECK(gate.acceptChunk(kPeer,kToken,sample,count,102 + offset/sizeof(sample)));
        offset += static_cast<uint32_t>(count);
    }
    CHECK(gate.receivedBytes()==kSize);
    CHECK(gate.finish(kPeer,kToken,kSize,130));
    CHECK(gate.phase()==TransferPhase::BytesCompleteAwaitingSignatureCheck);
    CHECK(!gate.finish(kPeer,kToken,kSize,131)); // cannot re-complete
    CHECK(!gate.acceptChunk(kPeer,kToken,sample,1,132));
    CHECK(!gate.arm(kPeer,kOtherToken,kSize,132));
    return 0;
}

int rejectInvalidArm() {
    IntentGate gate;
    CHECK(!gate.arm(0,kToken,kSize,0));
    CHECK(!gate.arm(kPeer,kEmptyToken,kSize,0));
    CHECK(!gate.arm(kPeer,kToken,IntentGate::kMinSignedTransportBytes-1,0));
    CHECK(!gate.arm(kPeer,kToken,IntentGate::kMaxSignedTransportBytes+1,0));
    CHECK(gate.phase()==TransferPhase::Idle);
    return 0;
}

int wrongBindingAndLength() {
    {
        IntentGate g; CHECK(g.arm(kPeer,kToken,kSize,10));
        CHECK(!g.start(kOtherPeer,kToken,kSize,11));
        CHECK(g.phase()==TransferPhase::Aborted);
        CHECK(!g.start(kPeer,kToken,kSize,12));
    }
    {
        IntentGate g; CHECK(g.arm(kPeer,kToken,kSize,10));
        CHECK(!g.start(kPeer,kOtherToken,kSize,11));
        CHECK(g.phase()==TransferPhase::Aborted);
    }
    {
        IntentGate g; CHECK(g.arm(kPeer,kToken,kSize,10));
        CHECK(!g.start(kPeer,kToken,kSize-1,11));
        CHECK(g.phase()==TransferPhase::Aborted);
    }
    return 0;
}

int duplicateStartAndNoRetry() {
    IntentGate g; CHECK(g.arm(kPeer,kToken,kSize,0));
    CHECK(g.start(kPeer,kToken,kSize,1));
    CHECK(!g.start(kPeer,kToken,kSize,2));
    CHECK(g.phase()==TransferPhase::Aborted);
    CHECK(!g.arm(kPeer,kOtherToken,kSize,3));
    return 0;
}

int malformedChunksAndDisconnect() {
    uint8_t bytes[4096]{};
    {
        IntentGate g; CHECK(g.arm(kPeer,kToken,kSize,0));
        CHECK(g.start(kPeer,kToken,kSize,1));
        CHECK(!g.acceptChunk(kPeer,kToken,bytes,0,2));
        CHECK(g.phase()==TransferPhase::Aborted);
    }
    {
        IntentGate g; CHECK(g.arm(kPeer,kToken,kSize,0));
        CHECK(g.start(kPeer,kToken,kSize,1));
        CHECK(!g.acceptChunk(kPeer,kToken,nullptr,1,2));
        CHECK(g.phase()==TransferPhase::Aborted);
    }
    {
        IntentGate g; CHECK(g.arm(kPeer,kToken,kSize,0));
        CHECK(g.start(kPeer,kToken,kSize,1));
        CHECK(!g.acceptChunk(kPeer,kToken,bytes,sizeof(bytes)+1,2));
        CHECK(g.phase()==TransferPhase::Aborted);
    }
    {
        IntentGate g; CHECK(g.arm(kPeer,kToken,kSize,0));
        CHECK(g.start(kPeer,kToken,kSize,1));
        CHECK(!g.acceptChunk(kOtherPeer,kToken,bytes,1,2));
        CHECK(g.phase()==TransferPhase::Aborted);
    }
    {
        IntentGate g; CHECK(g.arm(kPeer,kToken,kSize,0));
        CHECK(g.start(kPeer,kToken,kSize,1));
        CHECK(g.acceptChunk(kPeer,kToken,bytes,1,2));
        CHECK(!g.acceptChunk(kPeer,kOtherToken,bytes,1,3));
        CHECK(g.phase()==TransferPhase::Aborted);
    }
    {
        IntentGate g; CHECK(g.arm(kPeer,kToken,kSize,0));
        CHECK(g.start(kPeer,kToken,kSize,1));
        CHECK(g.acceptChunk(kPeer,kToken,bytes,1,2));
        g.abort(); // emulates client disconnect; no retry
        CHECK(g.phase()==TransferPhase::Aborted);
        CHECK(!g.acceptChunk(kPeer,kToken,bytes,1,3));
    }
    return 0;
}

int incompleteOverrunAndWrongReportedTotal() {
    uint8_t bytes[4096]{};
    {
        IntentGate g; CHECK(g.arm(kPeer,kToken,kSize,0));
        CHECK(g.start(kPeer,kToken,kSize,1));
        CHECK(g.acceptChunk(kPeer,kToken,bytes,1,2));
        CHECK(!g.finish(kPeer,kToken,kSize,3)); // early EOF
        CHECK(g.phase()==TransferPhase::Aborted);
    }
    {
        IntentGate g; CHECK(g.arm(kPeer,kToken,kSize,0));
        CHECK(g.start(kPeer,kToken,kSize,1));
        CHECK(g.acceptChunk(kPeer,kToken,bytes,4096,2));
        CHECK(!g.acceptChunk(kPeer,kToken,bytes,kSize-4096+1,3)); // oversized chunk fails
        CHECK(g.phase()==TransferPhase::Aborted);
    }
    {
        IntentGate g; CHECK(g.arm(kPeer,kToken,kSize,0));
        CHECK(g.start(kPeer,kToken,kSize,1));
        uint32_t offset=0;
        while(offset<kSize) {
            size_t count = (kSize-offset>sizeof(bytes))?sizeof(bytes):kSize-offset;
            CHECK(g.acceptChunk(kPeer,kToken,bytes,count,2+offset/4096));
            offset+=static_cast<uint32_t>(count);
        }
        CHECK(!g.acceptChunk(kPeer,kToken,bytes,1,50)); // one extra byte
        CHECK(g.phase()==TransferPhase::Aborted);
    }
    {
        IntentGate g; CHECK(g.arm(kPeer,kToken,kSize,0));
        CHECK(g.start(kPeer,kToken,kSize,1));
        uint32_t offset=0;
        while(offset<kSize) {
            size_t count = (kSize-offset>sizeof(bytes))?sizeof(bytes):kSize-offset;
            CHECK(g.acceptChunk(kPeer,kToken,bytes,count,2+offset/4096));
            offset+=static_cast<uint32_t>(count);
        }
        CHECK(!g.finish(kPeer,kToken,kSize-1,50)); // declared final total false
        CHECK(g.phase()==TransferPhase::Aborted);
    }
    return 0;
}

int timeoutsAndWraparound() {
    uint8_t b=0;
    {
        IntentGate g; CHECK(g.arm(kPeer,kToken,kSize,0));
        CHECK(!g.start(kPeer,kToken,kSize,IntentGate::kArmLifetimeMs));
        CHECK(g.phase()==TransferPhase::Aborted);
    }
    {
        IntentGate g; CHECK(g.arm(kPeer,kToken,kSize,0));
        CHECK(g.start(kPeer,kToken,kSize,1));
        CHECK(!g.checkTimeout(IntentGate::kStreamInactivityMs+1));
        CHECK(g.phase()==TransferPhase::Aborted);
    }
    {
        IntentGate g; CHECK(g.arm(kPeer,kToken,kSize,0xFFFFFF00u));
        CHECK(g.start(kPeer,kToken,kSize,0xFFFFFF10u));
        CHECK(g.acceptChunk(kPeer,kToken,&b,1,0x00000020u)); // millis wrap valid
        CHECK(g.phase()==TransferPhase::Streaming);
        CHECK(!g.checkTimeout(0x00003AC0u)); // 15000+ms inactivity
        CHECK(g.phase()==TransferPhase::Aborted);
    }
    {
        IntentGate g; CHECK(g.arm(kPeer,kToken,kSize,100));
        CHECK(g.start(kPeer,kToken,kSize,101));
        CHECK(g.acceptChunk(kPeer,kToken,&b,1,1000));
        CHECK(g.checkTimeout(1001)); // still active
        CHECK(g.phase()==TransferPhase::Streaming);
    }
    return 0;
}

int main() {
    if(happyPath() || rejectInvalidArm() || wrongBindingAndLength() ||
       duplicateStartAndNoRetry() || malformedChunksAndDisconnect() ||
       incompleteOverrunAndWrongReportedTotal() || timeoutsAndWraparound())
        return 1;
    std::cout << "PASS: 7 offline groups for bounded single-use OTA intent gate; "
                 "NO HTTP/flash/firmware writer.\n";
    return 0;
}
