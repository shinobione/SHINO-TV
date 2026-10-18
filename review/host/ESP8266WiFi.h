
#pragma once
#include <HostSocket.h>
enum {WIFI_OFF=0,WIFI_STA=1,WIFI_AP=2,WIFI_AP_STA=3,WL_CONNECTED=3,WL_WRONG_PASSWORD=6,WL_NO_SSID_AVAIL=1};
inline void(*testStaHook)()=nullptr;
struct WiFiFixture {
 bool persisted=true,staOk=true,apOk=true;int modeValue=WIFI_OFF,wifiStatus=0;
 unsigned apPeers=1;IPAddress sta;
 void persistent(bool x){persisted=x;}void setAutoReconnect(bool){}
 bool mode(int x){modeValue=x;return true;}int getMode(){return modeValue;}
 bool enableSTA(bool x){if(!staOk)return false;modeValue=x?(modeValue|WIFI_STA):(modeValue&~WIFI_STA);if(x&&testStaHook)testStaHook();return true;}
 bool enableAP(bool x){if(!apOk)return false;modeValue=x?(modeValue|WIFI_AP):(modeValue&~WIFI_AP);return true;}
 bool softAP(const char*,const char*,int,bool,int){return apOk;}
 bool softAPdisconnect(bool){modeValue&=~WIFI_AP;return true;}
 IPAddress softAPIP(){return IPAddress(192,168,4,1);}IPAddress localIP(){return sta;}
 IPAddress subnetMask(){return IPAddress(255,255,255,0);}int status(){return wifiStatus;}
 unsigned softAPgetStationNum(){return apPeers;}
};inline WiFiFixture WiFi;
