// SPDX-License-Identifier: GPL-3.0-or-later
#include "B52Clock.h"
#include "B53Sntp.h"
#include <boot/FslessMetrics.h>
#include <display/DisplayManager.h>
#include <ESP8266WiFi.h>
#include <font/glcdfont.h>
#include <cstring>

namespace B52Clock {
namespace {
ClockFoundation::State clockState;
ClockFreshness::Gate freshness;
uint32_t monotonic(){return millis();}
bool entropy(uint8_t* p,size_t n){
    if(WiFi.getMode()==WIFI_OFF)return false;
    ESP.random(p,n);return true; // pinned Core crypto nonce source, active RF required
}
ArtworkPilot::Renderer renderer;
bool clockChanged=true;
uint8_t lastAuthority=255;
uint32_t lastMinute=0,lastGeneration=0;
class Lcd final:public ArtworkPilot::Canvas {
public:
    void fill(int x,int y,int w,int h,uint16_t color)override{
        DisplayManager::getGfx()->fillRect(x,y,w,h,color);
    }
    void text(int x,int y,const char* s,uint16_t color,uint8_t size)override{
        auto* gfx=DisplayManager::getGfx();
        gfx->setFont(nullptr);gfx->setTextWrap(false);gfx->setTextSize(size);
        gfx->setTextColor(color);gfx->setCursor(x,y);gfx->print(s);
    }
    uint8_t glyphColumn(uint8_t ascii,unsigned column)override{
        return pgm_read_byte(&font[ascii*5+column]);
    }
    void row(int x,int y,uint16_t* data,int count,int repeats)override{
        for(int i=0;i<repeats;++i)DisplayManager::getGfx()->draw16bitRGBBitmap(x,y+i,data,count,1);
    }
} lcd;
}
bool challenge(uint32_t now){return freshness.issue(entropy,now);}
const uint8_t* bootToken(){return freshness.boot();}
const uint8_t* challengeToken(){return freshness.nonce();}
bool synchronize(const uint8_t* p,size_t n,uint32_t started,uint32_t now,
    const char* password,ClockFreshness::Workspace& workspace){
    if(!freshness.accept(clockState,workspace,password,p,n,started,now,monotonic))return false;
    clockChanged=true;return true;
}
#ifdef HOST_MOCK
void resetForTest(){clockState={};freshness={};clockChanged=true;lastValid=false;}
#endif
ClockFoundation::Snapshot snapshot(uint32_t now){return clockState.snapshot(now);}
void setWeather(const ArtworkPilot::WeatherData& sample){renderer.setWeather(sample);}
void refreshMetrics(){
    const auto m=FslessMetrics::snapshot();
    renderer.setMetrics({m.cpu,m.gpu,m.memoryGb,m.memoryTotalGb,m.gpuTempC,m.gpuAvailable,FslessMetrics::stale()});
}
void step(uint32_t now){
    freshness.expire(now); // latch pending expiry before a complete millis wrap
    B53Sntp::poll(now);
    const auto pc=clockState.snapshot(now);
    uint32_t ntpUtc=0;
    const bool fallback=!pc.valid && B53Sntp::current(now,ntpUtc);
    const uint8_t authority=pc.valid?1:(fallback?2:0);
    const uint32_t minute=pc.valid?pc.utc/60:(fallback?ntpUtc/60:0);
    if(clockChanged||authority!=lastAuthority||minute!=lastMinute||
       pc.generation!=lastGeneration){
        ArtworkPilot::ClockData selected{};
        if(pc.valid)selected=clockState.view(now);
        else if(fallback)B53Sntp::view(now,selected);
        renderer.setClock(selected);
        clockChanged=false;lastAuthority=authority;lastMinute=minute;
        lastGeneration=pc.generation;
    }
    // No receiver/image pointer; IDLE/OFFLINE only in this milestone.
    // Exactly one cooperative render task after the existing HTTP owner.
    renderer.step(lcd,{},now);
}
}

