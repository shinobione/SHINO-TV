// SPDX-License-Identifier: GPL-3.0-or-later
#pragma once
#include <stdint.h>
namespace B53WeatherHttps {
void begin(const char* latitude,const char* longitude);
void poll(uint32_t now,bool otaBusy,bool httpBusy,bool metricsStale);
}
