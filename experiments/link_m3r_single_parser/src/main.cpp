// M3-R real Xtensa type/link experiment. NO listener, NO credentials,
// NO authenticated socket, NO GPIO/flash/LittleFS, NO scene writer.
// Gate and parser are distinct from legacy metrics Core, but only one
// parser/buffer is allocated for the NEW M3 request.
#include <Arduino.h>
#include <ESP8266WiFi.h>
#include "../.pio/m3r-venv/ESP8266WebServer/src/ESP8266WebServer.h"
#include "../../link_m3o_core/M3OCoreHook.h"
#include "../M3RSingleParser.h"
#include "../../link_m3c_crypto/M3CBearSslCrypto.h"

namespace {
ESP8266WebServer dormantServer(80);
ShinoM3O::CoreHook dormantHook;
WiFiClient disconnectedProbe;
ShinoM3C::Identity inertIdentity{"lab.invalid","1234567890abcdef",
    "1234567890abcdef1234567890abcdef"};
ShinoM3C::Gate gate(inertIdentity,0u);
// Artificial lab bytes, NOT a private device key. Never used on a network.
const uint8_t inertKey[32]{1u,2u,3u};
volatile bool inertProbeEnabled=false;
volatile int inertResult=0;
}
extern "C" void __attribute__((used,noinline)) m3r_link_single_gate() {
    dormantHook.installBeforeExistingLegacyHooks(dormantServer);
    dormantServer.handleClient();
    // Real WiFiClient and real BearSSL are compiled into this INERT probe.
    // Disconnected client cannot authorize anything.
    const uint32_t start=millis();
    inertResult=int(ShinoM3R::readAuthenticatedHeaders<ShinoM3C::BearSslCrypto>(
        disconnectedProbe,gate,inertKey,[](){return millis();},
        [](){yield();},start));
}
void setup() {}
void loop() {if(inertProbeEnabled)m3r_link_single_gate();delay(1000);}
