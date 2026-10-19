// SOURCE-BUILT Xtensa Core parser A/B. INERT: do not upload to hardware.
// Uses one original server, never .begin(), never enables a command.
#include <Arduino.h>
#include <ESP8266WiFi.h>
#include <ESP8266WebServer.h>
#include "../../link_m3o_core/M3OCoreHook.h"
#ifndef SHINO_M3P_BOUNDED
#error explicit A/B Core3.1.2 parser profile required
#endif
namespace {
ESP8266WebServer untouchedListener(80);
ShinoM3O::CoreHook candidate{};
volatile bool nativeProbeEnabled=false;
volatile int observed=0;
}
extern "C" void __attribute__((noinline,used)) m3p_link_actual_parser() {
    candidate.installBeforeExistingLegacyHooks(untouchedListener);
    // Forces Core3.1.2 _parseRequest() and modified first-line reader to link
    // via the real ESP8266WebServer::handleClient() implementation.
    // Only reachable behind a volatile false global in this inert image.
    untouchedListener.handleClient();
    observed+=int(candidate.rejectPending(millis()));
}
void setup(){}
void loop(){
    if(nativeProbeEnabled)m3p_link_actual_parser();
    delay(1000);
}
