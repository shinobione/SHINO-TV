#pragma once
#include <ESP8266WebServer.h>
// No Updater/flash seam is present. Only route/auth delegation is measured.
namespace FactoryRollback {
inline int statuses=0,completions=0,uploads=0,ticks=0; inline bool uploadAuthorized=false;
inline void status(ESP8266WebServer& s){statuses++;s.send(200,"application/json","{}");}
inline void complete(ESP8266WebServer&,bool a){if(a)completions++;}
inline void upload(ESP8266WebServer&,bool a){uploads++;uploadAuthorized=a;}
inline void tick(){ticks++;}
}
