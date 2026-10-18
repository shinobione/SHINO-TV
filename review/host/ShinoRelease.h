#if defined(ESP8266) || !defined(HOST_MOCK)
#error "Synthetic identity: HOST review only, never a production firmware"
#endif
#pragma once
#define SHINO_OTA_PRIVATE 1
#define SHINO_OTA_DEVICE "0123456789abcdef"
#define SHINO_OTA_BUILD "aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa"
static constexpr uint8_t ShinoReleaseKey[32]={194,184,152,111,36,170,201,130,229,123,253,189,126,203,63,110,210,158,252,38,62,209,107,11,54,54,3,86,159,186,246,6};
