// SPDX-License-Identifier: GPL-3.0-or-later
#pragma once
#include <stddef.h>
#include <stdint.h>
#include <string.h>
namespace B54LanWeather {
// Raw URI, never URL-decoded or parsed as query arguments. No allocation.
inline bool statusPath(const char* uri,size_t length,uint8_t* challenge=nullptr){
 static const char prefix[]="/api/v1/weather/status/";
 constexpr size_t start=sizeof(prefix)-1;
 if(!uri||length!=start+16||memcmp(uri,prefix,start))return false;
 for(unsigned i=0;i<8;++i){unsigned value=0;
  for(unsigned j=0;j<2;++j){const char c=uri[start+i*2+j];
   if(!((c>='0'&&c<='9')||(c>='a'&&c<='f')))return false;
   value=value*16+unsigned(c<='9'?c-'0':c-'a'+10);
  }
  if(challenge)challenge[i]=uint8_t(value);
 }
 return true;
}
}
