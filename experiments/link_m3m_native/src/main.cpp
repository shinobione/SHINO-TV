// M3-M pinned original native Xtensa graph + optional real metrics handler.
// Not a device firmware, not a network listener, never upload/boot/OTA.
#include <Arduino.h>
#include <ESP8266WiFi.h>
#include <ArduinoJson.h>
#include "boot/FslessMetrics.h"
#include "boot/HomeLanPolicy.h"
#include "../../link_m3f_native/M3FSinglePortPump.h"
#include "../../link_m3c_crypto/M3CBearSslCrypto.h"
#ifndef SHINO_M3M_ENABLE_ADAPTER
#error "Explicit M3-M matched A/B native build required"
#endif
static_assert(ARDUINOJSON_VERSION_MAJOR == 7 &&
  ARDUINOJSON_VERSION_MINOR == 4 &&
  ARDUINOJSON_VERSION_REVISION == 3,
  "Exact real ArduinoJson 7.4.3 only");
#if SHINO_M3M_ENABLE_ADAPTER == 1
#include "../M3MActualMetricsHandler.h"
#endif
namespace {
WiFiServer dormantServer(80); // no begin anywhere
volatile bool privateInertProbe=false;
volatile unsigned result=0;
const ShinoM3C::Identity fixture{
    "192.168.1.46","1234567890abcdef",
    "1234567890abcdef1234567890abcdef"
};
const uint8_t PUBLIC_TEST_KEY[32]={
    1,2,3,4,5,6,7,8,9,10,11,12,13,14,15,16,
    17,18,19,20,21,22,23,24,25,26,27,28,29,30,31,32
};
using Pump=ShinoM3F::SinglePortPump<
    WiFiServer,WiFiClient,ShinoM3C::BearSslCrypto>;
Pump dormantPump(dormantServer,fixture,PUBLIC_TEST_KEY);
#if SHINO_M3M_ENABLE_ADAPTER == 1
alignas(4) char replyStorage[ShinoM3M::ActualMetricsHandler::kMinReply]{};
volatile bool fakePermit=false; // no code sets this true
struct FixtureVerifier {
  bool permit(ShinoM3M::Verb,ShinoM3M::Network,const char*) const {
      return fakePermit;
  }
};
#endif
}
extern "C" void __attribute__((used,noinline)) m3m_compiled_common(uint32_t now) {
    JsonDocument doc;
    FslessMetrics::describe(doc);
    result=static_cast<unsigned>(doc.size())+now;
    result+=HomeLan::endpoint(false,"/api/v1/bridge/metrics")?1u:0u;
    result+=static_cast<unsigned>(dormantPump.poll(now));
}
#if SHINO_M3M_ENABLE_ADAPTER == 1
extern "C" void __attribute__((used,noinline)) m3m_compiled_real_adapter() {
    const ShinoM3M::Request request{
        ShinoM3M::Verb::Get,ShinoM3M::Network::HomeSta,
        "/api/v1/bridge/metrics",nullptr,0,0,nullptr,false,false};
    const auto response=ShinoM3M::ActualMetricsHandler::handle(
        request,FixtureVerifier{},replyStorage,sizeof(replyStorage));
    result+=static_cast<unsigned>(response.status);
}
#endif
void setup(){} // deliberately no WiFi connection or listener
void loop(){
    if(privateInertProbe) {
        m3m_compiled_common(millis());
#if SHINO_M3M_ENABLE_ADAPTER == 1
        m3m_compiled_real_adapter();
#endif
    }
    delay(1000);
}
