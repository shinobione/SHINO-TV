#if defined(ESP8266) || !defined(HOST_MOCK)
#error "Synthetic identity: HOST review only, never a production firmware"
#endif
#pragma once
#define SHINO_OTA_DEVICE "0123456789abcdef"
#define SHINO_OTA_BUILD "cccccccccccccccccccccccccccccccccccccccccccccccccccccccccccccccc"
#define SHINO_OTA_PRIVATE 0
static constexpr uint8_t ShinoReleaseKey[32]={0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0};
