// SPDX-License-Identifier: GPL-3.0-or-later
#pragma once
#include <cstddef>
#include <cstdint>
namespace M9LittleFsMountProbe {
constexpr size_t READ_BUFFER_BYTES = 256;
constexpr size_t STATUS_JSON_BYTES = 768;
struct LittleFsMountProbeStatus {
    bool attempted = false;
    bool autoformat_disabled = false;
    bool mounted = false;
    bool inventory_checked = false;
    bool inventory_exact = false;
    bool config_seed_exact = false;
    bool write_paths_compiled = false; // No reachable application storage writers.
    uint16_t checked_file_count = 0;
    uint32_t checked_payload_bytes = 0;
    uint32_t blocked_write_attempts = 0;
    uint32_t available_heap_after_mount = 0;
    uint32_t available_heap_after_inventory = 0;
    uint32_t minimum_observed_free_heap = 0;
    uint32_t filesystem_start = 0;
    uint32_t filesystem_end_exclusive = 0;
    uint32_t filesystem_bytes = 0;
};
static_assert(sizeof(LittleFsMountProbeStatus) <= 52, "Probe status must stay fixed/bounded");
static_assert(READ_BUFFER_BYTES <= 512, "Unreviewed streaming allocation");
void begin();
void poll();
bool json(char* output, size_t capacity);
const LittleFsMountProbeStatus& status();
} // namespace M9LittleFsMountProbe
