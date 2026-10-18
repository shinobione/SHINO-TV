// SPDX-License-Identifier: GPL-3.0-or-later
#pragma once
#ifndef SHINO_ENABLE_HOME_LAN
#define SHINO_ENABLE_HOME_LAN 0
#endif
#if SHINO_ENABLE_HOME_LAN
#ifndef SHINO_HOME_LAN_PREBODY
#error "P1 requires the reviewed pre-body parser overlay; stock parser forbidden."
#endif
#include <ESP8266WebServer.h>
namespace HomeLan {
bool begin(const char* apName,const char* apPassword);
bool poll(bool transferBusy);
bool apRequest(ESP8266WebServer& server);
bool requestAllowed(ESP8266WebServer& server);
bool configured();
bool storageSafe();
bool changePending();
bool apply(const uint8_t* bytes,size_t size);
const char* stateName();
void registerRoutes(ESP8266WebServer& server,const char* user,const char* password);
bool beforeBody(ESP8266WebServer& server,const char* user,const char* password,bool busy);
}
#endif
