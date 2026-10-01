#pragma once
#include <stdint.h>
#include <stddef.h>
namespace m8 {
constexpr uint32_t secondaryBytes = 6200;
inline bool stackEligible(uint32_t heap, uint32_t block, uint32_t references,
                          bool occupied) {
  return !references && !occupied && heap >= secondaryBytes && block >= secondaryBytes;
}
struct CryptoStats {
  uint32_t allocations=0, allocationFailures=0, busyFailures=0;
  uint32_t calls=0, keyChecks=0, lastUs=0, maxUs=0;
  uint32_t lastUsed=0, maxUsed=0, canaryFailures=0;
  uint32_t beforeHeap=0, beforeBlock=0, beforeFragmentation=0;
  uint32_t afterHeap=0, afterBlock=0, afterFragmentation=0;
};
#ifdef ESP8266
extern CryptoStats cryptoStats;
struct RuntimeStats {
  uint32_t allocationFailures=0, shaLastUs=0, shaMaxUs=0;
  uint32_t pollMaxUs=0, serviceMaxUs=0, serviceLastUs=0, polls=0;
  uint32_t minHeap=UINT32_MAX,minBlock=UINT32_MAX,maxFragmentation=0;
  uint32_t minCont=4096;
  uint32_t arenaLast=0,arenaMax=0,arenaDenials=0;
};
extern RuntimeStats runtimeStats;
void sampleResources();
struct PollScope { uint32_t start; PollScope(); ~PollScope(); };
bool verifyChecked(const uint8_t*,const uint8_t*,const uint8_t*);
bool publicKeyChecked(const uint8_t*);
#else
inline bool hostDenyCryptoAllocation=false;
#endif
}
