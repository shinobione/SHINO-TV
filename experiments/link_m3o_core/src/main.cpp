// Core3.1.2 Xtensa INERT native hook A/B test. DO NOT FLASH.
// No network, credentials, OTA, LittleFS, display or HTTP listener begin.
#include <Arduino.h>
#include <ESP8266WiFi.h>
#include <ESP8266WebServer.h>
#ifndef M3O_HOOK_GRAPH
#error Explicit compile-only M3O variant required
#endif
#if M3O_HOOK_GRAPH==1
#include "../M3OCoreHook.h"
#endif
namespace {
ESP8266WebServer dormantOriginalServer(80);
volatile bool unreachableTestEnable=false;
volatile int compilerProof=0;
#if M3O_HOOK_GRAPH==1
ShinoM3O::CoreHook dormantHook;
#endif
}
#if M3O_HOOK_GRAPH==1
extern "C" void __attribute__((used,noinline)) m3o_compile_native_hook() {
    // Hook is installed only in a volatile-disabled path, after startup.
    // This lab has no .begin() and never accepts a live connection.
    dormantHook.installBeforeExistingLegacyHooks(dormantOriginalServer);
    compilerProof+=static_cast<int>(dormantHook.rejectPending(millis()));
}
#endif
void setup(){}
void loop() {
    if(unreachableTestEnable) {
#if M3O_HOOK_GRAPH==1
        m3o_compile_native_hook();
#else
        compilerProof+=static_cast<int>(millis());
#endif
    }
    delay(1000);
}
