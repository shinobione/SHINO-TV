// SPDX-License-Identifier: GPL-3.0-or-later
#pragma once

#include <Arduino.h>
#include <ArduinoJson.h>

// Volatile RAM-only PC telemetry. No LittleFS, EEPROM, SPI flash or network code.
namespace FslessMetrics {
struct Snapshot {
    float cpu = 0.0F;
    float gpu = 0.0F;
    float memoryGb = 0.0F;
    float vramMb = 0.0F;
    float gpuTempC = 0.0F;
    float gpuPowerW = 0.0F;
    bool gpuAvailable = false;
    bool received = false;
    uint32_t lastReceivedMs = 0;
};
bool apply(JsonVariantConst input, String& error);
Snapshot snapshot();
bool stale();
void describe(JsonDocument& out);
} // namespace FslessMetrics
