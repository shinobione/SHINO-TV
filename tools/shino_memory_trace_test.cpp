// SPDX-License-Identifier: GPL-3.0-or-later
// Host-only sanity tests for the real no-allocation maintenance tracer.
#include "ShinoMemoryTrace.h"
#include <cassert>
int main() {
    using namespace ShinoInstall;
    MemoryTrace trace;
    assert(!trace.has(TracePoint::Normal));
    assert(!trace.anyFailure());
    trace.add(TracePoint::Normal,{30224,30008,3248,1});
    trace.add(TracePoint::Normal,{27000,26000,3100,4});
    const auto& normal=trace.at(TracePoint::Normal);
    assert(normal.samples==2 && normal.minHeap==27000);
    assert(normal.minBlock==26000 && normal.minStack==3100 && normal.maxFrag==4);
    assert(!normal.failed);
    trace.add(TracePoint::ListenerReady,{27000,25000,3000,6});
    assert(trace.has(TracePoint::ListenerReady));
    trace.add(TracePoint::DuringStaging,{20479,18000,2200,2});
    assert(trace.anyFailure());
    assert(trace.at(TracePoint::DuringStaging).failed==1);
    // No false certification: an unsampled point retains the unobserved sentinel.
    assert(!trace.has(TracePoint::BeforeCommit));
    assert(trace.at(TracePoint::BeforeCommit).minHeap==UINT32_MAX);
    trace.clear();
    assert(!trace.anyFailure() && !trace.has(TracePoint::Normal));
    return 0;
}
