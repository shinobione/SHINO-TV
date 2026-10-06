// SPDX-License-Identifier: GPL-3.0-or-later
#pragma once
#include "boot/M9ResourceObserver.h"
#include <cstddef>
#include <cstdio>
#include <cstring>
#if defined(ESP8266)
#include <pgmspace.h>
#define M9_RESOURCE_FORMAT_STORAGE PROGMEM
#define M9_RESOURCE_SNPRINTF snprintf_P
#else
#define M9_RESOURCE_FORMAT_STORAGE
#define M9_RESOURCE_SNPRINTF std::snprintf
#endif
#if defined(_MSC_VER)
#define M9_RESOURCE_NOINLINE __declspec(noinline)
#else
#define M9_RESOURCE_NOINLINE __attribute__((noinline))
#endif
namespace M9MountProbeResources {
constexpr char SUFFIX_FORMAT[] M9_RESOURCE_FORMAT_STORAGE =
    ",\"resource_diagnostics_enabled\":true,\"resource_measurements_valid\":%s,"
    "\"mount_phase_cont_stack_start\":%u,\"mount_phase_cont_stack_min_free\":%u,"
    "\"heap_after_probe_free\":%u,\"heap_after_probe_largest_block\":%u,"
    "\"heap_after_probe_fragmentation\":%u,\"runtime_cont_stack_start\":%u,"
    "\"runtime_min_cont_stack_free\":%u,\"resource_sample_count\":%u,"
    "\"latest_free_heap\":%u,\"latest_largest_free_block\":%u,"
    "\"latest_fragmentation_percent\":%u,\"lowest_observed_free_heap\":%u,"
    "\"lowest_observed_largest_free_block\":%u,"
    "\"highest_observed_fragmentation_percent\":%u,\"resource_rejected_sample_count\":%u}";
// Exact type-level bound: twelve uint32_t values use 10 digits, three uint8_t
// fragmentation values use 3 digits, and false uses 5 chars. Includes final '}'.
constexpr size_t SUFFIX_MAX_BYTES = sizeof(SUFFIX_FORMAT) - 1 + 12 * 8 + 3 * 1 + 3;
constexpr size_t JSON_CHUNK_BYTES = 768;
static_assert(SUFFIX_MAX_BYTES + 1 <= JSON_CHUNK_BYTES, "Resource JSON bound exceeds fixed buffer");
inline bool suffix(const Observation& s, char* output, size_t capacity, size_t& size) {
    size = 0;
    if (!output || capacity == 0) return false;
    const int n = M9_RESOURCE_SNPRINTF(output, capacity, SUFFIX_FORMAT,
        s.resource_measurements_valid ? "true" : "false",
        static_cast<unsigned>(s.mount_phase_cont_stack_start),
        static_cast<unsigned>(s.mount_phase_cont_stack_min_free),
        static_cast<unsigned>(s.heap_after_probe.free), static_cast<unsigned>(s.heap_after_probe.largest),
        static_cast<unsigned>(s.heap_after_probe.fragmentation),
        static_cast<unsigned>(s.runtime_cont_stack_start), static_cast<unsigned>(s.runtime_min_cont_stack_free),
        static_cast<unsigned>(s.resource_sample_count), static_cast<unsigned>(s.latest.free),
        static_cast<unsigned>(s.latest.largest), static_cast<unsigned>(s.latest.fragmentation),
        static_cast<unsigned>(s.lowest_observed_free_heap),
        static_cast<unsigned>(s.lowest_observed_largest_free_block),
        static_cast<unsigned>(s.highest_observed_fragmentation_percent),
        static_cast<unsigned>(s.resource_rejected_sample_count));
    if (n <= 0 || static_cast<size_t>(n) >= capacity) { output[0] = '\0'; return false; }
    size = static_cast<size_t>(n);
    return true;
}
// Separate noinline frame prevents combining two 768-byte buffers in one frame.
// Validate BOTH chunks before headers/body are sent; sink sees no partial JSON
// on format overflow. Pure cached scalars only: no ESP/heap/stack sampling here.
template<class Sink> M9_RESOURCE_NOINLINE bool emit(
    const Observation& state, const char* base, size_t baseSize, Sink& sink) {
    char extension[JSON_CHUNK_BYTES];
    size_t bytes = 0;
    if (!base || baseSize < 2 || base[0] != '{' || base[baseSize - 1] != '}' ||
        !suffix(state, extension, sizeof(extension), bytes)) return false;
    sink.begin(baseSize - 1 + bytes);
    sink.write(base, baseSize - 1); // Replace original closing brace with cached suffix.
    sink.write(extension, bytes);
    return true;
}
} // namespace M9MountProbeResources
#undef M9_RESOURCE_FORMAT_STORAGE
#undef M9_RESOURCE_SNPRINTF
#undef M9_RESOURCE_NOINLINE
