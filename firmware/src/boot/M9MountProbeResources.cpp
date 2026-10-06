// SPDX-License-Identifier: GPL-3.0-or-later
#include "boot/ShinoBootProfile.h"
#if SHINO_M9_MOUNT_PROBE_RESOURCE_DIAGNOSTICS == 1
#include "boot/M9MountProbeResources.h"
#include "boot/M9LittleFsMountProbe.h"
#include "boot/M9ResourceObserver.h"
#include "boot/M9ResourceJson.h"
#include <Arduino.h>
namespace M9MountProbeResources {
namespace {
struct CoreSource {
    void resetStack() { ESP.resetFreeContStack(); }
    uint32_t stack() { return ESP.getFreeContStack(); }
    void heap(Heap& out) { ESP.getHeapStats(&out.free, &out.largest, &out.fragmentation); }
    uint32_t now() { return millis(); }
};
CoreSource core;
Observer<CoreSource> observer(core);
static_assert(sizeof(observer) <= 112, "Unreviewed persistent observer growth");
struct HttpSink {
    ESP8266WebServer& server;
    void begin(size_t bytes) {
        server.sendHeader(F("Cache-Control"), F("no-store"));
        server.sendHeader(F("X-Content-Type-Options"), F("nosniff"));
        server.setContentLength(bytes);
        server.send(200, "application/json", "");
    }
    void write(const char* data, size_t bytes) { server.sendContent(data, bytes); }
};
} // namespace
void beforeMount() { observer.beforeMount(); }
void afterMount() { observer.afterMount(); }
void poll() { observer.poll(); }
bool sendStatus(ESP8266WebServer& server) {
    char body[M9LittleFsMountProbe::STATUS_JSON_BYTES];
    if (!M9LittleFsMountProbe::json(body, sizeof(body))) return false;
    HttpSink sink{server};
    return emit(observer.status(), body, std::strlen(body), sink);
}
} // namespace M9MountProbeResources
#endif
