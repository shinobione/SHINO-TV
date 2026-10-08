// Explicit host-only hardware seams for the unmodified pinned Updater body.
#pragma once
#include <algorithm>
#include <cstdint>
#include <cstddef>
#include <cstring>
#include <string>
#include <vector>
#include <cstdio>
#ifdef _MSC_VER
#define strcasecmp _stricmp
#define __attribute__(x)
#endif
#define F(x) x
#define PSTR(x) x
#define OUTPUT 1
#define LOW 0
class String : public std::string {
public:
    using std::string::string;using std::string::operator=;
    String()=default;String(const std::string& s):std::string(s){}
    String(uint32_t n,int):std::string(std::to_string(n)){}
};
inline String operator+(const char* a,const String& b){return String(std::string(a)+static_cast<const std::string&>(b));}
inline String operator+(const String& a,const String& b){return String(static_cast<const std::string&>(a)+static_cast<const std::string&>(b));}
inline const String emptyString;
struct Stream {int peek(){return 0;}size_t readBytes(uint8_t*,size_t){return 0;}};
struct Print {template<class... A>void printf_P(const char*,A...){};};
inline void yield(){}inline void delay(int){}inline void pinMode(int,int){}inline void digitalWrite(int,int){}
enum FlashMode_t {FM_QIO=0,FM_QOUT=1,FM_DIO=2,FM_DOUT=3};
struct HostESP {
    std::vector<uint8_t> flash=std::vector<uint8_t>(0x400000,0xff);
    uint32_t current=399264,mode=2,heap=60000,eraseCalls=0,writeCalls=0,readCalls=0;
    bool failWrite=false,failErase=false,failRead=false;
    bool checkFlashConfig(bool){return true;}uint32_t getSketchSize(){return current;}
    uint32_t getFreeHeap(){return heap;}uint32_t getFlashChipRealSize(){return 0x400000;}
    uint32_t getFlashChipSize(){return 0x400000;}FlashMode_t getFlashChipMode(){return FlashMode_t(mode);}
    FlashMode_t magicFlashChipMode(uint8_t n){return FlashMode_t(n);}
    uint32_t magicFlashChipSize(uint8_t n){return n==4?0x400000:0x800000;}
    bool flashRead(uint32_t at,void* out,size_t n){++readCalls;if(failRead || at+n>flash.size())return false;std::memcpy(out,flash.data()+at,n);return true;}
    bool flashWrite(uint32_t at,uint8_t* data,size_t n){++writeCalls;if(failWrite || at<((current+4095)&~4095u) || at+n>0x200000)return false;std::memcpy(flash.data()+at,data,n);return true;}
    bool flashEraseSector(uint32_t s){++eraseCalls;if(failErase || s*4096<((current+4095)&~4095u) || s*4096+4096>0x200000)return false;std::fill(flash.begin()+s*4096,flash.begin()+(s+1)*4096,0xff);return true;}
};
extern HostESP ESP;
