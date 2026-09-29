#pragma once
#include <Arduino.h>
struct Arduino_GFX {
  template<class... A>void fillRoundRect(A...){} template<class... A>void drawRoundRect(A...){}
  template<class... A>void setTextColor(A...){} template<class... A>void setTextSize(A...){}
  template<class... A>void setTextWrap(A...){} template<class... A>void setCursor(A...){}
  template<class... A>void print(A...){} template<class... A>void fillRect(A...){}
  template<class... A>void drawCircle(A...){} template<class... A>void fillScreen(A...){}
};
enum {LCD_RED,LCD_BLACK,LCD_WHITE};
namespace DisplayManager { inline Arduino_GFX gfx; inline void begin(int){} inline void clearScreen(){} inline Arduino_GFX* getGfx(){return &gfx;} template<class... A>void drawTextWrapped(A...){} }
