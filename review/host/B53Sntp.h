// SPDX-License-Identifier: GPL-3.0-or-later
#pragma once
#include <stdint.h>
#include <display/SceneEngine.h>
namespace B53Sntp {
void begin();
void poll(uint32_t now);
bool current(uint32_t now,uint32_t& utc);
bool view(uint32_t now,ArtworkPilot::ClockData& out);
}
