#pragma once
#include <ESP8266WebServer.h>
// No writer linked. Events reflect actual parser->route->inert callback ordering.
namespace FactoryRollback {
inline int statuses=0,completions=0,uploads=0,ticks=0;inline bool uploadAuthorized=false;
inline std::vector<int> events;
inline void status(ESP8266WebServer& s){statuses++;s.send(200,"application/json","{\"inert_oem_status\":true}");}
inline void complete(ESP8266WebServer& s,bool a){events.push_back(100);if(a)completions++;s.send(200,"application/json","{\"inert_oem_completion\":true}");}
inline void upload(ESP8266WebServer& s,bool a){uploads++;uploadAuthorized=a;events.push_back(int(s.upload().status));}
inline void tick(){ticks++;}
}
