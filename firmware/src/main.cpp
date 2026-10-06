// SPDX-License-Identifier: GPL-3.0-or-later
/*
 * GeekMagic Open Firmware
 * Copyright (C) 2026 Times-Z
 *
 * This program is free software: you can redistribute it and/or modify
 * it under the terms of the GNU General Public License as published by
 * the Free Software Foundation, either version 3 of the License, or
 * (at your option) any later version.
 *
 * This program is distributed in the hope that it will be useful,
 * but WITHOUT ANY WARRANTY; without even the implied warranty of
 * MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
 * GNU General Public License for more details.
 *
 * You should have received a copy of the GNU General Public License
 * along with this program.  If not, see <https://www.gnu.org/licenses/>.
 */

#include <Arduino.h>
#include <LittleFS.h>
#include <Arduino_GFX_Library.h>
#include <SPI.h>
// The public unauthenticated /legacyupdate path is deliberately removed.

#include <Logger.h>
#include "project_version.h"
#include "config/ConfigManager.h"
#include "wireless/WiFiManager.h"
#include "display/DisplayManager.h"
#include "web/Webserver.h"
#include "web/Api.h"
#include "ntp/NTPClient.h"
#include "boot/RescueMode.h"
#include "boot/FirstBootBridge.h"
#include "scenes/SceneManager.h"
#include "recovery/FactoryRollback.h"
#include "shino_private_policy.h"
#include "boot/ShinoBootProfile.h"
#if SHINO_BOOT_PROFILE == 2
#include "boot/M9LittleFsMountProbe.h"
#include "boot/M9MountProbeResources.h"
#endif
#include <array>

#ifndef METRICS_URL
#define METRICS_URL ""
#endif

#if SHINO_BOOT_PROFILE != 2
ConfigManager configManager;
#endif
static String shinoApName;
const char* AP_SSID = nullptr;
const char* AP_PASSWORD = SHINO_SETUP_AP_PSK;
static_assert(sizeof(SHINO_SETUP_AP_PSK) >= 13, "Per-build setup AP WPA2 password missing");
static_assert(sizeof(SHINO_BOOTSTRAP_API_TOKEN) >= 25, "Per-build initial API secret missing");
static_assert(sizeof(SHINO_RESCUE_HTTP_PASSWORD) >= 21, "Per-build rescue HTTP secret missing");
#ifndef SHINO_BOOT_PROFILE
#error "Generated private profile required before compiling SHINO firmware"
#endif
// Initial install only. A normal boot with a different flash/FS map needs a
// separately reviewed migration and is NOT exposed by this source revision.
// The shared ShinoBootProfile.h keeps normal profile 1 prohibited and requires
// explicit opt-in for profile 2. Profile-0 setup/loop bodies stay unchanged.

WiFiManager* wifiManager = nullptr;
static constexpr const char* KV_SALT_STR = "GeekMagicOpenFirmwareIsAwesome";
static size_t initial_free_heap = 0;
static constexpr size_t FREE_BUF_SIZE = 32;
static constexpr size_t MSG_BUF_SIZE = 96;

static constexpr uint32_t SERIAL_BAUD_RATE = 115200;
static constexpr uint32_t BOOT_DELAY_MS = 200;
static constexpr int LOADING_BAR_TEXT_X = 50;
static constexpr int LOADING_BAR_TEXT_Y = 80;
static constexpr int LOADING_BAR_Y = 110;
static constexpr int LOADING_DELAY_MS = 1000;
static constexpr const char* METRICS_ENDPOINT = METRICS_URL;

Webserver* webserver = nullptr;
NTPClient* ntpClient = nullptr;

/**
 * @brief Formats bytes into a human-readable string
 *
 * @param value Size in bytes
 * @return Formatted string
 */
static void formatBytes(size_t value, char* outBuf, size_t outBufSize) {
    constexpr std::array<const char*, 5> UNITS = {"B", "KB", "MB", "GB", "TB"};
    constexpr double THRESHOLD = 1024.0;

    auto val = static_cast<double>(value);
    int unit = 0;
    while (val >= THRESHOLD && unit < static_cast<int>(UNITS.size()) - 1) {
        val /= THRESHOLD;
        ++unit;
    }

    if (unit == 0) {
        snprintf(outBuf, outBufSize, "%u %s", static_cast<unsigned int>(value), UNITS[unit]);
    } else {
        snprintf(outBuf, outBufSize, "%.1f %s", val, UNITS[unit]);
    }
}

/**
 * @brief Check whether LittleFS contains at least one entry
 *
 * @return true if filesystem root has any file/dir entry
 */
static auto littleFsHasEntries() -> bool {
    Dir dir = LittleFS.openDir("/");
    return dir.next();
}

/**
 * @brief Initializes the system
 *
 */
void setup() {
    Serial.begin(SERIAL_BAUD_RATE);
    delay(BOOT_DELAY_MS);
    Serial.println("");
    Logger::info(("GeekMagic Open Firmware " + String(PROJECT_VER_STR)).c_str());

#if SHINO_BOOT_PROFILE == 0
    // FIRST instruction path after serial startup: never mount/format LittleFS,
    // initialize EEPROM, migrate config, write boot counters, or use WiFi STA.
    FirstBootBridge::run();
    EspClass::wdtEnable(WDTO_2S);
    return;
#elif SHINO_BOOT_PROFILE == 2
    FirstBootBridge::run(); // Protected AP/LCD remains available on probe failure.
#if SHINO_M9_MOUNT_PROBE_RESOURCE_DIAGNOSTICS == 1
    M9MountProbeResources::beforeMount();
#endif
    M9LittleFsMountProbe::begin();
#if SHINO_M9_MOUNT_PROBE_RESOURCE_DIAGNOSTICS == 1
    M9MountProbeResources::afterMount();
#endif
    EspClass::wdtEnable(WDTO_2S);
    return;
#else
    // Held, non-deployable normal path. A future explicit FS migration review
    // must clear the compile-time error above BEFORE this path can be built.
    // The shared FS object must never autoformat when the owner's data remains.
    if (!LittleFS.setConfig(LittleFSConfig(false))) {
        Logger::error("Could not disable LittleFS autoformat; stopping startup", "FirstBoot");
        while (true) { delay(1000); }
    }


    constexpr int TOTAL_STEPS = 5;
    int step = 0;
    const bool littleFsMounted = LittleFS.begin();
    bool littleFsReadyForStatic = littleFsMounted;

    if (!littleFsMounted) {
        Logger::error("Failed to mount LittleFS");
        Logger::warn("LittleFS unavailable, static web UI disabled", "Global");
    } else if (!littleFsHasEntries()) {
        littleFsReadyForStatic = false;
        Logger::warn("LittleFS mounted but empty, static web UI disabled", "Global");
    }

    shinoApName = String(F("SHINO-TV-")) + String(ESP.getChipId(), HEX);
    AP_SSID = shinoApName.c_str();
    WiFi.persistent(false);

    SecureStorage::setSalt(KV_SALT_STR);

    if (configManager.secure.begin()) {
        Logger::info("SecureStorage initialized successfully", "ConfigManager");
    }

    if (configManager.load()) {
        Logger::info("Configuration loaded successfully");
    }

    if (configManager.getApiToken()[0] == '\0') {
        configManager.setApiToken(SHINO_BOOTSTRAP_API_TOKEN);
        configManager.secure.put("api_token", SHINO_BOOTSTRAP_API_TOKEN);
        Logger::info("Provisioned the generated per-build API token; secret not logged", "Global");
    }

    if (RescueMode::checkBootLoop()) {
        RescueMode::run();
        EspClass::wdtEnable(WDTO_2S);

        return;
    }

    step += 2;

    DisplayManager::begin();

    DisplayManager::drawLoadingBar((float)step / TOTAL_STEPS, LOADING_BAR_Y);

    step++;

    DisplayManager::drawTextWrapped(LOADING_BAR_TEXT_X, LOADING_BAR_TEXT_Y, "Starting...", 2, LCD_WHITE, LCD_BLACK,
                                    true);
    DisplayManager::drawLoadingBar((float)step / TOTAL_STEPS, LOADING_BAR_Y);
    step++;

    wifiManager = new WiFiManager(configManager.getSSID(), configManager.getPassword(), AP_SSID, AP_PASSWORD);
    wifiManager->begin();

    ntpClient = new NTPClient();
    ntpClient->begin();

    DisplayManager::drawLoadingBar((float)step / TOTAL_STEPS, LOADING_BAR_Y);

    step++;

    webserver = new Webserver();
    webserver->begin();

    initial_free_heap = ESP.getFreeHeap();  // NOLINT(readability-static-accessed-through-instance)

    DisplayManager::drawLoadingBar((float)step / TOTAL_STEPS, LOADING_BAR_Y);

    registerApiEndpoints(webserver);

    if (!littleFsReadyForStatic) {
        Logger::warn("LittleFS unavailable; NO unauthenticated fallback firmware updater", "Global");
    } else {
        webserver->serveStaticC("/", "/web/index.html", "text/html");
        // Deliberately do NOT expose /config.json, even during credential migration.
        webserver->registerGenericStaticFallback("/web", true);
    }

    DisplayManager::drawLoadingBar(1.0F, LOADING_BAR_Y);

    delay(LOADING_DELAY_MS);

    DisplayManager::drawStartup(wifiManager->getIP().toString());

    SceneManager::begin(METRICS_ENDPOINT);

    // enable watchdog before going to loop()
    // 2 seconds should be way more than the main loop needs to do stuff
    EspClass::wdtEnable(WDTO_2S);
#endif // SHINO_BOOT_PROFILE == 0
}

void loop() {
#if SHINO_BOOT_PROFILE == 0
    FirstBootBridge::loop();
    return;
#elif SHINO_BOOT_PROFILE == 2
    FirstBootBridge::loop();
    M9LittleFsMountProbe::poll();
#if SHINO_M9_MOUNT_PROBE_RESOURCE_DIAGNOSTICS == 1
    M9MountProbeResources::poll(); // Only at the end of the normal profile-2 loop.
#endif
    return;
#else
    if (RescueMode::isActive()) {
        RescueMode::loop();
        return;
    }

    static bool bootStableMarked = false;
    if (!bootStableMarked && millis() >= BOOT_STABLE_MS) {
        RescueMode::markBootStable();
        bootStableMarked = true;
    }

    if (webserver != nullptr) {
        webserver->handleClient();
    }

    if (ntpClient != nullptr) {
        ntpClient->loop();
    }

    DisplayManager::update();

    SceneManager::update();
    FactoryRollback::tick();

    static unsigned long last_free_heap_log = 0;
    static constexpr unsigned long FREE_HEAP_LOG_INTERVAL_MS = 10000UL;
    unsigned long now = millis();

    if (now - last_free_heap_log >= FREE_HEAP_LOG_INTERVAL_MS) {
        last_free_heap_log = now;
        char freeBuf[FREE_BUF_SIZE];
        char initBuf[FREE_BUF_SIZE];
        char msgBuf[MSG_BUF_SIZE];

        formatBytes(ESP.getFreeHeap(), freeBuf,  // NOLINT(readability-static-accessed-through-instance)
                    sizeof(freeBuf));
        formatBytes(initial_free_heap, initBuf, sizeof(initBuf));

        snprintf(msgBuf, sizeof(msgBuf), "Free heap: %s (initial: %s)", freeBuf, initBuf);
        Logger::info(msgBuf);
    }

    EspClass::wdtFeed();  // kick watchdog
#endif // SHINO_BOOT_PROFILE == 0
}
