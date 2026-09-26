// SPDX-License-Identifier: GPL-3.0-or-later
// SHINO // TV: strict first-boot diagnostics compiled into application flash.
// Does not invoke LittleFS.begin/format, EEPROM.begin/commit, SecureStorage,
// ConfigManager.load/save, NTP, scene engine or a filesystem-backed web UI.
// If explicitly built with experimental OEM return, the approved OTA *does*
// write staging flash and can overwrite the owner's original data region.
#include "boot/FirstBootBridge.h"

#include <Arduino.h>
#include <ESP8266WiFi.h>
#include <ESP8266WebServer.h>
#include <ArduinoJson.h>
#include <Logger.h>
#include "display/DisplayManager.h"
#include "boot/FslessMetrics.h"
#include "boot/FslessWebUI.h"
#include "boot/DashboardV2.h"
#include <cstdio>
#include <cstring>
#include "recovery/FactoryRollback.h"
#include "shino_private_policy.h"

#ifndef SHINO_BOOT_PROFILE
#error "A private, explicit first-boot profile is required."
#endif
static_assert(SHINO_BOOT_PROFILE == 0 || SHINO_BOOT_PROFILE == 1,
              "Only conservative bridge (0) or separately reviewed normal profile (1) is supported.");
static_assert(sizeof(SHINO_SETUP_AP_PSK) >= 13, "Missing private per-build WPA2 key");
static_assert(sizeof(SHINO_RESCUE_HTTP_PASSWORD) >= 21, "Missing private Digest secret");
#ifndef SHINO_ENABLE_FS_MIGRATION
#error "Missing explicit FS migration safety gate"
#endif
static_assert(SHINO_ENABLE_FS_MIGRATION == 0,
              "In-place LittleFS migration is forbidden in this single-device bridge build.");
static_assert(SHINO_FS_BYTES == 2072576, "Unreviewed alternative LittleFS partition geometry.");
#ifndef SHINO_FS_IMAGE_PRESENT
#error "Explicit none/pinned alternative filesystem reference is required."
#endif
static_assert(SHINO_FS_IMAGE_PRESENT == 0 || SHINO_FS_IMAGE_PRESENT == 1,
              "Only optional offline FS research image reference is supported.");
#if SHINO_FS_IMAGE_PRESENT
static_assert(sizeof(SHINO_FS_SHA256) == 65, "Invalid optional image SHA-256.");
static_assert(sizeof(SHINO_FS_MD5) == 33, "Invalid optional image MD5.");
#else
static_assert(sizeof(SHINO_FS_SHA256) == 1 && sizeof(SHINO_FS_MD5) == 1,
              "FS-less profile must not pretend that a filesystem image is pinned.");
#endif

namespace {
ESP8266WebServer server(80);
bool active = false;
bool networkReady = false;
String ssid;

bool telemetryNeedsRedraw = true;
bool stalePreviously = true;
uint32_t lastDrawMs = 0;

bool requireAuth() {
    if (server.authenticate(SHINO_RESCUE_HTTP_USER, SHINO_RESCUE_HTTP_PASSWORD)) return true;
    server.requestAuthentication(DIGEST_AUTH, "SHINO-FirstBoot");
    return false;
}
void respond(int code, const String& data) {
    server.sendHeader(F("Cache-Control"), F("no-store"));
    server.sendHeader(F("X-Content-Type-Options"), F("nosniff"));
    server.send(code, "application/json", data);
}
void sendFsPlan() {
    if (!requireAuth()) return;
    JsonDocument doc;
    doc["mode"] = "READ_ONLY_FS_MIGRATION_PLAN";
    doc["fs_research_image_present"] = SHINO_FS_IMAGE_PRESENT == 1;
    doc["pinned_image_sha256"] = SHINO_FS_IMAGE_PRESENT ? SHINO_FS_SHA256 : "NONE__NO_LITTLEFS_IMAGE_BUILT";
    doc["pinned_image_bytes"] = SHINO_FS_IMAGE_PRESENT ? SHINO_FS_BYTES : 0;
    doc["linked_shino_fs_start"] = "0x200000";
    doc["linked_shino_fs_end_exclusive"] = "0x3fa000";
    doc["stock_fs_start_inferred_NOT_PROVEN"] = "0x100000";
    doc["stock_fs_bytes_at_risk_under_inferred_layout"] = SHINO_FS_BYTES;
    doc["standard_updater_erases_and_writes_active_fs_BEFORE_MD5_validation"] = true;
    doc["atomic_full_image_staging_available_with_current_app"] = false;
    doc["OEM_application_image_cannot_restore_stock_filesystem"] = true;
    doc["first_boot_fs_mount_or_migration_performed"] = false;
    doc["filesystem_writer_compiled"] = false;
    doc["owner_migration_authorized"] = false;
    String result;
    serializeJson(doc, result);
    respond(200, result);
}
void sendStatus() {
    if (!requireAuth()) return;
    JsonDocument doc;
    doc["mode"] = "FIRST_BOOT_BRIDGE";
    doc["application_littlefs_begin_called"] = false;
    doc["application_autoformat_enabled"] = false;
    doc["application_eeprom_begin_called"] = false;
    doc["application_eeprom_commit_called"] = false;
    doc["sdk_wifi_persistence_enabled"] = false;
    doc["filesystem_provisioning_route"] = false;
    doc["filesystem_impact_report_route"] = "/api/v1/bridge/fs-plan";
    doc["pinned_littlefs_image_available_off_device"] = SHINO_FS_IMAGE_PRESENT == 1;
    doc["browser_ui_source"] = "PROGRAM_FLASH_ONLY";
    doc["pc_metrics_storage"] = "RAM_ONLY";
    doc["pc_metrics_route"] = "/api/v1/bridge/metrics";
    doc["filesystem_migration_writes_compiled"] = false;
    doc["manufacturer_original_flash_backup_available"] = false;
    doc["linked_shino_FS_start_offset"] = "0x200000";
    doc["inferred_stock_FS_start_offset_UNVERIFIED"] = "0x100000";
    doc["physical_flash_bytes_observed_at_runtime"] = ESP.getFlashChipRealSize();
    doc["running_application_bytes"] = ESP.getSketchSize();
    doc["linker_declared_free_sketch_bytes_NOT_stock_OTA_capacity"] = ESP.getFreeSketchSpace();
    doc["available_heap_bytes"] = ESP.getFreeHeap();
    doc["factory_app_return_compiled"] = SHINO_ENABLE_FACTORY_RESTORE == 1;
    doc["physical_flash_or_application_OTA_writes_performed_by_diagnostics"] = false;
    doc["physical_flash_installation_authorized"] = false;
    String result;
    serializeJson(doc, result);
    respond(200, result);
}
void sendMetrics() {
    if (!requireAuth()) return;
    JsonDocument doc;
    FslessMetrics::describe(doc);
    String body;
    serializeJson(doc, body);
    respond(200, body);
}

void acceptMetrics() {
    if (!requireAuth()) return;
    // Small bounded sample with no filenames, scripts, assets or device writes.
    const String payload = server.arg("plain");
    if (payload.length() < 16 || payload.length() > 384) {
        respond(413, F("{\"error\":\"Invalid bounded telemetry payload length\"}"));
        return;
    }
    JsonDocument doc;
    if (deserializeJson(doc, payload)) {
        respond(422, F("{\"error\":\"Invalid JSON telemetry\"}"));
        return;
    }
    String error;
    if (!FslessMetrics::apply(doc.as<JsonVariantConst>(), error)) {
        respond(422, F("{\"error\":\"Invalid, missing or out-of-range telemetry fields\"}"));
        return;
    }
    telemetryNeedsRedraw = true;
    respond(200, F("{\"status\":\"RAM_SAMPLE_ACCEPTED\",\"persisted\":false}"));
}

// Only four little 108x108 rectangles are repainted when their contents
// change. No full 240x240 RAM framebuffer and no filesystem access.
struct Card {
    char number[16] = {};
    float percent = -1.0F;  // negative: unavailable/neutral track.
    bool degree = false;
};
bool firstFrame = true;
char lastNumbers[4][16] = {};
uint8_t lastPixels[4] = {255, 255, 255, 255};
int8_t priorBand[4] = {-1, -1, -1, -1};

void paintCard(uint8_t index, const Card& card) {
    const int8_t band = DashboardV2::stableBand(priorBand[index], card.percent);
    const uint8_t pixels = DashboardV2::fillPixels(card.percent);
    if (!firstFrame && strcmp(lastNumbers[index], card.number) == 0 &&
        lastPixels[index] == pixels && priorBand[index] == band) return;

    Arduino_GFX* gfx = DisplayManager::getGfx();
    const int16_t x = DashboardV2::X[index];
    const int16_t y = DashboardV2::Y[index];
    gfx->fillRoundRect(x, y, DashboardV2::CARD_SIZE, DashboardV2::CARD_SIZE, 12, DashboardV2::CARD);
    gfx->drawRoundRect(x, y, DashboardV2::CARD_SIZE, DashboardV2::CARD_SIZE, 12, DashboardV2::BORDER);

    gfx->setTextColor(DashboardV2::LABEL);
    gfx->setTextSize(1);
    gfx->setTextWrap(false);
    gfx->setCursor(x + 10, y + 11);
    if (index == 0) gfx->print(F("CPU usage"));
    else if (index == 1) gfx->print(F("GPU usage"));
    else if (index == 2) gfx->print(F("RAM in use"));
    else {
        gfx->print(F("GPU"));
        gfx->setCursor(x + 10, y + 22);
        gfx->print(F("temperature"));
    }

    const int16_t valueX = x + 10;
    const int16_t valueY = y + 47;
    gfx->setTextColor(DashboardV2::VALUE);
    if (card.number[0] == '\0') {
        // Original Arduino bitmap font does not reliably support UTF-8 em dash.
        // Draw a neutral em dash as a primitive, preserving all four cards.
        gfx->fillRect(valueX, valueY + 8, 16, 2, DashboardV2::VALUE);
    } else if (card.degree) {
        gfx->setTextSize(2);
        gfx->setCursor(valueX, valueY);
        gfx->print(card.number);  // ASCII number only; UTF-8 degree is NOT sent to bitmap font.
        const int16_t degreeX = valueX + static_cast<int16_t>(strlen(card.number)) * 12 + 3;
        gfx->drawCircle(degreeX, valueY + 4, 2, DashboardV2::VALUE);
        gfx->setCursor(degreeX + 5, valueY);
        gfx->print('C');
    } else {
        // 6x8 bitmap font at size 2 = 12px/glyph; long RAM strings
        // must never clip outside a 90px-wide value region.
        gfx->setTextSize(strlen(card.number) * 12 <= 90 ? 2 : 1);
        gfx->setCursor(valueX, valueY);
        gfx->print(card.number);
    }

    const int16_t trackX = x + 9;
    const int16_t trackY = y + 91;
    gfx->fillRoundRect(trackX, trackY, 90, 6, 3, DashboardV2::TRACK);
    if (pixels > 0 && band >= 0) {
        const uint16_t color = DashboardV2::PALETTE[band];
        if (pixels < 6) gfx->fillRect(trackX, trackY, pixels, 6, color);
        else gfx->fillRoundRect(trackX, trackY, pixels, 6, 3, color);
    }
    memcpy(lastNumbers[index], card.number, sizeof(card.number));
    lastPixels[index] = pixels;
    priorBand[index] = band; // a stale/unavailable card resets hysteresis to -1.
    yield();
}

void paintNativeDashboard() {
    const FslessMetrics::Snapshot m = FslessMetrics::snapshot();
    const bool old = FslessMetrics::stale();
    if (firstFrame) DisplayManager::getGfx()->fillScreen(DashboardV2::BACKGROUND);

    Card cards[4]{};
    if (!old) {
        snprintf(cards[0].number, sizeof(cards[0].number), "%.1f%%", m.cpu);
        cards[0].percent = DashboardV2::clamp100(m.cpu);

        if (m.gpuAvailable) {
            snprintf(cards[1].number, sizeof(cards[1].number), "%.1f%%", m.gpu);
            cards[1].percent = DashboardV2::clamp100(m.gpu);
            snprintf(cards[3].number, sizeof(cards[3].number), "%.1f", m.gpuTempC);
            cards[3].degree = true;
            cards[3].percent = DashboardV2::tempPercent(m.gpuTempC);
        }
        snprintf(cards[2].number, sizeof(cards[2].number), "%.1f GB", m.memoryGb);
        cards[2].percent = DashboardV2::ramPercent(m.memoryGb, m.memoryTotalGb);
    }
    for (uint8_t i = 0; i < 4; ++i) paintCard(i, cards[i]);
    firstFrame = false;
    stalePreviously = old;
    lastDrawMs = millis();
    telemetryNeedsRedraw = false;
}

} // namespace

namespace FirstBootBridge {
bool isActive() { return active; }

void run() {
    active = true;
    WiFi.persistent(false); // Must precede every mode/softAP operation.
    WiFi.mode(WIFI_AP);
    ssid = String(F("SHINO-FirstBoot-")) + String(ESP.getChipId(), HEX);
    networkReady = WiFi.softAP(ssid.c_str(), SHINO_SETUP_AP_PSK, 6, false, 2);
    if (!networkReady) {
        // Never silently start an open AP or enter a storage-writing fallback.
        WiFi.mode(WIFI_OFF);
        Logger::error("FirstBoot private AP failed; no fallback and no storage writes", "FirstBoot");
        DisplayManager::begin();
        DisplayManager::clearScreen();
        DisplayManager::drawTextWrapped(8, 14, F("FIRST BOOT"), 2, LCD_RED, LCD_BLACK, false);
        DisplayManager::drawTextWrapped(8, 65, F("PRIVATE AP FAILED"), 1, LCD_WHITE, LCD_BLACK, false);
        DisplayManager::drawTextWrapped(8, 110, F("NO STORAGE WRITE"), 1, LCD_WHITE, LCD_BLACK, false);
        return;
    }
    server.on("/", HTTP_GET, []() {
        if (!requireAuth()) return;
        server.sendHeader(F("Cache-Control"), F("no-store"));
        server.sendHeader(F("Content-Security-Policy"),
                          F("default-src 'none'; style-src 'unsafe-inline'; script-src 'self'; connect-src 'self'; base-uri 'none'; form-action 'none'"));
        server.send_P(200, PSTR("text/html; charset=utf-8"), FslessWebUI::PAGE);
    });
    server.on("/ui.js", HTTP_GET, []() {
        if (!requireAuth()) return;
        server.sendHeader(F("Cache-Control"), F("no-store"));
        server.sendHeader(F("X-Content-Type-Options"), F("nosniff"));
        server.send_P(200, PSTR("application/javascript; charset=utf-8"), FslessWebUI::SCRIPT);
    });
    server.on("/api/v1/bridge/metrics", HTTP_GET, sendMetrics);
    server.on("/api/v1/bridge/metrics", HTTP_POST, acceptMetrics);
    server.on("/api/v1/bridge/status", HTTP_GET, sendStatus);
    server.on("/api/v1/bridge/fs-plan", HTTP_GET, sendFsPlan);
    server.on("/api/v1/bridge/factory-return", HTTP_GET, []() {
        if (!requireAuth()) return;
        FactoryRollback::status(server);
    });
#if SHINO_ENABLE_FACTORY_RESTORE
    server.on("/api/v1/bridge/factory-return", HTTP_POST,
        []() {
            if (!requireAuth()) return;
            FactoryRollback::complete(server, true);
        },
        []() {
            FactoryRollback::upload(server, server.authenticate(SHINO_RESCUE_HTTP_USER,
                                                                 SHINO_RESCUE_HTTP_PASSWORD));
        });
#endif
    server.onNotFound([]() {
        if (!requireAuth()) return;
        respond(404, F("{\"error\":\"No arbitrary update, erase or filesystem route exists\"}"));
    });
    server.begin();

    // LCD dashboard and browser assets are compiled into program flash. Only
    // validated numeric PC samples are stored in volatile RAM.
    DisplayManager::begin();
    paintNativeDashboard();
    Logger::info("FirstBoot protected AP running; no filesystem or EEPROM initialization", "FirstBoot");
}

void loop() {
    if (networkReady) server.handleClient();
    if (networkReady &&
        (telemetryNeedsRedraw || FslessMetrics::stale() != stalePreviously) &&
        static_cast<uint32_t>(millis() - lastDrawMs) >= 250) paintNativeDashboard();
    FactoryRollback::tick();
    ESP.wdtFeed();
    yield();
}
} // namespace FirstBootBridge
