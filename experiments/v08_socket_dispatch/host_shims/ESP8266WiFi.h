#pragma once
#include <HostSocket.h>
enum {WIFI_AP,WIFI_OFF};
struct WiFiFixture {bool persisted=true;void persistent(bool b){persisted=b;}void mode(int){}bool softAP(const char*,const char*,int,bool,int){return true;}};
inline WiFiFixture WiFi;
