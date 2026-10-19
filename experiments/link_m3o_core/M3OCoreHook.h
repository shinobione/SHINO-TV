// SHINO // LINK M3-O: REAL Arduino ESP8266 3.1.2 addHook prototype.
// This class is NEVER registered in existing firmware. Calling install()
// in an INERT compile-only probe proves type/linking, not live behavior.
// It must be installed *BEFORE* the existing B5.3 HomeLan route-allowlist
// hook, else that allowlist denies the new STA route at request line.
// The original Core reads an UNBOUNDED dynamic String request line BEFORE
// any hook: this is a HARD STOP for installing the experiment on hardware.
#pragma once
#include <Arduino.h>
#include <ESP8266WiFi.h>
#include <ESP8266WebServer.h>
#include "boot/HomeLanPolicy.h"
#include "M3OClientSlot.h"
namespace ShinoM3O {
inline uint32_t ip32(const IPAddress& ip) {
    return (uint32_t(ip[0])<<24u)|(uint32_t(ip[1])<<16u)|
           (uint32_t(ip[2])<<8u)|uint32_t(ip[3]);
}
inline bool authenticatedNetworkBoundary(const WiFiClient& client) {
    // No accepted socket data is trusted as peer/local identity; only
    // actual WiFiClient metadata. AP fallback is deliberately forbidden.
    if(WiFi.status()!=WL_CONNECTED)return false;
    const IPAddress sta=WiFi.localIP();
    const IPAddress local=client.localIP();
    if(local!=sta || local==WiFi.softAPIP())return false;
    return HomeLan::peerOnSubnet(ip32(client.remoteIP()),
                                ip32(sta),ip32(WiFi.subnetMask()));
}
class CoreHook final {
    ClientSlot<WiFiClient> slot_{};
    bool installed_=false;
public:
    CoreHook()=default;
    CoreHook(const CoreHook&)=delete;
    CoreHook& operator=(const CoreHook&)=delete;
    bool installed()const{return installed_;}
    bool busy()const{return slot_.busy();}
    void installBeforeExistingLegacyHooks(ESP8266WebServer& server) {
        if(installed_)return;
        installed_=true;
        server.addHook([this](const String& method,const String& uri,
                       WiFiClient* offered,
                       ESP8266WebServer::ContentTypeFunction)
                       -> ESP8266WebServer::ClientFuture {
            using S=ESP8266WebServer;
            if(uri!=F("/api/v1/display/mode"))
                return S::CLIENT_REQUEST_CAN_CONTINUE;
            // No fallback to the existing auth or metrics handlers;
            // only POST on the exact new path may be given.
            if(method!=F("POST") || !offered || slot_.busy() ||
               !authenticatedNetworkBoundary(*offered))
                return S::CLIENT_MUST_STOP;
            if(!slot_.take(offered,millis()))
                return S::CLIENT_MUST_STOP;
            return S::CLIENT_IS_GIVEN;
        });
    }
    Result rejectPending(uint32_t now) {
        // Does NOT authenticate, parse, or accept display changes.
        // In a future integration, a new state machine MUST validate real
        // Host/Origin and HMAC before any body byte. Not implemented here.
        return slot_.denyAndRelease(now);
    }
};
}
