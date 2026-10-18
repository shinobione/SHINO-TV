// SPDX-License-Identifier: GPL-3.0-or-later
#include "boot/HomeLan.h"
#if SHINO_ENABLE_HOME_LAN
#include "boot/HomeLanPolicy.h"
#include <ESP8266WiFi.h>
extern "C" {
#include <user_interface.h>
extern uint32_t _FS_start, _FS_end, _EEPROM_start;
}
namespace HomeLan {
namespace {
uint32_t networkOrder(const IPAddress& ip) {
    return uint32_t(ip[0])<<24 | uint32_t(ip[1])<<16 | uint32_t(ip[2])<<8 | ip[3];
}
struct Sdk {
    bool strong=false;
    bool safe() const {
        constexpr uint32_t base=0x40200000;
        return layoutSafe(ESP.getFlashChipRealSize(),ESP.getFlashChipSize(),
            uint32_t(&_FS_start)-base,uint32_t(&_FS_end)-base,uint32_t(&_EEPROM_start)-base);
    }
    bool read(Credentials& out) {
        station_config config{};
        const bool ok=wifi_station_get_config_default(&config);
        if(ok) {
            wipe(out.ssid,sizeof(out.ssid)); wipe(out.password,sizeof(out.password));
            out.ssidBytes=strnlen(reinterpret_cast<char*>(config.ssid),32);
            out.passwordBytes=strnlen(reinterpret_cast<char*>(config.password),64);
            memcpy(out.ssid,config.ssid,out.ssidBytes); memcpy(out.password,config.password,out.passwordBytes);
            strong=config.threshold.authmode>=AUTH_WPA2_PSK && config.threshold.authmode<=AUTH_WPA_WPA2_PSK;
        }
        wipe(&config,sizeof(config)); return ok;
    }
    bool wpa2() const { return strong; }
    bool write(const Credentials& value) {
        if(!safe()) return false;
        // SDK2 rejects station configuration in AP-only mode. Enable the STA
        // interface in RAM while keeping the authenticated recovery AP alive.
        if(!WiFi.enableSTA(true)) return false;
        station_config config{};
        memcpy(config.ssid,value.ssid,32); memcpy(config.password,value.password,64);
        config.threshold.rssi=-127;
        config.threshold.authmode=AUTH_WPA2_PSK;
#if NONOSDK >= 0x30000
        config.open_and_wep_mode_disable=1;
#endif
        // Only persistent call in P1. SDK owns redundant system-param sectors.
        // Leave Arduino persistence globally disabled, including mode/AP calls.
        const bool ok=wifi_station_set_config(&config);
        wipe(&config,sizeof(config)); return ok;
    }
    bool connectSaved() {
        if(!safe()) return false;
        station_config config{};
        bool ok=wifi_station_get_config_default(&config);
        if(ok) ok=wifi_station_set_config_current(&config);
        wipe(&config,sizeof(config));
        if(ok) { wifi_station_dhcpc_start(); ok=wifi_station_connect(); }
        return ok;
    }
} sdk;
Store<Sdk> store(sdk);
Controller controller;
Intent intent;
const char* apName=nullptr; const char* apPassword=nullptr;
bool ready=false,pending=false;
uint32_t address=0;
uint32_t recoveryAt=0; bool recoveryRequested=false;
bool recoveryStartPending=false;
bool effects(unsigned flags) {
    if(flags&StartAp) {
        WiFi.mode(controller.hasSaved()?WIFI_AP_STA:WIFI_AP);
        if(!WiFi.softAP(apName,apPassword,6,false,2)) { controller.fault(); WiFi.mode(WIFI_OFF); ready=false; return false; }
        ready=true;
    }
    if(flags&StartSta) { wifi_station_disconnect(); sdk.connectSaved(); }
    if(flags&StopAp) { WiFi.softAPdisconnect(false); WiFi.mode(WIFI_STA); }
    return ready;
}
bool digest(ESP8266WebServer& s,const char* user,const char* password) {
    if(s.header("Authorization").startsWith("Digest ") && s.authenticate(user,password)) return true;
    s.requestAuthentication(DIGEST_AUTH,"SHINO-FirstBoot"); return false;
}
void answer(ESP8266WebServer& s,int code,const char* value) {
    s.sendHeader("Cache-Control","no-store"); s.sendHeader("X-Content-Type-Options","nosniff");
    s.send(code,"application/json",value);
}
}
bool storageSafe() { return sdk.safe(); }
bool configured() { return controller.hasSaved(); }
bool changePending() { return pending; }
bool begin(const char* name,const char* password) {
    apName=name; apPassword=password;
    WiFi.persistent(false); WiFi.setAutoReconnect(false);
    Credentials value;
    const bool present=sdk.safe() && store.load(value) && sdk.wpa2();
    return effects(controller.begin(millis(),present));
}
bool poll(bool transferBusy) {
    if(transferBusy) return ready; // no radio change during active media/OEM.
    if(recoveryStartPending) { recoveryStartPending=false; effects(controller.recover(millis())); }
    if(pending) {
        pending=false; intent.clear();
        Credentials value;
        effects(controller.begin(millis(),sdk.safe() && store.load(value) && sdk.wpa2()));
    }
    const uint32_t now=millis();
    const uint32_t ip=networkOrder(WiFi.localIP());
    const bool connected=WiFi.status()==WL_CONNECTED && ip!=0;
    if(ip!=address) { address=ip; intent.clear(); }
    if(recoveryRequested && uint32_t(now-recoveryAt)>=300000) recoveryRequested=false;
    effects(controller.tick(now,connected,WiFi.softAPgetStationNum()!=0 || intent.live(now) || recoveryRequested));
    return ready;
}
bool apRequest(ESP8266WebServer& s) {
    return controller.apActive() && s.client().localIP()==WiFi.softAPIP() &&
        peerOnSubnet(networkOrder(s.client().remoteIP()),networkOrder(WiFi.softAPIP()),0xffffff00);
}
bool requestAllowed(ESP8266WebServer& s) {
    const bool ap=apRequest(s);
    const auto local=s.client().localIP();
    if(!ap && (WiFi.status()!=WL_CONNECTED || local!=WiFi.localIP() ||
        !peerOnSubnet(networkOrder(s.client().remoteIP()),networkOrder(local),networkOrder(WiFi.subnetMask())))) return false;
    const String ip=local.toString();
    return authority(s.hostHeader().c_str(),s.header("Origin").c_str(),ip.c_str()) && endpoint(ap,s.uri().c_str());
}
bool apply(const uint8_t* bytes,size_t size) {
    Credentials value; bool forget=false;
    if(!decode(bytes,size,value,forget)) return false;
    const Save result=forget?store.forget():store.change(value);
    if(result==Save::Failed) { controller.fault(); return false; }
    if(result==Save::Denied) return false;
    pending=true; return true;
}
bool beforeBody(ESP8266WebServer& s,const char* user,const char* password,bool busy) {
    if(!requestAllowed(s)) { answer(s,403,"{\"error\":\"NETWORK_POLICY\"}"); return false; }
    if(s.uri()=="/api/v1/bridge/metrics" && s.method()==HTTP_POST) {
        const String& length=s.header("Content-Length");
        const unsigned n=length.toInt();
        if(length!=String(n) || n<16 || n>384 || s.header("Transfer-Encoding").length() ||
            s.header("Content-Type")!="application/json") {
            answer(s,400,"{\"error\":\"METRICS_FRAMING\"}"); return false;
        }
    }
    if(s.uri()=="/api/v1/bridge/wifi" || s.uri()=="/api/v1/bridge/wifi/recovery") {
        if(busy || pending) { answer(s,409,"{\"error\":\"TRANSFER_BUSY\"}"); return false; }
        if(s.method()!=HTTP_POST) { answer(s,405,"{\"error\":\"POST_REQUIRED\"}"); return false; }
        if(!digest(s,user,password)) return false;
        const bool recovery=s.uri().endsWith("/recovery");
        const String& length=s.header("Content-Length");
        const unsigned n=length.toInt();
        if(s.header("Transfer-Encoding").length() || length!=String(n) ||
            (recovery?n!=0:(n<1||n>99)) || s.header("Content-Type")!="application/octet-stream") {
            answer(s,400,"{\"error\":\"WIFI_FRAMING\"}"); return false;
        }
    }
    return true;
}
const char* stateName() {
    switch(controller.state) {
    case State::NoCredentials:return "NO_SAVED_WIFI";
    case State::Connecting:return "STA_CONNECTING";
    case State::Recovery:return "AP_RECOVERY_RETRY";
    case State::Online:return "STA_ONLINE";
    default:return "STORAGE_OR_AP_FAULT_HOLD";
    }
}
void registerRoutes(ESP8266WebServer& s,const char* user,const char* password) {
    s.on("/api/v1/bridge/wifi/recovery",HTTP_POST,[&s,user,password]() {
        if(!requestAllowed(s)||!digest(s,user,password)) return;
        recoveryRequested=true; recoveryAt=millis();
        recoveryStartPending=true;
        answer(s,200,"{\"protected_ap\":true,\"window_seconds\":300}");
    });
    s.on("/api/v1/bridge/wifi/intent",HTTP_GET,[&s,user,password]() {
        if(!apRequest(s)||!requestAllowed(s)) { answer(s,403,"{\"error\":\"AP_ONLY\"}"); return; }
        if(!digest(s,user,password)) return;
        if(!storageSafe() || pending || controller.state==State::Fault) { answer(s,409,"{\"error\":\"HOLD\"}"); return; }
        uint8_t random[16]{}; char token[33]{}; static constexpr char hex[]="0123456789abcdef";
        ESP.random(random,sizeof(random));
        for(size_t i=0;i<16;++i) { token[i*2]=hex[random[i]>>4]; token[i*2+1]=hex[random[i]&15]; }
        intent.arm(token,networkOrder(s.client().remoteIP()),networkOrder(s.client().localIP()),millis());
        char reply[64]{}; snprintf(reply,sizeof(reply),"{\"intent\":\"%s\"}",token);
        answer(s,200,reply); wipe(random,sizeof(random)); wipe(token,sizeof(token)); wipe(reply,sizeof(reply));
    });
    s.on("/api/v1/bridge/wifi",HTTP_POST,[&s,user,password]() {
        // Legacy parser reads an ordinary bounded body before this handler.
        // The P1 overlay adds 99-byte framing bounds before body allocation.
        const String& body=s.arg("plain");
        const auto clearBody=[&]() { wipe(const_cast<char*>(body.c_str()),body.length()); };
        if(!apRequest(s)||!requestAllowed(s)) { clearBody(); answer(s,403,"{\"error\":\"AP_ONLY\"}"); return; }
        if(!digest(s,user,password)) { clearBody(); return; }
        if(pending || controller.state==State::Fault || s.args()!=0 || s.argName(0)!="plain" ||
            s.header("Content-Type")!="application/octet-stream" || !body.length() || body.length()>99 ||
            s.header("Content-Length")!=String(body.length()) ||
            !intent.consume(s.header("X-Shino-Wifi-Intent").c_str(),networkOrder(s.client().remoteIP()),networkOrder(s.client().localIP()),millis())) {
            clearBody(); answer(s,403,"{\"error\":\"INVALID_WIFI_REQUEST\"}"); return;
        }
        const bool ok=apply(reinterpret_cast<const uint8_t*>(body.c_str()),body.length());
        clearBody(); answer(s,ok?200:409,ok?"{\"saved\":true,\"readback_verified\":true}":"{\"error\":\"WIFI_STORAGE_HOLD\"}");
    });
}
}
#endif
