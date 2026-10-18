// SPDX-License-Identifier: GPL-3.0-or-later
#pragma once
#include <cstdint>
#include <cstring>
namespace ShinoInstall {
struct Budget {
    uint32_t heap,block,stack; uint8_t frag;
    bool safe()const{return heap>=20480 && block>=16384 && stack>=2048 && frag<=25;}
};
inline bool hex(const char* s,size_t n){if(std::strlen(s)!=n)return false;for(size_t i=0;i<n;++i)if(!((s[i]>='0'&&s[i]<='9')||(s[i]>='a'&&s[i]<='f')))return false;return true;}
}
