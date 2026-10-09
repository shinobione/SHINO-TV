// SPDX-License-Identifier: GPL-3.0-or-later
#pragma once
#include <ESP8266WebServer.h>
namespace ShinoInstall {
class ReclaimingHttp:public ESP8266WebServer {
public:
    using ESP8266WebServer::ESP8266WebServer;
    void quiesce(){
        // Core close() alone leaves pending contexts queued. Close the listener
        // first, then drain/abort; callbacks cannot add more accepted clients.
        _server.close();
        while(_server.hasClient()){auto pending=_server.accept();pending.abort();}
        _currentClient.abort();_currentClient=WiFiClient();
        // The pinned Core destructor does not delete these two raw arrays.
        delete[] _currentArgs;_currentArgs=nullptr;_currentArgCount=0;_currentArgsHavePlain=false;
        delete[] _postArgs;_postArgs=nullptr;_postArgsLen=0;
        // Destruction immediately follows; Core then releases headers/handlers,
        // Strings, upload state and prebody/not-found closures exactly once.
    }
};
}
