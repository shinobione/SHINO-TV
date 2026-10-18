// SPDX-License-Identifier: GPL-3.0-or-later
#pragma once
#include <stdint.h>
#include <stddef.h>
#include <string.h>
#include <bearssl/bearssl.h>
#if defined(ESP8266)
#include <pgmspace.h>
#define B54_WX_FLASH PROGMEM
#else
#define B54_WX_FLASH
#endif
namespace B54LanWeather {
constexpr size_t FrameBytes=80;
using KeyReader=bool(*)(uint8_t*);
enum class Result:uint32_t { Accepted,Framing,Mac,Identity,Replay,Clock,Range,Expired,Unavailable };
struct State {
 uint8_t device[8]{},boot[8]{},location[8]{};
 uint32_t sequence=0,observed=0,acceptedMs=0,leaseMs=0,acceptedUtc=0,expiresUtc=0;
 int16_t tenths=0;uint8_t wmo=255;
 bool have=false,fresh=false,ready=false;
};
struct Workspace {
 uint8_t wire[80]{},pad[64]{},digest[32]{};
 br_sha256_context hash{};
};
inline uint32_t be32(const uint8_t* p){return uint32_t(p[0])<<24|uint32_t(p[1])<<16|uint32_t(p[2])<<8|p[3];}
inline void put32(uint8_t* p,uint32_t n){for(unsigned i=0;i<4;++i)p[i]=uint8_t(n>>(24-8*i));}
inline void wipe(void* p,size_t n){auto* b=static_cast<volatile uint8_t*>(p);while(n--)*b++=0;}
inline bool nonzero(const uint8_t* p,size_t n){uint8_t v=0;while(n--)v|=*p++;return v!=0;}
inline void flashCopy(void* out,const void* in,size_t n){
#if defined(ESP8266)
 memcpy_P(out,in,n);
#else
 memcpy(out,in,n);
#endif
}
inline bool domain(uint8_t kind,const char*& text,size_t& length){
 static const char sample[] B54_WX_FLASH="SHINO-WX/SAMPLE/1";
 static const char status[] B54_WX_FLASH="SHINO-WX/STATUS/1";
 static const char ack[] B54_WX_FLASH="SHINO-WX/ACK/1";
 if(kind==1){text=sample;length=sizeof(sample)-1;}
 else if(kind==2){text=status;length=sizeof(status)-1;}
 else if(kind==3){text=ack;length=sizeof(ack)-1;}
 else return false;
 return true;
}
// RFC2104 HMAC with an exact32-byte key. SHA256 is the pinned BearSSL primitive.
// Dedicated static context; inner finishes before reinitialization for outer.
inline bool hmac(Workspace& w,KeyReader key,const char* prefix,size_t prefixSize,
                 const uint8_t* data,size_t size){
 if(!key||prefixSize>sizeof(w.digest)||size>1024)return false;
 memset(w.pad,0,sizeof(w.pad));
 if(!key(w.pad)){wipe(w.pad,sizeof(w.pad));return false;}
 for(auto& b:w.pad)b^=0x36;
 br_sha256_init(&w.hash);br_sha256_update(&w.hash,w.pad,sizeof(w.pad));
 if(prefixSize){flashCopy(w.digest,prefix,prefixSize);br_sha256_update(&w.hash,w.digest,prefixSize);}
 br_sha256_update(&w.hash,data,size);br_sha256_out(&w.hash,w.digest);
 for(auto& b:w.pad)b^=0x36^0x5c;
 br_sha256_init(&w.hash);br_sha256_update(&w.hash,w.pad,sizeof(w.pad));
 br_sha256_update(&w.hash,w.digest,sizeof(w.digest));br_sha256_out(&w.hash,w.digest);
 wipe(w.pad,sizeof(w.pad));wipe(&w.hash,sizeof(w.hash));return true;
}
inline bool wmoValid(unsigned c){
 switch(c){case 0:case 1:case 2:case 3:case 45:case 48:case 51:case 53:case 55:
 case 56:case 57:case 61:case 63:case 65:case 66:case 67:case 71:case 73:case 75:
 case 77:case 80:case 81:case 82:case 85:case 86:case 95:case 96:case 99:return true;default:return false;}
}
class Receiver {
 State state_{};Workspace work_{};
public:
 const State& state()const{return state_;}
 Workspace& workspace(){return work_;}
 void clearWorkspace(){wipe(&work_,sizeof work_);}
 void configure(const uint8_t* device,const uint8_t* boot,const uint8_t* location){
  state_={};clearWorkspace();
  if(!device||!boot||!location||!nonzero(device,8)||!nonzero(boot,8)||!nonzero(location,8))return;
  memcpy(state_.device,device,8);memcpy(state_.boot,boot,8);memcpy(state_.location,location,8);state_.ready=true;
 }
 Result receive(const uint8_t* wire,size_t n,uint32_t utc,bool trusted,uint32_t now,KeyReader key){
  if(!state_.ready)return Result::Unavailable;
  if(!wire||n!=FrameBytes||memcmp(wire,"SWX1",4)||wire[4]!=1||wire[5]!=1||wire[6]!=0||wire[7]!=80)return Result::Framing;
  const char* text=nullptr;size_t length=0;domain(1,text,length);
  if(!hmac(work_,key,text,length,wire,48))return Result::Mac;
  uint8_t difference=0;for(unsigned i=0;i<32;++i)difference|=work_.digest[i]^wire[48+i];
  wipe(work_.digest,sizeof(work_.digest));
  if(difference)return Result::Mac;
  if(memcmp(wire+8,state_.device,8)||memcmp(wire+16,state_.boot,8)||memcmp(wire+40,state_.location,8))return Result::Identity;
  const uint32_t sequence=be32(wire+24),observed=be32(wire+28);
  if(state_.sequence==UINT32_MAX||!sequence||sequence!=state_.sequence+1)return Result::Replay;
  if(!trusted||utc<1577836800U||utc>4102444799U)return Result::Clock;
  const uint32_t ttl=uint32_t(wire[32])*256U+wire[33];
  const unsigned encoded=unsigned(wire[34])*256U+wire[35];
  const int temp=encoded>=32768?int(encoded)-65536:int(encoded);
  if(observed<1577836800U||observed>4102444799U||!ttl||ttl>2700||temp<-900||temp>650||
     !wmoValid(wire[36])||wire[37]||wire[38]||wire[39])return Result::Range;
  if(observed>utc&&observed-utc>60)return Result::Range;
  const uint32_t age=utc>observed?utc-observed:0;
  if(age>=ttl)return Result::Expired;
  // No mutation of publication/replay state above this commit point.
  state_.sequence=sequence;state_.observed=observed;state_.acceptedMs=now;
  state_.leaseMs=(ttl-age)*1000U;state_.acceptedUtc=utc;state_.expiresUtc=observed+ttl;
  state_.tenths=int16_t(temp);state_.wmo=wire[36];state_.have=state_.fresh=true;
  return Result::Accepted;
 }
 void poll(uint32_t utc,bool trusted,uint32_t now){
  if(state_.fresh&&(!trusted||utc<1577836800U||utc>4102444799U||utc+2<state_.acceptedUtc||
     uint32_t(now-state_.acceptedMs)>=state_.leaseMs||
     utc>=state_.expiresUtc))state_.fresh=false;
 }
 bool status(uint8_t kind,const uint8_t* challenge,uint32_t utc,KeyReader key){
  if(!state_.ready||!challenge||(kind!=2&&kind!=3))return false;
  auto* out=work_.wire;memset(out,0,FrameBytes);memcpy(out,"SWX1",4);
  out[4]=1;out[5]=kind;out[7]=80;memcpy(out+8,state_.device,8);memcpy(out+16,state_.boot,8);
  put32(out+24,state_.sequence);memcpy(out+28,challenge,8);put32(out+36,utc);memcpy(out+40,state_.location,8);
  const char* text=nullptr;size_t length=0;domain(kind,text,length);
  if(!hmac(work_,key,text,length,out,48))return false;
  memcpy(out+48,work_.digest,32);wipe(work_.digest,sizeof(work_.digest));return true;
 }
};
}
#undef B54_WX_FLASH
