// SPDX-License-Identifier: GPL-3.0-or-later
#pragma once
#include <display/ClockFoundation.h>
#include "ClockFreshness.h"
namespace B52Clock {
constexpr size_t FRAME_BYTES=ClockFreshness::FRAME_BYTES;
bool challenge(uint32_t now);
const uint8_t* bootToken();
const uint8_t* challengeToken();
bool synchronize(const uint8_t* frame,size_t n,uint32_t started,uint32_t now,
    const char* password,ClockFreshness::Workspace& workspace);
#ifdef HOST_MOCK
void resetForTest();
#endif
ClockFoundation::Snapshot snapshot(uint32_t now);
void refreshMetrics();
void step(uint32_t now);
}

