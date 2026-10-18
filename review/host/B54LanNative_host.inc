// SPDX-License-Identifier: GPL-3.0-or-later
#include "B54LanNative.h"
#include "B54LanPrivate.h"
#include "ShinoRelease.h"
#include "B53Sntp.h"
#include "B52Clock.h"
#include <Arduino.h>
namespace B54LanNative {
static_assert(B53Diagnostic::WordsUsed==59,"Weather uses only the five existing spare journal words");
namespace {
B54LanWeather::Receiver receiver;
B53Diagnostic::Journal* journal=nullptr;
bool busy=false,publishedFresh=false;uint32_t publishedSequence=0;
bool key(uint8_t* out){
#if SHINO_WEATHER_OWNER
 memcpy_P(out,B54LanKey,32);return B54LanWeather::nonzero(out,32);
#else
 (void)out;return false;
#endif
}
bool decode(const char* text,uint8_t* out){
 for(unsigned i=0;i<8;++i){unsigned n=0;
  for(unsigned j=0;j<2;++j){const char c=text[i*2+j];
   if(!((c>='0'&&c<='9')||(c>='a'&&c<='f')))return false;
   n=n*16+unsigned(c<='9'?c-'0':c-'a'+10);}
  out[i]=uint8_t(n);
 }return true;
}
}
void begin(B53Diagnostic::Journal& log,const char* boot){
 journal=&log;
#if SHINO_WEATHER_OWNER
 uint8_t device[8]{},tag[8]{};
 if(strlen(SHINO_OTA_DEVICE)==16&&strlen(boot)==32&&decode(SHINO_OTA_DEVICE,device)&&decode(boot,tag))
  receiver.configure(device,tag,reinterpret_cast<const uint8_t*>("DEMO0001"));
#else
 (void)boot;
#endif
 log.value(B53Diagnostic::Word(59),0x574c0001U);
}
bool ready(){return journal&&receiver.state().ready;}
bool acquire(){if(busy||!ready())return false;busy=true;return true;}
void release(){receiver.clearWorkspace();busy=false;}
uint8_t* buffer(){return receiver.workspace().wire;}
bool status(uint8_t kind,const uint8_t nonce[8]){
 if(!busy)return false;
 uint32_t utc=0;const auto now=uint32_t(millis());
 if(!B53Sntp::current(now,utc))utc=0;
 return receiver.status(kind,nonce,utc,key);
}
B54LanWeather::Result accept(){
 if(!busy)return B54LanWeather::Result::Unavailable;
 const uint32_t now=millis();uint32_t utc=0;const bool trusted=B53Sntp::current(now,utc);
 const auto result=receiver.receive(buffer(),80,utc,trusted,now,key);
 if(result==B54LanWeather::Result::Accepted&&journal)journal->count(B53Diagnostic::Word(60));
 return result;
}
void record(uint32_t code,uint32_t elapsed){
 if(!journal)return;
 journal->value(B53Diagnostic::Word(61),code);journal->peak(B53Diagnostic::Word(62),elapsed);
 journal->value(B53Diagnostic::Word(63),receiver.state().sequence);
}
void invalidate(){receiver.poll(0,false,uint32_t(millis()));}
void poll(){
 if(!ready())return;
 const uint32_t now=millis();uint32_t utc=0;const bool trusted=B53Sntp::current(now,utc);
 receiver.poll(utc,trusted&&!journal->frozen(),now);
 const auto& s=receiver.state();
 if(s.sequence==publishedSequence&&s.fresh==publishedFresh)return;
 ArtworkPilot::WeatherData sample{};sample.valid=s.have;sample.synthetic=false;
 sample.tenthsC=s.tenths;sample.wmoCode=s.wmo;sample.observedMs=s.acceptedMs;
 sample.validForMs=s.fresh?s.leaseMs:0;
 B52Clock::setWeather(sample);publishedSequence=s.sequence;publishedFresh=s.fresh;
}
}
