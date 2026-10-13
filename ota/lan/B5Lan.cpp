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
    // Reuse one wiped SDK structure outside the 4 KiB continuation stack.
    // Calls are serialized by the normal HTTP owner and provision lease.
    station_config scratch{};
    bool safe() const {
        constexpr uint32_t base=0x40200000;
        return HomeLan::layoutSafe(ESP.getFlashChipRealSize(),ESP.getFlashChipSize(),
            uint32_t(&_FS_start)-base,uint32_t(&_FS_end)-base,uint32_t(&_EEPROM_start)-base);
    }
    bool memorySafe() const {
        uint32_t heap=0,block=0;uint8_t frag=0;
        ESP.getHeapStats(&heap,&block,&frag);
        // SDK22x's default getter/setter allocates 0x49c bytes. Retain the
        // unchanged floors plus 1216 B (rounded payload + allocator margin).
        return heap>=20480+1216 && block>=16384+1216 &&
               ESP.getFreeContStack()>=2048 && frag<=25;
    }
    __attribute__((noinline)) bool read(HomeLan::Credentials& out) {
        HomeLan::wipe(&out,sizeof(out));
        HomeLan::wipe(&scratch,sizeof(scratch));
        bool ok=wifi_station_get_config_default(&scratch);
        if(ok) {
            out.ssidBytes=strnlen(reinterpret_cast<const char*>(scratch.ssid),32);
            out.passwordBytes=strnlen(reinterpret_cast<const char*>(scratch.password),64);
            memcpy(out.ssid,scratch.ssid,out.ssidBytes);
            memcpy(out.password,scratch.password,out.passwordBytes);
        }
        // SDK22x getters copy only SSID/password/BSSID, NOT threshold.
        // A zero-initialized threshold is not evidence of saved authmode.
        HomeLan::wipe(&scratch,sizeof(scratch));
        return ok;
    }
    void policy() {
        scratch.bssid_set=0; // router replacement / channel changes allowed
        scratch.threshold.rssi=-127;
        scratch.threshold.authmode=AUTH_WPA2_PSK;
#if NONOSDK >= 0x30000
        scratch.open_and_wep_mode_disable=1;
#endif
#if NONOSDK >= 0x30200
        scratch.channel=0;scratch.all_channel_scan=true;
#endif
    }
    __attribute__((noinline)) bool write(const HomeLan::Credentials& value) {
        HomeLan::wipe(&scratch,sizeof(scratch));
        memcpy(scratch.ssid,value.ssid,32);
        memcpy(scratch.password,value.password,64);
        policy();
        // The only persistent call. Arduino persistent(false) does not change
        // this direct SDK API; no raw flash, EEPROM, LittleFS or RTC writes.
        const bool result=wifi_station_set_config(&scratch);
        HomeLan::wipe(&scratch,sizeof(scratch));
        return result;
    }
} sdk;
HomeLan::Controller controller;
HomeLan::Intent challenge;
const char* recoveryName=nullptr;
const char* recoverySecret=nullptr;
enum class Stored:uint8_t { Unknown, Empty, Valid, Invalid };
Stored stored=Stored::Unknown;
ProvisionCode lastProvision=ProvisionCode::NotAttempted;
const char* lastConnection="NOT_STARTED";
bool started=false,pending=false,provisionBusy=false;
uint32_t pendingSince=0;
uint32_t previousIp=0;
__attribute__((noinline)) bool loadSaved() {
    stored=Stored::Unknown;
    if(!sdk.safe()){lastConnection="LAYOUT_HOLD";return false;}
    if(!sdk.memorySafe()){lastConnection="MEMORY_HOLD";return false;}
    HomeLan::Credentials saved;
    if(!sdk.read(saved)){lastConnection="SDK_READ_FAILED";return false;}
    stored=!saved.ssidBytes&&!saved.passwordBytes?Stored::Empty:
           saved.valid()?Stored::Valid:Stored::Invalid;
    return stored==Stored::Valid;
}
__attribute__((noinline)) bool connectSaved() {
    if(!sdk.safe()){lastConnection="LAYOUT_HOLD";return false;}
    if(!sdk.memorySafe()){lastConnection="MEMORY_HOLD";return false;}
    if(!WiFi.enableSTA(true)){lastConnection="STA_ENABLE_FAILED";return false;}
    if(!sdk.memorySafe()){lastConnection="MEMORY_HOLD";return false;}
    HomeLan::Credentials saved;
    if(!sdk.read(saved)){lastConnection="SDK_READ_FAILED";return false;}
    if(!saved.valid()){lastConnection="SAVED_WIFI_INVALID";return false;}
    memcpy(sdk.scratch.ssid,saved.ssid,32);
    memcpy(sdk.scratch.password,saved.password,64);
    sdk.policy(); // ALWAYS reapply WPA2 policy; never trust getter's threshold
    bool ok=wifi_station_set_config_current(&sdk.scratch);
    HomeLan::wipe(&sdk.scratch,sizeof(sdk.scratch));
    if(!ok){lastConnection="SDK_CURRENT_CONFIG_FAILED";return false;}
    if(wifi_station_dhcpc_status()!=DHCP_STARTED&&!wifi_station_dhcpc_start()) {
        lastConnection="DHCP_START_FAILED";return false;
    }
    if(!wifi_station_connect()){lastConnection="STA_CONNECT_FAILED";return false;}
    lastConnection="WAIT_ASSOCIATION_OR_DHCP";return true;
}
bool applyEffects(unsigned flags) {
    if(flags&HomeLan::StartAp) {
        // Start the recovery interface independently of station activation.
        // A STA failure cannot cancel a successful AP / existing listener.
        if(!WiFi.enableAP(true)){controller.fault();started=false;return false;}
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
        (void)connectSaved();
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
    pending=false;challenge.clear();previousIp=0;
    const bool present=loadSaved();
    return applyEffects(controller.begin(millis(),present));
}
void poll(bool otaActive) {
    if(otaActive)return;
    if(pending && uint32_t(millis()-pendingSince)>=2000) {
        pending=false;challenge.clear();
        const bool present=loadSaved();
        applyEffects(controller.begin(millis(),present));
    }
    const uint32_t now=millis(),current=word(WiFi.localIP());
    if(current!=previousIp){previousIp=current;challenge.clear();}
    const bool connected=WiFi.status()==WL_CONNECTED&&current!=0;
    if(connected)lastConnection="STA_ONLINE";
    else if(WiFi.status()==WL_WRONG_PASSWORD)lastConnection="STA_AUTH_REJECTED";
    else if(WiFi.status()==WL_NO_SSID_AVAIL)lastConnection="STA_NO_SSID";
    applyEffects(controller.tick(now,connected,WiFi.softAPgetStationNum()!=0||challenge.live(now)));
}
bool active(){return started;}
bool online(){return WiFi.status()==WL_CONNECTED&&word(WiFi.localIP())!=0;}
IPAddress address(){return online()?WiFi.localIP():IPAddress(0,0,0,0);}
const char* state() {
    if(stored==Stored::Unknown)return "SAVED_WIFI_UNKNOWN_HOLD";
    if(stored==Stored::Invalid)return "SAVED_WIFI_INVALID_HOLD";
    switch(controller.state) {
      case HomeLan::State::NoCredentials:return "NO_SAVED_WIFI";
      case HomeLan::State::Connecting:return "STA_CONNECTING";
      case HomeLan::State::Recovery:return "AP_RECOVERY_RETRY";
      case HomeLan::State::Online:return "STA_ONLINE";
      default:return "LAN_FAULT_HOLD";
    }
}
const char* storageState() {
    switch(stored){case Stored::Empty:return "EMPTY";case Stored::Valid:return "VERIFIED";
      case Stored::Invalid:return "INVALID";default:return "UNKNOWN";}
}
const char* connectionState(){return lastConnection;}
const char* codeName(ProvisionCode code) {
    switch(code) {
      case ProvisionCode::NotAttempted:return "NOT_ATTEMPTED";
      case ProvisionCode::Verified:return "PROVISION_VERIFIED";
      case ProvisionCode::ApUnavailable:return "PROVISION_AP_STATE";
      case ProvisionCode::IntentInvalid:return "PROVISION_INTENT_INVALID";
      case ProvisionCode::PayloadInvalid:return "PROVISION_PAYLOAD_INVALID";
      case ProvisionCode::LayoutUnsafe:return "PROVISION_LAYOUT_UNSAFE";
      case ProvisionCode::StaEnableFailed:return "PROVISION_STA_ENABLE_FAILED";
      case ProvisionCode::MemoryHold:return "PROVISION_MEMORY_HOLD";
      case ProvisionCode::SdkReadFailed:return "PROVISION_SDK_READ_FAILED";
      case ProvisionCode::SdkWriteFailed:return "PROVISION_SDK_WRITE_FAILED_UNKNOWN";
      case ProvisionCode::ReadbackFailed:return "PROVISION_READBACK_FAILED_UNKNOWN";
      default:return "PROVISION_READBACK_MISMATCH_UNKNOWN";
    }
}
const char* provisionState(){return codeName(lastProvision);}
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
    if(!apPeer(server)||!sdk.safe()||pending||provisionBusy||stored==Stored::Unknown||
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
void cancelIntent(){challenge.clear();}
ProvisionCode provision(ESP8266WebServer& server,const uint8_t* raw,size_t size,const char* proof) {
    if(!apPeer(server)||pending||provisionBusy||controller.state==HomeLan::State::Fault)
        return ProvisionCode::ApUnavailable;
    provisionBusy=true;
    struct Lease {~Lease(){provisionBusy=false;}} lease;
    if(!challenge.consume(proof,word(server.client().remoteIP()),
                          word(server.client().localIP()),millis()))
        return ProvisionCode::IntentInvalid;
    HomeLan::Credentials desired;bool forget=false;
    if(!HomeLan::decode(raw,size,desired,forget)||forget)
        return ProvisionCode::PayloadInvalid;
    auto result=[&]() -> ProvisionCode {
        if(!sdk.safe())return ProvisionCode::LayoutUnsafe;
        if(!sdk.memorySafe())return ProvisionCode::MemoryHold;
        if(!WiFi.enableSTA(true))return ProvisionCode::StaEnableFailed;
        if(!sdk.memorySafe())return ProvisionCode::MemoryHold;
        HomeLan::Credentials check;
        if(!sdk.read(check))return ProvisionCode::SdkReadFailed;
        if(check.same(desired)){stored=Stored::Valid;return ProvisionCode::Verified;}
        if(!sdk.memorySafe())return ProvisionCode::MemoryHold;
        // From here any failure is UNKNOWN; a false SDK return is not proof
        // that its persistent operation had no effect. Never rewrite/retry.
        stored=Stored::Unknown;
        if(!sdk.write(desired))return ProvisionCode::SdkWriteFailed;
        if(!sdk.memorySafe()||!sdk.read(check))return ProvisionCode::ReadbackFailed;
        if(!check.same(desired))return ProvisionCode::ReadbackMismatch;
        stored=Stored::Valid;return ProvisionCode::Verified;
    }();
    lastProvision=result;
    if(result==ProvisionCode::Verified){pending=true;pendingSince=millis();}
    return result;
}
} // namespace B5Lan
