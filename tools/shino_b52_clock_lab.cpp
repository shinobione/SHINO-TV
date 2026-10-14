// HOST-only tests for the actual fixed clock policy and native SceneEngine.
#include <display/ClockFoundation.h>
#include <font/glcdfont.h>
#include <array>
#include <cstdlib>
#include <fstream>
#include <iostream>
#include <stdexcept>
#include <string>
#include <vector>
static size_t allocations=0;
void* operator new(size_t n){++allocations;if(void* p=malloc(n?n:1))return p;throw std::bad_alloc();}
void* operator new[](size_t n){return ::operator new(n);}
void operator delete(void* p) noexcept{free(p);}
void operator delete[](void* p) noexcept{free(p);}
void operator delete(void* p,size_t) noexcept{free(p);}
void operator delete[](void* p,size_t) noexcept{free(p);}
using namespace ArtworkPilot;
static unsigned checks=0,cases=0,worstPixels=0;
void check(bool ok,const char* name){++checks;if(!ok)throw std::runtime_error(name);}
struct Text {int x,y;char value[41];};
struct Lcd:Canvas {
    std::array<uint16_t,240*240> pixels{}; // HOST ONLY
    std::vector<Text> texts;
    unsigned writes=0,metricDraws=0;
    Lcd(){texts.reserve(8192);}
    void bounds(int x,int y,int w,int h){
        check(x>=0&&y>=0&&w>=0&&h>=0&&x+w<=240&&y+h<=240,"240x240 bounds");
        writes+=unsigned(w*h);
    }
    void fill(int x,int y,int w,int h,uint16_t color)override{
        bounds(x,y,w,h);
        for(int yy=y;yy<y+h;++yy)for(int xx=x;xx<x+w;++xx)pixels[yy*240+xx]=color;
    }
    void text(int x,int y,const char* s,uint16_t color,uint8_t size)override{
        check(strlen(s)<=40,"bounded text");
        Text item{x,y,{}};strcpy(item.value,s);texts.push_back(item);
        for(const char* label:{"CPU","GPU","RAM","GPU TEMP"})if(!strcmp(label,s))++metricDraws;
        for(unsigned n=0;s[n];++n){
            bounds(x+int(n)*6*size,y,6*size,8*size);
            for(unsigned col=0;col<5;++col)for(unsigned row=0;row<8;++row)
                if(font[uint8_t(s[n])*5+col]&(1U<<row))
                    for(unsigned yy=0;yy<size;++yy)for(unsigned xx=0;xx<size;++xx)
                        pixels[(y+row*size+yy)*240+x+(n*6+col)*size+xx]=color;
        }
    }
    uint8_t glyphColumn(uint8_t ch,unsigned col)override{check(ch>=32&&ch<127&&col<5,"font bounds");return font[ch*5+col];}
    void row(int x,int y,uint16_t* p,int n,int repeats)override{
        bounds(x,y,n,repeats);
        for(int yy=0;yy<repeats;++yy)for(int xx=0;xx<n;++xx)pixels[(y+yy)*240+x+xx]=p[xx];
    }
    bool has(int x,int y,const char* s)const{
        for(auto i=texts.rbegin();i!=texts.rend();++i)if(i->x==x&&i->y==y)return !strcmp(i->value,s);
        return false;
    }
    void save(const std::string& path){
        std::ofstream f(path,std::ios::binary);f<<"P6\n240 240\n255\n";
        for(auto p:pixels){
            unsigned r=(p>>11)&31,g=(p>>5)&63,b=p&31;
            char v[3]={char((r<<3)|(r>>2)),char((g<<2)|(g>>4)),char((b<<3)|(b>>2))};
            f.write(v,3);
        }
        check(f.good(),"capture saved");
    }
};
constexpr uint32_t UTC=1791980760; // 2026-10-14 12:26 UTC, synthetic HOST fixture
static Metrics fresh{37.5F,68.0F,12.4F,16.0F,71.2F,true,false};
void settle(Renderer& r,Lcd& lcd,uint32_t now){
    auto before=allocations;
    for(unsigned i=0;i<200;++i){
        lcd.writes=0;
        bool changed=r.step(lcd,{},now);
        if(lcd.writes>worstPixels)worstPixels=lcd.writes;
        check(allocations==before,"zero renderer heap allocation");
        if(!changed)return;
    }
    check(false,"bounded render completion");
}
template<class F>void run(const char* name,F f){try{f();++cases;}catch(...){std::cerr<<name<<"\n";throw;}}
int main(int argc,char** argv){
    try{
        check(argc==2,"capture directory");
        std::string out=argv[1];
        run("cold boot",[]{
            ClockFoundation::State c;auto s=c.snapshot(10);
            check(!s.valid&&!s.synced,"no uptime clock");
            check(!c.view(10).valid,"no civil time before sync");
        });
        run("initial sync and lease does not renew",[]{
            ClockFoundation::State c;
            check(c.synchronize(UTC,120,120,100,102),"real-source sample admitted");
            auto v=c.view(100);
            check(v.valid&&v.hour==14&&v.minute==26&&v.day==14&&v.month==10&&v.year==2026,"UTC to local");
            check(v.source==ClockSource::PairedPc&&!v.synthetic,"explicit authenticated-PC source");
            check(c.snapshot(60100).remainingMs==60000,"reading does not renew lease");
        });
        run("invalid values preserve good sample",[]{
            ClockFoundation::State c;check(c.synchronize(UTC,60,120,100,100),"initial good");
            for(uint32_t epoch:{0U,1577836799U,4102444800U})
                check(!c.synchronize(epoch,60,120,1000,1000),"invalid epoch rejected");
            for(int offset:{-721,841})
                check(!c.synchronize(UTC,offset,120,1000,1000),"invalid offset rejected");
            for(unsigned lease:{0U,121U})
                check(!c.synchronize(UTC,60,lease,1000,1000),"invalid lease rejected");
            check(!c.synchronize(UTC,60,1,1000,2000),"sample expired in admitted request");
            check(c.snapshot(1100).remainingMs==119000,"bad sample never renews good state");
        });
        run("expiration latches",[]{
            ClockFoundation::State c;c.synchronize(UTC,60,2,100,100);
            check(c.snapshot(2099).valid,"fresh before deadline");
            check(!c.snapshot(2100).valid&&c.snapshot(2100).synced,"expired at deadline");
            check(!c.snapshot(101).valid,"expired sample does not resurrect after rollover");
            check(c.synchronize(UTC+20,60,120,102,102)&&c.snapshot(103).valid,"new sync restores clock");
        });
        run("millis rollover",[]{
            ClockFoundation::State c;uint32_t start=0xfffffff0U;
            check(c.synchronize(UTC,120,120,start,start+5),"near rollover");
            check(c.snapshot(start+1000).valid&&c.snapshot(start+1000).ageMs==1000,"wrap-safe age");
            check(c.view(start+60000).minute==27,"minute across rollover");
            check(!c.snapshot(start+120000).valid,"expiry across rollover");
        });
        run("midnight and date",[]{
            ClockFoundation::State c;c.synchronize(1791928799U,120,120,0,0);
            auto before=c.view(0),after=c.view(1000);
            check(before.hour==23&&before.minute==59&&before.day==13,"before local midnight");
            check(after.hour==0&&after.minute==0&&after.day==14,"after local midnight");
        });
        run("new year",[]{
            ClockFoundation::State c;c.synchronize(1798757999U,60,120,0,0);
            auto v=c.view(1000);check(v.year==2027&&v.month==1&&v.day==1&&v.hour==0,"new year");
        });
        run("leap dates",[]{
            ClockFoundation::State c;c.synchronize(1835391599U,60,120,0,0);
            auto v=c.view(1000);check(v.year==2028&&v.month==2&&v.day==29,"leap day");
            c.synchronize(1835477999U,60,120,0,0);v=c.view(1000);
            check(v.month==3&&v.day==1,"after leap day");
        });
        run("DST re-sync and no fabricated gap",[]{
            ClockFoundation::State c;c.synchronize(1792889999U,120,1,0,0);
            check(c.view(0).hour==2&&c.view(0).minute==59,"before autumn transition");
            check(!c.snapshot(1000).valid,"old offset expires at transition");
            c.synchronize(1792890000U,60,120,1000,1000);
            check(c.view(1000).hour==2&&c.view(1000).minute==0,"new offset on authenticated resync");
        });
        run("spring DST resync",[]{
            ClockFoundation::State c;c.synchronize(1774745999U,60,1,0,0);
            check(c.view(0).hour==1&&c.view(0).minute==59,"before spring transition");
            check(!c.snapshot(1000).valid,"old spring offset expires");
            check(c.synchronize(1774746000U,120,120,1000,1000),"fresh spring resync");
            check(c.view(1000).hour==3&&c.view(1000).minute==0,"after spring transition");
        });
        run("disconnect and reconnect",[]{
            ClockFoundation::State c;c.synchronize(UTC,120,120,100,100);
            check(c.snapshot(60100).valid,"bounded holdover independent of telemetry");
            check(!c.snapshot(120100).valid,"no PC expires time");
            check(c.synchronize(UTC+200,120,120,200100,200100)&&c.snapshot(200100).valid,"reconnect authenticated sync");
        });
        run("all four live cards and source",[&]{
            ClockFoundation::State c;c.synchronize(UTC,120,120,100,100);
            Renderer r;Lcd lcd;auto v=c.view(100);v.synthetic=true;r.setClock(v);r.setMetrics(fresh);settle(r,lcd,100);
            check(lcd.metricDraws==4,"four cards");
            check(lcd.has(14,143,"37.5%")&&lcd.has(128,143,"68.0%")&&lcd.has(14,200,"12.4 GB")&&lcd.has(128,200,"71.2 C"),"four real values");
            check(lcd.pixels[164*240+14]==BARS[1]&&lcd.pixels[164*240+128]==BARS[2],"CPU GPU dynamic bars");
            check(lcd.pixels[221*240+14]==BARS[2]&&lcd.pixels[221*240+128]==TRACK,"RAM justified; temp neutral");
            check(lcd.has(8,109,"PC SYNC 0m"),"sync age visible");
            lcd.save(out+"/idle-synced.ppm");
            r.setClock(c.view(60100));settle(r,lcd,60100);check(lcd.has(8,109,"PC SYNC 1m"),"aging visible");
        });
        run("cold display and expired display",[&]{
            ClockFoundation::State c;Renderer r;Lcd lcd;r.setMetrics(fresh);r.setClock(c.view(100));settle(r,lcd,100);
            check(lcd.has(8,39,"TIME NOT SYNCED"),"unsynced explicit");
            lcd.save(out+"/idle-unsynced.ppm");
            c.synchronize(UTC,120,120,100,100);r.setClock(c.view(120100));settle(r,lcd,120100);
            check(lcd.has(8,12,"PC CLOCK EXPIRED")&&lcd.has(8,79,"CLOCK STALE / INVALID"),"expired explicit");
            check(lcd.metricDraws>=4,"metrics retained after expiration");
            lcd.save(out+"/idle-expired.ppm");
        });
        run("telemetry expires independently",[&]{
            ClockFoundation::State c;c.synchronize(UTC,120,120,100,100);
            Renderer r;Lcd lcd;auto v=c.view(7100);v.synthetic=true;r.setClock(v);auto m=fresh;m.stale=true;r.setMetrics(m);settle(r,lcd,7100);
            check(lcd.has(14,143,"--")&&lcd.has(128,143,"--")&&lcd.has(14,200,"--")&&lcd.has(128,200,"--"),"stale four unknown cards");
            check(r.currentScene()==Scene::Idle&&lcd.has(8,35,"14:26"),"clock independent of metrics TTL");
            lcd.save(out+"/idle-pc-disconnected.ppm");
        });
        run("GPU absent and missing RAM total",[]{
            Renderer r;Lcd lcd;auto m=fresh;m.gpuAvailable=false;m.ramTotalGb=0;r.setMetrics(m);settle(r,lcd,100);
            check(lcd.has(128,143,"--")&&lcd.has(128,200,"--")&&lcd.has(14,200,"12.4 GB"),"honest unknown GPU and actual RAM");
            check(lcd.pixels[221*240+14]==TRACK,"no invented RAM denominator");
        });
        run("extreme values fit",[]{
            Renderer r;Lcd lcd;Metrics m{100,100,256,256,-40,true,false};r.setMetrics(m);settle(r,lcd,100);
            check(lcd.has(14,200,"256.0 GB")&&lcd.has(128,200,"-40.0 C"),"bounded maximum values");
        });
        run("midnight render",[&]{
            ClockFoundation::State c;c.synchronize(1791928799U,120,120,100,100);
            Renderer r;Lcd lcd;auto v=c.view(1100);v.synthetic=true;r.setClock(v);r.setMetrics(fresh);settle(r,lcd,1100);
            check(lcd.has(8,35,"00:00")&&lcd.has(8,79,"14/10/2026"),"midnight render date");
            lcd.save(out+"/idle-midnight.ppm");
        });
        std::cout<<"{\"cases_passed\":"<<cases<<",\"checks\":"<<checks<<",\"clock_state_bytes\":"<<sizeof(ClockFoundation::State)
            <<",\"renderer_bytes\":"<<sizeof(Renderer)<<",\"max_slice_pixel_writes\":"<<worstPixels
            <<",\"render_heap_allocations\":0,\"device_contacts\":0,\"individual_preview_size\":[240,240]}\n";
    }catch(const std::exception& e){std::cerr<<e.what()<<"\n";return 1;}
}

