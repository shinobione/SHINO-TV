// SPDX-License-Identifier: GPL-3.0-or-later
// SHINO // TV native scenes, based on Times-Z's GPL-3.0-or-later firmware.
// Bounded ASCII fields; ESP8266 built-in bitmap font has no general Unicode support.
#include "scenes/SceneManager.h"

#include <Arduino_GFX_Library.h>
#include <cstring>

#include "dashboard/DashboardManager.h"
#include "display/DisplayManager.h"

namespace {
enum class Kind : uint8_t { LEGACY, METRICS, MUSIC, AGENT, RELEASE };

struct Scene {
    Kind kind = Kind::LEGACY;
    char artist[33]{};
    char track[49]{};
    char status[19]{};
    char task[57]{};
    uint8_t progress = 0;
    uint16_t days = 0;
};

constexpr uint32_t STALE_AFTER_MS = 60000;
constexpr uint16_t BG = 0x0841;
constexpr uint16_t PANEL = 0x18C3;
constexpr uint16_t MUTED = 0xA514;
constexpr uint16_t GOLD = 0xE54B;
constexpr uint16_t WHITE = 0xFFFF;
constexpr uint16_t GREEN = 0xA676;
constexpr uint16_t TRACK = 0x3186;

Scene active;
String pcMetricsUrl;
bool metricsConfigured = false;
bool frameDirty = false;
bool contentDirty = false;
bool staleRendered = false;
uint32_t lastPushMs = 0;

const char* name(Kind kind) {
    switch (kind) {
        case Kind::METRICS: return "metrics";
        case Kind::MUSIC: return "music";
        case Kind::AGENT: return "agent";
        case Kind::RELEASE: return "release";
        default: return "legacy";
    }
}

const char* title(Kind kind) {
    switch (kind) {
        case Kind::MUSIC: return "NOW PLAYING";
        case Kind::AGENT: return "CODEX STATUS";
        case Kind::RELEASE: return "NEXT RELEASE";
        case Kind::METRICS: return "PC HEALTH";
        default: return "SHINO // TV";
    }
}

bool copyPrintable(JsonObjectConst object, const char* key, char* destination, size_t capacity, String& error) {
    JsonVariantConst value = object[key];
    if (!value.is<const char*>()) {
        error = String("Missing/invalid string: ") + key;
        return false;
    }
    const char* text = value.as<const char*>();
    const size_t size = strlen(text);
    if (size == 0 || size >= capacity) {
        error = String("String length out of range: ") + key;
        return false;
    }
    for (size_t i = 0; i < size; ++i) {
        const unsigned char character = static_cast<unsigned char>(text[i]);
        if (character < 32 || character > 126) {
            error = String("ASCII printable text required: ") + key;
            return false;
        }
    }
    memcpy(destination, text, size + 1);
    return true;
}

bool readNumber(JsonObjectConst object, const char* key, int maximum, int& out, String& error) {
    JsonVariantConst value = object[key];
    if (!value.is<int>()) {
        error = String("Missing/invalid integer: ") + key;
        return false;
    }
    const int number = value.as<int>();
    if (number < 0 || number > maximum) {
        error = String("Out of range: ") + key;
        return false;
    }
    out = number;
    return true;
}

bool fieldAllowed(Kind kind, const char* field) {
    if (strcmp(field, "kind") == 0) return true;
    if (kind == Kind::MUSIC) {
        return strcmp(field, "artist") == 0 || strcmp(field, "track") == 0 || strcmp(field, "progress") == 0;
    }
    if (kind == Kind::AGENT) {
        return strcmp(field, "status") == 0 || strcmp(field, "task") == 0 || strcmp(field, "progress") == 0;
    }
    if (kind == Kind::RELEASE) {
        return strcmp(field, "artist") == 0 || strcmp(field, "track") == 0 || strcmp(field, "days") == 0;
    }
    return false;
}

void printText(Arduino_GFX* gfx, const char* text, int16_t x, int16_t y, uint8_t scale,
               uint16_t foreground, uint16_t background, size_t maxChars) {
    char buffer[49]{};
    const size_t n = strnlen(text, maxChars);
    memcpy(buffer, text, n);
    gfx->setTextColor(foreground, background);
    gfx->setTextSize(scale);
    gfx->setCursor(x, y);
    gfx->print(buffer);
}

void drawProgress(Arduino_GFX* gfx, uint8_t percent) {
    gfx->fillRoundRect(20, 179, 200, 9, 4, TRACK);
    if (percent > 0) {
        gfx->fillRoundRect(20, 179, percent * 2, 9, 4, GOLD);
    }
    char label[12]{};
    snprintf(label, sizeof(label), "%u%%", percent);
    printText(gfx, label, 20, 200, 1, MUTED, BG, 10);
}

void drawFrame() {
    auto* gfx = DisplayManager::getGfx();
    gfx->fillScreen(BG);
    gfx->fillRoundRect(12, 12, 216, 32, 6, PANEL);
    printText(gfx, "//", 21, 23, 1, GOLD, PANEL, 2);
    printText(gfx, title(active.kind), 42, 23, 1, WHITE, PANEL, 20);
    gfx->fillRect(18, 52, 36, 2, GOLD);
}

void drawContents(bool stale) {
    auto* gfx = DisplayManager::getGfx();
    gfx->fillRect(12, 59, 216, 164, BG);
    if (stale) {
        printText(gfx, "DATA STALE", 19, 94, 2, GOLD, BG, 12);
        printText(gfx, "WAITING FOR PC", 19, 129, 1, MUTED, BG, 20);
        return;
    }

    if (active.kind == Kind::MUSIC) {
        gfx->fillRoundRect(19, 69, 75, 75, 9, PANEL);
        printText(gfx, "S", 39, 84, 5, GOLD, PANEL, 1);
        printText(gfx, active.artist, 106, 83, 1, GOLD, BG, 19);
        printText(gfx, active.track, 106, 105, 1, WHITE, BG, 19);
        printText(gfx, "NOW PLAYING", 106, 131, 1, MUTED, BG, 18);
        drawProgress(gfx, active.progress);
    } else if (active.kind == Kind::AGENT) {
        printText(gfx, "AGENT STATUS", 19, 77, 1, MUTED, BG, 19);
        gfx->fillRoundRect(19, 91, 202, 45, 7, PANEL);
        printText(gfx, active.status, 30, 106, 2, GREEN, PANEL, 15);
        printText(gfx, active.task, 19, 153, 1, WHITE, BG, 33);
        drawProgress(gfx, active.progress);
    } else if (active.kind == Kind::RELEASE) {
        printText(gfx, active.artist, 19, 75, 1, GOLD, BG, 28);
        printText(gfx, active.track, 19, 103, 1, WHITE, BG, 33);
        gfx->fillRoundRect(19, 123, 202, 79, 8, PANEL);
        char countdown[9]{};
        snprintf(countdown, sizeof(countdown), "%u", active.days);
        printText(gfx, countdown, 31, 142, 4, GOLD, PANEL, 4);
        printText(gfx, "DAYS", 142, 162, 2, WHITE, PANEL, 4);
    }
}
}  // namespace

void SceneManager::begin(const char* metricsUrl) {
    pcMetricsUrl = metricsUrl == nullptr ? "" : metricsUrl;
    metricsConfigured = pcMetricsUrl.length() != 0;
    active = Scene{};
    if (metricsConfigured) {
        active.kind = Kind::METRICS;
        DashboardManager::begin(pcMetricsUrl.c_str());
    }
    frameDirty = false;
    contentDirty = false;
    staleRendered = false;
}

bool SceneManager::apply(JsonVariantConst root, String& error) {
    if (!root.is<JsonObjectConst>()) {
        error = "Scene must be a JSON object";
        return false;
    }
    JsonObjectConst object = root.as<JsonObjectConst>();
    JsonVariantConst kindValue = object["kind"];
    if (!kindValue.is<const char*>()) {
        error = "kind is required";
        return false;
    }
    const char* requested = kindValue.as<const char*>();
    Scene next;
    if (strcmp(requested, "metrics") == 0) {
        if (!metricsConfigured) {
            error = "metrics URL is not configured in this build";
            return false;
        }
        next.kind = Kind::METRICS;
    } else if (strcmp(requested, "music") == 0) {
        next.kind = Kind::MUSIC;
    } else if (strcmp(requested, "agent") == 0) {
        next.kind = Kind::AGENT;
    } else if (strcmp(requested, "release") == 0) {
        next.kind = Kind::RELEASE;
    } else {
        error = "Unsupported kind";
        return false;
    }

    for (JsonPairConst pair : object) {
        if (!fieldAllowed(next.kind, pair.key().c_str())) {
            error = String("Unknown field: ") + pair.key().c_str();
            return false;
        }
    }
    int numeric = 0;
    if (next.kind == Kind::MUSIC) {
        if (!copyPrintable(object, "artist", next.artist, sizeof(next.artist), error) ||
            !copyPrintable(object, "track", next.track, sizeof(next.track), error) ||
            !readNumber(object, "progress", 100, numeric, error)) return false;
        next.progress = static_cast<uint8_t>(numeric);
    } else if (next.kind == Kind::AGENT) {
        if (!copyPrintable(object, "status", next.status, sizeof(next.status), error) ||
            !copyPrintable(object, "task", next.task, sizeof(next.task), error) ||
            !readNumber(object, "progress", 100, numeric, error)) return false;
        next.progress = static_cast<uint8_t>(numeric);
    } else if (next.kind == Kind::RELEASE) {
        if (!copyPrintable(object, "artist", next.artist, sizeof(next.artist), error) ||
            !copyPrintable(object, "track", next.track, sizeof(next.track), error) ||
            !readNumber(object, "days", 9999, numeric, error)) return false;
        next.days = static_cast<uint16_t>(numeric);
    }

    if (next.kind == Kind::METRICS && active.kind != Kind::METRICS) {
        DisplayManager::stopGif();
        DashboardManager::begin(pcMetricsUrl.c_str());
    }
    if (next.kind != Kind::METRICS && active.kind != next.kind) {
        DisplayManager::stopGif();
        frameDirty = true;
    }
    if (next.kind != Kind::METRICS) contentDirty = true;
    active = next;
    lastPushMs = millis();
    staleRendered = false;
    return true;
}

void SceneManager::update() {
    if (active.kind == Kind::METRICS) {
        DashboardManager::update();
        return;
    }
    if (active.kind == Kind::LEGACY) return;
    const bool stale = static_cast<uint32_t>(millis() - lastPushMs) >= STALE_AFTER_MS;
    if (frameDirty) {
        drawFrame();
        frameDirty = false;
        contentDirty = true;
    }
    if (contentDirty || stale != staleRendered) {
        drawContents(stale);
        contentDirty = false;
        staleRendered = stale;
    }
}

void SceneManager::describe(JsonDocument& out) {
    out["kind"] = name(active.kind);
    out["metrics_configured"] = metricsConfigured;
    if (active.kind == Kind::LEGACY || active.kind == Kind::METRICS) {
        out["stale"] = false;
        return;
    }
    out["stale"] = static_cast<uint32_t>(millis() - lastPushMs) >= STALE_AFTER_MS;
    out["ttl_seconds"] = STALE_AFTER_MS / 1000;
}
