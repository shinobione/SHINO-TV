// SPDX-License-Identifier: GPL-3.0-or-later
#pragma once
#include "B53Diagnostic.h"
namespace B53Integrated {
void begin(B53Diagnostic::Journal& journal);
void critical(); // Before server/Digest/OTA/transition work; no heap inspection.
void poll(bool ota,bool incoming,bool linkFresh);
void linkAccepted(uint32_t latencyMs);
void observe(uint32_t heap,uint32_t block,uint8_t frag,uint32_t stack);
}
