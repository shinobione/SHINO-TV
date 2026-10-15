// SPDX-License-Identifier: GPL-3.0-or-later
// Pure HOST exercise of the EXACT materialized B5.3 SceneEngine.h.
// No Arduino, socket, device, flash, secrets or PlatformIO emulation claimed.
#include <display/SceneEngine.h>
#include <cassert>
#include <cstdio>
#include <cstring>
#include <string>
#include <vector>

struct FakeCanvas final : ArtworkPilot::Canvas {
    struct TextCall { int x,y; unsigned size; std::string value; };
    std::vector<TextCall> texts;
    bool escaped=false;
    void fill(int x,int y,int w,int h,uint16_t) override {
        if(x<0 || y<0 || w<=0 || h<=0 || x+w>240 || y+h>240)
            escaped=true;
    }
    void text(int x,int y,const char* s,uint16_t,uint8_t size=1) override {
        if(x<0 || y<0 || x+int(std::strlen(s))*6*size>240 || y+8*size>240)
            escaped=true;
        texts.push_back({x,y,size,s});
    }
    uint8_t glyphColumn(uint8_t,unsigned) override { return 0; }
    void row(int x,int y,uint16_t*,int count,int repeats) override {
        if(x<0 || y<0 || count<1 || repeats<1 || x+count>240 || y+repeats>240)
            escaped=true;
    }
    bool has(const char* val) const {
        for(const auto& t:texts)if(t.value==val)return true;
        return false;
    }
    bool at(const char* val,int x,int y,unsigned size) const {
        for(const auto& t:texts)
            if(t.value==val && t.x==x && t.y==y && t.size==size)return true;
        return false;
    }
};
static void drain(ArtworkPilot::Renderer& renderer,FakeCanvas& canvas,uint32_t now) {
    for(unsigned i=0;i<200;++i) {
        if(!renderer.step(canvas,{},now))return;
    }
    assert(false && "cooperative renderer did not finish within 200 tasks");
}
int main() {
    ArtworkPilot::Renderer renderer;
    ArtworkPilot::ClockData pc{};
    pc.year=2026;pc.month=10;pc.day=15;
    pc.hour=9;pc.minute=41;
    pc.observedMs=1000;pc.validForMs=120000;
    pc.valid=true;pc.source=ArtworkPilot::ClockSource::PairedPc;
    renderer.setClock(pc);
    renderer.setMetrics({32.0F,40.0F,9.2F,16.0F,54.0F,true,false});
    FakeCanvas on;
    drain(renderer,on,1000);
    assert(!on.escaped);
    assert(on.at("SHINO // TV",87,10,1));
    assert(on.at("09:41",60,32,4));
    assert(on.has("WEATHER --"));
    assert(on.has("CPU") && on.has("GPU") && on.has("RAM") && on.has("GPU temp"));
    assert(on.has("32%") && on.has("40%") && on.has("9.2G") && on.has("54C"));
    assert(!on.has("PC OFFLINE"));

    renderer.setMetrics({0,0,0,0,0,false,true});
    FakeCanvas off;
    drain(renderer,off,1100);
    assert(!off.escaped);
    assert(off.has("PC OFFLINE") && off.has("NO PC METRICS"));
    assert(!off.has("CPU") && !off.has("GPU temp"));
    assert(off.has("09:41"));

    renderer.setMetrics({56.0F,81.0F,8.0F,16.0F,71.0F,true,false});
    FakeCanvas reconnect;
    drain(renderer,reconnect,1200);
    assert(!reconnect.escaped);
    assert(reconnect.has("CPU") && reconnect.has("56%"));
    assert(!reconnect.has("PC OFFLINE"));

    ArtworkPilot::WeatherData weather{};
    std::memcpy(weather.condition,"Cloudy",7);
    std::memcpy(weather.place,"Test",5);
    weather.observedMs=1200;weather.validForMs=1200000;
    weather.tenthsC=182;weather.valid=true;
    renderer.setWeather(weather);
    FakeCanvas withWeather;
    drain(renderer,withWeather,1300);
    assert(!withWeather.escaped);
    assert(withWeather.has("18.2 C") && withWeather.has("Cloudy"));

    // Weather expiry must remove the previous forecast.
    FakeCanvas expired;
    drain(renderer,expired,1200+1200001U);
    assert(!expired.escaped);
    assert(expired.has("WEATHER STALE"));
    assert(!expired.has("18.2 C"));
    std::puts("B53_MATERIALIZED_IDLE_SCENE_PASS");
}
