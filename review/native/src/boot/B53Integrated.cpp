// SPDX-License-Identifier: GPL-3.0-or-later
// Isolated integrated diagnostic graph. No storage or HTTP controls here.
#include "B53Integrated.h"
#if !defined(SHINO_B53_DIAGNOSTIC_OFF)
#include "B53Integration.h"
#endif
#if defined(SHINO_B54_WEATHER_DELIVERY)
#include "B54WeatherProfile.h"
#include "B54WeatherEvidence.h"
#include <lwip/priv/tcp_priv.h>
#endif
#include "B53Sntp.h"
#include "B52Clock.h"
#include <Arduino.h>
#include <ESP8266WiFi.h>
#include <new>
#if !defined(SHINO_B53_AUTONOMY_EXPERIMENTAL) || SHINO_B53_AUTONOMY_EXPERIMENTAL != 1
#error Only the distinct offline experimental graph may compile this module
#endif
#ifndef SHINO_B53_WEATHER_ENABLED
#define SHINO_B53_WEATHER_ENABLED 0
#endif
#ifndef SHINO_B53_LATITUDE
#define SHINO_B53_LATITUDE ""
#endif
#ifndef SHINO_B53_LONGITUDE
#define SHINO_B53_LONGITUDE ""
#endif
#if defined(SHINO_B53_DIAGNOSTIC_OFF)
#if SHINO_B53_DIAGNOSTIC_OFF != 1 || SHINO_B53_WEATHER_ENABLED != 0
#error Diagnostic OFF must be immutable and cannot enable weather transport
#endif
#include "B53OffDiagnostic.h"
namespace B53Integrated {
namespace { B53OffDiagnostic::Monitor monitor; }
void begin(B53Diagnostic::Journal& journal){monitor.begin(journal);}
void critical(){} // No transport, PCB, DNS ticket or callback can exist in this graph.
void observe(uint32_t heap,uint32_t block,uint8_t frag,uint32_t stack){
    monitor.observe(heap,block,frag,stack,millis());
}
void linkAccepted(uint32_t latencyMs){monitor.linkAccepted(latencyMs,millis());}
void poll(bool,bool,bool linkFresh){monitor.poll(linkFresh,millis());}
}
#else
namespace B53Integrated {
// External linkage + volatile permission retain the real transport code even OFF.
// No HTTP/UI/config setter. Defaults remain OFF/UNKNOWN, including experimental graph.
volatile bool weatherRequested=SHINO_B53_WEATHER_ENABLED!=0;
#if defined(SHINO_B54_WEATHER_DELIVERY)
// Read-only partial accounting. No setter/HTTP payload can certify missing SDK coverage.
const B53Integration::Bounds qualificationBounds=
    B54WeatherEvidence::partial(sizeof(tcp_pcb),sizeof(tcp_seg),sizeof(pbuf));
// Linked read-only sizeof evidence, consumed by the owner-local ELF reporter.
extern const uint32_t weatherAllocationWitness[4] PROGMEM __attribute__((used))=
    {sizeof(tcp_pcb),sizeof(tcp_seg),sizeof(pbuf),B54WeatherEvidence::COPY_CHUNK};
#else
B53Integration::Bounds qualificationBounds{};
#endif
namespace {
using namespace B53Integration;
alignas(Coordinator) uint8_t storage[sizeof(Coordinator)];
Coordinator* owner=nullptr;
B53Diagnostic::Journal* log=nullptr;
Conditions state{};
Resources resources{};
Publication<ArtworkPilot::WeatherData> publication;
uint32_t serviced=0,lastLink=0;
bool servicedOnce=false,linkSeen=false,wasFresh=false;
void publish(const ArtworkPilot::WeatherData& weather){
    if(publication.update(weather))B52Clock::setWeather(weather);
}
__attribute__((noinline)) void measure(){
    const uint32_t mark=micros();
    uint32_t heap=0,block=0;uint8_t frag=0;
    ESP.getHeapStats(&heap,&block,&frag);
    resources={heap,block,ESP.getFreeContStack(),frag,uint32_t(millis()),true};
    log->capture(micros(),heap,block,frag,resources.stack,uint32_t(micros()-mark));
    log->captureCost(uint32_t(micros()-mark));
}
}
void begin(B53Diagnostic::Journal& journal){
    if(owner)return;
    log=&journal;owner=new(storage) Coordinator(journal); // placement only, no heap
    owner->configure(SHINO_B53_LATITUDE,SHINO_B53_LONGITUDE);
    log->value(B53Diagnostic::Version,2);
#if defined(SHINO_B54_WEATHER_DELIVERY)
    uint32_t accounted=0;
    for(unsigned i=0;i<4;++i)accounted+=pgm_read_dword(weatherAllocationWitness+i);
    log->value(B53Diagnostic::Word(B54WeatherEvidence::ExtraHeap),accounted);
    log->value(B53Diagnostic::Word(B54WeatherEvidence::ExtraBlock),qualificationBounds.blockRequired-17600);
    log->value(B53Diagnostic::Word(B54WeatherEvidence::ExtraStack),qualificationBounds.extraStack);
    log->value(B53Diagnostic::Word(B54WeatherEvidence::Coverage),0); // native coverage UNKNOWN
#endif
}
void critical(){if(owner)owner->suspend(state);}
void observe(uint32_t heap,uint32_t block,uint8_t frag,uint32_t stack){
    if(owner){
        resources={heap,block,stack,frag,uint32_t(millis()),true};
        if(log->frozen())critical();
    }
}
void linkAccepted(uint32_t latencyMs){
    if(!log)return;
    log->peak(B53Diagnostic::LinkLatencyMax,latencyMs);
    log->count(B53Diagnostic::LinkAccepts);
    const uint32_t now=millis();
    if(linkSeen)log->peak(B53Diagnostic::LinkAcceptIntervalMax,uint32_t(now-lastLink));
    lastLink=now;linkSeen=true;wasFresh=true;
    critical();
}
void poll(bool ota,bool incoming,bool linkFresh){
    if(!owner||!log->started())return;
    if(log->frozen()){
        critical();ArtworkPilot::WeatherData empty{};publish(empty);return;
    }
    const uint32_t now=millis();
    state={};state.sta=WiFi.status()==WL_CONNECTED;
    state.utcValid=B53Sntp::current(now,state.utc);
    state.ota=ota;state.digest=incoming;state.linkPending=incoming;state.linkFresh=linkFresh;
    if(ota||incoming||linkFresh||!state.sta)owner->suspend(state);
    if(linkSeen&&linkFresh)log->peak(B53Diagnostic::LinkAgeMax,uint32_t(now-lastLink));
    if(linkSeen&&wasFresh&&!linkFresh)log->count(B53Diagnostic::LinkStaleEpisodes);
    wasFresh=linkFresh;
    // At most one owner weather service and extra resource scan per20ms.
    // Critical revocation above is never delayed by this cadence.
    if(servicedOnce&&uint32_t(now-serviced)<20)return;
    serviced=now;servicedOnce=true;
    const bool deferred=owner->deferred();
    if(!resources.valid||owner->active()||deferred){
        measure();if(deferred)log->count(B53Diagnostic::DeferredCaptures);
        owner->acknowledgeCapture();
    }
    owner->step(state,resources,qualificationBounds,weatherRequested);
#if defined(SHINO_B54_WEATHER_DELIVERY)
    log->value(B53Diagnostic::Word(B54WeatherEvidence::Result),uint32_t(owner->result()));
#endif
    ArtworkPilot::WeatherData weather{};
    owner->view(weather,now,state,false);publish(weather);
}
}

#endif // distinct full transport graph
