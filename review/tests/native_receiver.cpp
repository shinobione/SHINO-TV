// HOST/native contract, exact pinned SHA256; no socket/device/credentials.
#include "B54LanWeather.h"
#include <cassert>
#include <cstdio>
#include <cstdlib>
#include <string>
#include <vector>
#include <iostream>
#include <sstream>
using namespace B54LanWeather;
static bool key(uint8_t* out){for(unsigned i=0;i<32;++i)out[i]=uint8_t(i);return true;}
static bool rfcKey(uint8_t* out){memset(out,0,32);memset(out,0x0b,20);return true;}
static unsigned nibble(char c){return c>='0'&&c<='9'?unsigned(c-'0'):unsigned(c-'a'+10);}
static std::vector<uint8_t> bytes(const char* text){
 size_t n=strlen(text);assert(n%2==0);std::vector<uint8_t> out(n/2);
 for(size_t i=0;i<n;i+=2)out[i/2]=uint8_t(nibble(text[i])*16+nibble(text[i+1]));return out;
}
static void setup(Receiver& r){
 const uint8_t device[]={1,2,3,4,5,6,7,8},boot[]={0x10,0x20,0x30,0x40,0x50,0x60,0x70,0x80};
 r.configure(device,boot,reinterpret_cast<const uint8_t*>("DEMO0001"));
}
#include "vectors.inc"
static std::string hex(const uint8_t* p,size_t n){
 static const char alphabet[]="0123456789abcdef";std::string s;for(size_t i=0;i<n;++i){s+=alphabet[p[i]>>4];s+=alphabet[p[i]&15];}return s;
}
// The same pure renderer used by native B52Clock, with an instrumented LCD
// canvas. This is a HOST drawing contract, never a hardware LCD assertion.
#include <display/SceneEngine.h>
struct WxDrawProbe final : ArtworkPilot::Canvas {
 struct Label { std::string value; int x,y; uint8_t scale; };
 std::vector<Label> labels;
 unsigned cardWrites=0;
 void fill(int x,int y,int w,int h,uint16_t) override {
  assert(x>=0&&y>=0&&w>=0&&h>=0&&x+w<=240&&y+h<=240);
  if(y>=106)++cardWrites;
 }
 void text(int x,int y,const char* s,uint16_t,uint8_t scale=1) override {
  assert(x>=0&&x<240&&y>=0&&y<240&&s&&scale>=1);
  labels.push_back({s,x,y,scale});
 }
 uint8_t glyphColumn(uint8_t,unsigned) override {return 0;}
 void row(int x,int y,uint16_t* pixels,int count,int repeats) override {
  assert(pixels&&x>=0&&y>=0&&count>=0&&repeats>=0&&x+count<=240&&y+repeats<=240);
 }
 bool has(const char* text) const {
  for(const auto& label:labels)if(label.value==text)return true;
  return false;
 }
 void clear(){labels.clear();cardWrites=0;}
};
static void paintWeatherToIdle(ArtworkPilot::Renderer& renderer,WxDrawProbe& probe,uint32_t now){
 bool done=false;
 for(unsigned i=0;i<100;++i)if(!renderer.step(probe,{},now)){done=true;break;}
 assert(done); // bounded cooperative progress; no drawing starvation.
}
static void renderWeatherGate(const std::vector<uint8_t>& wire){
 B54LanWeather::Receiver receiver;setup(receiver);
 assert(receiver.receive(wire.data(),wire.size(),1791955392,true,1000,key)==B54LanWeather::Result::Accepted);
 const auto& state=receiver.state();
 ArtworkPilot::WeatherData fresh{};
 fresh.valid=state.have;fresh.synthetic=false;fresh.tenthsC=state.tenths;
 fresh.wmoCode=state.wmo;fresh.observedMs=state.acceptedMs;fresh.validForMs=state.leaseMs;
 assert(fresh.valid&&fresh.tenthsC==182&&fresh.wmoCode==3&&fresh.validForMs>0);

 ArtworkPilot::ClockData clock{};
 clock.valid=true;clock.year=2026;clock.month=10;clock.day=19;
 clock.hour=12;clock.minute=34;clock.observedMs=1000;
 clock.validForMs=86400000;clock.source=ArtworkPilot::ClockSource::Sntp;

 // PC connected: actual renderer draws signed weather plus all four metrics.
 ArtworkPilot::Renderer online;WxDrawProbe lcd;
 online.setClock(clock);online.setMetrics({22,34,8,16,56,true,false});
 online.setWeather(fresh);paintWeatherToIdle(online,lcd,1000);
 for(const char* label:{"CPU","GPU","RAM","GPU temp","18.2","Cloudy","12:34"})
  assert(lcd.has(label));
 assert(lcd.cardWrites>0);

 // Trust loss: the receiver latches stale; the renderer must erase the
 // temperature and must not overwrite existing metric-card pixels.
 receiver.poll(1791955392,false,1002);
 assert(!receiver.state().fresh);
 ArtworkPilot::WeatherData stale=fresh;stale.validForMs=0;
 lcd.clear();online.setWeather(stale);paintWeatherToIdle(online,lcd,1002);
 assert(lcd.has("WEATHER STALE")&&!lcd.has("18.2")&&!lcd.has("Cloudy"));
 assert(lcd.cardWrites==0);

 // PC absent: autonomous time and weather remain, but stale PC metrics
 // cannot be presented as live readings.
 ArtworkPilot::Renderer offline;WxDrawProbe unplugged;
 offline.setClock(clock);offline.setMetrics({22,34,8,16,56,true,true});
 offline.setWeather(fresh);paintWeatherToIdle(offline,unplugged,1000);
 assert(unplugged.has("12:34")&&unplugged.has("18.2")&&unplugged.has("Cloudy"));
 for(const char* label:{"CPU","GPU","RAM","GPU temp"})
  assert(!unplugged.has(label));

 unplugged.clear();offline.setWeather(stale);
 paintWeatherToIdle(offline,unplugged,1002);
 assert(unplugged.has("WEATHER STALE")&&!unplugged.has("18.2"));

 // No accepted sample must show an explicit unavailable state.
 ArtworkPilot::Renderer noSample;WxDrawProbe empty;
 noSample.setClock(clock);noSample.setMetrics({0,0,0,0,0,false,true});
 paintWeatherToIdle(noSample,empty,1000);
 assert(empty.has("WEATHER --")&&!empty.has("18.2"));

 // Product mode: owner may request clock/weather even with PC telemetry
 // still fresh. This is a renderer API only, not an unauthenticated HTTP route.
 ArtworkPilot::Renderer selectable;WxDrawProbe modes;
 selectable.setClock(clock);selectable.setWeather(fresh);
 selectable.setMetrics({22,34,8,16,56,true,false});
 assert(selectable.currentDisplayMode()==ArtworkPilot::DisplayMode::Auto);
 paintWeatherToIdle(selectable,modes,1000);
 for(const char* label:{"CPU","GPU","RAM","GPU temp"}) assert(modes.has(label));
 assert(modes.has("18.2")&&modes.has("12:34"));
 modes.clear();
 selectable.setDisplayMode(ArtworkPilot::DisplayMode::ClockWeather);
 paintWeatherToIdle(selectable,modes,1001);
 assert(!selectable.telemetryStale()); // Switch must not falsify LINK freshness.
 assert(modes.has("18.2")&&modes.has("Cloudy")&&modes.has("12:34"));
 for(const char* label:{"CPU","GPU","RAM","GPU temp"}) assert(!modes.has(label));
 modes.clear();
 selectable.setDisplayMode(ArtworkPilot::DisplayMode::Auto);
 paintWeatherToIdle(selectable,modes,1002);
 for(const char* label:{"CPU","GPU","RAM","GPU temp"}) assert(modes.has(label));
 assert(modes.has("18.2"));
 assert(!selectable.telemetryStale());

 // A manually selected clock/weather scene overrides PLAYING/cover, but
 // AUTO restores music priority without modifying the music status.
 ArtworkPilot::Caption playing{};playing.state=ArtworkPilot::State::Playing;
 ArtworkPilot::View view{};view.caption=&playing;view.revision=9;
 selectable.setDisplayMode(ArtworkPilot::DisplayMode::ClockWeather);
 for(unsigned i=0;i<100;++i)if(!selectable.step(modes,view,1003))break;
 assert(selectable.currentScene()==ArtworkPilot::Scene::Idle);
 selectable.setDisplayMode(ArtworkPilot::DisplayMode::Auto);
 selectable.step(modes,view,1004);
 assert(selectable.currentScene()==ArtworkPilot::Scene::NoArtwork);
 std::puts("SHINO_DISPLAY_MODE_HOST_PASS auto/manual/pc_fresh/music_priority/return");
 std::puts("B54_WEATHER_RENDER_HOST_PASS signed_sample/cards/pc_off/trust_loss/stale/absent");
}

int main(int argc,char**){
 if(argc>1){
  Receiver receiver;setup(receiver);std::string line;
  while(std::getline(std::cin,line)){
   std::istringstream in(line);std::string command,wire;uint32_t utc=0,now=0;unsigned trust=1;
   in>>command;
   if(command=="STATUS"){
    in>>wire>>utc>>now;auto challenge=bytes(wire.c_str());assert(challenge.size()==8);
    receiver.poll(utc,utc!=0,now);assert(receiver.status(2,challenge.data(),utc,key));
    std::cout<<hex(receiver.workspace().wire,80)<<std::endl;
   }else if(command=="SAMPLE"){
    in>>wire>>utc>>trust>>now;auto data=bytes(wire.c_str());
    const auto result=receiver.receive(data.data(),data.size(),utc,trust!=0,now,key);
    std::cout<<unsigned(result)<<" ";
    if(result==Result::Accepted){uint8_t nonce[8];memcpy(nonce,data.data()+48,8);
     assert(receiver.status(3,nonce,utc,key));std::cout<<hex(receiver.workspace().wire,80);}
    else std::cout<<"-";
    std::cout<<std::endl;receiver.clearWorkspace();
   }else if(command=="POLL"){
    in>>utc>>trust>>now;receiver.poll(utc,trust!=0,now);
    std::cout<<receiver.state().sequence<<" "<<receiver.state().fresh<<" "<<receiver.state().tenths<<std::endl;
   }else if(command=="RESET"){
    in>>wire;auto boot=bytes(wire.c_str());assert(boot.size()==8);
    const uint8_t device[]={1,2,3,4,5,6,7,8};receiver.configure(device,boot.data(),reinterpret_cast<const uint8_t*>("DEMO0001"));std::cout<<"RESET"<<std::endl;
   }else if(command=="MAC"){
    in>>wire;auto data=bytes(wire.c_str());assert(hmac(receiver.workspace(),key,nullptr,0,data.data(),data.size()));
    std::cout<<hex(receiver.workspace().digest,32)<<std::endl;receiver.clearWorkspace();
   }else return 2;
  }
  return 0;
 }
 Receiver r;setup(r);auto frame=bytes(FrozenSample);
 Workspace rfc{};assert(hmac(rfc,rfcKey,nullptr,0,reinterpret_cast<const uint8_t*>("Hi There"),8));
 assert(hex(rfc.digest,32)=="b0344c61d8db38535ca8afceaf0bf12b881dc200c9833da726e9376c2e32cff7");
 assert(r.receive(frame.data(),frame.size(),1791955392,true,1000,key)==Result::Accepted);
 assert(r.state().tenths==182&&r.state().wmo==3&&r.state().sequence==1);
 const State prior=r.state();
 assert(r.receive(frame.data(),80,1791955392,true,1001,key)==Result::Replay);
 assert(memcmp(&prior,&r.state(),sizeof prior)==0);
 for(unsigned at=0;at<80;++at){Receiver bad;setup(bad);const State previous=bad.state();auto corrupt=frame;corrupt[at]^=1;
  assert(bad.receive(corrupt.data(),80,1791955392,true,1,key)!=Result::Accepted);
  assert(memcmp(&previous,&bad.state(),sizeof previous)==0);}
 for(size_t n=0;n<80;++n){Receiver cut;setup(cut);assert(cut.receive(frame.data(),n,1791955392,true,0,key)==Result::Framing);}
 r.poll(1791955392,false,1002);assert(!r.state().fresh);
 r.poll(1791955392,true,1003);assert(!r.state().fresh); // Trust loss cannot revive.
 renderWeatherGate(frame);
 std::printf("B54_LAN_NATIVE_HOST_PASS corrupt_bytes=80 truncations=80 replay/no-mutation/clock-trust sizeof(State)=%zu sizeof(Workspace)=%zu\n",sizeof(State),sizeof(Workspace));
}
