#if defined(ESP8266) || !defined(HOST_MOCK)
#error "Synthetic identity: HOST review only, never a production firmware"
#endif
#pragma once
#include <stdint.h>
#include <pgmspace.h>
#define SHINO_WEATHER_OWNER 0
