// SPDX-License-Identifier: GPL-3.0-or-later
#pragma once
#include <cstdint>
#include <cstddef>
#include <cstring>

namespace HomeLan {
inline void wipe(void* memory, size_t bytes) {
    volatile uint8_t* p = static_cast<volatile uint8_t*>(memory);
    while (bytes--) *p++ = 0;
}
struct Credentials {
    uint8_t ssid[32]{};
    uint8_t password[64]{};
    size_t ssidBytes = 0, passwordBytes = 0;
    bool valid() const {
        if (!ssidBytes || ssidBytes > 32 || passwordBytes < 8 || passwordBytes > 64) return false;
        for (size_t i=0; i<ssidBytes; ++i) if (ssid[i]<32 || ssid[i]>126) return false;
        for (size_t i=0; i<passwordBytes; ++i) {
            const uint8_t c=password[i];
            if (c<32 || c>126) return false;
            if (passwordBytes==64 && !((c>='0'&&c<='9')||(c>='a'&&c<='f')||(c>='A'&&c<='F'))) return false;
        }
        return true;
    }
    bool same(const Credentials& other) const {
        return ssidBytes==other.ssidBytes && passwordBytes==other.passwordBytes &&
            !memcmp(ssid,other.ssid,32) && !memcmp(password,other.password,64);
    }
    ~Credentials() { wipe(this,sizeof(*this)); }
};
// Only SDK system parameters; no EEPROM, filesystem, raw flash or RTC writes.
constexpr uint32_t flashBytes=0x400000, sdkStart=0x3fd000, sdkEnd=0x400000;
inline bool layoutSafe(uint32_t real, uint32_t header, uint32_t fsStart, uint32_t fsEnd, uint32_t eeprom) {
    return real==flashBytes && header==flashBytes && fsStart==0x100000 &&
        fsEnd==0x3fa000 && eeprom==0x3fb000 && eeprom+0x1000<sdkStart;
}
enum class Save { Unchanged, Verified, Denied, Failed };
// Backend is the same SDK adapter used on target; tests inject only its I/O.
template<class Backend> class Store {
    Backend& io;
public:
    explicit Store(Backend& b):io(b){}
    bool load(Credentials& out) { return io.read(out) && out.valid(); }
    Save change(const Credentials& desired) {
        if (!io.safe() || !desired.valid()) return Save::Denied;
        Credentials old;
        if (!io.read(old)) return Save::Failed;
        if (old.same(desired) && io.wpa2()) return Save::Unchanged;
        if (!io.write(desired)) return Save::Failed;
        Credentials check;
        return io.read(check) && check.same(desired) && io.wpa2() ? Save::Verified : Save::Failed;
    }
    Save forget() {
        if (!io.safe()) return Save::Denied;
        Credentials old;
        if (!io.read(old)) return Save::Failed;
        if (!old.ssidBytes && !old.passwordBytes) return Save::Unchanged;
        Credentials blank;
        if (!io.write(blank)) return Save::Failed;
        Credentials check;
        return io.read(check) && !check.ssidBytes && !check.passwordBytes ? Save::Verified : Save::Failed;
    }
};
enum class State { NoCredentials, Connecting, Recovery, Online, Fault };
enum Effect : unsigned { None=0, StartAp=1, StartSta=2, StopAp=4 };
class Controller {
    bool saved=false, ap=false;
    uint32_t since=0, stable=0;
public:
    State state=State::NoCredentials;
    static constexpr uint32_t connectMs=20000, retryMs=60000, stableMs=15000;
    unsigned begin(uint32_t now, bool present) {
        saved=present; ap=true; since=now; stable=now;
        state=present?State::Connecting:State::NoCredentials;
        return StartAp | (present?StartSta:None);
    }
    unsigned tick(uint32_t now, bool addressed, bool ownerUsingAp) {
        if(state==State::Fault) return None;
        if (addressed && saved) {
            if(state!=State::Online) { state=State::Online; stable=now; }
            if(ap && !ownerUsingAp && uint32_t(now-stable)>=stableMs) { ap=false; return StopAp; }
            return None;
        }
        if(state==State::Online) {
            state=State::Connecting; since=now; ap=true;
            return StartAp|StartSta;
        }
        if(state==State::Connecting && uint32_t(now-since)>=connectMs) {
            state=State::Recovery; since=now;
        }
        if(state==State::Recovery && saved && uint32_t(now-since)>=retryMs) {
            state=State::Connecting; since=now; return StartSta;
        }
        return None;
    }
    void fault() { state=State::Fault; }
    bool hasSaved() const { return saved; }
    bool apActive() const { return ap; }
    unsigned recover(uint32_t now) { ap=true; stable=now; return StartAp; }
};
// Network-order IPv4. Numeric authority only: explicit DHCP IP from router.
inline bool authority(const char* host, const char* origin, const char* local) {
    char withPort[24]{}; char url[40]{}; char urlPort[40]{};
    const size_t n=strlen(local);
    if(!n || n>15) return false;
    memcpy(withPort,local,n); memcpy(withPort+n,":80",4);
    memcpy(url,"http://",7); memcpy(url+7,local,n);
    memcpy(urlPort,"http://",7); memcpy(urlPort+7,withPort,n+4);
    return (!strcmp(host,local)||!strcmp(host,withPort)) &&
        (!*origin||!strcmp(origin,url)||!strcmp(origin,urlPort));
}
inline bool peerOnSubnet(uint32_t peer, uint32_t local, uint32_t mask) {
    const uint32_t inverse=~mask;
    return mask && !(inverse&(inverse+1)) && (peer&mask)==(local&mask) &&
        peer!=local && (peer&inverse)!=0 && (peer&inverse)!=inverse;
}
inline bool endpoint(bool ap, const char* path) {
    if(ap) return true;
    return !strcmp(path,"/") || !strcmp(path,"/ui.js") ||
        !strcmp(path,"/api/v1/bridge/metrics") || !strcmp(path,"/api/v1/bridge/status") ||
        !strcmp(path,"/api/v1/bridge/wifi/recovery") ||
        !strcmp(path,"/api/v1/bridge/ota/capabilities");
}
class Intent {
    char token[33]{};
    uint32_t peer=0, local=0, issued=0;
public:
    void clear() { wipe(token,sizeof(token)); peer=local=issued=0; }
    void arm(const char* value,uint32_t p,uint32_t l,uint32_t now) {
        clear(); if(strlen(value)!=32) return;
        memcpy(token,value,32); peer=p; local=l; issued=now;
    }
    bool live(uint32_t now) const { return token[0] && uint32_t(now-issued)<60000; }
    bool consume(const char* value,uint32_t p,uint32_t l,uint32_t now) {
        if(!live(now)||p!=peer||l!=local||strlen(value)!=32) return false;
        uint8_t diff=0; for(size_t i=0;i<32;++i) diff|=token[i]^value[i];
        if(diff) return false;
        clear(); return true;
    }
};
// Length-prefixed binary, maximum 99 bytes; no secrets in URL/query/JSON/error.
// Change: 'C', ssid length, password length, SSID bytes, password bytes.
// Forget: exactly 'F'. All fields validated before SDK persistence.
inline bool decode(const uint8_t* bytes,size_t size,Credentials& out,bool& forget) {
    forget=size==1 && bytes[0]=='F'; if(forget) return true;
    if(size<3 || size>99 || bytes[0]!='C') return false;
    out.ssidBytes=bytes[1]; out.passwordBytes=bytes[2];
    if(out.ssidBytes>32||out.passwordBytes>64||size!=3+out.ssidBytes+out.passwordBytes) return false;
    memcpy(out.ssid,bytes+3,out.ssidBytes); memcpy(out.password,bytes+3+out.ssidBytes,out.passwordBytes);
    return out.valid();
}
}
