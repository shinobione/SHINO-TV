
#pragma once
#include "Arduino.h"
#include <cassert>
#define LCD_WHITE 1
#define LCD_BLACK 0
struct Arduino_GFX {
    unsigned cards=0,dashes=0,operations=0;
    std::vector<std::string> printed;
    void note(const char* value){if(!value)return; if(printed.size()==128)printed.erase(printed.begin());printed.emplace_back(value);}
    bool has(const char* value)const {for(const auto& item:printed)if(item==value)return true;return false;}
    void clearPrinted(){printed.clear();}
    void setFont(void*){}void fillScreen(uint16_t){}
    void rect(int x,int y,int w,int h){assert(x>=0&&y>=0&&x+w<=240&&y+h<=240);}
    void fillRoundRect(int x,int y,int w,int h,int,uint16_t){rect(x,y,w,h);if(w==108)++cards;}
    void drawRoundRect(int x,int y,int w,int h,int,uint16_t){rect(x,y,w,h);}
    void fillRect(int x,int y,int w,int h,uint16_t){++operations;rect(x,y,w,h);if(w==16&&h==2)++dashes;}
    void drawCircle(int x,int y,int r,uint16_t){rect(x-r,y-r,2*r,2*r);}
    void draw16bitRGBBitmap(int x,int y,uint16_t*,int w,int h){rect(x,y,w,h);++operations;}
    void setTextColor(uint16_t){}void setTextSize(int){}void setTextWrap(bool){}
    void setCursor(int x,int y){assert(x>=0&&y>=0&&x<240&&y<240);}void print(const char* value){note(value);}
    void print(const String& value){note(value.c_str());}
    void print(const __FlashStringHelper* value){note(reinterpret_cast<const char*>(value));}
    template<class T>void print(T){}
};
namespace DisplayManager{inline Arduino_GFX gfx;inline unsigned starts=0;
    inline void begin(int rotation){assert(rotation==0);++starts;}inline Arduino_GFX* getGfx(){return &gfx;}
    inline void clearScreen(){}inline void drawTextWrapped(int,int,const char*,int,int,int,bool){}
}
