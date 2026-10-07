// SPDX-License-Identifier: GPL-3.0-or-later
#pragma once
#include "boot/M9NormalResources.h"
#include "boot/M9LittleFsMountProbe.h"
#include <cstdio>
#include <cstring>
#ifdef ARDUINO_ARCH_ESP8266
#define M9N_FORMAT snprintf_P
#define M9N_TEXT(text) PSTR(text)
#else
#define M9N_FORMAT std::snprintf
#define M9N_TEXT(text) text
#endif
namespace M9NormalStatusJson {
constexpr size_t BUFFER_BYTES = 512;
struct Snapshot {
    const M9NormalResources::Observation& resources;
    const M9LittleFsMountProbe::LittleFsMountProbeStatus& fs;
    bool config, ap;
};
// No clock, heap getter, stack getter/reset or private string enters this API.
inline int part(char* out, size_t capacity, unsigned index, const Snapshot& s) {
    const auto& r = s.resources; const auto& f = s.fs;
    if (index == 0) return M9N_FORMAT(out, capacity, M9N_TEXT(
        "{\"mode\":\"M9_NORMAL_STAGE_A\",\"boot_profile\":1,\"normal_qualification\":true,"
        "\"config_loaded_readonly\":%s,\"private_ap_ready\":%s,\"digest_auth_required\":true,"
        "\"api_identity_ram_only\":true,\"secure_storage_enabled\":false,\"eeprom_enabled\":false,"
        "\"rtc_writes_enabled\":false,\"sdk_wifi_persistence_enabled\":false,\"sta_enabled\":false,"
        "\"filesystem_writes_enabled\":false,\"static_fs_reads_enabled\":false,"),
        s.config ? "true" : "false", s.ap ? "true" : "false");
    if (index == 1) return M9N_FORMAT(out, capacity, M9N_TEXT(
        "\"native_ota_writer_enabled\":false,\"media_ingress_enabled\":false,\"legacy_mutation_routes_enabled\":false,"
        "\"telemetry_storage\":\"RAM_ONLY\",\"telemetry_ttl_ms\":6000,\"physical_authorization\":false,"
        "\"mount_attempted\":%s,\"autoformat_disabled\":%s,\"mounted\":%s,\"inventory_exact\":%s,"
        "\"config_seed_exact\":%s,\"checked_file_count\":%u,\"checked_payload_bytes\":%u,\"blocked_write_attempts\":%u,"),
        f.attempted ? "true" : "false", f.autoformat_disabled ? "true" : "false", f.mounted ? "true" : "false",
        f.inventory_exact ? "true" : "false", f.config_seed_exact ? "true" : "false",
        unsigned(f.checked_file_count), unsigned(f.checked_payload_bytes), unsigned(f.blocked_write_attempts));
    if (index == 2) return M9N_FORMAT(out, capacity, M9N_TEXT(
        "\"setup_cont_stack_start\":%u,\"setup_cont_stack_min\":%u,\"fs_config_cont_stack_start\":%u,"
        "\"fs_config_cont_stack_min\":%u,\"runtime_cont_stack_start\":%u,\"runtime_cont_stack_min\":%u,"
        "\"heap_after_fs\":%u,\"block_after_fs\":%u,\"frag_after_fs\":%u,\"heap_after_setup\":%u,"
        "\"block_after_setup\":%u,\"frag_after_setup\":%u,"),
        unsigned(r.setup_start), unsigned(r.setup_min), unsigned(r.fs_start), unsigned(r.fs_min),
        unsigned(r.runtime_start), unsigned(r.runtime_min), unsigned(r.after_fs.free), unsigned(r.after_fs.largest),
        unsigned(r.after_fs.fragmentation), unsigned(r.after_setup.free), unsigned(r.after_setup.largest), unsigned(r.after_setup.fragmentation));
    return M9N_FORMAT(out, capacity, M9N_TEXT(
        "\"free_heap\":%u,\"largest_block\":%u,\"fragmentation_percent\":%u,\"lowest_heap\":%u,\"lowest_block\":%u,"
        "\"highest_fragmentation_percent\":%u,\"resource_sample_count\":%u,\"rejected_sample_count\":%u,"
        "\"resource_measurements_valid\":%s,\"design_floors_observed\":%s,\"heap_floor\":20480,"
        "\"block_floor\":16384,\"fragmentation_ceiling\":25,\"continuation_floor\":2048}"),
        unsigned(r.latest.free), unsigned(r.latest.largest), unsigned(r.latest.fragmentation), unsigned(r.min_heap),
        unsigned(r.min_block), unsigned(r.max_frag), unsigned(r.samples), unsigned(r.rejected),
        r.valid ? "true" : "false", M9NormalResources::floors(r) ? "true" : "false");
}
template<class Sink>
#ifdef _MSC_VER
__declspec(noinline)
#else
__attribute__((noinline))
#endif
bool emit(const Snapshot& snapshot, Sink& sink) {
    char body[BUFFER_BYTES]; size_t total = 0;
    // Check every chunk before sending headers; no partial response on overflow.
    for (unsigned i = 0; i < 4; ++i) {
        const int length = part(body, sizeof(body), i, snapshot);
        if (length < 0 || size_t(length) >= sizeof(body)) return false;
        total += size_t(length);
    }
    sink.begin(total);
    for (unsigned i = 0; i < 4; ++i) {
        const int length = part(body, sizeof(body), i, snapshot);
        sink.write(body, size_t(length));
    }
    return true;
}
} // namespace M9NormalStatusJson
#undef M9N_FORMAT
#undef M9N_TEXT
