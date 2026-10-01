// Actual native authentication/receiver plus the same scene renderer as ESP8266.
// The 240x240 pixel array and signing fixtures exist only in this offline lab.
#include <MediaIngress.h>
#include <display/ArtworkPilot.h>
#include <font/glcdfont.h>
#include "fixtures.inc"
#include <array>
#include <chrono>
#include <cstdlib>
#include <fstream>
#include <iostream>
#include <stdexcept>
#include <string>
#include <vector>
static size_t allocations=0;
void* operator new(size_t n) { ++allocations; if(void* p=malloc(n?n:1))return p;throw std::bad_alloc(); }
void* operator new[](size_t n) { return ::operator new(n); }
void* operator new(size_t n,const std::nothrow_t&) noexcept {try{return ::operator new(n);}catch(...){return nullptr;}}
void* operator new[](size_t n,const std::nothrow_t&) noexcept {return ::operator new(n,std::nothrow);}
void operator delete(void* p) noexcept { free(p); }
void operator delete[](void* p) noexcept { free(p); }
void operator delete(void* p,size_t) noexcept { free(p); }
void operator delete[](void* p,size_t) noexcept { free(p); }
void operator delete(void* p,const std::nothrow_t&) noexcept {free(p);}
void operator delete[](void* p,const std::nothrow_t&) noexcept {free(p);}
using namespace ArtworkPilot;
static unsigned checks=0,passed=0,worstPixels=0,worstTransfers=0;
static uint32_t now=100;
static void check(bool ok,const char* label) {++checks;if(!ok)throw std::runtime_error(label);}
struct DrawText {int x,y;char text[41];};
class SoftwareLcd final : public Canvas {
public:
    std::array<uint16_t,240*240> pixels{};
    std::vector<DrawText> texts;
    unsigned rows=0,operations=0,stepPixels=0,stepTransfers=0,metricDraws=0;
    SoftwareLcd() {texts.reserve(4096);}
    void bounds(int x,int y,int w,int h) {
        check(x>=0 && y>=0 && w>=0 && h>=0 && x+w<=240 && y+h<=240,"LCD bounds");
        ++operations; stepPixels+=w*h; ++stepTransfers;
    }
    void fill(int x,int y,int w,int h,uint16_t color) override {
        bounds(x,y,w,h);
        for(int yy=y;yy<y+h;++yy)for(int xx=x;xx<x+w;++xx)pixels[yy*240+xx]=color;
    }
    void text(int x,int y,const char* s,uint16_t color,uint8_t size) override {
        check(strlen(s)<=40,"bounded provider/metric text");
        DrawText t{x,y,{}};strcpy(t.text,s);texts.push_back(t);
        for(const char* label:{"CPU","GPU","RAM","GPU TEMP"})if(!strcmp(s,label))++metricDraws;
        for(unsigned n=0;s[n];++n) {
            // Transparent GFX glyphs write a subset of this conservative cell
            // area. Explicit row/fill writes are exact. No native time claim.
            bounds(x+n*6*size,y,6*size,8*size);
            for(int col=0;col<5;++col)for(int row=0;row<8;++row)
                if(font[uint8_t(s[n])*5+col]&(1U<<row))
                    for(unsigned yy=0;yy<size;++yy)for(unsigned xx=0;xx<size;++xx)
                        pixels[(y+row*size+yy)*240+x+(n*6+col)*size+xx]=color;
        }
    }
    uint8_t glyphColumn(uint8_t ch,unsigned col) override {
        check(ch>=32 && ch<127 && col<5,"bounded pinned font access");return font[ch*5+col];
    }
    void row(int x,int y,uint16_t* data,int count,int repeats) override {
        bounds(x,y,count,repeats);stepTransfers+=repeats-1;++rows;
        for(int r=0;r<repeats;++r)for(int i=0;i<count;++i)pixels[(y+r)*240+x+i]=data[i];
    }
    bool textAt(int x,int y,const char* expected) const {
        for(auto it=texts.rbegin();it!=texts.rend();++it)
            if(it->x==x && it->y==y)return !strcmp(it->text,expected);
        return false;
    }
    void save(const std::string& path) {
        std::ofstream out(path,std::ios::binary);out<<"P6\n240 240\n255\n";
        for(uint16_t p:pixels) {
            const unsigned r=(p>>11)&31,g=(p>>5)&63,b=p&31;
            const char rgb[3]={char((r<<3)|(r>>2)),char((g<<2)|(g>>4)),char((b<<3)|(b>>2))};out.write(rgb,3);
        }
        check(out.good(),"software preview output");
    }
};
static Metrics fresh{37.5F,68.0F,12.4F,16.0F,71.2F,true,false};
static const Group& group(const char* name) {
    for(const auto& g:groups)if(!strcmp(g.name,name))return g;
    throw std::runtime_error("missing fixture");
}
static std::string decode(const char* hex) {
    std::string b(strlen(hex)/2,'\0');check(m7::unhex(hex,reinterpret_cast<uint8_t*>(b.data()),b.size()),"fixture decoding");return b;
}
struct Bytes {
    std::string bytes;size_t at=0;
    int available(){return int(bytes.size()-at);}
    int read(){return available()?uint8_t(bytes[at++]):-1;}
    bool connected(){return false;}
};
struct Harness {
    m7::Authority authority{0x1122334455667788ULL};
    m7::Receiver receiver;
    m7::Ingress ingress{authority,receiver,"tv.test",[](){return now;}};
    Renderer renderer;
    SoftwareLcd lcd;
    Harness() {
        now=100;
        uint8_t point[65];check(m7::unhex(publicPoint,point,65),"public fixture point");
        check(authority.enroll("media-test",point,15),"real native enrollment");
        renderer.setMetrics(fresh);settle();
    }
    void packet(const Packet& p,bool partial=false) {
        check(authority.issue(0,p.nonce,now,1000),"bounded native challenge");
        std::string raw=std::string(p.header)+decode(p.body);
        if(partial)raw.resize(raw.size()-200);
        const size_t n=raw.find("\r\n");check(ingress.begin(raw.substr(0,n).c_str(),now),"native ingress Begin");
        Bytes client{raw.substr(n+2)};const unsigned before=lcd.operations;
        for(unsigned i=0;i<50;++i)if(!(ingress.needsProof()?ingress.verifyHeaders():ingress.poll(client)))break;
        check(lcd.operations==before,"no LCD operation in authentication/receiver ingress");
        check(ingress.bodyBytes()==0,"terminal ingress body cleanup");
    }
    void commit(const Group& g) {
        for(unsigned i=0;i<g.count-1;++i)packet(g.packets[i]);
        check(!strcmp(ingress.outcome,"COMMITTED"),"real verified native Commit");
        check(!receiver.pending && !receiver.stagedBytes(),"Commit staging cleanup");
    }
    bool step() {
        lcd.stepPixels=lcd.stepTransfers=0;const size_t before=allocations;
        const bool changed=renderer.step(lcd,receiver.sink.borrow(),now);
        check(allocations==before,"renderer performs zero heap allocations");
        if(lcd.stepPixels>worstPixels)worstPixels=lcd.stepPixels;
        if(lcd.stepTransfers>worstTransfers)worstTransfers=lcd.stepTransfers;
        check(lcd.stepPixels<=10000,"bounded LCD pixel work per slice");return changed;
    }
    void settle() {
        for(unsigned i=0;i<160;++i)if(!step())return;
        check(false,"bounded cooperative convergence");
    }
    void artEquals(const Group& g) {
        const auto bytes=decode(g.image);
        for(int y=0;y<ART_SIZE;++y)for(int x=0;x<ART_SIZE;++x) {
            const unsigned at=((y/SCALE)*32+x/SCALE)*2;
            check(lcd.pixels[(ART_Y+y)*240+ART_X+x]==
                  (uint16_t(uint8_t(bytes[at]))|(uint16_t(uint8_t(bytes[at+1]))<<8)),"integer RGB565LE upscale");
        }
    }
    void fixtures() {
        ClockData c;c.valid=c.synthetic=true;c.year=2026;c.month=10;c.day=1;c.hour=14;c.minute=26;
        c.observedMs=now;c.validForMs=600000;renderer.setClock(c);
        WeatherData w;w.valid=w.synthetic=true;w.observedMs=now;w.validForMs=600000;w.tenthsC=180;
        strcpy(w.place,"Lezignan");strcpy(w.condition,"Clear");renderer.setWeather(w);settle();
    }
};
int main(int argc,char** argv) {
 try {
    check(argc==2,"preview directory argument");const std::string out=argv[1];std::vector<std::string> names;
    auto run=[&](const char* name,auto f){f();++passed;names.push_back(name);};
    run("idle with explicit synthetic clock/weather and four cards",[&](){
        Harness h;h.fixtures();check(h.renderer.currentScene()==Scene::Idle,"IDLE scene");
        check(h.lcd.textAt(8,12,"SYNTHETIC PREVIEW DATA") && h.lcd.textAt(8,35,"14:26"),"fixture clearly labeled");
        check(h.lcd.textAt(14,143,"37.5%") && h.lcd.textAt(128,143,"68.0%") && h.lcd.textAt(14,200,"12.4 GB") && h.lcd.textAt(128,200,"71.2 C"),"all four values");
        check(h.lcd.textAt(64,187,"/16.0 GB"),"RAM total is explicit");
        check(h.lcd.pixels[164*240+14]==BARS[1] && h.lcd.pixels[164*240+128]==BARS[2] && h.lcd.pixels[221*240+14]==BARS[2],"owner bar thresholds");
        check(h.lcd.pixels[221*240+128]==TRACK,"no invented temperature percentage");h.lcd.save(out+"/idle.ppm");
    });
    run("first native Commit selects music only",[&](){Harness h;const auto cards=h.lcd.metricDraws;
        h.commit(group("first"));h.settle();h.artEquals(group("first"));check(h.renderer.currentScene()==Scene::Playing && h.lcd.metricDraws==cards,"PLAYING has zero metric paints");
        check(h.lcd.textAt(8,210,"PLAYING") && h.lcd.textAt(8,230,"0:42") && h.lcd.textAt(208,230,"3:00"),"authenticated reported progress");
        check(h.lcd.pixels[130*240+14]==BG,"old metric region removed");h.lcd.save(out+"/playing.ppm");});
    run("replacement during cooperative drawing owns complete new cover",[&](){Harness h;h.commit(group("first"));for(int i=0;i<40;++i)h.step();
        h.commit(group("replacement"));h.settle();h.artEquals(group("replacement"));check(h.receiver.sink.commits==2,"replacement Commit count");});
    run("same cover repeat retains marquee and no full scene redraw",[&](){Harness h;h.commit(group("first"));h.settle();const auto before=h.lcd.pixels;
        h.commit(group("repeat"));h.settle();check(before==h.lcd.pixels,"same-cover repeat deterministic");const auto ops=h.lcd.operations;
        check(!h.step() && ops==h.lcd.operations,"steady state no LCD work");});
    run("validated Begin presents fallback but never staged pixels",[&](){Harness h;h.commit(group("first"));h.settle();h.packet(group("replacement").packets[0]);h.settle();
        check(h.receiver.pending && !h.receiver.sink.image && h.renderer.currentScene()==Scene::NoArtwork,"Begin releases image and selects NO ARTWORK");
        check(!strcmp(h.receiver.sink.caption.title,"Neon Streets") && h.receiver.sink.borrow().data==nullptr,"only authenticated Begin metadata exposed");
        h.packet(group("replacement").packets[1]);const auto before=h.lcd.pixels;h.settle();check(before==h.lcd.pixels,"staging tile does not become artwork");});
    run("interrupted body and authenticated Abort clean terminal resources",[&](){Harness h;h.commit(group("first"));h.settle();const auto& g=group("replacement");
        h.packet(g.packets[0]);h.packet(g.packets[1]);h.packet(g.packets[2],true);check(!strcmp(h.ingress.outcome,"PARTIAL"),"partial incoming tile denied");
        h.packet(g.packets[g.count-1]);h.settle();check(!h.receiver.pending && !h.receiver.stagedBytes() && !h.receiver.sink.image && h.renderer.currentScene()==Scene::NoArtwork,"Abort cleanup with bounded metadata fallback");});
    run("successful Commit after fallback displays complete cover",[&](){Harness h;const auto& g=group("first");h.packet(g.packets[0]);h.settle();
        for(unsigned i=1;i<g.count-1;++i)h.packet(g.packets[i]);h.settle();h.artEquals(g);check(h.renderer.currentScene()==Scene::Playing,"Commit transition");});
    run("rejected canonical metadata preserves ownership and display",[&](){Harness h;h.commit(group("first"));h.settle();const auto revision=h.receiver.sink.revision;
        const auto* image=h.receiver.sink.image.get();const auto before=h.lcd.pixels;h.packet(group("rejected").packets[0]);h.settle();
        check(!strcmp(h.ingress.outcome,"BAD_METADATA") && image==h.receiver.sink.image.get() && revision==h.receiver.sink.revision && before==h.lcd.pixels,"metadata denial preserves valid owner");});
    run("coverless Commit music placeholder",[&](){Harness h;const auto cards=h.lcd.metricDraws;h.commit(group("missing"));h.settle();
        check(h.renderer.currentScene()==Scene::NoArtwork && h.lcd.metricDraws==cards && !h.receiver.sink.image,"NO ARTWORK has zero metric paints");
        check(h.lcd.textAt(90,ART_Y+ART_SIZE/2+22,"NO ARTWORK"),"tasteful native placeholder");h.lcd.save(out+"/no-artwork.ppm");});
    run("playing pause resume with reported position frozen",[&](){Harness h;h.commit(group("first"));h.settle();h.commit(group("paused"));h.settle();
        check(h.renderer.currentScene()==Scene::Paused && h.lcd.textAt(8,210,"PAUSED"),"PAUSED scene");h.artEquals(group("paused"));h.lcd.save(out+"/paused.ppm");
        const auto before=h.lcd.pixels;now+=10000;h.settle();check(before==h.lcd.pixels,"paused position never fabricated/interpolated");
        h.commit(group("resume"));h.settle();check(h.renderer.currentScene()==Scene::Playing,"resume transition");});
    run("paused timeout is disabled until owner sets policy",[&](){Harness h;h.commit(group("paused"));h.settle();now+=86400000;h.settle();
        check(h.renderer.currentScene()==Scene::Paused,"default PAUSED retention");h.renderer.setPolicy({1000,300});h.settle();check(h.renderer.currentScene()==Scene::Idle,"explicit configurable timeout seam");
        now=100;h.settle();check(h.renderer.currentScene()==Scene::Idle,"expired pause cannot resurrect on timer rollover");});
    run("paused missing cover remains music only",[&](){Harness h;h.commit(group("paused_missing"));h.settle();
        check(h.renderer.currentScene()==Scene::NoArtwork && h.lcd.textAt(8,210,"PAUSED"),"paused fallback");});
    run("STOPPED debounce then exclusive IDLE",[&](){Harness h;h.commit(group("first"));h.settle();h.commit(group("stopped"));h.settle();
        check(h.renderer.currentScene()==Scene::Playing && h.lcd.textAt(8,210,"STOPPED"),"bounded STOPPED dwell");now+=299;h.settle();
        check(h.renderer.currentScene()==Scene::Playing,"no premature transition");++now;h.settle();check(h.renderer.currentScene()==Scene::Idle,"debounced IDLE");});
    run("NO SESSION and UNAVAILABLE select IDLE",[&](){Harness h;h.commit(group("first"));h.settle();h.commit(group("no_session"));h.settle();
        check(h.renderer.currentScene()==Scene::Idle,"NO SESSION IDLE");h.commit(group("unavailable"));h.settle();check(h.renderer.currentScene()==Scene::Idle,"UNAVAILABLE IDLE");});
    run("telemetry background updates and stale flags preserve music",[&](){Harness h;h.commit(group("first"));h.settle();const auto cards=h.lcd.metricDraws,ops=h.lcd.operations;
        Metrics m=fresh;m.cpu=92;m.gpu=18;m.ramGb=14;m.gpuTempC=88;h.renderer.setMetrics(m);h.settle();
        check(cards==h.lcd.metricDraws && ops==h.lcd.operations,"fresh telemetry retained with no music repaint");m.stale=true;h.renderer.setMetrics(m);now+=6001;h.settle();
        check(h.renderer.telemetryStale() && h.renderer.currentScene()==Scene::Playing && cards==h.lcd.metricDraws,"independent stale telemetry during music");
        h.commit(group("no_session"));h.settle();check(h.renderer.currentScene()==Scene::Offline,"no session plus unsynced PC disconnect");
        m.stale=false;h.renderer.setMetrics(m);h.settle();check(h.renderer.currentScene()==Scene::Idle && h.lcd.textAt(14,143,"92.0%"),"latest background sample on return to IDLE");});
    run("offline waiting never invents time or weather",[&](){Harness h;Metrics m=fresh;m.stale=true;h.renderer.setMetrics(m);h.settle();
        check(h.renderer.currentScene()==Scene::Offline && h.lcd.textAt(8,39,"WAITING FOR PC") && h.lcd.textAt(8,79,"DATE UNAVAILABLE") && h.lcd.textAt(8,97,"WEATHER UNAVAILABLE"),"explicit offline state");
        check(h.lcd.pixels[164*240+14]==TRACK && h.lcd.pixels[221*240+128]==TRACK,"stale metric tracks neutral");h.lcd.save(out+"/offline.ppm");});
    run("valid clock continues over disconnect and expires honestly",[&](){Harness h;h.fixtures();Metrics m=fresh;m.stale=true;h.renderer.setMetrics(m);now+=60000;h.settle();
        check(h.renderer.currentScene()==Scene::Idle && h.lcd.textAt(8,35,"14:27"),"trusted lease keeps ticking");now+=540001;h.settle();
        check(h.renderer.currentScene()==Scene::Offline && h.lcd.textAt(8,79,"CLOCK STALE / INVALID") && h.lcd.textAt(8,97,"WEATHER STALE / INVALID"),"lease expiry not a fake live value");});
    run("provider validity requires dates and explicit freshness lease",[&](){Harness h;ClockData c;c.valid=true;c.year=2026;c.month=13;c.day=1;c.validForMs=10000;c.observedMs=now;
        h.renderer.setClock(c);WeatherData w;w.valid=true;w.tenthsC=180;h.renderer.setWeather(w);h.settle();
        check(h.lcd.textAt(8,39,"TIME NOT SYNCED") && h.lcd.textAt(8,97,"WEATHER STALE / INVALID"),"invalid provider facts withheld");});
    run("weather cache displays age even without a clock provider",[&](){Harness h;WeatherData w;w.valid=true;w.observedMs=now;w.validForMs=180000;w.tenthsC=-1;
        strcpy(w.place,"Lezignan");strcpy(w.condition,"Clear");h.renderer.setWeather(w);h.settle();
        check(h.lcd.textAt(8,97,"-0.1 C | Lezignan") && h.lcd.textAt(196,109,"0m old"),"weather precision and known age");
        now+=60000;h.settle();check(h.lcd.textAt(196,109,"1m old"),"independent weather aging");});
    run("trusted clock date leap and millis rollover",[&](){Harness h;now=0xfffffff0U;ClockData c;c.valid=true;c.year=2028;c.month=2;c.day=28;c.hour=23;c.minute=59;c.second=59;
        c.validForMs=60000;c.observedMs=now;h.renderer.setClock(c);now+=2000;h.settle();
        check(h.lcd.textAt(8,35,"00:00") && h.lcd.textAt(8,79,"29/02/2028"),"wrap-safe trusted date rollover");});
    run("RAM unknown denominator and GPU unavailable remain neutral",[&](){Harness h;Metrics m=fresh;m.gpuAvailable=false;m.ramTotalGb=0;h.renderer.setMetrics(m);h.settle();
        check(h.lcd.pixels[164*240+128]==TRACK && h.lcd.pixels[221*240+14]==TRACK && h.lcd.textAt(14,200,"12.4 GB"),"unknown percentages honest");});
    run("bar boundaries retain two percentage point hysteresis",[&](){Harness h;Metrics m=fresh;m.cpu=19;h.renderer.setMetrics(m);h.settle();
        check(h.lcd.pixels[164*240+14]==BARS[1],"reviewed previous yellow band at 19");m.cpu=17.9F;h.renderer.setMetrics(m);h.settle();check(h.lcd.pixels[164*240+14]==BARS[0],"falls below 18");
        m.cpu=21.9F;h.renderer.setMetrics(m);h.settle();check(h.lcd.pixels[164*240+14]==BARS[0],"below rising 22");m.cpu=22;h.renderer.setMetrics(m);h.settle();check(h.lcd.pixels[164*240+14]==BARS[1],"rises at 22");});
    run("marquee full sixty codepoints with initial delay and endpoint dwell",[&](){Harness h;h.commit(group("long"));h.settle();
        check(strlen(h.receiver.sink.caption.title)==60 && strlen(h.receiver.sink.caption.artist)==60,"full native metadata lengths retained");
        const auto start=h.lcd.pixels;h.lcd.save(out+"/marquee-start.ppm");now+=1499;h.settle();check(h.renderer.currentTitleOffset()==0 && start==h.lcd.pixels,"initial stationary delay");
        now=100+Marquee::INITIAL_MS+248*Marquee::PIXEL_MS;h.settle();check(h.renderer.currentTitleOffset()==248,"slow title middle");h.lcd.save(out+"/marquee-middle.ppm");
        now=100+Marquee::INITIAL_MS+496*Marquee::PIXEL_MS;h.settle();check(h.renderer.currentTitleOffset()==496,"title far end");h.lcd.save(out+"/marquee-end.ppm");
        now+=Marquee::END_MS-1;h.settle();check(h.renderer.currentTitleOffset()==496,"far-end dwell");});
    run("marquee moves smoothly both directions and is wrap safe",[&](){Marquee m;m.reset(0xfffffff0U);uint16_t previous=0;
        for(uint32_t elapsed=0;elapsed<85000;elapsed+=40){const auto offset=m.offset(0xfffffff0U+elapsed,720);
            check(offset<=496 && (offset>previous?offset-previous:previous-offset)<=1,"bounded smooth bounce without jump");previous=offset;}
        check(m.offset(200,100)==0,"fitting caption does not scroll");});
    run("slow cooperative loop cannot starve artist status or progress",[&](){Harness h;h.commit(group("long"));
        for(unsigned i=0;i<100;++i){now+=40;h.step();}
        check(h.lcd.textAt(8,210,"PLAYING") && h.lcd.textAt(8,230,"0:42") && h.renderer.currentArtistOffset()>0,"fair bounded text scheduling");});
    run("marquee title and artist clipping never alters cover or surrounding pixels",[&](){Harness h;h.commit(group("long"));h.settle();const auto before=h.lcd.pixels;
        now+=Marquee::INITIAL_MS+200*Marquee::PIXEL_MS;h.settle();
        check(h.renderer.currentArtistOffset()>0,"long artist gets equivalent slow scrolling");
        for(int y=0;y<240;++y)for(int x=0;x<240;++x)if(!(x>=8 && x<232 && ((y>=176 && y<192)||(y>=196 && y<204))))
            check(before[y*240+x]==h.lcd.pixels[y*240+x],"strict text viewport clipping");});
    run("track or scene change resets a moving marquee",[&](){Harness h;h.commit(group("long"));h.settle();now+=10000;h.settle();check(h.renderer.currentTitleOffset()>0,"moving title");
        h.commit(group("after_long"));h.settle();check(h.renderer.currentTitleOffset()==0,"new track starts at origin");
        h.commit(group("paused_missing"));h.settle();check(h.renderer.currentTitleOffset()==0 && h.renderer.currentArtistOffset()==0,"scene resets both marquees");});
    run("track identity is not inferred from matching labels",[&](){Harness h;h.commit(group("long"));h.settle();now+=10000;h.settle();check(h.renderer.currentTitleOffset()>0,"first title scrolling");
        h.commit(group("same_labels_new_track"));h.settle();check(h.renderer.currentTitleOffset()==0,"signed track key resets matching title");});
    run("accented names transliterate and unsupported UTF8 uses one fallback",[&](){Harness h;h.commit(group("utf8"));h.settle();
        check(!strcmp(h.receiver.sink.caption.title,"Cafe / ?") && !strcmp(h.receiver.sink.caption.artist,"Bjork"),"native font limits explicit");
        h.commit(group("accented_long"));h.settle();check(strlen(h.receiver.sink.caption.title)==60,"sixty accented codepoints not shortened");
        char result[61];const char incomplete[2]={char(0xe2),char(0x82)};captionText(result,incomplete,2);check(!strcmp(result,"?"),"bounded incomplete UTF8 decode");});
    run("progress null zero missing and invalid never invent timing",[&](){Harness h;h.commit(group("unknown_progress"));h.settle();check(h.lcd.textAt(8,230,"--:--"),"unknown position");
        h.commit(group("zero_duration"));h.settle();check(h.lcd.textAt(8,230,"--:--"),"zero duration");h.commit(group("position_only"));h.settle();check(h.lcd.textAt(8,230,"--:--"),"absent denominator");
        const auto revision=h.receiver.sink.revision;h.packet(group("invalid_progress").packets[0]);check(!strcmp(h.ingress.outcome,"BAD_METADATA") && revision==h.receiver.sink.revision,"invalid position rejected before publication");});
    run("reported hour durations and empty labels render safely",[&](){Harness h;h.commit(group("hour_progress"));h.settle();check(h.lcd.textAt(8,230,"1:00:01") && h.lcd.textAt(178,230,"168:00:00"),"bounded seven-day durations");
        h.commit(group("empty_labels"));h.settle();check(h.renderer.currentScene()==Scene::NoArtwork,"empty captions fallback safely");});
    run("absent invalid and 48px image ownership fails closed",[&](){Harness h;h.commit(group("first"));h.settle();h.receiver.sink.image.reset();h.settle();
        check(h.receiver.sink.borrow().cover==Cover::Invalid && h.renderer.currentScene()==Scene::NoArtwork,"absent allocation never dereferenced");
        h.receiver.sink.committedBytes=1;h.receiver.sink.image.reset(new uint8_t[1]);h.settle();check(h.receiver.sink.borrow().cover==Cover::Invalid,"invalid extent");
        h.receiver.sink.image.reset(new uint8_t[4608]);h.receiver.sink.committedBytes=4608;++h.receiver.sink.revision;h.settle();check(h.receiver.sink.borrow().cover==Cover::Unsupported,"48px never enabled");
        h.receiver.sink.clear();h.settle();check(h.renderer.currentScene()==Scene::Idle,"clear deterministic IDLE");});
    run("expiry and principal cancellation release terminal resources",[&](){Harness h;h.packet(group("first").packets[0]);now+=8001;check(!h.receiver.tick(now),"eight-second native deadline unchanged");h.settle();
        check(!h.receiver.pending && !h.receiver.stagedBytes() && !h.receiver.sink.image && h.renderer.currentScene()==Scene::NoArtwork,"expiry safe fallback");
        h.packet(group("replacement").packets[0]);h.receiver.cancelPrincipal(0);h.settle();check(h.renderer.currentScene()==Scene::Idle && !h.receiver.sink.presented,"revocation drops presentation");});
    Harness benchmark;benchmark.commit(group("first"));const auto start=std::chrono::steady_clock::now();benchmark.settle();
    const auto us=std::chrono::duration_cast<std::chrono::microseconds>(std::chrono::steady_clock::now()-start).count();
    std::cout<<"{\"cases_passed\":"<<passed<<",\"checks\":"<<checks<<",\"renderer_bytes\":"<<sizeof(Renderer)<<",\"caption_bytes\":"<<sizeof(Caption)<<",\"scale\":"<<SCALE<<",\"cover_size\":"<<ART_SIZE<<",\"host_render_us\":"<<us<<",\"max_slice_pixel_writes_upper_bound\":"<<worstPixels<<",\"max_slice_transfer_requests_upper_bound\":"<<worstTransfers<<",\"render_heap_allocations\":0,\"device_contacts\":0,\"tests\":[";
    for(size_t i=0;i<names.size();++i){if(i)std::cout<<',';std::cout<<'"'<<names[i]<<'"';}std::cout<<"]}\n";return 0;
 } catch(const std::exception& e){std::cerr<<e.what()<<'\n';return 1;}
}
