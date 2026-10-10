// SPDX-License-Identifier: GPL-3.0-or-later
#pragma once
// Tiny allocation-free resource trace; cannot initiate OTA or device IO.
#include <stdint.h>
#include "ShinoWifiPolicy.h"
namespace ShinoInstall {
enum class TracePoint : uint8_t {
    Normal=0, HttpClosed, ListenerReady, ClientAccepted, BeforeStaging,
    DuringStaging, BeforeCommit, Recovery, Restored, Count
};
struct TraceSlot {
    uint32_t minHeap=UINT32_MAX, minBlock=UINT32_MAX, minStack=UINT32_MAX;
    uint16_t samples=0;
    uint8_t maxFrag=0, failed=0;
};
class MemoryTrace {
public:
    static constexpr unsigned Count=static_cast<unsigned>(TracePoint::Count);
    void add(TracePoint point, Budget b) {
        unsigned i=static_cast<unsigned>(point);
        if(i>=Count)return;
        TraceSlot& s=slots_[i];
        if(s.samples!=UINT16_MAX)++s.samples;
        if(b.heap<s.minHeap)s.minHeap=b.heap;
        if(b.block<s.minBlock)s.minBlock=b.block;
        if(b.stack<s.minStack)s.minStack=b.stack;
        if(b.frag>s.maxFrag)s.maxFrag=b.frag;
        if(!b.safe())s.failed=1;
        if(!b.safe())failed_=true;
    }
    const TraceSlot& at(TracePoint point) const {return slots_[static_cast<unsigned>(point)];}
    bool anyFailure() const {return failed_;}
    bool has(TracePoint point) const {return at(point).samples!=0;}
    void clear() { *this=MemoryTrace{}; }
private:
    TraceSlot slots_[Count]{};
    bool failed_=false;
};
static_assert(sizeof(MemoryTrace)<=192,"Read-only resource trace must stay tiny");
}
