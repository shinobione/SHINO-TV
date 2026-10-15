// SPDX-License-Identifier: GPL-3.0-or-later
#pragma once
#include <stdint.h>
namespace B53WeatherGate {
// Extra headroom for BearSSL's secondary stack, X509 and MFLN buffers.
// These are conservative PRE-connection requirements, not proof of TLS peaks.
constexpr uint32_t HEAP_MIN=36864, BLOCK_MIN=32768, STACK_MIN=3072;
constexpr uint8_t FRAG_MAX=20;
constexpr uint32_t PERIOD_MS=1800000;
inline bool allowed(bool configured,bool sta,bool ntp,bool metricsStale,
                    bool otaBusy,bool requestPending,uint32_t heap,
                    uint32_t block,uint32_t stack,uint8_t frag){
 return configured&&sta&&ntp&&metricsStale&&!otaBusy&&!requestPending&&
   heap>=HEAP_MIN&&block>=BLOCK_MIN&&stack>=STACK_MIN&&frag<=FRAG_MAX;
}
}
