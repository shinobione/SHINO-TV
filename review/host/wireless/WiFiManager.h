#pragma once
class WiFiManager{public:WiFiManager(const char*,const char*,const char*,const char*){}bool startAccessPointMode(){return !WiFi.persisted;}};
