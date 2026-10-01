// Actual native receiver + pinned BearSSL, with a host-only software LCD.
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
static unsigned checks=0, passed=0, worstPixels=0;
static uint32_t now=100;
static void check(bool ok,const char* label) { ++checks;if(!ok)throw std::runtime_error(label); }
struct DrawText {int x,y;char text[21];};
class SoftwareLcd final : public Canvas {
public:
    std::array<uint16_t,240*240> pixels{}; // HOST ONLY; never native firmware
    std::vector<DrawText> texts;
    unsigned rows=0, operations=0, maxStepPixels=0, stepPixels=0;
    SoftwareLcd() {texts.reserve(4096);}
    void bounds(int x,int y,int w,int h) {
        check(x>=0 && y>=0 && w>=0 && h>=0 && x+w<=240 && y+h<=240,"LCD bounds");
        ++operations;stepPixels+=w*h;
    }
    void fill(int x,int y,int w,int h,uint16_t color) override {
        bounds(x,y,w,h);
        for(int yy=y;yy<y+h;++yy)for(int xx=x;xx<x+w;++xx)pixels[yy*240+xx]=color;
    }
    void text(int x,int y,const char* s,uint16_t color,uint8_t size) override {
        check(strlen(s)<=20,"caption/metric text width");
        DrawText t{x,y,{}};strcpy(t.text,s);texts.push_back(t);
        for(unsigned n=0;s[n];++n) {
            bounds(x+n*6*size,y,6*size,8*size);
            for(int col=0;col<5;++col)for(int row=0;row<8;++row)
                if(font[uint8_t(s[n])*5+col]&(1U<<row))
                    for(unsigned yy=0;yy<size;++yy)for(unsigned xx=0;xx<size;++xx)
                        pixels[(y+row*size+yy)*240+x+(n*6+col)*size+xx]=color;
        }
    }
    void row(int x,int y,uint16_t* data,int count,int repeats) override {
        bounds(x,y,count,repeats);++rows;
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
            const char rgb[3]={char((r<<3)|(r>>2)),char((g<<2)|(g>>4)),char((b<<3)|(b>>2))};
            out.write(rgb,3);
        }
        check(out.good(),"software preview output");
    }
};
static Metrics fresh{37.5F,68.0F,12.4F,32.0F,71.2F,true,false};
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
        uint8_t point[65];check(m7::unhex(publicPoint,point,65),"public fixture point");
        check(authority.enroll("media-test",point,15),"real native enrollment");
        renderer.setMetrics(fresh);settle();
    }
    void packet(const Packet& p,bool partial=false) {
        check(authority.issue(0,p.nonce,now,1000),"bounded native challenge");
        std::string raw=std::string(p.header)+decode(p.body);
        if(partial)raw.resize(raw.size()-200);
        const size_t n=raw.find("\r\n");
        check(ingress.begin(raw.substr(0,n).c_str(),now),"native ingress Begin");
        Bytes client{raw.substr(n+2)};
        const unsigned before=lcd.operations;
        for(unsigned i=0;i<50;++i)
            if(!(ingress.needsProof()?ingress.verifyHeaders():ingress.poll(client)))break;
        check(lcd.operations==before,"no LCD operation in authentication/receiver ingress");
        check(ingress.bodyBytes()==0,"terminal ingress body cleanup");
    }
    void commit(const Group& g) {
        for(unsigned i=0;i<g.count-1;++i)packet(g.packets[i]);
        check(!strcmp(ingress.outcome,"COMMITTED"),"real verified native Commit");
        check(!receiver.pending && receiver.stagedBytes()==0,"Commit staging cleanup");
    }
    void settle() {
        const size_t before=allocations;bool idle=false;
        for(unsigned i=0;i<160;++i) {
            bool changed=step();
            if(!changed){idle=true;break;}
        }
        check(idle,"bounded cooperative convergence");
        check(allocations==before,"renderer performs zero heap allocations");
        check(lcd.maxStepPixels<=12000,"bounded LCD work per slice");
    }
    bool step() {
        lcd.stepPixels=0;
        const bool changed=renderer.step(lcd,receiver.sink.borrow());
        if(lcd.stepPixels>lcd.maxStepPixels)lcd.maxStepPixels=lcd.stepPixels;
        if(lcd.stepPixels>worstPixels)worstPixels=lcd.stepPixels;
        return changed;
    }
    void artEquals(const Group& g) {
        const auto bytes=decode(g.image);
        for(int y=0;y<96;++y)for(int x=0;x<96;++x) {
            size_t at=((y/3)*32+x/3)*2;
            uint16_t p=uint8_t(bytes[at])|(uint16_t(uint8_t(bytes[at+1]))<<8);
            check(lcd.pixels[(y+8)*240+x+8]==p,"nearest-neighbor RGB565LE pixels");
        }
    }
};
int main(int argc,char** argv) {
 try {
    if(argc!=2)throw std::runtime_error("preview output directory required");
    const std::string out=argv[1];std::vector<const char*> names;
    auto run=[&](const char* name,auto test){test();++passed;names.push_back(name);};
    run("first committed RGB565LE cover",[&](){Harness h;h.commit(group("first"));h.settle();h.artEquals(group("first"));check(h.lcd.pixels[8*240+8]==0xf800 && h.lcd.pixels[8*240+56]==0x001f,"red/blue byte order");h.lcd.save(out+"/playing.ppm");});
    run("replacement during cooperative draw",[&](){Harness h;h.commit(group("first"));for(int i=0;i<26;++i)h.step();h.commit(group("replacement"));h.settle();h.artEquals(group("replacement"));check(h.receiver.sink.commits==2,"replacement Commit count");h.lcd.save(out+"/replacement.ppm");});
    run("same-cover repeat and steady state",[&](){Harness h;h.commit(group("first"));h.settle();const auto image=h.lcd.pixels;h.commit(group("repeat"));h.settle();check(image==h.lcd.pixels,"same cover deterministic repeat");const auto count=h.lcd.operations;check(!h.renderer.step(h.lcd,h.receiver.sink.borrow()) && count==h.lcd.operations,"steady state no LCD redraw");});
    run("interrupted transfer and authenticated Abort",[&](){Harness h;h.commit(group("first"));h.settle();const Group& g=group("replacement");h.packet(g.packets[0]);check(h.receiver.pending && !h.receiver.sink.image,"accepted Begin releases committed owner");h.packet(g.packets[1]);h.packet(g.packets[2],true);check(!strcmp(h.ingress.outcome,"PARTIAL"),"partial incoming tile rejected");h.settle();check(h.lcd.textAt(26,52,"NO ARTWORK"),"partial image never displayed");h.lcd.save(out+"/during-transfer.ppm");h.packet(g.packets[g.count-1]);check(!h.receiver.pending && !h.receiver.stagedBytes() && !h.receiver.sink.image,"Abort terminal cleanup");h.settle();});
    run("rejected metadata preserves committed display",[&](){Harness h;h.commit(group("first"));h.settle();const auto revision=h.receiver.sink.revision;const auto* ptr=h.receiver.sink.image.get();const auto pixels=h.lcd.pixels;h.packet(group("rejected").packets[0]);check(!strcmp(h.ingress.outcome,"BAD_METADATA"),"authenticated invalid metadata denial");h.settle();check(ptr==h.receiver.sink.image.get() && revision==h.receiver.sink.revision && pixels==h.lcd.pixels,"denial does not mutate display ownership");});
    run("coverless metadata and missing artwork",[&](){Harness h;h.commit(group("missing"));h.settle();check(h.receiver.sink.borrow().cover==Cover::Missing,"coverless committed view");check(h.lcd.textAt(112,96,"PLAYING"),"metadata renders without artwork");h.lcd.save(out+"/missing-artwork.ppm");});
    for(const char* state:{"paused","stopped","no_session"})run(state,[&](){Harness h;h.commit(group(state));h.settle();check(h.lcd.textAt(112,96,stateText(stateFrom(!strcmp(state,"paused")?"PAUSED":!strcmp(state,"stopped")?"STOPPED":"NO_SESSION"))),"playback state");h.lcd.save(out+"/"+state+".ppm");});
    run("telemetry updates coexist with committed cover",[&](){Harness h;h.commit(group("first"));h.settle();const auto rows=h.lcd.rows;Metrics m=fresh;m.cpu=92.0F;m.gpu=18.0F;m.ramGb=18.2F;m.gpuTempC=88.0F;h.renderer.setMetrics(m);h.settle();h.artEquals(group("first"));check(rows==h.lcd.rows,"telemetry does not redraw artwork");check(h.lcd.textAt(17,141,"92.0%") && h.lcd.textAt(133,141,"18.0%") && h.lcd.textAt(17,199,"18.2 GB") && h.lcd.textAt(133,199,"88.0 C"),"all four actual telemetry values");check(h.lcd.pixels[163*240+17]==DashboardV2::PALETTE[3],"CPU dynamic burgundy bar");m.stale=true;h.renderer.setMetrics(m);h.settle();check(h.lcd.pixels[163*240+17]==DashboardV2::TRACK,"stale telemetry resets bar to neutral");h.lcd.save(out+"/stale-telemetry.ppm");});
    run("unknown GPU and RAM denominator",[&](){Harness h;Metrics m=fresh;m.gpuAvailable=false;m.ramTotalGb=0;h.renderer.setMetrics(m);h.settle();check(h.lcd.pixels[163*240+133]==DashboardV2::TRACK && h.lcd.pixels[221*240+17]==DashboardV2::TRACK,"unavailable percentage is neutral");check(h.lcd.textAt(17,199,"12.4 GB"),"RAM used retained without inferred total");});
    run("long captions truncate with ellipsis",[&](){Harness h;h.commit(group("long"));h.settle();check(!strcmp(h.receiver.sink.caption.title+51,"...") && !strcmp(h.receiver.sink.caption.artist+37,"..."),"title/artist truncation");h.lcd.save(out+"/long-title.ppm");});
    run("UTF-8 uses explicit bitmap fallback",[&](){Harness h;h.commit(group("utf8"));h.settle();check(!strcmp(h.receiver.sink.caption.title,"Caf? / ?") && !strcmp(h.receiver.sink.caption.artist,"Bj?rk"),"unsupported codepoints replaced once");});
    run("absent and invalid image ownership",[&](){Harness h;h.commit(group("first"));h.settle();h.receiver.sink.image.reset();h.settle();check(h.receiver.sink.borrow().cover==Cover::Invalid && h.lcd.textAt(17,52,"INVALID COVER"),"absent allocation fails closed");h.receiver.sink.committedBytes=1;h.receiver.sink.image.reset(new uint8_t[1]);h.settle();check(h.receiver.sink.borrow().cover==Cover::Invalid,"invalid extent never dereferenced");h.receiver.sink.clear();h.settle();check(h.lcd.textAt(112,96,"NO SESSION"),"clear deterministic fallback");});
    run("48px ownership remains unsupported",[&](){Harness h;h.receiver.sink.image.reset(new uint8_t[4608]);h.receiver.sink.committedBytes=4608;h.receiver.sink.committed=true;++h.receiver.sink.revision;h.settle();check(h.receiver.sink.borrow().cover==Cover::Unsupported,"48px not enabled by pilot");});
    run("transaction expiry during draw",[&](){Harness h;h.commit(group("first"));h.settle();h.packet(group("replacement").packets[0]);now+=8001;check(!h.receiver.tick(now),"native transaction expiry");h.settle();check(!h.receiver.pending && !h.receiver.stagedBytes() && !h.receiver.sink.image,"expiry terminal cleanup");now=100;});
    Harness benchmark;benchmark.commit(group("first"));
    const auto start=std::chrono::steady_clock::now();benchmark.settle();
    const auto us=std::chrono::duration_cast<std::chrono::microseconds>(std::chrono::steady_clock::now()-start).count();
    std::cout<<"{\"cases_passed\":"<<passed<<",\"checks\":"<<checks<<",\"renderer_bytes\":"<<sizeof(Renderer)<<",\"caption_bytes\":"<<sizeof(Caption)<<",\"host_render_us\":"<<us<<",\"max_slice_pixel_writes\":"<<worstPixels<<",\"render_heap_allocations\":0,\"device_contacts\":0,\"tests\":[";
    for(size_t i=0;i<names.size();++i){if(i)std::cout<<',';std::cout<<'"'<<names[i]<<'"';}std::cout<<"]}\n";
    return 0;
 } catch(const std::exception& e){std::cerr<<e.what()<<'\n';return 1;}
}
