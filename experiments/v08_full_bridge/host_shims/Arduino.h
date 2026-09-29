#pragma once
// HOST ONLY. These are dependency seams, not ESP8266/TCP/RNG evidence.
#include <cstdint>
#include <string>
#include <algorithm>
#include <cstdio>
struct String : std::string {
  using std::string::string; using std::string::operator=;
  String(std::string s):std::string(std::move(s)){}
  String(uint32_t value, int base) { char b[24]; snprintf(b,sizeof b,base==16?"%x":"%u",value); assign(b); }
  int indexOf(char c, size_t start=0) const { auto p=find(c,start); return p==npos?-1:int(p); }
  String substring(size_t a, size_t b=npos) const { return substr(a,b==npos?b:b-a); }
  void trim(){auto a=find_first_not_of(" \t\r\n"),b=find_last_not_of(" \t\r\n"); assign(a==npos?"":substr(a,b-a+1));}
  size_t write(uint8_t b){push_back(char(b));return 1;}
  size_t write(const uint8_t* p,size_t n){append(reinterpret_cast<const char*>(p),n);return n;}
};
#define F(x) x
#define PSTR(x) x
#define PROGMEM
#define HEX 16
extern uint32_t host_ms;
inline uint32_t millis(){return host_ms;}
inline void yield(){}
struct EspFixture {
  uint32_t randomCounter=0; int feeds=0;
  void random(uint8_t* p,size_t n){for(size_t i=0;i<n;i++)p[i]=uint8_t(++randomCounter);}
  uint32_t getChipId(){return 0x1234;}
  uint32_t getFlashChipRealSize(){return 4*1024*1024;}
  uint32_t getSketchSize(){return 400000;}
  uint32_t getFreeSketchSpace(){return 500000;}
  uint32_t getFreeHeap(){return 30000;}
  void wdtFeed(){feeds++;}
};
inline EspFixture ESP;
