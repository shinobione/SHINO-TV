// SPDX-License-Identifier: GPL-3.0-or-later
#include "B53WeatherFrame.h"
#include <cassert>
#include <cstring>
#include <cstdio>
int main(){
 using namespace B53WeatherFrame;
 Sample value{};
 const char* ok=R"({"latitude":43.2,"current_units":{"temperature_2m":"\u00b0C"},"current":{"time":"2026-10-15T17:00","interval":900,"temperature_2m":18.4,"weather_code":3}})";
 assert(parse(ok,strlen(ok),value)&&value.tenthsC==184&&value.code==3);
 const char* minus=R"({"current":{"temperature_2m":-0.1,"weather_code":61},"generationtime_ms":0.02})";
 assert(parse(minus,strlen(minus),value)&&value.tenthsC==-1&&value.code==61);
 const char* invalid[]={
 R"({"current":{"temperature_2m":null,"weather_code":3}})",
 R"({"current":{"temperature_2m":18.4,"weather_code":19}})",
 R"({"current":{"temperature_2m":18.4,"temperature_2m":17.4,"weather_code":3}})",
 R"({"current":{"temperature_2m":18.4,"weather_code":3},"current":{"temperature_2m":1,"weather_code":2}})",
 R"({"current":{"temperature_2m":18.4,"weather_code":3}}garbage)",
 R"({"current":{"temperature_2m":18.47,"weather_code":3}})",
 R"({"current":{"temperature_2m":70.1,"weather_code":3}})",
 R"({"current":{"temperature_2m":18.4,"weather_code":3.4}})",
 R"({"current":{"temperature_2m":18.4,"weather_code":3})",
 R"({"current":{"weather_code":3}})",
 R"({"current":{"temperature_2m":18.4}})",
 R"({"current":{"temperature_2m":18.4,"weather_code":3},"extra":[[[[[[42]]]]]]})"
 };
 for(auto s:invalid)assert(!parse(s,strlen(s),value));
 char oversized[MAX_BODY+1];memset(oversized,' ',sizeof(oversized));
 assert(!parse(oversized,sizeof(oversized),value));
 assert(label(0)&&label(99)&&!label(19));
 std::puts("B53_WEATHER_STRICT_PARSER_PASS");
}
