#pragma once
#include <Arduino.h>
struct IPAddress { uint32_t value=1; bool operator!=(const IPAddress& other)const{return value!=other.value;} };
enum { WIFI_AP, WIFI_OFF };
struct WiFiFixture { bool persisted=true, ap=true; void persistent(bool b){persisted=b;} void mode(int){} bool softAP(const char*,const char*,int,bool,int){return ap;} };
inline WiFiFixture WiFi;
