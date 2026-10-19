// M3-Q INERT Xtensa proof; never a deployable SHINO // TV firmware.
#include <Arduino.h>
#include <ESP8266WiFi.h>
#include "../.pio/m3q-venv/ESP8266WebServer/src/ESP8266WebServer.h"
#include "../../link_m3o_core/M3OCoreHook.h"
#if SHINO_M3Q_HEADERS==1
#include "../M3QBoundedHeaders.h"
#endif
#ifndef SHINO_M3Q_HEADERS
#error Explicit M3-Q inert A/B environment required
#endif
namespace {
ESP8266WebServer dormantWebServer(80);
ShinoM3O::CoreHook dormantHook{};
WiFiClient disconnectedProbeClient{};
volatile bool probeEnabled=false;
volatile int observed=0;
#if SHINO_M3Q_HEADERS==1
ShinoM3Q::HeaderGuard guard{}; // member storage, not CONT stack
#endif
}
extern "C" void __attribute__((used,noinline)) m3q_link_actual_core() {
    dormantHook.installBeforeExistingLegacyHooks(dormantWebServer);
    dormantWebServer.handleClient();
    observed+=int(dormantHook.rejectPending(millis()));
#if SHINO_M3Q_HEADERS==1
    const uint32_t t0=millis();
    // No connected socket; this is LINKAGE only.
    observed+=int(ShinoM3Q::readHeaders(disconnectedProbeClient,guard,
        [](){return millis();},[](){yield();},t0));
#endif
}
void setup(){}
void loop(){if(probeEnabled)m3q_link_actual_core();delay(1000);}
