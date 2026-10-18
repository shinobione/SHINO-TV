#if defined(ESP8266) || !defined(HOST_MOCK)
#error "Synthetic identity: HOST review only, never a production firmware"
#endif
#pragma once
#define SHINO_WEATHER_OWNER 1
static const uint8_t B54LanKey[32]={0,1,2,3,4,5,6,7,8,9,10,11,12,13,14,15,16,17,18,19,20,21,22,23,24,25,26,27,28,29,30,31};
