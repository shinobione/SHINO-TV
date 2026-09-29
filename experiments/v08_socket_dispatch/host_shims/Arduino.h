#pragma once
// HOST ONLY: std::string, controllable ticks, deterministic RNG and inert hardware.
#include <algorithm>
#include <cctype>
#include <cstdint>
#include <cstdio>
#include <cstring>
#include <cstdlib>
#include <string>
#include <vector>
#include <type_traits>
#include <chrono>
struct __FlashStringHelper {};
#define F(x) reinterpret_cast<const __FlashStringHelper*>(x)
#define FPSTR(x) x
#define PSTR(x) x
#define PROGMEM
#define HEX 16
#define strlen_P strlen
#define __attribute__(x)
using PGM_P=const char*;
#ifdef _WIN32
using ssize_t=std::intptr_t;
#endif
struct String:std::string {
 using std::string::string; using std::string::operator=;
 using std::string::operator+=;
 String& operator+=(const __FlashStringHelper* s){append(reinterpret_cast<const char*>(s));return *this;}
 String()=default;
 String(std::string s):std::string(std::move(s)){}
 String(const __FlashStringHelper* s):std::string(reinterpret_cast<const char*>(s)){}
 bool operator==(const String& s)const{return compare(s)==0;}
 bool operator==(const char* s)const{return compare(s)==0;}
 bool operator==(const __FlashStringHelper* s)const{return compare(reinterpret_cast<const char*>(s))==0;}
 template<class T, std::enable_if_t<std::is_integral_v<T> && !std::is_same_v<T,char>,int> =0>
 String(T n):std::string(std::to_string(n)){}
 String(char c):std::string(1,c){}
 String(uint32_t n,int base){char b[32];snprintf(b,sizeof b,base==16?"%x":"%u",n);assign(b);}
 int indexOf(char c,size_t a=0)const{auto p=find(c,a);return p==npos?-1:int(p);}
 int indexOf(const String& s,size_t a=0)const{auto p=find(s,a);return p==npos?-1:int(p);}
 String substring(size_t a,size_t b=npos)const{a=std::min(a,size());return substr(a,b==npos?b:(b<a?0:b-a));}
 void trim(){auto a=find_first_not_of(" \t\r\n"),b=find_last_not_of(" \t\r\n");assign(a==npos?"":substr(a,b-a+1));}
 bool equalsIgnoreCase(const String& v)const{if(size()!=v.size())return false;for(size_t i=0;i<size();i++)if(std::tolower((unsigned char)(*this)[i])!=std::tolower((unsigned char)v[i]))return false;return true;}
 bool equalsConstantTime(const String& v)const{unsigned d=unsigned(size()^v.size());for(size_t i=0;i<std::min(size(),v.size());i++)d|=(*this)[i]^v[i];return d==0;}
 bool startsWith(const String& v)const{return rfind(v,0)==0;}
 bool endsWith(const String& v)const{return size()>=v.size() && compare(size()-v.size(),v.size(),v)==0;}
 bool isEmpty()const{return empty();}
 char charAt(size_t i)const{return i<size()?(*this)[i]:0;}
 long toInt()const{return atol(c_str());}
 void concat(const char* p,size_t n){append(p,n);}
 void replace(const String& a,const String& b){size_t p=0;while((p=find(a,p))!=npos){std::string::replace(p,a.size(),b);p+=b.size();}}
 size_t write(uint8_t b){push_back(char(b));return 1;}
 size_t write(const uint8_t* p,size_t n){append(reinterpret_cast<const char*>(p),n);return n;}
};
inline String operator+(const String& a,const String& b){return String(static_cast<const std::string&>(a)+static_cast<const std::string&>(b));}
inline String operator+(const String& a,char b){return a+String(b);}
inline String operator+(const String& a,int b){return a+String(b);}
inline String operator+(const String& a,const char* b){return a+String(b);}
inline String operator+(const char* a,const String& b){return String(a)+b;}
inline String operator+(const String& a,const __FlashStringHelper* b){return a+String(b);}
inline const String emptyString;
extern uint32_t host_ms;
inline bool lab_real_clock=false;
inline auto lab_clock_origin=std::chrono::steady_clock::now();
inline uint32_t millis(){return lab_real_clock?uint32_t(std::chrono::duration_cast<std::chrono::milliseconds>(std::chrono::steady_clock::now()-lab_clock_origin).count()):host_ms;}
void yield();
inline uint32_t lab_random=0;
#define RANDOM_REG32 (++lab_random)
struct EspFixture {
 uint32_t randomCounter=0;int feeds=0;
 void random(uint8_t* p,size_t n){for(size_t i=0;i<n;i++)p[i]=uint8_t(++randomCounter);}
 uint32_t getChipId(){return 0x1234;}
 uint32_t getFlashChipRealSize(){return 4*1024*1024;}
 uint32_t getSketchSize(){return 400000;}
 uint32_t getFreeSketchSpace(){return 500000;}
 uint32_t getFreeHeap(){return 30000;}
 void wdtFeed(){feeds++;}
};
inline EspFixture ESP;
