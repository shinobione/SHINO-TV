// SPDX-License-Identifier: GPL-3.0-or-later
// SHINO // TV: exact-image-only manufacturer 9.0.44 rollback from a RUNNING app.
// This code cannot recover a non-booting chip, original FS, settings or partition map.
#include "recovery/FactoryRollback.h"

#include <Arduino.h>
#include <ESP8266WiFi.h>
#include <Updater.h>
#include <Updater_Signing.h> // Core-wide ARDUINO_SIGNING: MD5 must never silently be bypassed.
#include "shino_private_policy.h"

#ifndef SHINO_ENABLE_NATIVE_SIGNED_OTA
#error "Explicit native OTA safety gate required in generated private policy."
#endif
#if SHINO_ENABLE_NATIVE_SIGNED_OTA != 0
#error "Native signed OTA has no writer: never combine shared signature verifier with unsigned pinned OEM return."
#endif
#if SHINO_ENABLE_FACTORY_RESTORE && ARDUINO_SIGNING
#error "Core auto-signing bypasses MD5 verifier; pinned unsigned OEM application return forbidden."
#endif

#ifndef SHINO_FACTORY_BYTES
#error "Official V9.0.44 reference missing; generate private policy from pinned manufacturer ZIP."
#endif
#ifndef SHINO_FACTORY_MD5
#error "Official V9.0.44 digest missing."
#endif
#ifndef SHINO_FACTORY_SHA256
#error "Official V9.0.44 SHA-256 missing."
#endif
#ifndef SHINO_ENABLE_FACTORY_RESTORE
#error "Explicit read-only versus experimental OEM restore setting required."
#endif
static_assert(SHINO_FACTORY_BYTES == 494144, "Official pinned factory application size changed");
static_assert(sizeof(SHINO_FACTORY_MD5) == 33, "Official MD5 must be a full hex digest");
static_assert(sizeof(SHINO_FACTORY_SHA256) == 65, "Official SHA-256 must be a full hex digest");
static_assert(SHINO_ENABLE_FACTORY_RESTORE == 0 || SHINO_ENABLE_FACTORY_RESTORE == 1,
              "Factory restore must be explicitly disabled or experimental");

namespace {
constexpr uint32_t PHYSICAL_FLASH_BYTES = 0x400000UL;
constexpr uint32_t REBOOT_WAIT_MS = 2000;

void reply(ESP8266WebServer& server, int status, const String& message) {
    server.sendHeader(F("Cache-Control"), F("no-store"));
    server.sendHeader(F("X-Content-Type-Options"), F("nosniff"));
    server.send(status, F("application/json"), message);
}

#if SHINO_ENABLE_FACTORY_RESTORE
struct Transfer {
    bool authenticated = false;
    bool begun = false;
    bool completed = false;
    bool accepted = false;
    bool invalid = false;
    size_t received = 0;
};
Transfer transfer;
bool restartPending = false;
uint32_t restartAt = 0;

void deferRestart() {
    restartPending = true;
    restartAt = millis();
}

void deny(Transfer& t) {
    t.invalid = true;
}
#endif
} // namespace

namespace FactoryRollback {
void status(ESP8266WebServer& server) {
    const String response =
        String(F("{\"firmware\":\"GeekMagic Ultra-V9.0.44\",\"application_bytes\":494144,"
                 "\"manufacturer_sha256\":\"")) + String(SHINO_FACTORY_SHA256) +
        String(F("\",\"full_flash_backup\":false,\"filesystem_layout_verified\":false,"
                 "\"write_enabled\":")) +
        String(SHINO_ENABLE_FACTORY_RESTORE ? F("true") : F("false")) + F("}");
    reply(server, 200, response);
}

void upload(ESP8266WebServer& server, bool authenticated) {
#if SHINO_ENABLE_FACTORY_RESTORE
    HTTPUpload& item = server.upload();
    if (item.status == UPLOAD_FILE_START) {
        transfer = Transfer{};
        transfer.authenticated = authenticated;
        if (!authenticated) return; // Reject unauthenticated request BEFORE Update.begin().
        if (item.name != F("factory_v9_0_44") || !item.filename.endsWith(F(".bin"))) {
            deny(transfer);
            return;
        }
        if (ESP.getFlashChipRealSize() != PHYSICAL_FLASH_BYTES ||
            ESP.getFreeSketchSpace() < (SHINO_FACTORY_BYTES + 4096UL) ||
            Update.isRunning()) {
            deny(transfer);
            return;
        }
        if (!Update.begin(SHINO_FACTORY_BYTES, U_FLASH)) {
            deny(transfer);
            return;
        }
        transfer.begun = true;
        if (!Update.setMD5(SHINO_FACTORY_MD5)) {
            deny(transfer);
            return;
        }
    } else if (item.status == UPLOAD_FILE_WRITE) {
        if (!authenticated || !transfer.authenticated || !transfer.begun || transfer.invalid) return;
        if (transfer.received == 0 &&
            (item.currentSize < 2 || item.buf[0] != 0xE9 ||
             item.buf[1] == 0 || item.buf[1] > 16)) {
            deny(transfer);
            return;
        }
        if (item.currentSize > SHINO_FACTORY_BYTES - transfer.received) {
            deny(transfer);
            return;
        }
        if (Update.write(item.buf, item.currentSize) != item.currentSize) {
            deny(transfer);
            return;
        }
        transfer.received += item.currentSize;
    } else if (item.status == UPLOAD_FILE_END) {
        if (!authenticated || !transfer.authenticated || !transfer.begun || transfer.invalid) return;
        if (transfer.received != SHINO_FACTORY_BYTES || item.totalSize != SHINO_FACTORY_BYTES) {
            deny(transfer);
            return;
        }
        // ESP8266 Updater validates the exact manufacturer MD5 before scheduling
        // its ROM eboot copy; end(false) rejects incomplete uploads.
        if (!Update.end(false) || Update.hasError()) {
            deny(transfer);
            return;
        }
        transfer.accepted = true;
        transfer.completed = true;
    } else if (item.status == UPLOAD_FILE_ABORTED) {
        deny(transfer);
    }
#else
    (void) server;
    (void) authenticated;
#endif
}

void complete(ESP8266WebServer& server, bool authenticated) {
#if SHINO_ENABLE_FACTORY_RESTORE
    if (!authenticated || !transfer.authenticated) {
        reply(server, 401, F("{\"status\":\"denied\",\"message\":\"Authentication required\"}"));
        return;
    }
    if (!transfer.accepted || !transfer.completed || transfer.invalid) {
        reply(server, 422, F("{\"status\":\"rejected\",\"message\":\"Original image was not fully verified; no successful OTA commit\"}"));
        if (transfer.begun) deferRestart(); // Reset staged, uncommitted Update state.
        return;
    }
    reply(server, 200, F("{\"status\":\"staged\",\"message\":\"Verified OEM application image; reboot scheduled. Original filesystem restoration unproven\"}"));
    deferRestart();
#else
    (void)authenticated;
    reply(server, 403, F("{\"status\":\"read_only\",\"message\":\"Experimental factory writes not compiled in this firmware\"}"));
#endif
}

void tick() {
#if SHINO_ENABLE_FACTORY_RESTORE
    if (restartPending && static_cast<uint32_t>(millis() - restartAt) >= REBOOT_WAIT_MS) {
        ESP.restart();
    }
#endif
}
} // namespace FactoryRollback
