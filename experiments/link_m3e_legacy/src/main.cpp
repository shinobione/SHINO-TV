// M3-E: NO network listeners, no handler dispatch, no OTA or LCD. NEVER flash.
#include <Arduino.h>
#include "../M3ELegacyRouteGate.h"

static volatile uint8_t retainedFixtureResult = 0u;
extern "C" void __attribute__((noinline,used))
m3e_inert_esp8266_route_compile_probe(uint32_t tick) {
    const ShinoM3E::Options mode{true,false,false};
    const ShinoM3E::Classification result =
        ShinoM3E::LegacyRouteGate::inspect(
            (tick & 1u) ? "GET" : "POST",
            (tick & 2u) ? "/api/v1/bridge/metrics" :
                          "/api/v1/display/mode",
            (tick & 4u) ? ShinoM3E::Peer::HomeLan :
                          ShinoM3E::Peer::AccessPoint,mode);
    retainedFixtureResult = static_cast<uint8_t>(result.kind);
    // No handler can be called: result.allowedToDispatch is always false.
}
void setup() {}
void loop() {
    m3e_inert_esp8266_route_compile_probe(millis());
    delay(1000);
}
