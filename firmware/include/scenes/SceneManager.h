// SPDX-License-Identifier: GPL-3.0-or-later
// SHINO // TV — native scene state. All updates live in RAM, never in LittleFS.
#pragma once

#include <Arduino.h>
#include <ArduinoJson.h>

class SceneManager {
   public:
    // Keep Times-Z's existing PC dashboard as the default when its URL is configured.
    static void begin(const char* metricsUrl);
    static void update();
    // Strict, bounded JSON. Rejects invalid payloads without replacing the previous scene.
    static bool apply(JsonVariantConst root, String& error);
    static void describe(JsonDocument& out);
};
