// HOST only: exact ClockFreshness and pinned BearSSL, no SDK or network.
#ifdef _MSC_VER
#define __attribute__(x)
#endif
#include "ClockFreshness.h"
#include <chrono>
#include <cstdlib>
#include <cstring>
#include <iostream>
#include <stdexcept>

static unsigned checks=0,cases=0,entropyCounter=0;
static ClockFreshness::Gate* reentrant=nullptr;
static bool reentryDenied=false;
static uint32_t lateTime(){return 2000;}
static unsigned sameNonceCalls=0;
static bool sameNonce(uint8_t* p,size_t n){std::memset(p,(++sameNonceCalls%2)?uint8_t(0x60+sameNonceCalls):0x77,n);return true;}
static void check(bool ok,const char* message){++checks;if(!ok)throw std::runtime_error(message);}
static bool entropy(uint8_t* p,size_t n){
    const unsigned c=++entropyCounter;
    for(size_t i=0;i<n;++i)p[i]=uint8_t((c>>((i%4)*8))^0x35^i);
    return true;
}
static bool zero(uint8_t* p,size_t n){std::memset(p,0,n);return true;}
static bool stuck(uint8_t* p,size_t n){std::memset(p,0x55,n);return true;}
static bool fail(uint8_t*,size_t){return false;}
static bool nested(uint8_t* p,size_t n){
    reentryDenied=!reentrant->issue(entropy,100);return entropy(p,n);
}
constexpr uint32_t UTC=1791980760;
constexpr const char* PASSWORD="PUBLIC-INERT-LAB-HTTP-FIXTURE";
static void frame(uint8_t* p,const ClockFreshness::Gate& gate,ClockFreshness::Workspace& w,uint32_t utc=UTC){
    std::memcpy(p,"SHINOCL2",8);
    for(unsigned i=0;i<4;++i)p[8+i]=uint8_t(utc>>(i*8));
    p[12]=120;p[13]=0;p[14]=120;p[15]=0;
    std::memcpy(p+16,gate.nonce(),16);ClockFreshness::tag(w,PASSWORD,gate.boot(),p,p+32);
}
template<class F>static void run(F f){f();++cases;}
int main(){
    try{
        using ClockFreshness::Gate;using ClockFreshness::Workspace;
        Workspace w;uint8_t p[64];
        run([&]{Gate g;ClockFoundation::State c;check(g.issue(entropy,100),"issue");frame(p,g,w);
            check(g.accept(c,w,PASSWORD,p,64,110,111),"fresh accepted");check(c.snapshot(111).valid,"fresh valid");
            check(!g.accept(c,w,PASSWORD,p,64,60110,60110),"exact replay60s rejected");
            check(c.snapshot(60110).remainingMs==60000,"replay never renews");
            check(!g.accept(c,w,PASSWORD,p,64,120110,120110)&&!c.snapshot(120110).valid,"replay after expiry rejected");});
        run([&]{Gate g;ClockFoundation::State c;check(g.issue(entropy,100),"issue");frame(p,g,w,1577836800);
            check(!g.accept(c,w,PASSWORD,p,16,110,110),"legacy old plausible cold frame refused");check(!c.snapshot(110).valid,"cold unknown");});
        run([&]{Gate g;ClockFoundation::State c;g.issue(entropy,0);frame(p,g,w);check(g.accept(c,w,PASSWORD,p,64,0,0),"initial");
            const auto before=c.snapshot(20000);g.issue(entropy,20000);frame(p,g,w,UTC-86400);
            check(!g.accept(c,w,PASSWORD,p,64,20000,20000),"day backward refused");check(c.snapshot(20000).remainingMs==before.remainingMs,"no backward renewal");
            g.issue(entropy,30000);frame(p,g,w,UTC+20);check(!g.accept(c,w,PASSWORD,p,64,30000,30000),"projected valid time cannot rewind");
            check(!c.snapshot(120000).valid,"expiry still120s");g.issue(entropy,130000);frame(p,g,w,UTC-1);
            check(!g.accept(c,w,PASSWORD,p,64,130000,130000),"watermark retained after expiration");});
        run([&]{Gate a,b;ClockFoundation::State c;a.issue(entropy,0);frame(p,a,w);b.issue(entropy,0);
            check(!b.accept(c,w,PASSWORD,p,64,1,1),"previous boot proof refused");check(!c.snapshot(1).valid,"new boot unknown");});
        run([&]{Gate a,b;ClockFoundation::State c;a.issue(sameNonce,0);frame(p,a,w);b.issue(sameNonce,0);
            check(ClockFreshness::equal(a.nonce(),b.nonce(),16),"same nonce boot binding fixture");
            check(!b.accept(c,w,PASSWORD,p,64,1,1),"MAC binds different boot even with identical nonce");});
        run([&]{Gate g;ClockFoundation::State c;check(c.synchronize(UTC,120,120,0,0),"fractional initial");
            g.issue(entropy,1500);frame(p,g,w,UTC+1);
            check(!g.accept(c,w,PASSWORD,p,64,1500,2100),"fractional delayed sample cannot rewind current projection");
            check(c.snapshot(2100).utc==UTC+2&&c.snapshot(2100).remainingMs==117900,"fractional reject preserves anchor and lease");});
        run([&]{Gate g;ClockFoundation::State c;check(c.synchronize(UTC,120,120,0,0),"progress initial");
            g.issue(entropy,1500);frame(p,g,w,UTC+3);
            check(g.accept(c,w,PASSWORD,p,64,1500,2100),"legitimate advancing sync accepted");
            check(c.snapshot(2100).utc==UTC+3,"legitimate projection progresses");});
        run([&]{Gate g;ClockFoundation::State c;g.issue(entropy,0);frame(p,g,w);
            check(!g.accept(c,w,PASSWORD,p,64,2000,2000),"challenge expiration inclusive");check(!c.snapshot(2000).valid,"expired challenge no clock");});
        run([&]{Gate g;ClockFoundation::State c;g.issue(entropy,0);frame(p,g,w);
            check(!g.accept(c,w,PASSWORD,p,64,1990,1999,lateTime),"MAC completed after deadline refused");check(!c.snapshot(2000).valid,"late verification never sets clock");});
        run([&]{Gate g;ClockFoundation::State c;c.synchronize(UTC,120,120,0,0);g.issue(entropy,0);frame(p,g,w,UTC+3);
            check(!g.accept(c,w,PASSWORD,p,64,1990,1999,lateTime),"late MAC cannot replace good clock");
            check(c.snapshot(2000).utc==UTC+2&&c.snapshot(2000).remainingMs==118000,"late MAC preserves existing lease");});
        run([&]{Gate g;ClockFoundation::State c;g.issue(entropy,100);frame(p,g,w);
            check(g.accept(c,w,PASSWORD,p,64,2098,2099),"fresh at1999ms boundary");
            check(!g.accept(c,w,PASSWORD,p,64,2098,2099),"boundary single-use remains enforced");});
        run([&]{Gate g;ClockFoundation::State c;g.issue(entropy,100);frame(p,g,w);g.expire(2100);
            check(!g.accept(c,w,PASSWORD,p,64,110,110),"full millis wrap never resurrects expired challenge");});
        run([&]{Gate g;ClockFoundation::State c;g.issue(entropy,0);frame(p,g,w);
            check(!g.accept(c,w,PASSWORD,p,64,0xfffffff0U,1),"request deadline/wrap rejected");});
        run([&]{Gate g;ClockFoundation::State c;uint32_t start=0xfffffff0U;g.issue(entropy,start);frame(p,g,w);
            check(g.accept(c,w,PASSWORD,p,64,start+5,start+6),"fresh challenge over millis wrap");});
        run([&]{Gate g;ClockFoundation::State c;for(unsigned at:{0U,8U,12U,14U,32U,63U}){
            g.issue(entropy,0);frame(p,g,w);p[at]^=1;
            check(!g.accept(c,w,PASSWORD,p,64,1,1),"modified body or proof refused");check(!c.snapshot(1).valid,"tamper does not set clock");}});
        run([&]{Gate g;ClockFoundation::State c;g.issue(entropy,0);frame(p,g,w);p[63]^=1;
            check(!g.accept(c,w,PASSWORD,p,64,1,1),"bad MAC refused");p[63]^=1;
            check(!g.accept(c,w,PASSWORD,p,64,1,1),"bad MAC consumes matching challenge");});
        run([&]{Gate g;ClockFoundation::State c;g.issue(entropy,0);frame(p,g,w);
            check(!g.accept(c,w,"PUBLIC-WRONG-KEY",p,64,1,1),"wrong root key refused");});
        run([&]{Gate g;ClockFoundation::State c;g.issue(entropy,0);frame(p,g,w);g.issue(entropy,0);
            check(!g.accept(c,w,PASSWORD,p,64,1,1),"replaced old challenge refused");});
        run([&]{Gate g;ClockFoundation::State c;check(!g.issue(zero,0),"zero entropy closed");
            check(!g.issue(fail,0),"failed entropy closed");check(!g.issue(stuck,0),"stuck boot and nonce closed");check(!c.snapshot(0).valid,"entropy failure no time");});
        run([&]{Gate g;reentrant=&g;check(g.issue(nested,0),"outer issue");check(reentryDenied,"reentrant issuance refused");reentrant=nullptr;});
        run([&]{Gate g;ClockFoundation::State c;g.issue(entropy,0);frame(p,g,w,1577836800);
            check(g.accept(c,w,PASSWORD,p,64,1,1),"LIMIT freshly signed wrong PC2020 time admitted at unanchored boot");});
        // Real crypto timing is HOST only, not an ESP8266 cycle/latency bound.
        Gate g;g.issue(entropy,0);frame(p,g,w);
        auto begin=std::chrono::steady_clock::now();
        for(unsigned i=0;i<100;++i)ClockFreshness::tag(w,PASSWORD,g.boot(),p,p+32);
        double cryptoUs=std::chrono::duration<double,std::micro>(std::chrono::steady_clock::now()-begin).count()/100;
        std::cout<<"{\"cases_passed\":"<<cases<<",\"checks\":"<<checks<<",\"gate_bytes\":"<<sizeof(Gate)
            <<",\"host_workspace_bytes\":"<<sizeof(Workspace)<<",\"host_hmac_mean_us\":"<<cryptoUs
            <<",\"absolute_utc_proven\":false,\"device_contacts\":0}"<<std::endl;
    }catch(const std::exception& e){std::cerr<<e.what()<<std::endl;return 1;}
    return 0;
}
