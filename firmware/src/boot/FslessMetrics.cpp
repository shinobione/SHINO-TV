// SPDX-License-Identifier: GPL-3.0-or-later
#include "boot/FslessMetrics.h"
#include <cmath>

namespace {
constexpr uint32_t METRICS_STALE_MS = 6000;
FslessMetrics::Snapshot state;

bool bounded(JsonVariantConst input, const char* key,
             float minimum, float maximum, float& result) {
    JsonVariantConst value = input[key];
    if (!(value.is<float>() || value.is<double>() ||
          value.is<int>() || value.is<unsigned int>() ||
          value.is<long>() || value.is<unsigned long>())) return false;
    const float numeric = value.as<float>();
    if (!std::isfinite(numeric) || numeric < minimum || numeric > maximum) return false;
    result = numeric;
    return true;
}
} // namespace

namespace FslessMetrics {
bool apply(JsonVariantConst input, String& error) {
    if (!input.is<JsonObjectConst>() || !input["ok"].is<bool>() ||
        !input["ok"].as<bool>() || !input["gpu_available"].is<bool>()) {
        error = F("Expected healthy PC telemetry object with gpu_available boolean");
        return false;
    }
    Snapshot next{};
    if (!bounded(input, "cpu_usage", 0.0F, 100.0F, next.cpu) ||
        !bounded(input, "gpu_usage", 0.0F, 100.0F, next.gpu) ||
        !bounded(input, "memory_used_gb", 0.0F, 256.0F, next.memoryGb) ||
        !bounded(input, "gpu_vram_mb", 0.0F, 65536.0F, next.vramMb) ||
        !bounded(input, "gpu_temp_c", -40.0F, 130.0F, next.gpuTempC) ||
        !bounded(input, "gpu_power", 0.0F, 1200.0F, next.gpuPowerW)) {
        error = F("Missing, nonfinite or out-of-range numeric PC telemetry");
        return false;
    }
    next.gpuAvailable = input["gpu_available"].as<bool>();
    next.received = true;
    next.lastReceivedMs = millis();
    state = next; // Invalid payload never replaces the previous good sample.
    error = "";
    return true;
}

Snapshot snapshot() { return state; }

bool stale() {
    return !state.received || static_cast<uint32_t>(millis() - state.lastReceivedMs) > METRICS_STALE_MS;
}

void describe(JsonDocument& out) {
    out["mode"] = "FSLESS_PC_TELEMETRY_RAM_ONLY";
    out["received"] = state.received;
    out["stale"] = stale();
    out["ttl_seconds"] = METRICS_STALE_MS / 1000;
    out["cpu_usage"] = state.cpu;
    out["gpu_usage"] = state.gpu;
    out["memory_used_gb"] = state.memoryGb;
    out["gpu_vram_mb"] = state.vramMb;
    out["gpu_temp_c"] = state.gpuTempC;
    out["gpu_power"] = state.gpuPowerW;
    out["gpu_available"] = state.gpuAvailable;
    out["filesystem_or_eeprom_write_performed"] = false;
}
} // namespace FslessMetrics
