#pragma once
#include <ctime>
inline void(*sntpCallback)(bool)=nullptr;
inline void settimeofday_cb(void(*callback)(bool)){sntpCallback=callback;}
inline void configTime(const char*,const char*,const char*){}
#ifdef _MSC_VER
inline tm* localtime_r(const time_t* value,tm* out){return localtime_s(out,value)==0?out:nullptr;}
#endif
