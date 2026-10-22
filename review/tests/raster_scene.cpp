// SPDX-License-Identifier: GPL-3.0-or-later
// HOST-only pixel capture of the genuine B5.4 SceneEngine + pinned 5x7 GFX font.
// No ESP SDK, network, flash, credentials or on-device framebuffer.
#include <display/SceneEngine.h>
#include <font/glcdfont.h>
#include <array>
#include <cassert>
#include <cstdint>
#include <cstring>
#include <filesystem>
#include <fstream>
#include <iostream>
#include <stdexcept>
#include <string>
#include <vector>

namespace {
constexpr int WIDTH=240, HEIGHT=240;
struct Raster final: ArtworkPilot::Canvas {
    std::array<uint16_t,WIDTH*HEIGHT> pixels{};
    struct Label {std::string s; int x,y,scale;};
    std::vector<Label> labels;
    void fill(int x,int y,int w,int h,uint16_t color) override {
        if(x<0||y<0||w<0||h<0||x+w>WIDTH||y+h>HEIGHT)
            throw std::runtime_error("LCD fill outside 240x240");
        for(int yy=y;yy<y+h;++yy)
            for(int xx=x;xx<x+w;++xx) pixels[yy*WIDTH+xx]=color;
    }
    void text(int x,int y,const char* s,uint16_t color,uint8_t size=1) override {
        if(!s||size<1||size>6)throw std::runtime_error("Invalid LCD text");
        const size_t len=std::strlen(s);
        if(x<0||y<0||x+int(len)*6*size>WIDTH||y+8*size>HEIGHT)
            throw std::runtime_error("LCD text clipped to outer display");
        labels.push_back({s,x,y,size});
        for(size_t i=0;i<len;++i) {
            uint8_t code=static_cast<uint8_t>(s[i]);
            if(code>127)throw std::runtime_error("GFX font has no contracted UTF-8");
            for(int col=0;col<5;++col) {
                const uint8_t bits=font[code*5+col];
                for(int row=0;row<8;++row)if(bits&(1U<<row))
                    fill(x+int(i*6+col)*size,y+row*size,size,size,color);
            }
        }
    }
    uint8_t glyphColumn(uint8_t ascii,unsigned col) override {
        if(col>=5)throw std::runtime_error("Invalid font column");
        return font[ascii*5+col];
    }
    void row(int x,int y,uint16_t* p,int count,int repeats) override {
        if(!p||x<0||y<0||count<0||repeats<0||x+count>WIDTH||y+repeats>HEIGHT)
            throw std::runtime_error("LCD row overflow");
        for(int yy=y;yy<y+repeats;++yy)
            for(int xx=0;xx<count;++xx) pixels[yy*WIDTH+x+xx]=p[xx];
    }
    bool has(const char* s) const {
        for(const auto& l:labels)if(l.s==s)return true;
        return false;
    }
    void save(const std::filesystem::path& file) const {
        std::ofstream out(file,std::ios::binary);
        if(!out)throw std::runtime_error("Cannot create PPM");
        out<<"P6\n240 240\n255\n";
        for(const auto rgb:pixels) {
            const uint8_t r=uint8_t((((rgb>>11)&31)*255+15)/31);
            const uint8_t g=uint8_t((((rgb>>5)&63)*255+31)/63);
            const uint8_t b=uint8_t(((rgb&31)*255+15)/31);
            out.put(char(r));out.put(char(g));out.put(char(b));
        }
        if(!out)throw std::runtime_error("Incomplete PPM");
    }
};
ArtworkPilot::ClockData clock() {
    ArtworkPilot::ClockData c{};
    c.valid=true;c.synthetic=false;c.year=2026;c.month=10;c.day=19;
    c.hour=12;c.minute=34;c.second=0;c.observedMs=1000;
    c.validForMs=86400000;c.source=ArtworkPilot::ClockSource::Sntp;
    return c;
}
ArtworkPilot::WeatherData weather(bool stale=false) {
    ArtworkPilot::WeatherData w{};
    w.valid=true;w.synthetic=false;w.wmoCode=3;
    w.tenthsC=182;w.observedMs=1000;w.validForMs=stale?0:2700000;
    return w;
}
Raster capture(const std::filesystem::path& out,const char* name,
               ArtworkPilot::Metrics metrics,
               ArtworkPilot::DisplayMode mode,bool weatherStale=false) {
    ArtworkPilot::Renderer renderer;
    renderer.setClock(clock());
    renderer.setWeather(weather(weatherStale));
    renderer.setMetrics(metrics);
    renderer.setDisplayMode(mode);
    Raster canvas;
    bool completed=false;
    for(unsigned i=0;i<160;++i) {
        if(!renderer.step(canvas,{},1000)){completed=true;break;}
    }
    if(!completed)throw std::runtime_error("Renderer cooperative tasks starved");
    if(!canvas.has("12:34"))throw std::runtime_error("Clock missing");
    const bool clockOnly=metrics.stale||mode==ArtworkPilot::DisplayMode::ClockWeather;
    if(clockOnly) {
        if(!canvas.has("LUNDI"))throw std::runtime_error("Weekday missing");
        for(const char* s:{"CPU","GPU","RAM","GPU temp"})
            if(canvas.has(s))throw std::runtime_error("Stale/manual scene leaked a metric");
    } else {
        for(const char* s:{"CPU","GPU","RAM","GPU temp"})
            if(!canvas.has(s))throw std::runtime_error("Monitoring lost a metric");
    }
    if(weatherStale) {
        if(!canvas.has("METEO PERIMEE")||canvas.has("18.2"))
            throw std::runtime_error("Stale weather masquerades as current");
    } else if(!canvas.has("Nuageux")||!canvas.has("18.2"))
        throw std::runtime_error("Fresh weather missing");
    if(!metrics.stale&&mode==ArtworkPilot::DisplayMode::Auto) {
        bool checked=false;
        for(const auto& l:canvas.labels)if(l.s=="8.0 Go"||l.s=="123.4 Go") {
            checked=true;const auto& box=B53Layout::CARDS[2];
            if(l.x<box.x || l.y<box.y ||
               l.x+int(l.s.size())*l.scale*6>box.x+box.w ||
               l.y+8*l.scale>box.y+box.h)
                throw std::runtime_error("RAM caption overflowed its card");
        }
        if(!checked)throw std::runtime_error("RAM in Go missing");
    }
    canvas.save(out/name);
    std::cout<<name<<": "<<canvas.labels.size()<<" text items, full 240x240 RGB565 raster\n";
    return canvas;
}
} // namespace
int main(int argc,char** argv) {
    try {
        if(argc!=2)return 2;
        const std::filesystem::path out=argv[1];
        std::filesystem::create_directories(out);
        const ArtworkPilot::Metrics pc{22,34,8,16,56,true,false};
        const ArtworkPilot::Metrics pcOff{22,34,8,16,56,true,true};
        const ArtworkPilot::Metrics max{100,100,123.4F,128,100,true,false};
        const auto monitor=capture(out,"01_monitoring.ppm",pc,ArtworkPilot::DisplayMode::Auto);
        const auto autonomous=capture(out,"02_horloge_meteo.ppm",pcOff,ArtworkPilot::DisplayMode::Auto);
        const auto manual=capture(out,"03_horloge_meteo_manuel.ppm",pc,ArtworkPilot::DisplayMode::ClockWeather);
        const auto extremes=capture(out,"04_monitoring_limites.ppm",max,ArtworkPilot::DisplayMode::Auto);
        capture(out,"05_meteo_perimee.ppm",pcOff,ArtworkPilot::DisplayMode::Auto,true);
        if(manual.pixels!=autonomous.pixels)
            throw std::runtime_error("Manual clock doesn't match PC-off autonomous display");
        if(monitor.pixels==autonomous.pixels||extremes.pixels==monitor.pixels)
            throw std::runtime_error("Unexpected identical raster");
        std::cout<<"B54_UI_RASTER_HOST_PASS cases=5 no_clipped_text=1 same_manual_autonomous=1\n";
    }catch(const std::exception& e) {
        std::cerr<<"B54_UI_RASTER_HOST_FAIL: "<<e.what()<<"\n";return 1;
    }
    return 0;
}
