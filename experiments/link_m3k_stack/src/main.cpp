// Exact M3-J inert Xtensa source, same graph, same pinned compilation.
// M3-K varies solely SHINO_M3C_STACK_MEMBER_SCRATCH in platformio.ini.
// These programs are NEVER valid owner-device firmware.
#include <Arduino.h>
#include <ESP8266WiFi.h>
#include <ArduinoJson.h>
#include "../../link_m3j_native/src/main.cpp"
