// M3-L: same dormant Xtensa code graph as M3-J/K, compile-only.
// Explicit includes ensure PlatformIO library finder sees Core WiFi.
#include <Arduino.h>
#include <ESP8266WiFi.h>
#include <ArduinoJson.h>
#include "../../link_m3j_native/src/main.cpp"
