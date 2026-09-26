// SPDX-License-Identifier: GPL-3.0-or-later
// SHINO // TV: separately compiled Wi-Fi OTA trampoline, NOT a persistent bootloader.
// Firmware writes are compile-time DISABLED by default. Only ephemeral CI images
// and a separately approved, locally provisioned build may enable write handlers.
// Requires a generated private local_policy.h (gitignored). Never hardcode secrets.
#include <Arduino.h>
#include <ESP8266WiFi.h>
#include <ESP8266WebServer.h>
#include <Updater.h>
#include "local_policy.h"

#ifndef SHINO_RECOVERY_AP_PSK
#error "Generate the private policy before compiling. No default AP password exists."
#endif
#ifndef SHINO_RECOVERY_HTTP_PASSWORD
#error "Missing generated HTTP secret."
#endif
#ifndef SHINO_ENABLE_LOADER_WRITES
#error "Missing explicit compile-time read-only vs write-enabled selection."
#endif

static_assert(sizeof(SHINO_RECOVERY_AP_PSK) >= 13,
              "WPA2 recovery AP must have >= 12-character per-build password.");
static_assert(sizeof(SHINO_RECOVERY_HTTP_PASSWORD) >= 21,
              "Recovery HTTP password must be >= 20 characters.");
static_assert(SHINO_ENABLE_LOADER_WRITES == 0 || SHINO_ENABLE_LOADER_WRITES == 1,
              "Writes must be explicitly 0 (safe default) or 1 (experimental).");

namespace {
ESP8266WebServer server(80);
constexpr uint32_t REBOOT_DELAY_MS = 1600;
bool rebootPending = false;
uint32_t restartScheduledAt = 0;

void sendSafe(int code, const __FlashStringHelper* message) {
  server.sendHeader(F("Cache-Control"), F("no-store"));
  server.sendHeader(F("X-Content-Type-Options"), F("nosniff"));
  server.send(code, F("text/plain; charset=utf-8"), message);
}

bool requireAuth() {
  if (server.authenticate(SHINO_RECOVERY_HTTP_USER, SHINO_RECOVERY_HTTP_PASSWORD))
    return true;
  server.requestAuthentication(DIGEST_AUTH, "SHINO-Recovery");
  return false;
}

#if SHINO_ENABLE_LOADER_WRITES
static_assert(SHINO_FACTORY_BYTES == 494144,
              "OEM rollback size must match pinned official V9.0.44 manifest.");
static_assert(sizeof(SHINO_FACTORY_MD5) == 33, "OEM rollback MD5 must be a full hex digest.");
static_assert(SHINO_CANDIDATE_BYTES > 0,
              "Write-enabled builds require an explicitly pinned SHINO candidate.");
static_assert(sizeof(SHINO_CANDIDATE_MD5) == 33, "Candidate MD5 must be a full hex digest.");
enum class Image : uint8_t { SHINO, FACTORY };
struct UploadState {
  bool authenticated = false;
  bool started = false;
  bool finished = false;
  bool good = false;
  String error;
  size_t received = 0;
  Image image = Image::SHINO;
};
UploadState transfer;

size_t requiredBytes(Image image) {
  return image == Image::FACTORY ? SHINO_FACTORY_BYTES : SHINO_CANDIDATE_BYTES;
}

const char* requiredMd5(Image image) {
  return image == Image::FACTORY ? SHINO_FACTORY_MD5 : SHINO_CANDIDATE_MD5;
}

void scheduleRestart() {
  rebootPending = true;
  restartScheduledAt = millis();
}

void onUpload(Image image) {
  HTTPUpload& upload = server.upload();
  if (upload.status == UPLOAD_FILE_START) {
    transfer = UploadState{};
    transfer.image = image;
    transfer.authenticated = server.authenticate(SHINO_RECOVERY_HTTP_USER,
                                                   SHINO_RECOVERY_HTTP_PASSWORD);
    if (!transfer.authenticated) return;
    if (upload.name != F("firmware")) {
      transfer.error = F("Only the firmware upload field is allowed.");
      return;
    }
    if (!upload.filename.endsWith(F(".bin"))) {
      transfer.error = F("A raw .bin application image is required.");
      return;
    }
    if (ESP.getFlashChipRealSize() != 0x400000) {
      transfer.error = F("Unexpected physical flash capacity; stopped.");
      return;
    }
    if (!Update.begin(requiredBytes(image), U_FLASH)) {
      transfer.error = F("Insufficient safe OTA staging space or flash configuration mismatch.");
      return;
    }
    if (!Update.setMD5(requiredMd5(image))) {
      transfer.error = F("Invalid pinned image digest configuration.");
      return;
    }
    transfer.started = true;
  } else if (upload.status == UPLOAD_FILE_WRITE) {
    if (!transfer.authenticated || !transfer.started || transfer.error.length()) return;
    if (transfer.received == 0 &&
        (upload.currentSize < 2 || upload.buf[0] != 0xE9 ||
         upload.buf[1] == 0 || upload.buf[1] > 16)) {
      transfer.error = F("Invalid ESP8266 application header; stopped.");
      return;
    }
    const size_t expected = requiredBytes(image);
    if (upload.currentSize > expected - transfer.received) {
      transfer.error = F("Upload larger than pinned image; stopped.");
      return;
    }
    if (Update.write(upload.buf, upload.currentSize) != upload.currentSize) {
      transfer.error = F("Flash staging write error; no boot switch requested.");
      return;
    }
    transfer.received += upload.currentSize;
  } else if (upload.status == UPLOAD_FILE_END) {
    if (!transfer.authenticated || !transfer.started || transfer.error.length()) return;
    if (transfer.received != requiredBytes(image) ||
        upload.totalSize != requiredBytes(image)) {
      transfer.error = F("Truncated or incorrectly sized image; no boot switch requested.");
      return;
    }
    // The ESP8266 Updater computes the pinned MD5 BEFORE its eboot copy action
    // is scheduled. end(false) rejects missing bytes and an incorrect digest.
    if (!Update.end(false)) {
      transfer.error = F("Firmware validation/commit failed; no reboot to new image.");
      return;
    }
    transfer.good = true;
    transfer.finished = true;
  } else if (upload.status == UPLOAD_FILE_ABORTED) {
    transfer.error = F("Upload aborted; boot change not requested.");
  }
}

void uploadComplete(Image expectedImage) {
  if (!requireAuth()) return;
  if (!transfer.authenticated || transfer.image != expectedImage ||
      !transfer.started || !transfer.finished || !transfer.good) {
    sendSafe(422, F("Upload rejected. No successful OTA boot-switch was confirmed. Rebooting loader."));
    // If a rejected upload left a staged updater active, reboot resets RAM
    // state. Never call Update.end() to discard it: a completed image could commit.
    scheduleRestart();
    return;
  }
  sendSafe(200, F("Pinned image validated and staged. Rebooting."));
  scheduleRestart();
}
#endif

void beginRoutes() {
  server.on("/", HTTP_GET, []() {
    if (!requireAuth()) return;
#if SHINO_ENABLE_LOADER_WRITES
    sendSafe(200, F("SHINO Recovery Loader: experimental, write-enabled build.\n"
                    "POST only a preapproved raw .bin to /install or /restore.\n"
                    "Any other binary fails the fixed per-build length/MD5 check.\n"
                    "This trampoline is replaced by the final application; it is NOT persistent.\n"));
#else
    sendSafe(200, F("SHINO Recovery Loader: SAFE READ-ONLY BUILD.\n"
                    "No OTA upload routes compiled into this firmware.\n"
                    "This is an offline prototype; never flash without explicit approval.\n"));
#endif
  });
  server.on("/status", HTTP_GET, []() {
    if (!requireAuth()) return;
#if SHINO_ENABLE_LOADER_WRITES
    sendSafe(200, F("read_only=false; experimental; one device-specific candidate and OEM 9.0.44 pinned"));
#else
    sendSafe(200, F("read_only=true; flash writes disabled at compile time"));
#endif
  });
#if SHINO_ENABLE_LOADER_WRITES
  server.on("/install", HTTP_POST,
            []() { uploadComplete(Image::SHINO); },
            []() { onUpload(Image::SHINO); });
  server.on("/restore", HTTP_POST,
            []() { uploadComplete(Image::FACTORY); },
            []() { onUpload(Image::FACTORY); });
#endif
  server.onNotFound([]() {
    if (!requireAuth()) return;
    sendSafe(404, F("No such recovery route."));
  });
  server.begin();
}
} // namespace

void setup() {
  // Never join the owner's existing LAN; a private WPA2 setup AP only.
  WiFi.persistent(false);
  WiFi.mode(WIFI_AP);
  WiFi.disconnect();
  const String ssid = String(F("SHINO-Recovery-")) + String(ESP.getChipId(), HEX);
  if (!WiFi.softAP(ssid.c_str(), SHINO_RECOVERY_AP_PSK, 6, false, 2)) {
    // Fail closed: no open-AP fallback, no OTA server, no automatic writes.
    while (true) { delay(1000); }
  }
  beginRoutes();
}

void loop() {
  server.handleClient();
  if (rebootPending && static_cast<uint32_t>(millis() - restartScheduledAt) > REBOOT_DELAY_MS)
    ESP.restart();
  yield();
}
