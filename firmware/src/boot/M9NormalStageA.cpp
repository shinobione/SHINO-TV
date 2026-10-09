// SPDX-License-Identifier: GPL-3.0-or-later
#include "boot/ShinoBootProfile.h"
#if SHINO_M9_NORMAL_QUALIFICATION == 1
#include "boot/M9NormalStageA.h"
#include "boot/M9NormalResources.h"
#include "boot/M9NormalStatusJson.h"
#include "boot/M9NormalHttpPolicy.h"
#include "boot/M9LittleFsMountProbe.h"
#include "boot/FslessMetrics.h"
#include "config/ConfigManager.h"
#include "display/DisplayManager.h"
#include "wireless/WiFiManager.h"
#include "web/Webserver.h"
#ifndef SHINO_ENABLE_HOME_LAN
#define SHINO_ENABLE_HOME_LAN 0
#endif
static_assert(SHINO_BOOT_PROFILE == 1 && SHINO_ENABLE_HOME_LAN == 0 &&
              SHINO_ENABLE_FACTORY_RESTORE == 0 && SHINO_ENABLE_NATIVE_SIGNED_OTA == 0 &&
              SHINO_ENABLE_FS_MIGRATION == 0, "StageA forbids LAN, recovery, OTA and migration writers");
static_assert(sizeof(SHINO_SETUP_AP_PSK) >= 13 && sizeof(SHINO_RESCUE_HTTP_PASSWORD) >= 21 &&
              sizeof(SHINO_BOOTSTRAP_API_TOKEN) >= 25, "StageA requires generated private identity");
namespace M9NormalDashboard { void render(); }
namespace M9NormalStageA {
namespace {
struct CoreSource {
    void resetStack() { ESP.resetFreeContStack(); }
    uint32_t stack() { return ESP.getFreeContStack(); }
    void heap(M9NormalResources::Heap& out) { ESP.getHeapStats(&out.free, &out.largest, &out.fragmentation); }
    uint32_t now() { return millis(); }
};
CoreSource core;
M9NormalResources::Observer<CoreSource> observer(core);
static_assert(sizeof(observer) <= 128, "StageA persistent observer budget");
Webserver service;
WiFiManager network("", "", "SHINO-TV-StageA", SHINO_SETUP_AP_PSK);
bool begun = false, configReady = false, apReady = false, dirty = true;
uint32_t lastDraw = 0;
bool lastStale = true;
bool auth() {
    auto& server = service.raw();
    // Explicit Digest scheme: never accept Basic even with valid private values.
    if (server.header("Authorization").startsWith("Digest ") &&
        server.authenticate(SHINO_RESCUE_HTTP_USER, SHINO_RESCUE_HTTP_PASSWORD)) return true;
    server.requestAuthentication(DIGEST_AUTH, "SHINO-StageA");
    return false;
}
void respond(int code, const char* body) {
    auto& server = service.raw();
    server.sendHeader(F("Cache-Control"), F("no-store"));
    server.sendHeader(F("X-Content-Type-Options"), F("nosniff"));
    server.send(code, "application/json", body);
}
struct HttpSink {
    ESP8266WebServer& server;
    void begin(size_t bytes) {
        server.sendHeader(F("Cache-Control"), F("no-store"));
        server.sendHeader(F("X-Content-Type-Options"), F("nosniff"));
        server.setContentLength(bytes); server.send(200, "application/json", "");
    }
    void write(const char* data, size_t bytes) { server.sendContent(data, bytes); }
};
void status() {
    if (!auth()) return;
    const M9NormalStatusJson::Snapshot snapshot{observer.status(), M9LittleFsMountProbe::status(), configReady, apReady};
    HttpSink sink{service.raw()};
    if (!M9NormalStatusJson::emit(snapshot, sink)) respond(500, "{\"error\":\"STATUS_BOUND\"}");
}
bool beforeBody() {
    auto& server = service.raw();
    server.keepAlive(false); // Rejected body never becomes a second request.
    // Snapshot the complete, strict, allocation-free route decision BEFORE
    // Digest authentication allocates/parses temporary Strings. The observed
    // device regression followed authenticated POST/GET transitions: never
    // depend on mutable request metadata after authentication churn. Preserve
    // auth-first RESPONSE semantics; a rejected unauthenticated path gets 401.
    const int result = M9NormalHttpPolicy::classify(server.method() == HTTP_GET, server.method() == HTTP_POST,
        server.uri().c_str(), server.header("Content-Length").c_str(),
        server.header("Content-Type").c_str(), server.header("Transfer-Encoding").c_str());
    if (!auth()) return false;
    if (result != 200) { respond(result, "{\"error\":\"STAGE_A_PREBODY\"}"); return false; }
    if (server.method() == HTTP_POST && !configReady) {
        respond(503, "{\"error\":\"READONLY_CONFIG_HOLD\"}"); return false;
    }
    return true;
}
void telemetry() {
    if (!auth()) return; // Before body access, parsing, or RAM update.
    if (!configReady) { respond(503, "{\"error\":\"READONLY_CONFIG_HOLD\"}"); return; }
    const String& payload = service.raw().arg("plain");
    if (payload.length() < 16 || payload.length() > 384) {
        respond(413, "{\"error\":\"TELEMETRY_BOUND\"}"); return;
    }
    JsonDocument doc;
    if (deserializeJson(doc, payload)) { respond(422, "{\"error\":\"JSON\"}"); return; }
    String error;
    if (!FslessMetrics::apply(doc.as<JsonVariantConst>(), error)) {
        respond(422, "{\"error\":\"TELEMETRY\"}"); return;
    }
    dirty = true;
    respond(200, "{\"status\":\"RAM_SAMPLE_ACCEPTED\",\"persisted\":false}");
}
void metrics() {
    if (!auth()) return;
    JsonDocument doc; FslessMetrics::describe(doc);
    char body[768];
    if (measureJson(doc) >= sizeof(body)) { respond(500, "{\"error\":\"METRICS_BOUND\"}"); return; }
    serializeJson(doc, body, sizeof(body)); respond(200, body);
}
} // namespace
void beforeSetup() { observer.beforeSetup(); }
void begin(ConfigManager& config) {
    if (begun) return; // No second mount, retry or fallback.
    begun = true;
    DisplayManager::begin(0);
    observer.beforeFs();
    M9LittleFsMountProbe::begin(); // Sole owner: proven physical deny callbacks + exact manifest.
    const auto& fs = M9LittleFsMountProbe::status();
    configReady = config.loadMountedReadOnly(fs.mounted && fs.inventory_exact && fs.config_seed_exact);
    observer.afterFs();
    if (configReady) config.setApiToken(SHINO_BOOTSTRAP_API_TOKEN); // std::string RAM only.
    WiFi.persistent(false); // Before every AP mode/state change; never network.begin().
    apReady = network.startAccessPointMode(); // Closed WPA2 AP; failure switches WIFI_OFF.
    if (!apReady) {
        DisplayManager::clearScreen();
        DisplayManager::drawTextWrapped(8, 14, F("STAGE A AP HOLD"), 1, LCD_WHITE, LCD_BLACK, false);
        return; // No unauthenticated or open AP fallback; no HTTP listener.
    }
    service.raw().collectHeaders("Authorization", "Content-Length", "Content-Type", "Transfer-Encoding");
    service.raw().setStageAPrebody(beforeBody);
    service.on("/status", HTTP_GET, status);
    service.on("/api/v1/m9/normal/status", HTTP_GET, status);
    service.on("/api/v1/m9/normal/resources", HTTP_GET, status);
    service.on("/api/v1/bridge/metrics", HTTP_POST, telemetry);
    service.on("/api/v1/bridge/metrics", HTTP_GET, metrics);
    service.onNotFound([]() { if (auth()) respond(404, "{\"error\":\"STAGE_A_ROUTE_CLOSED\"}"); });
    service.begin(); // No beginFS, static fallback, legacy API or storage registration.
    if (configReady) M9NormalDashboard::render();
}
void afterSetup() { observer.afterSetup(); }
void loop() {
    if (apReady) service.handleClient();
    const uint32_t now = millis();
    const bool stale = FslessMetrics::stale();
    if (configReady && apReady && static_cast<uint32_t>(now - lastDraw) >= 250 && (dirty || stale != lastStale)) {
        M9NormalDashboard::render(); lastDraw = now; lastStale = stale; dirty = false;
    }
    EspClass::wdtFeed(); yield();
    observer.poll(); // Sole steady sampling location: cooperative loop end, <=1 Hz.
}
} // namespace M9NormalStageA
#endif
