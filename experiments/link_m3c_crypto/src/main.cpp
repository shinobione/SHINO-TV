// M3-C: isolated, INERT, compile/link proof. NEVER flash/install this image.
// NO server, WiFi, OTA, LittleFS, AUTH secret, credentials or scene mutation.
// The PUBLIC pattern below is a test vector, NOT a production key.
#include <Arduino.h>
#include "../M3CAuthenticatedIngress.h"
#include "../M3CBearSslCrypto.h"

extern "C" void __attribute__((noinline,used))
m3c_offline_compile_proof(uint32_t tick) {
    using namespace ShinoM3C;
    static const Identity id{"192.168.1.46","1234567890abcdef",
                             "1234567890abcdef1234567890abcdef"};
    static Gate gate(id,0u);
    const uint8_t TEST_VECTOR_ONLY[32] = {
      1,2,3,4,5,6,7,8,9,10,11,12,13,14,15,16,
      17,18,19,20,21,22,23,24,25,26,27,28,29,30,31,32
    };
    (void)gate.headerByte<BearSslCrypto>(
        static_cast<char>(tick & 0xffu),tick % 100u,TEST_VECTOR_ONLY);
    uint8_t dummy[32]{};
    (void)BearSslCrypto::sha256(
        reinterpret_cast<const uint8_t*>(&tick),sizeof(tick),dummy);
    for (auto& c : dummy) c=0u;
}
void setup() {}
void loop() {
    m3c_offline_compile_proof(millis());
    delay(1000);
}
