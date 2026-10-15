// SPDX-License-Identifier: GPL-3.0-or-later
#include "B53WeatherChunked.h"
#include <string>
#include <cstdio>
#include <cassert>
#include <cstring>
static bool decode(const std::string& stream,size_t cap,size_t& count,bool& done) {
    char out[769]={};
    B53WeatherChunked::Decoder d(out,cap);
    bool accepted=true;
    for(unsigned char byte:stream)if(!d.consume(byte)){accepted=false;break;}
    count=d.size();done=d.complete();
    return accepted;
}
int main(){
    size_t n=0;bool done=false;
    assert(decode("3\r\nabc\r\n2\r\nde\r\n0\r\n\r\n",768,n,done)&&done&&n==5);
    assert(decode("0\r\n\r\n",768,n,done)&&done&&n==0);
    const char* json=R"({"current":{"temperature_2m":18.4,"weather_code":3}})";
    char size[24];std::snprintf(size,sizeof(size),"%X\r\n",unsigned(std::strlen(json)));
    assert(decode(std::string(size)+json+"\r\n0\r\n\r\n",768,n,done)&&
           done&&n==std::strlen(json));
    assert(decode("3\r\nabc\r\n",768,n,done)&&!done);
    assert(!decode("3\nabc\n0\n\n",768,n,done));
    assert(!decode("3;ext=1\r\nabc\r\n0\r\n\r\n",768,n,done));
    assert(!decode("3\r\nabc\r\n0\r\nX\r\n",768,n,done));
    assert(!decode("G\r\nabc\r\n0\r\n\r\n",768,n,done));
    assert(!decode("00001\r\nx\r\n0\r\n\r\n",768,n,done));
    assert(!decode("3\r\nabc\r\n0\r\n\r\nX",768,n,done));
    const std::string maxbody(768,'x');
    assert(decode("300\r\n"+maxbody+"\r\n0\r\n\r\n",768,n,done)&&
           done&&n==768);
    assert(!decode("301\r\n"+maxbody+"y\r\n0\r\n\r\n",768,n,done));
    std::string many;
    for(int i=0;i<768;i++)many+="1\r\nx\r\n";
    many+="0\r\n\r\n";
    assert(decode(many,768,n,done)&&done&&n==768);
    many.insert(many.size()-5,"1\r\nx\r\n");
    assert(!decode(many,768,n,done));
    std::puts("B53_CHUNKED_BOUNDED_PASS");
}
