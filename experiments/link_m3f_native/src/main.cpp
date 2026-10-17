// Isolated compile/link of actual WiFiServer and WiFiClient template types.
// NEVER FLASH. NO begin() / no connection made / no credentials / no OTA.
#include <Arduino.h>
#include <ESP8266WiFi.h>
#include "../M3FSinglePortPump.h"
#include "../../link_m3c_crypto/M3CBearSslCrypto.h"

namespace {
static WiFiServer unstartedListener(80); // construct only; NEVER begin().
static const ShinoM3C::Identity id{
  "192.168.1.46","1234567890abcdef","1234567890abcdef1234567890abcdef"};
static const uint8_t PUBLIC_VECTOR_NOT_SECRET[32]={
  1,2,3,4,5,6,7,8,9,10,11,12,13,14,15,16,
  17,18,19,20,21,22,23,24,25,26,27,28,29,30,31,32};
using Pump = ShinoM3F::SinglePortPump<
    WiFiServer,WiFiClient,ShinoM3C::BearSslCrypto>;
static Pump dormantPump(unstartedListener,id,PUBLIC_VECTOR_NOT_SECRET);
}
extern "C" void __attribute__((noinline,used))
m3f_compile_only_real_wifi_types(uint32_t now) {
    // Not called by setup() or loop(). Forces real Xtensa instantiation.
    (void)dormantPump.poll(now);
}
void setup() {}
void loop() { delay(1000); } // No Wi-Fi mode or listener activity.
