// SPDX-License-Identifier: GPL-3.0-or-later
#include "boot/ShinoBootProfile.h"
#if SHINO_BOOT_PROFILE == 2
#include "boot/M9LittleFsMountProbe.h"
#include "boot/M9ProbeManifest.h"
#include "boot/M9ProbeStream.h"
#include "display/DisplayManager.h"
#include <Arduino.h>
#include <LittleFS.h>
#include <bearssl/bearssl_hash.h>
#include <flash_hal.h>
#include <new>
#include <cstdio>
#include <cstring>

namespace M9LittleFsMountProbe {
namespace {
LittleFsMountProbeStatus result;
// Replace the default LittleFS implementation only in this dedicated profile.
// Defense in depth: read-only opens plus denied mutations AND denied physical
// prog/erase callbacks, including a hypothetical internal metadata repair.
class ReadOnlyImpl final : public littlefs_impl::LittleFSImpl {
public:
    ReadOnlyImpl() : LittleFSImpl(FS_PHYS_ADDR, FS_PHYS_SIZE, FS_PHYS_PAGE, FS_PHYS_BLOCK, 1) {
        _lfs_cfg.prog = denyProg;
        _lfs_cfg.erase = denyErase;
    }
    FileImplPtr open(const char* path, OpenMode mode, AccessMode access) override {
        if (mode != OM_DEFAULT || access != AM_READ) { denied(); return FileImplPtr(); }
        return LittleFSImpl::open(path, mode, access);
    }
    bool format() override { return denied(); }
    bool remove(const char*) override { return denied(); }
    bool rename(const char*, const char*) override { return denied(); }
    bool mkdir(const char*) override { return denied(); }
    bool rmdir(const char*) override { return denied(); }
private:
    static bool denied() { ++result.blocked_write_attempts; return false; }
    static int denyProg(const lfs_config*, lfs_block_t, lfs_off_t, const void*, lfs_size_t) {
        denied(); return LFS_ERR_IO;
    }
    static int denyErase(const lfs_config*, lfs_block_t) { denied(); return LFS_ERR_IO; }
};
static_assert(sizeof(ReadOnlyImpl) <= 512, "Unreviewed persistent FS adapter allocation");

void observeHeap() {
    const uint32_t heap = ESP.getFreeHeap();
    if (!result.minimum_observed_free_heap || heap < result.minimum_observed_free_heap)
        result.minimum_observed_free_heap = heap;
}

void fail(const __FlashStringHelper* reason) {
    Serial.print(F("M9 FS PROBE FAIL: ")); Serial.println(reason);
    DisplayManager::drawTextWrapped(8, 8, F("FS PROBE FAILED"), 1, LCD_RED, LCD_BLACK, false);
    observeHeap(); // AP/status/telemetry remain available; no retry/repair/reset.
}

struct Sha256 {
    br_sha256_context context;
    void begin() { br_sha256_init(&context); }
    void update(const void* data, size_t size) { br_sha256_update(&context, data, size); }
    void end(uint8_t output[32]) { br_sha256_out(&context, output); }
};
static_assert(sizeof(Sha256) <= 128, "Unreviewed hash context growth");
// One fixed instance exists only in profile 2. No payload scratch on cont stack.
M9ProbeStream::Workspace<Sha256> payloadWorkspace;
static_assert(sizeof(payloadWorkspace) <= 512, "Unreviewed persistent payload scratch growth");

M9ProbeManifest::Entry entry(size_t index) {
    M9ProbeManifest::Entry value;
    memcpy_P(&value, &M9ProbeManifest::FILES[index], sizeof(value));
    return value;
}
bool knownFile(const char* path, uint32_t& seen) {
    for (size_t i = 0; i < M9ProbeManifest::FILE_COUNT; ++i) {
        const auto pin = entry(i);
        if (std::strcmp(path, pin.path) == 0) {
            const uint32_t mask = 1UL << i;
            if (seen & mask) return false;
            seen |= mask;
            return true;
        }
    }
    return false;
}
bool exactInventory() {
    static const char* const directories[] = {"/", "/web", "/web/css", "/web/js"};
    uint32_t seen = 0;
    uint8_t entries = 0;
    uint8_t directoryMask = 0;
    for (const char* directory : directories) {
        Dir dir = LittleFS.openDir(directory);
        while (dir.next()) {
            if (++entries > M9ProbeManifest::FILE_COUNT + 3) return false;
            const String name = dir.fileName(); // Core names bounded by LFS_NAME_MAX=32.
            if (!name.length() || name.length() > 32 || name.indexOf('/') >= 0) return false;
            char path[64];
            const int length = snprintf(path, sizeof(path), "%s%s%s", directory,
                std::strcmp(directory, "/") == 0 ? "" : "/", name.c_str());
            if (length <= 0 || static_cast<size_t>(length) >= sizeof(path)) return false;
            if (dir.isFile()) {
                if (!knownFile(path, seen)) return false;
            } else if (dir.isDirectory()) {
                uint8_t bit = 0;
                for (uint8_t i = 1; i < 4; ++i)
                    if (std::strcmp(path, directories[i]) == 0) bit = 1U << (i - 1);
                if (!bit || (directoryMask & bit)) return false;
                directoryMask |= bit;
            } else return false;
            observeHeap(); yield();
        }
    }
    return seen == ((1UL << M9ProbeManifest::FILE_COUNT) - 1) && directoryMask == 7;
}
bool checkPayloads() {
    for (size_t i = 0; i < M9ProbeManifest::FILE_COUNT; ++i) {
        const auto pin = entry(i);
        if (!LittleFS.exists(pin.path)) return false;
        File file = LittleFS.open(pin.path, "r");
        if (!file || !file.isFile() || file.size() != pin.bytes) return false;
        const bool config = std::strcmp(pin.path, "/config.json") == 0;
        const auto seed = [config](uint32_t offset, const uint8_t* bytes, size_t size) {
            if (!config) return true;
            return offset + size <= M9ProbeManifest::CONFIG_BYTES &&
                memcmp_P(bytes, M9ProbeManifest::CONFIG_SEED + offset, size) == 0;
        };
        const bool exact = M9ProbeStream::validate(file, pin.bytes, pin.sha256, payloadWorkspace, seed,
            []() { observeHeap(); yield(); }, result.checked_payload_bytes);
        file.close();
        if (!exact || result.blocked_write_attempts) return false;
        if (config) result.config_seed_exact = true;
        ++result.checked_file_count;
    }
    return result.config_seed_exact;
}
const char* boolean(bool value) { return value ? "true" : "false"; }
} // namespace

void begin() {
    if (result.attempted) return; // A failed attempt cannot become a retry.
    result.attempted = true;
    result.filesystem_start = FS_PHYS_ADDR;
    result.filesystem_bytes = FS_PHYS_SIZE;
    result.filesystem_end_exclusive = FS_PHYS_ADDR + FS_PHYS_SIZE;
    observeHeap();
    if (ESP.getFlashChipRealSize() != 0x400000 || FS_PHYS_ADDR != 0x200000 ||
        FS_PHYS_SIZE != 2072576 || FS_PHYS_BLOCK != 8192 || FS_PHYS_PAGE != 256) {
        fail(F("GEOMETRY")); return;
    }
    ReadOnlyImpl* implementation = new (std::nothrow) ReadOnlyImpl;
    if (!implementation) { fail(F("ALLOCATION")); return; }
    LittleFS = FS(FSImplPtr(implementation));
    if (!LittleFS.setConfig(LittleFSConfig(false))) {
        fail(F("AUTOFORMAT_DISABLE")); return;
    }
    result.autoformat_disabled = true;
    result.mounted = LittleFS.begin(); // Exactly one call; failure stays failure.
    result.available_heap_after_mount = ESP.getFreeHeap();
    observeHeap();
    if (!result.mounted) { fail(F("MOUNT")); return; }
    result.inventory_checked = true;
    result.inventory_exact = exactInventory() && checkPayloads() && !result.blocked_write_attempts;
    result.available_heap_after_inventory = ESP.getFreeHeap();
    observeHeap();
    if (!result.inventory_exact) { fail(F("INVENTORY_OR_PAYLOAD")); return; }
    Serial.printf("M9 FS PROBE PASS: files=%u bytes=%u writes=%u heap=%u/%u min=%u\n",
        result.checked_file_count, result.checked_payload_bytes, result.blocked_write_attempts,
        result.available_heap_after_mount, result.available_heap_after_inventory,
        result.minimum_observed_free_heap);
}
void poll() { observeHeap(); }
const LittleFsMountProbeStatus& status() { return result; }
bool json(char* output, size_t capacity) {
#if SHINO_M9_MOUNT_PROBE_RESOURCE_DIAGNOSTICS == 0
    observeHeap();
#endif
    const int length = snprintf(output, capacity,
        "{\"attempted\":%s,\"autoformat_disabled\":%s,\"mounted\":%s,"
        "\"inventory_checked\":%s,\"inventory_exact\":%s,\"checked_file_count\":%u,"
        "\"checked_payload_bytes\":%u,\"config_seed_exact\":%s,\"write_paths_compiled\":false,"
        "\"blocked_write_attempts\":%u,\"available_heap_after_mount\":%u,"
        "\"available_heap_after_inventory\":%u,\"minimum_observed_free_heap\":%u,"
        "\"filesystem_start\":%u,\"filesystem_end_exclusive\":%u,\"filesystem_bytes\":%u}",
        boolean(result.attempted), boolean(result.autoformat_disabled), boolean(result.mounted),
        boolean(result.inventory_checked), boolean(result.inventory_exact), result.checked_file_count,
        result.checked_payload_bytes, boolean(result.config_seed_exact), result.blocked_write_attempts,
        result.available_heap_after_mount, result.available_heap_after_inventory,
        result.minimum_observed_free_heap, result.filesystem_start, result.filesystem_end_exclusive,
        result.filesystem_bytes);
    return length > 0 && static_cast<size_t>(length) < capacity;
}
} // namespace M9LittleFsMountProbe
#endif
