// Inert M3-N Xtensa A/B; no network connection or server.begin().
// Authenticating with legacy MD5 is codegen research only and can never
// enable a control command: M3 must use M3-C HMAC-SHA256.
#include <Arduino.h>
#include <ArduinoJson.h>
#include <ESP8266WiFi.h>
#include "boot/FslessMetrics.h"
#include "../../link_m3m_native/M3MActualMetricsHandler.h"
#include "../../link_m3c_crypto/M3CBearSslCrypto.h"
#include "../../link_m3f_native/M3FSinglePortPump.h"
#ifndef M3N_NATIVE_AUTH_ENABLE
#error "Explicit M3N A/B native variant required"
#endif
#if M3N_NATIVE_AUTH_ENABLE == 1
#include "../M3NLegacyDigest.h"
#include "../M3NBearMd5.h"
#include "../M3NMetricsAuthority.h"
#endif
namespace {
WiFiServer notListening(80);
volatile bool probe=false;
volatile unsigned sink=0;
const ShinoM3C::Identity identity{
   "192.168.1.46","1234567890abcdef",
   "1234567890abcdef1234567890abcdef"
};
const uint8_t PUBLIC_M3_TEST_KEY[32]={
  1,2,3,4,5,6,7,8,9,10,11,12,13,14,15,16,
  17,18,19,20,21,22,23,24,25,26,27,28,29,30,31,32
};
using Pump=ShinoM3F::SinglePortPump<WiFiServer,WiFiClient,
                                    ShinoM3C::BearSslCrypto>;
Pump silentPump(notListening,identity,PUBLIC_M3_TEST_KEY);
char originalMetricsReply[ShinoM3M::ActualMetricsHandler::kMinReply]{};
struct DenyMetrics {
 bool permit(ShinoM3M::Verb,ShinoM3M::Network,const char*)const {return false;}
};
#if M3N_NATIVE_AUTH_ENABLE == 1
ShinoM3N::DigestState digest;
ShinoM3N::BrowserReadSessions sessions;
#endif
}
extern "C" void __attribute__((used,noinline)) m3n_common_source_probe(uint32_t now) {
  const ShinoM3M::Request q{
    ShinoM3M::Verb::Get,ShinoM3M::Network::HomeSta,
    "/api/v1/bridge/metrics",nullptr,0,0,nullptr,false,false};
  const auto r=ShinoM3M::ActualMetricsHandler::handle(
      q,DenyMetrics{},originalMetricsReply,sizeof(originalMetricsReply));
  sink+=static_cast<unsigned>(r.status)+
        static_cast<unsigned>(silentPump.poll(now));
}
#if M3N_NATIVE_AUTH_ENABLE == 1
extern "C" void __attribute__((used,noinline)) m3n_digest_bearssl_probe(uint32_t now) {
  // PUBLIC deterministic vectors here are intentionally not production
  // credentials or an entropy source. No route is ever activated.
  const uint8_t publicEntropy[32]{
     1,2,3,4,5,6,7,8,9,10,11,12,13,14,15,16,
     17,18,19,20,21,22,23,24,25,26,27,28,29,30,31,32
  };
  const ShinoM3N::Peer peer{0xc0a80132u,0xc0a8012eu};
  (void)digest.issue(publicEntropy,peer,now);
  const ShinoM3N::NetworkContext net{
     peer,0xffffff00u,false,false,true,true,
     "192.168.1.46","192.168.1.46",""
  };
  const ShinoM3N::MetricsAuthority<ShinoM3N::BearMd5> bound(
     net,digest,sessions,
     "Digest username=\"invalid\"",25u,nullptr,0u,
     "nonsecret-fixture-user","nonsecret-fixture-password",now);
  const ShinoM3M::Request request{
     ShinoM3M::Verb::Get,ShinoM3M::Network::HomeSta,
     "/api/v1/bridge/metrics",nullptr,0,0,nullptr,false,false
  };
  auto denied=ShinoM3M::ActualMetricsHandler::handle(
     request,bound,originalMetricsReply,sizeof(originalMetricsReply));
  sink+=static_cast<unsigned>(denied.status);
}
#endif
void setup() {}
void loop() {
  if(probe) {
    m3n_common_source_probe(millis());
#if M3N_NATIVE_AUTH_ENABLE == 1
    m3n_digest_bearssl_probe(millis());
#endif
  }
  delay(1000);
}
