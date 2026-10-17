// M3-J: isolated compile/link resource comparison, inert and not deployed.
#include <Arduino.h>
#include <ESP8266WiFi.h>
#include <ArduinoJson.h>
#include "boot/FslessMetrics.h"
#include "boot/HomeLanPolicy.h"
#include "boot/NativeOtaLegacySessionReview.h"
#ifndef M3J_INERT_ENABLE_GATE
#error An explicit A/B build profile is required
#endif
static_assert(ARDUINOJSON_VERSION_MAJOR==7 && ARDUINOJSON_VERSION_MINOR==4 &&
              ARDUINOJSON_VERSION_REVISION==3, "Pinned ArduinoJson 7.4.3 required");
#if M3J_INERT_ENABLE_GATE==1
#include "../../link_m3f_native/M3FSinglePortPump.h"
#include "../../link_m3c_crypto/M3CBearSslCrypto.h"
#endif
namespace {
WiFiServer unstartedListener(80);
volatile unsigned result=0;
volatile bool inertLabProbeEnabled=false;
#if M3J_INERT_ENABLE_GATE==1
const ShinoM3C::Identity id{"192.168.1.46","1234567890abcdef",
                            "1234567890abcdef1234567890abcdef"};
const uint8_t PUBLIC_TEST_VECTOR[32]={1,2,3,4,5,6,7,8,9,10,11,12,13,14,15,16,
                                     17,18,19,20,21,22,23,24,25,26,27,28,29,30,31,32};
using Pump=ShinoM3F::SinglePortPump<WiFiServer,WiFiClient,ShinoM3C::BearSslCrypto>;
Pump dormantPump(unstartedListener,id,PUBLIC_TEST_VECTOR);
#endif
}
extern "C" void __attribute__((used,noinline)) m3j_baseline_probe(uint32_t now){
  JsonDocument doc; FslessMetrics::describe(doc);
  result=static_cast<unsigned>(doc.size())+now;
  result+=HomeLan::endpoint(false,"/api/v1/bridge/metrics")?1u:0u;
}
#if M3J_INERT_ENABLE_GATE==1
extern "C" void __attribute__((used,noinline)) m3j_crypto_probe(uint32_t now){
  result+=static_cast<unsigned>(dormantPump.poll(now));
}
#endif
void setup(){}
void loop(){
  if(inertLabProbeEnabled) {
    m3j_baseline_probe(millis());
#if M3J_INERT_ENABLE_GATE==1
    m3j_crypto_probe(millis());
#endif
  }
  delay(1000);
}
