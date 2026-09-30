// Isolated qualification adapter derived from pinned Core 3.1.2 StackThunk.cpp.
// LGPL-2.1-or-later, original mechanism copyright 2017 Earle F. Philhower III.
// Deviation: checked, lazy allocation replaces stock abort-on-OOM add_ref.
// The stock switch, repaint, usage scan, canary and del_ref are unchanged.
#ifdef ESP8266
#include "MediaCrypto.h"
#include "MediaStackThunk.h"
#include <Arduino.h>
#include <StackThunk.h>
#include <umm_malloc/umm_heap_select.h>
#include <stdlib.h>
extern "C" __attribute__((noinline)) uint32_t m8CryptoVerifyNative(
    const uint8_t *q,const uint8_t *hash,const uint8_t *sig) {
  br_ec_public_key pk={BR_EC_secp256r1,const_cast<unsigned char*>(q),65};
  return br_ecdsa_i15_vrfy_raw(&br_ec_p256_m31,hash,32,&pk,sig,64);
}
extern "C" __attribute__((noinline)) uint32_t m8CryptoKeyNative(const uint8_t *q) {
  uint8_t copy[65],one[32]={};
  memcpy(copy,q,65); one[31]=1;
  return q[0]==4 && br_ec_p256_m31.mul(copy,65,one,32,BR_EC_secp256r1)==1;
}
make_stack_thunk(m8CryptoVerifyNative)
make_stack_thunk(m8CryptoKeyNative)
extern "C" uint32_t thunk_m8CryptoVerifyNative(const uint8_t*,const uint8_t*,const uint8_t*);
extern "C" uint32_t thunk_m8CryptoKeyNative(const uint8_t*);
namespace m8 {
CryptoStats cryptoStats;
RuntimeStats runtimeStats;
void sampleResources() {
  auto &s=runtimeStats;
  const uint32_t heap=ESP.getFreeHeap(),block=ESP.getMaxFreeBlockSize();
  const uint32_t frag=ESP.getHeapFragmentation(),cont=ESP.getFreeContStack();
  if(heap<s.minHeap) s.minHeap=heap;
  if(block<s.minBlock) s.minBlock=block;
  if(frag>s.maxFragmentation) s.maxFragmentation=frag;
  if(cont<s.minCont) s.minCont=cont;
}
PollScope::PollScope():start(micros()) {
  auto &s=runtimeStats;
  if(s.serviceLastUs && uint32_t(start-s.serviceLastUs)>s.serviceMaxUs)
    s.serviceMaxUs=uint32_t(start-s.serviceLastUs);
  s.serviceLastUs=start; ++s.polls;
}
PollScope::~PollScope() {
  auto &s=runtimeStats; const uint32_t elapsed=uint32_t(micros()-start);
  if(elapsed>s.pollMaxUs) s.pollMaxUs=elapsed;
  sampleResources();
}
static bool acquire() {
  HeapSelectDram dram;
  auto &s=cryptoStats;
  s.beforeHeap=ESP.getFreeHeap(); s.beforeBlock=ESP.getMaxFreeBlockSize();
  s.beforeFragmentation=ESP.getHeapFragmentation();
  if (stack_thunk_refcnt || stack_thunk_ptr || stack_thunk_save) {
    ++s.busyFailures; return false;
  }
  if (!stackEligible(s.beforeHeap,s.beforeBlock,0,false)) {
    ++s.allocationFailures; return false;
  }
  uint32_t *checked=static_cast<uint32_t*>(malloc(secondaryBytes));
  if (!checked) { ++s.allocationFailures; return false; }
  // Exact stock layout and ownership semantics, initialized only after success.
  stack_thunk_ptr=checked;
  stack_thunk_top=checked+(secondaryBytes/4)-1;
  stack_thunk_save=nullptr;
  stack_thunk_refcnt=1;
  stack_thunk_repaint();
  ++s.allocations;
  sampleResources(); // Continuation SP; capture secondary-stack heap coexistence.
  return true;
}
static void release(uint32_t start) {
  auto &s=cryptoStats;
  s.lastUs=uint32_t(micros()-start);
  if (s.lastUs>s.maxUs) s.maxUs=s.lastUs;
  s.lastUsed=stack_thunk_get_max_usage();
  if(s.lastUsed>s.maxUsed) s.maxUsed=s.lastUsed;
  // Stock thunk already checks this before restoring continuation SP.
  if(!stack_thunk_ptr || stack_thunk_ptr[0]!=0xdeadbeef) {
    ++s.canaryFailures; stack_thunk_fatal_smashing();
  }
  stack_thunk_del_ref(); // Exact stock cleanup resets pointers/save/refcount.
  s.afterHeap=ESP.getFreeHeap(); s.afterBlock=ESP.getMaxFreeBlockSize();
  s.afterFragmentation=ESP.getHeapFragmentation();
}
__attribute__((noinline)) bool verifyChecked(const uint8_t *q,const uint8_t *hash,const uint8_t *sig) {
  if(!acquire()) return false;
  ++cryptoStats.calls;
  const uint32_t start=micros();
  const bool ok=thunk_m8CryptoVerifyNative(q,hash,sig)==1;
  release(start);
  return ok;
}
__attribute__((noinline)) bool publicKeyChecked(const uint8_t *q) {
  if(!acquire()) return false;
  ++cryptoStats.keyChecks;
  const uint32_t start=micros();
  const bool ok=thunk_m8CryptoKeyNative(q)==1;
  release(start);
  return ok;
}
}
#endif
