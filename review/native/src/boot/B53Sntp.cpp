// SPDX-License-Identifier: GPL-3.0-or-later
// Native ESP8266 Core 3.1.2 async SNTP fallback. No application socket,
// credential, flash write, polling wait or unverified time accepted.
#include "B53Sntp.h"
#include "B53AutonomyPolicy.h"
#include <Arduino.h>
#include <ESP8266WiFi.h>
#include <TZ.h>
#include <coredecls.h>
#include <time.h>
namespace B53Sntp {
namespace {
B53Autonomy::Policy state;
bool begun=false,expired=true;
void onTimeSet(bool fromSntp) {
    if(!fromSntp || WiFi.status()!=WL_CONNECTED) return;
    const time_t epoch=time(nullptr);
    if(epoch<0 || uint64_t(epoch)<B53Autonomy::UTC_MIN ||
       uint64_t(epoch)>B53Autonomy::UTC_MAX) return;
    if(state.acceptSntp(uint32_t(epoch),0,millis(),B53Autonomy::NTP_MAX_LEASE_MS))
        expired=false;
}
}
void begin(){
    if(begun)return;
    begun=true;
    settimeofday_cb(onTimeSet);
    // The Core handles periodic SNTP in lwIP, including reconnects.
    configTime(TZ_Europe_Paris,"pool.ntp.org","time.cloudflare.com");
}
void poll(uint32_t now){
    // Expiry remains latched across millis rollover until an actual SNTP event.
    if(!expired && !state.time(now).valid) expired=true;
}
bool current(uint32_t now,uint32_t& utc){
    if(!begun || expired)return false;
    const auto data=state.time(now);
    if(!data.valid || data.authority!=B53Autonomy::Authority::Sntp)return false;
    utc=data.utc;return true;
}
bool view(uint32_t now,ArtworkPilot::ClockData& out){
    uint32_t utc=0;
    if(!current(now,utc))return false;
    const auto data=state.time(now);
    if(data.ageMs>=B53Autonomy::NTP_MAX_LEASE_MS)return false;
    const time_t epoch=static_cast<time_t>(utc);
    struct tm local{};
    if(localtime_r(&epoch,&local)!=&local ||
       local.tm_year<120 || local.tm_year>199 ||
       local.tm_mon<0 || local.tm_mon>11 ||
       local.tm_mday<1 || local.tm_mday>31 ||
       local.tm_hour<0 || local.tm_hour>23 ||
       local.tm_min<0 || local.tm_min>59 ||
       local.tm_sec<0 || local.tm_sec>60 ||
       local.tm_isdst<0)return false;
    ArtworkPilot::ClockData sample{};
    sample.year=uint16_t(local.tm_year+1900);
    sample.month=uint8_t(local.tm_mon+1);
    sample.day=uint8_t(local.tm_mday);
    sample.hour=uint8_t(local.tm_hour);
    sample.minute=uint8_t(local.tm_min);
    sample.second=uint8_t(local.tm_sec==60?59:local.tm_sec);
    // Europe/Paris in the pinned TZ database: CET/CEST.
    sample.utcOffsetMinutes=int16_t(local.tm_isdst?120:60);
    sample.observedMs=now;
    sample.syncedMs=now-data.ageMs;
    sample.validForMs=B53Autonomy::NTP_MAX_LEASE_MS-data.ageMs;
    sample.valid=true;
    sample.source=ArtworkPilot::ClockSource::Sntp;
    out=sample;
    return true;
}
}
