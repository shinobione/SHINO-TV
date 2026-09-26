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
#include "recovery/FactoryRollback.h"
#include "shino_private_policy.h"

#ifndef SHINO_BOOT_PROFILE
#error "A private, explicit first-boot profile is required."
#endif
static_assert(SHINO_BOOT_PROFILE == 0 || SHINO_BOOT_PROFILE == 1,
              "Only conservative bridge (0) or separately reviewed normal profile (1) is supported.");
static_assert(sizeof(SHINO_SETUP_AP_PSK) >= 13, "Missing private per-build WPA2 key");
static_assert(sizeof(SHINO_RESCUE_HTTP_PASSWORD) >= 21, "Missing private Digest secret");

namespace {
ESP8266WebServer server(80);
bool active = false;
bool networkReady = false;
String ssid;

const char LANDING[] PROGMEM = R"HTML(<!doctype html><html lang="en"><meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>SHINO // TV — First boot</title>
<h1>SHINO // TV / FIRST BOOT</h1>
<p>Conservative firmware bridge. Manufacturer file area has not been mounted
or initialized by the SHINO application. This is not proof that a full flash
backup or a nonbooting rescue is available.</p>
<p>Authenticated diagnostics: <a href="/api/v1/bridge/status">status</a>,
<a href="/api/v1/bridge/factory-return">original application reference</a>.</p>
<p>No filesystem provisioning or arbitrary update control is installed.</p>
</html>)HTML";

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
                          F("default-src 'none'; style-src 'unsafe-inline'; base-uri 'none'; form-action 'none'"));
        server.send_P(200, PSTR("text/html; charset=utf-8"), LANDING);
    });
    server.on("/api/v1/bridge/status", HTTP_GET, sendStatus);
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

    // The display driver runs from application flash and does not read the FS.
    DisplayManager::begin();
    DisplayManager::clearScreen();
    DisplayManager::drawTextWrapped(8, 12, F("SHINO // TV"), 2, LCD_WHITE, LCD_BLACK, false);
    DisplayManager::drawTextWrapped(8, 56, F("FIRST BOOT"), 2, LCD_GREEN, LCD_BLACK, false);
    DisplayManager::drawTextWrapped(8, 105, F("No FS migration"), 1, LCD_WHITE, LCD_BLACK, false);
    DisplayManager::drawTextWrapped(8, 135, ssid, 1, LCD_WHITE, LCD_BLACK, false);
    DisplayManager::drawTextWrapped(8, 175, WiFi.softAPIP().toString(), 2,
                                    LCD_WHITE, LCD_BLACK, false);
    Logger::info("FirstBoot protected AP running; no filesystem or EEPROM initialization", "FirstBoot");
}

void loop() {
    if (networkReady) server.handleClient();
    FactoryRollback::tick();
    ESP.wdtFeed();
    yield();
}
} // namespace FirstBootBridge
