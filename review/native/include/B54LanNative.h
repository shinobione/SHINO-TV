// SPDX-License-Identifier: GPL-3.0-or-later
#pragma once
#include "B54LanWeather.h"
#include "B53Diagnostic.h"
namespace B54LanNative {
void begin(B53Diagnostic::Journal&,const char* bootHex);
bool ready();bool acquire();void release();
uint8_t* buffer();
bool status(uint8_t kind,const uint8_t challenge[8]);
B54LanWeather::Result accept();
void poll();void invalidate();
void record(uint32_t code,uint32_t elapsedUs);
}
