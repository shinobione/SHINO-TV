// SHINO // TV B5 — home-LAN client for the opt-in 4m2m OTA normal profile.
// Prepared only inside a disposable B5 build graph, NEVER linked into B4.
#pragma once
#include <Arduino.h>
#include <ESP8266WiFi.h>
#include <ESP8266WebServer.h>
#include "boot/HomeLanPolicy.h"
namespace B5Lan {
bool begin(const char* ssid,const char* psk);
void poll(bool otaActive);
bool permitted(ESP8266WebServer& server);
bool apPeer(ESP8266WebServer& server);
bool online();
bool active();
const char* state();
const char* storageState();
const char* connectionState();
const char* provisionState();
IPAddress address();
bool intentStart(ESP8266WebServer& server,char out[33]);
void cancelIntent();
// Non-secret, fixed error codes. No SSID/password/token in the response.
enum class ProvisionCode : uint8_t {
    NotAttempted, Verified, ApUnavailable, IntentInvalid, PayloadInvalid,
    LayoutUnsafe, StaEnableFailed, MemoryHold, SdkReadFailed, SdkWriteFailed,
    ReadbackFailed, ReadbackMismatch
};
const char* codeName(ProvisionCode code);
ProvisionCode provision(ESP8266WebServer& server,const uint8_t* bytes,size_t length,const char* proof);
} // namespace B5Lan
