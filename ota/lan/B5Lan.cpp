// SPDX-License-Identifier: GPL-3.0-or-later
// B5 only: never replace the deployed B4 source.
#include "B5Lan.h"
extern "C" {
#include <user_interface.h>
extern uint32_t _FS_start, _FS_end, _EEPROM_start;
}
namespace B5Lan {
namespace {
uint32_t word(const IPAddress& a) {
    return uint32_t(a[0])<<24 | uint32_t(a[1])<<16 |
           uint32_t(a[2])<<8 | a[3];
}
struct Sdk {
    bool strong=false;
    bool safe() const {
        constexpr uint32_t base=0x40200000;
        return HomeLan::layoutSafe(ESP.getFlashChipRealSize(),ESP.getFlashChipSize(),
            uint32_t(&_FS_start)-base,uint32_t(&_FS_end)-base,uint32_t(&_EEPROM_start)-base);
    }
    bool read(HomeLan::Credentials& out) {
        station_config saved{};
        bool ok=wifi_station_get_config_default(&saved);
        if(ok) {
            out.ssidBytes=strnlen(reinterpret_cast<const char*>(saved.ssid),32);
            out.passwordBytes=strnlen(reinterpret_cast<const char*>(saved.password),64);
            memcpy(out.ssid,saved.ssid,out.ssidBytes);
            memcpy(out.password,saved.password,out.passwordBytes);
            strong=saved.threshold.authmode>=AUTH_WPA2_PSK &&
                   saved.threshold.authmode<=AUTH_WPA_WPA2_PSK;
        }
        HomeLan::wipe(&saved,sizeof(saved));
        return ok;
    }
    bool wpa2() const { return strong; }
    bool write(const HomeLan::Credentials& value) {
        if(!safe() || !WiFi.enableSTA(true))return false;
        station_config saved{};
        memcpy(saved.ssid,value.ssid,32);
        memcpy(saved.password,value.password,64);
        saved.threshold.rssi=-127;
        saved.threshold.authmode=AUTH_WPA2_PSK;
#if NONOSDK >= 0x30000
        saved.open_and_wep_mode_disable=1;
#endif
        const bool result=wifi_station_set_config(&saved);
        HomeLan::wipe(&saved,sizeof(saved));
        return result;
    }
    bool connectSaved() {
        if(!safe())return false;
        station_config saved{};
        bool ok=wifi_station_get_config_default(&saved);
        if(ok)ok=wifi_station_set_config_current(&saved);
        HomeLan::wipe(&saved,sizeof(saved));
        if(ok){wifi_station_dhcpc_start();ok=wifi_station_connect();}
        return ok;
    }
} sdk;
HomeLan::Store<Sdk> store(sdk);
HomeLan::Controller controller;
HomeLan::Intent challenge;
const char* recoveryName=nullptr;
const char* recoverySecret=nullptr;
bool started=false,pending=false;
uint32_t pendingSince=0;
uint32_t previousIp=0;
bool applyEffects(unsigned flags) {
    if(flags&HomeLan::StartAp) {
        WiFi.mode(controller.hasSaved()?WIFI_AP_STA:WIFI_AP);
        if(!WiFi.softAP(recoveryName,recoverySecret,6,false,2)) {
            controller.fault();started=false;return false;
        }
        started=true;
    }
    if(flags&HomeLan::StartSta) {
        wifi_station_disconnect();
        // A failed STA start must NEVER disable the already-started
        // protected recovery AP / HTTP listener. Retry is governed by
        // HomeLan::Controller, while the owner can still reach the AP.
        // In particular, B5Lan::begin() must stay successful when StartAp
        // succeeded but the station SDK rejected its initial connect.
        (void)sdk.connectSaved();
    }
    if(flags&HomeLan::StopAp) {
        WiFi.softAPdisconnect(false);
        WiFi.mode(WIFI_STA);
    }
    return started;
}
} // anonymous namespace
bool begin(const char* ssid,const char* psk) {
    recoveryName=ssid;recoverySecret=psk;
    WiFi.persistent(false);WiFi.setAutoReconnect(false);
    HomeLan::Credentials saved;
    const bool present=sdk.safe()&&store.load(saved)&&sdk.wpa2();
    return applyEffects(controller.begin(millis(),present));
}
void poll(bool otaActive) {
    if(otaActive)return;
    if(pending && uint32_t(millis()-pendingSince)>=2000) {
        pending=false;challenge.clear();
        HomeLan::Credentials saved;
        const bool present=sdk.safe()&&store.load(saved)&&sdk.wpa2();
        applyEffects(controller.begin(millis(),present));
    }
    const uint32_t now=millis(),current=word(WiFi.localIP());
    if(current!=previousIp){previousIp=current;challenge.clear();}
    const bool connected=WiFi.status()==WL_CONNECTED&&current!=0;
    applyEffects(controller.tick(now,connected,WiFi.softAPgetStationNum()!=0||challenge.live(now)));
}
bool active(){return started;}
bool online(){return WiFi.status()==WL_CONNECTED&&word(WiFi.localIP())!=0;}
IPAddress address(){return online()?WiFi.localIP():IPAddress(0,0,0,0);}
const char* state() {
    switch(controller.state) {
      case HomeLan::State::NoCredentials:return "NO_SAVED_WIFI";
      case HomeLan::State::Connecting:return "STA_CONNECTING";
      case HomeLan::State::Recovery:return "AP_RECOVERY_RETRY";
      case HomeLan::State::Online:return "STA_ONLINE";
      default:return "LAN_FAULT_HOLD";
    }
}
bool apPeer(ESP8266WebServer& server) {
    const auto local=server.client().localIP(),peer=server.client().remoteIP();
    return controller.apActive()&&local==WiFi.softAPIP()&&
        HomeLan::peerOnSubnet(word(peer),word(local),0xffffff00u);
}
bool permitted(ESP8266WebServer& server) {
    const auto local=server.client().localIP(),peer=server.client().remoteIP();
    if(!apPeer(server)) {
        if(!online()||local!=WiFi.localIP()||
           !HomeLan::peerOnSubnet(word(peer),word(local),word(WiFi.subnetMask())))return false;
    }
    const String origin=server.header("Origin");
    const String host=server.hostHeader();
    const String numeric=local.toString();
    return HomeLan::authority(host.c_str(),origin.c_str(),numeric.c_str());
}
bool intentStart(ESP8266WebServer& server,char out[33]) {
    if(!apPeer(server)||!sdk.safe()||pending||
       controller.state==HomeLan::State::Fault)return false;
    uint8_t random[16]{};
    static constexpr char hex[]="0123456789abcdef";
    ESP.random(random,sizeof(random));
    for(size_t i=0;i<16;++i){out[i*2]=hex[random[i]>>4];out[i*2+1]=hex[random[i]&15];}
    out[32]=0;
    challenge.arm(out,word(server.client().remoteIP()),word(server.client().localIP()),millis());
    HomeLan::wipe(random,sizeof(random));
    return true;
}
bool provision(ESP8266WebServer& server,const uint8_t* raw,size_t size,const char* proof) {
    if(!apPeer(server)||pending||controller.state==HomeLan::State::Fault||
       !challenge.consume(proof,word(server.client().remoteIP()),
                          word(server.client().localIP()),millis()))return false;
    HomeLan::Credentials desired;bool forget=false;
    if(!HomeLan::decode(raw,size,desired,forget)||forget)return false;
    const auto result=store.change(desired);
    if(result!=HomeLan::Save::Verified && result!=HomeLan::Save::Unchanged)return false;
    pending=true;pendingSince=millis();return true;
}
} // namespace B5Lan
