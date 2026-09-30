// Qualification-only, generated shadow FirstBoot TU. Never a production route.
#include <MediaIngress.h>
#include <StackThunk.h>
#include "M8TestKey.h"
static m7::Authority m7Authority(0x1122334455667788ULL);
static m7::Receiver m7Receiver;
static m7::Ingress m7Ingress(m7Authority,m7Receiver,"tv.test",[]()->uint32_t{return millis();});
static bool m8Enrolled=false,m8ResetPending=false;
static uint32_t m8Boot=0,m8Phase=0,m8Reconnects=0;
static unsigned m8PriorStations=0;
static char m8Json[2048];
static void m8QualDiagnostic() {
  if(!requireAuth()) return;
  const String action=server.arg("action");
  bool actionOk=true;
  if(action=="reset") m8ResetPending=true;
  else if(action=="enroll") {
    if(m8Enrolled) actionOk=false;
    else { m8Enrolled=m7Authority.enroll("media-test",M8_TEST_PUBLIC_POINT,15); actionOk=m8Enrolled; }
  } else if(action=="issue") {
    const String nonce=server.arg("nonce");
    actionOk=m8Enrolled && nonce.length()==22 && m7Authority.issue(0,nonce.c_str(),millis(),10000);
  } else if(action.length()!=0) actionOk=false;
  m8::sampleResources();
  const auto &c=m8::cryptoStats; const auto &s=m8::runtimeStats;
  const int n=snprintf(m8Json,sizeof m8Json,
    "{\"mode\":\"M8_STACKTHUNK_QUALIFICATION\",\"boot\":%u,\"uptime_ms\":%u,\"phase\":%u,"
    "\"reset_pending\":%s,\"action_ok\":%s,\"enrolled\":%s,\"reset_reason\":%u,\"wifi_mode\":%u,\"stations\":%u,\"reconnects\":%u,"
    "\"heap\":%u,\"block\":%u,\"frag\":%u,\"min_heap\":%u,\"min_block\":%u,\"max_frag\":%u,\"cont_free\":%u,\"min_cont\":%u,"
    "\"secondary_bytes\":6200,\"secondary_refs\":%u,\"secondary_allocs\":%u,\"secondary_alloc_failures\":%u,\"secondary_busy\":%u,"
    "\"secondary_used_last\":%u,\"secondary_used_max\":%u,\"secondary_margin\":%u,\"canary_failures\":%u,"
    "\"ecdsa_calls\":%u,\"key_checks\":%u,\"ecdsa_us_last\":%u,\"crypto_us_max\":%u,"
    "\"crypto_before_heap\":%u,\"crypto_before_block\":%u,\"crypto_before_frag\":%u,\"crypto_after_heap\":%u,\"crypto_after_block\":%u,\"crypto_after_frag\":%u,"
    "\"allocation_failures\":%u,\"sha_us_last\":%u,\"sha_us_max\":%u,\"poll_us_max\":%u,\"service_us_max\":%u,"
    "\"receiver_pending\":%s,\"body_bytes\":%u,\"staged_bytes\":%u,\"image_bytes\":%u,\"challenges\":%u,\"ingress_phase\":%u,"
    "\"body_reads\":%u,\"body_allocations\":%u,\"accepted\":%u,\"rejected\":%u,\"commits\":%u,\"highest\":%u,\"outcome\":\"%s\"}",
    m8Boot,uint32_t(millis()),m8Phase,m8ResetPending?"true":"false",actionOk?"true":"false",m8Enrolled?"true":"false",
    ESP.getResetInfoPtr()->reason,unsigned(WiFi.getMode()),unsigned(WiFi.softAPgetStationNum()),m8Reconnects,
    ESP.getFreeHeap(),ESP.getMaxFreeBlockSize(),unsigned(ESP.getHeapFragmentation()),s.minHeap,s.minBlock,s.maxFragmentation,
    ESP.getFreeContStack(),s.minCont,stack_thunk_get_refcnt(),c.allocations,c.allocationFailures,c.busyFailures,
    c.lastUsed,c.maxUsed,c.maxUsed<=6200?6200-c.maxUsed:0,c.canaryFailures,c.calls,c.keyChecks,c.lastUs,c.maxUs,
    c.beforeHeap,c.beforeBlock,c.beforeFragmentation,c.afterHeap,c.afterBlock,c.afterFragmentation,
    s.allocationFailures,s.shaLastUs,s.shaMaxUs,s.pollMaxUs,s.serviceMaxUs,m7Receiver.pending?"true":"false",
    m7Ingress.bodyBytes(),m7Receiver.stagedBytes(),m7Receiver.imageBytes(),m7Authority.liveChallenges(),m7Ingress.phaseCode(),
    m7Ingress.bodyReads,m7Ingress.bodyAllocations,m7Ingress.accepted,m7Ingress.rejected,m7Receiver.sink.commits,
    uint32_t(m7Receiver.highest),m7Ingress.outcome);
  if(n<0 || unsigned(n)>=sizeof m8Json) { respond(500,F("{\"error\":\"DIAGNOSTIC_CAP\"}")); return; }
  respond(actionOk?200:409,m8Json);
}
void m8QualRegister() {
  m8Boot=ESP.random();
  server.setOfflineMedia(&m7Ingress);
  server.on("/api/v1/bridge/m8",HTTP_GET,m8QualDiagnostic);
}
void m8QualAfterLoop() {
  if(m8ResetPending) {
    m8ResetPending=false; ++m8Phase;
    ESP.resetFreeContStack();
    m8::runtimeStats.minCont=4096;
    m8::runtimeStats.minHeap=UINT32_MAX; m8::runtimeStats.minBlock=UINT32_MAX;
    m8::runtimeStats.maxFragmentation=0;
    m8::runtimeStats.pollMaxUs=0; m8::runtimeStats.serviceMaxUs=0;
  }
  const unsigned stations=WiFi.softAPgetStationNum();
  if(stations && !m8PriorStations && m8Phase) ++m8Reconnects;
  m8PriorStations=stations;
  m8::sampleResources();
}
