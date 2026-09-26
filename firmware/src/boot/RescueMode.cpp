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
#include <ESP8266WiFi.h>
#include <ArduinoJson.h>
#include <Logger.h>
#include <Updater.h>

#include "boot/RescueMode.h"
#include "project_version.h"
#include "config/ConfigManager.h"
#include "display/DisplayManager.h"
#include "web/Webserver.h"
#include "recovery/FactoryRollback.h"
#include "shino_private_policy.h"

extern ConfigManager configManager;

bool RescueMode::_active = false;

// RTC memory layout: 4-byte aligned struct stored at user RTC offset 0
// ESP8266 RTC user memory starts at offset 64 (256 bytes user area = 64 uint32_t slots)
static constexpr uint32_t RTC_MAGIC = 0x524D4246;  // "RMBF" – Rescue Mode Boot Flag
static constexpr int RTC_OFFSET = 0;               // First user-accessible RTC slot (byte offset)

struct RtcBootData {
    uint32_t magic;
    uint32_t crashCount;
};

static_assert(sizeof(RtcBootData) % 4 == 0, "RTC data must be 4-byte aligned");

extern const char* AP_SSID;
extern const char* AP_PASSWORD;
static constexpr uint16_t RESCUE_PORT = 80;

static constexpr int16_t DBG_PADDING = 5;
static constexpr int16_t DBG_Y_START = 5;
static constexpr int16_t DBG_LINE_HEIGHT = 16;
static constexpr uint8_t DBG_FONT_SIZE = 1;
static constexpr size_t LOG_BUF_SIZE = 96;
static constexpr int RESCUE_AP_DELAY_MS = 100;
static constexpr int REBOOT_DELAY_MS = 500;
static constexpr uint32_t FLASH_KB_DIV = 1024;
static constexpr uint32_t OTA_OFFSET = 0x1000;
static constexpr uint32_t OTA_MASK = 0xFFFFF000;

static Webserver* rescueWebserver = nullptr;

/**
 * @brief Read boot data from RTC memory
 * @param data Reference to RtcBootData struct to fill
 *
 * @return true if read was successful, false on error
 */
static auto readRtcBoot(RtcBootData& data) -> bool {
    return ESP.rtcUserMemoryRead(  // NOLINT(readability-static-accessed-through-instance)
        RTC_OFFSET, reinterpret_cast<uint32_t*>(&data), sizeof(data));
}

/**
 * @brief Write boot data to RTC memory
 * @param data Reference to RtcBootData struct to write
 *
 * @return true if write was successful, false on error
 */
static auto writeRtcBoot(const RtcBootData& data) -> bool {
    return ESP.rtcUserMemoryWrite(RTC_OFFSET,  // NOLINT(readability-static-accessed-through-instance)
                                  const_cast<uint32_t*>(reinterpret_cast<const uint32_t*>(&data)), sizeof(data));
}

/**
 * @brief Inspect RTC memory and increment crash counter.
 *        Returns true if boot loop is detected.
 */
auto RescueMode::checkBootLoop() -> bool {
    RtcBootData data{};

    bool readOk = readRtcBoot(data);
    std::array<char, LOG_BUF_SIZE> logBuf{};
    snprintf(logBuf.data(), logBuf.size(), "RTC read ok=%s magic=0x%08X crashCount=%u", readOk ? "true" : "false",
             data.magic, data.crashCount);
    Logger::info(logBuf.data(), "RescueMode");

    String persistentStr = configManager.secure.get("rescue_persistent_crash_count", "0");
    auto persistentCount = static_cast<uint32_t>(persistentStr.toInt());

    persistentCount++;
    bool putOk = configManager.secure.put("rescue_persistent_crash_count", String(persistentCount).c_str());
    if (!putOk) {
        Logger::warn("Failed to persist rescue_persistent_crash_count", "RescueMode");
    } else {
        Logger::info((String("Persistent boot counter incremented to ") + String(persistentCount)).c_str(),
                     "RescueMode");
    }

    configManager.secure.put("rescue_last_boot_clean", "0");

    if (!readOk || data.magic != RTC_MAGIC) {
        data.magic = RTC_MAGIC;
        data.crashCount = 1;
        writeRtcBoot(data);

        Logger::info("RTC initialized, crashCount=1", "RescueMode");
    } else {
        data.crashCount++;
        writeRtcBoot(data);

        snprintf(logBuf.data(), logBuf.size(), "Crash counter incremented to %u (threshold=%u)", data.crashCount,
                 BOOT_LOOP_THRESHOLD);
        Logger::info(logBuf.data(), "RescueMode");
    }

    if (data.crashCount >= BOOT_LOOP_THRESHOLD) {
        _active = true;
        Logger::warn("Boot loop detected (RTC), entering rescue mode", "RescueMode");

        return true;
    }

    if (persistentCount >= BOOT_LOOP_THRESHOLD) {
        _active = true;
        Logger::warn("Boot loop detected (persistent counter), entering rescue mode", "RescueMode");

        return true;
    }

    return false;
}

/**
 * @brief Called once the device has been running stably for BOOT_STABLE_MS.
 *        Resets the crash counter so the device won't enter rescue mode next reboot.
 */
auto RescueMode::markBootStable() -> void {
    RtcBootData data{};
    data.magic = RTC_MAGIC;
    data.crashCount = 0;
    writeRtcBoot(data);

    configManager.secure.put("rescue_persistent_crash_count", "0");
    configManager.secure.put("rescue_last_boot_clean", "1");

    Logger::info("Boot stable, crash counter reset (RTC + persistent)", "RescueMode");
}

/**
 * @brief Check if rescue mode is active
 *
 * @return true if rescue mode is active, false otherwise
 */
auto RescueMode::isActive() -> bool { return _active; }

/**
 * @brief Start rescue mode: private WPA2 AP + Digest-protected, OEM-only routes.
 */
auto RescueMode::run() -> void {
    _active = true;

    DisplayManager::begin();

    WiFi.persistent(false);
    WiFi.mode(WIFI_AP);
    if (!WiFi.softAP(AP_SSID, AP_PASSWORD, 6, false, 2)) {
        Logger::error("Private rescue AP failed; refusing open fallback", "RescueMode");
        drawDebugScreen();
        return; // No network recovery interface is exposed on AP failure.
    }
    delay(RESCUE_AP_DELAY_MS);

    IPAddress rescueApIp = WiFi.softAPIP();
    Logger::warn((String("Rescue AP started, IP: ") + rescueApIp.toString()).c_str(), "RescueMode");

    drawDebugScreen();

    rescueWebserver = new Webserver(RESCUE_PORT);
    rescueWebserver->begin();

    registerRescueApi();

    Logger::info("Rescue mode ready", "RescueMode");
}

/**
 * @brief Rescue mode main loop – handles web requests only
 */
auto RescueMode::loop() -> void {
    if (rescueWebserver != nullptr) {
        rescueWebserver->handleClient();
    }

    FactoryRollback::tick();
    ESP.wdtFeed();  // NOLINT(readability-static-accessed-through-instance)
}

/**
 * @brief Draw rescue mode debug screen with system info
 */
auto RescueMode::drawDebugScreen() -> void {
    DisplayManager::clearScreen();

    auto* gfx = DisplayManager::getGfx();
    if (gfx == nullptr) {
        return;
    }

    int16_t yPos = DBG_Y_START;

    gfx->setTextSize(DBG_FONT_SIZE);
    gfx->setTextColor(LCD_RED, LCD_BLACK);
    gfx->setCursor(DBG_PADDING, yPos);
    gfx->print(F("!! RESCUE MODE !!"));
    yPos += DBG_LINE_HEIGHT * 2;

    gfx->setTextColor(LCD_WHITE, LCD_BLACK);

    // Firmware version
    gfx->setCursor(DBG_PADDING, yPos);
    gfx->print(F("FW: "));
    gfx->print(PROJECT_VER_STR);
    yPos += DBG_LINE_HEIGHT;

    // Free heap
    gfx->setCursor(DBG_PADDING, yPos);
    gfx->print(F("Heap free: "));
    gfx->print(ESP.getFreeHeap());  // NOLINT(readability-static-accessed-through-instance)
    gfx->print(F(" B"));
    yPos += DBG_LINE_HEIGHT;

    // Heap fragmentation
    gfx->setCursor(DBG_PADDING, yPos);
    gfx->print(F("Heap frag: "));
    gfx->print(ESP.getHeapFragmentation());  // NOLINT(readability-static-accessed-through-instance)
    gfx->print(F("%"));
    yPos += DBG_LINE_HEIGHT;

    // CPU frequency
    gfx->setCursor(DBG_PADDING, yPos);
    gfx->print(F("CPU: "));
    gfx->print(ESP.getCpuFreqMHz());  // NOLINT(readability-static-accessed-through-instance)
    gfx->print(F(" MHz"));
    yPos += DBG_LINE_HEIGHT;

    // Screen dimensions
    gfx->setCursor(DBG_PADDING, yPos);
    gfx->print(F("Screen: "));
    gfx->print(gfx->width());
    gfx->print(F("x"));
    gfx->print(gfx->height());
    yPos += DBG_LINE_HEIGHT;

    // Flash size
    gfx->setCursor(DBG_PADDING, yPos);
    gfx->print(F("Flash: "));
    gfx->print(ESP.getFlashChipRealSize() / FLASH_KB_DIV);  // NOLINT(readability-static-accessed-through-instance)
    gfx->print(F(" KB"));
    yPos += DBG_LINE_HEIGHT;

    // Reset reason
    gfx->setCursor(DBG_PADDING, yPos);
    gfx->print(F("Reset: "));
    gfx->print(ESP.getResetReason());  // NOLINT(readability-static-accessed-through-instance)
    yPos += DBG_LINE_HEIGHT * 2;

    // AP info
    gfx->setTextColor(LCD_GREEN, LCD_BLACK);
    gfx->setCursor(DBG_PADDING, yPos);
    gfx->print(F("AP: "));
    gfx->print(AP_SSID);
    yPos += DBG_LINE_HEIGHT;

    gfx->setCursor(DBG_PADDING, yPos);
    gfx->print(F("IP: "));
    gfx->print(WiFi.softAPIP().toString());
}

// No generic OTA, password reset, reboot or unauthenticated counter-reset endpoints.
// Failure to mount LittleFS does not unlock a public recovery writer.
static bool requireRescueAuth() {
    if (rescueWebserver->raw().authenticate(SHINO_RESCUE_HTTP_USER,
                                            SHINO_RESCUE_HTTP_PASSWORD)) return true;
    rescueWebserver->raw().requestAuthentication(DIGEST_AUTH, "SHINO-Rescue");
    return false;
}

static void sendRescueStatus() {
    if (!requireRescueAuth()) return;
    JsonDocument doc;
    doc["status"] = "rescue";
    doc["firmware"] = PROJECT_VER_STR;
    doc["free_heap"] = ESP.getFreeHeap();
    doc["flash_bytes"] = ESP.getFlashChipRealSize();
    doc["generic_ota_enabled"] = false;
    doc["token_reset_enabled"] = false;
    doc["oem_only_restore_writes_enabled"] = SHINO_ENABLE_FACTORY_RESTORE == 1;
    doc["filesystem_restore_supported"] = false;
    RtcBootData data{};
    doc["boot_counter_rtc"] = (readRtcBoot(data) && data.magic == RTC_MAGIC) ? data.crashCount : 0;
    String json;
    serializeJson(doc, json);
    rescueWebserver->raw().sendHeader("Cache-Control", "no-store");
    rescueWebserver->raw().send(HTTP_CODE_OK, "application/json", json);
}

auto RescueMode::registerRescueApi() -> void {
    rescueWebserver->raw().on("/api/v1/rescue/status", HTTP_GET, sendRescueStatus);
    rescueWebserver->raw().on("/api/v1/rescue/factory-restore", HTTP_GET, []() {
        if (!requireRescueAuth()) return;
        FactoryRollback::status(rescueWebserver->raw());
    });
#if SHINO_ENABLE_FACTORY_RESTORE
    rescueWebserver->raw().on("/api/v1/rescue/factory-restore", HTTP_POST,
        []() {
            if (!requireRescueAuth()) return;
            FactoryRollback::complete(rescueWebserver->raw(), true);
        },
        []() {
            const bool authenticated =
                rescueWebserver->raw().authenticate(SHINO_RESCUE_HTTP_USER,
                                                     SHINO_RESCUE_HTTP_PASSWORD);
            FactoryRollback::upload(rescueWebserver->raw(), authenticated);
        });
#endif
    rescueWebserver->raw().onNotFound([]() {
        if (!requireRescueAuth()) return;
        rescueWebserver->raw().sendHeader("Cache-Control", "no-store");
        rescueWebserver->raw().send(HTTP_CODE_NOT_FOUND, "text/plain", "Not found");
    });
    Logger::info("Digest-protected rescue status and gated factory-only restore registered", "RescueMode");
}
