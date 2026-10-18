
#pragma once
#include <cstdint>
#include <cstring>
#include <cassert>
#include <ESP8266WiFi.h>
enum {AUTH_WPA2_PSK=3, AUTH_WPA_WPA2_PSK=4, DHCP_STOPPED=0, DHCP_STARTED=1};
struct station_config {uint8_t ssid[32],password[64],bssid_set,bssid[6];
 struct {int8_t rssi;uint32_t authmode;} threshold;};
inline station_config testSaved{};
inline unsigned testReads=0,testWrites=0,testCurrents=0,testConnects=0,testFailReadAt=0;
inline bool testWriteOk=true,testWriteAfter=false,testMismatch=false,testReadbackFail=false;
inline bool testCurrentOk=true,testDhcpOk=true,testConnectOk=true,testWpa2Applied=false;
inline int testDhcp=DHCP_STOPPED;
inline void(*testDuringWrite)()=nullptr;
// Exact SDK22x output fields: threshold/rssi are NOT populated, in any mode.
inline bool wifi_station_get_config_default(station_config* out){
 ++testReads;if(testReads==testFailReadAt)return false;
 memcpy(out->ssid,testSaved.ssid,32);memcpy(out->password,testSaved.password,64);
 out->bssid_set=testSaved.bssid_set;memcpy(out->bssid,testSaved.bssid,6);return true;
}
inline bool wifi_station_set_config(station_config* in){
 ++testWrites;assert((WiFi.modeValue&WIFI_STA)!=0 && !WiFi.persisted);
 assert(in->threshold.authmode==AUTH_WPA2_PSK && in->threshold.rssi==-127);
 if(testWriteOk||testWriteAfter){testSaved=*in;if(testMismatch)testSaved.password[0]^=1;}
 if(testReadbackFail)testFailReadAt=testReads+1;
 if(testDuringWrite)testDuringWrite();
 return testWriteOk;
}
inline bool wifi_station_set_config_current(station_config* in){
 ++testCurrents;testWpa2Applied=in->threshold.authmode==AUTH_WPA2_PSK&&in->threshold.rssi==-127&&!in->bssid_set;
 return testCurrentOk;
}
inline int wifi_station_dhcpc_status(){return testDhcp;}
inline bool wifi_station_dhcpc_start(){if(testDhcpOk)testDhcp=DHCP_STARTED;return testDhcpOk;}
inline bool wifi_station_connect(){++testConnects;return testConnectOk;}
inline bool wifi_station_disconnect(){return true;}
