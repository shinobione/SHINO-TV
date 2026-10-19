// Compile/run actual M3-P reader algorithm in HOST C++ with simulated
// fragmented clients and deadlines. Does not claim to test real ESP8266 lwIP.
#include "M3PBoundedLine.h"
#include <cstdio>
#include <cstdlib>
#include <string>
struct Client {
    std::string bytes;
    size_t used=0;
    size_t exposed=0;
    bool stayConnected=true;
    int reads=0;
    int available()const{return int(exposed-used);}
    bool connected()const{return stayConnected || used<bytes.size();}
    int read() {if(used>=exposed)return -1;++reads;
                return static_cast<unsigned char>(bytes[used++]);}
};
static void check(bool condition,const char* msg) {
    if(!condition){std::fprintf(stderr,"M3P_FAIL:%s\n",msg);std::exit(2);}
}
static bool parse(Client& stream,std::string& out,uint32_t& clock,
                  uint32_t tickPerYield=1u) {
    return ShinoM3P::readFirstLine(stream,out,[&](){return clock;},
        [&](){
            clock+=tickPerYield;
            if(stream.exposed<stream.bytes.size())++stream.exposed;
        },clock);
}
int main() {
    std::string result;
    uint32_t now=10;
    Client exact{"POST /api/v1/display/mode HTTP/1.1\r\nHost: example\r\n"};
    exact.exposed=exact.bytes.size();
    check(parse(exact,result,now),"normal M3 CRLF");
    check(result=="POST /api/v1/display/mode HTTP/1.1","exact raw line");
    check(exact.bytes.substr(exact.used)=="Host: example\r\n",
          "must leave HEADER AND BODY bytes entirely unread");
    Client legacy{"GET /api/v1/bridge/metrics HTTP/1.1\r\n"};
    legacy.exposed=legacy.bytes.size();
    check(parse(legacy,result,now),"normal legacy metrics");
    check(result=="GET /api/v1/bridge/metrics HTTP/1.1","legacy byte equality");
    Client boundary{std::string(256,'A')+"\r\n"};
    boundary.exposed=boundary.bytes.size();
    check(parse(boundary,result,now),"exactly 256 visible ASCII bytes allowed");
    check(result.size()==256,"256 character bound correctly included");
    Client overflow{std::string(257,'A')+"\r\nHost: x\r\n"};
    overflow.exposed=overflow.bytes.size();
    check(!parse(overflow,result,now),"257 chars reject");
    check(overflow.used==257u,"reject before reading CRLF or headers");
    Client bareLF{"POST /api/v1/display/mode HTTP/1.1\nX"};
    bareLF.exposed=bareLF.bytes.size();
    check(!parse(bareLF,result,now),"bare LF rejected");
    Client bareCR{"GET / HTTP/1.1\rX"};
    bareCR.exposed=bareCR.bytes.size();
    check(!parse(bareCR,result,now),"CR then non-LF rejected");
    Client nullByte{std::string("GET / HTTP/1.1",14)+"\0X\r\n"};
    nullByte.bytes="GET / HTTP/1.1";
    nullByte.bytes.push_back('\0');
    nullByte.bytes+="X\r\n";
    nullByte.exposed=nullByte.bytes.size();
    check(!parse(nullByte,result,now),"NUL rejected");
    Client highByte{"GET / HTTP/1.1"};
    highByte.bytes.push_back(char(0xff));highByte.bytes+="\r\n";
    highByte.exposed=highByte.bytes.size();
    check(!parse(highByte,result,now),"non ASCII rejected");
    Client split{"GET / HTTP/1.1\r\nHost: x\r\n"};
    split.exposed=0; // one byte per cooperative scheduler pass
    const uint32_t before=now;
    check(parse(split,result,now),"split CRLF under deadline");
    check(now>before,"yield expected for fragmented input");
    check(split.bytes.substr(split.used)=="Host: x\r\n","no header read under split");
    // A truly silent peer sends ZERO bytes; the fake scheduler must
    // not reveal a complete line while testing the timeout.
    Client silent{""};
    silent.exposed=0;
    silent.stayConnected=true;
    const uint32_t t0=now;
    check(!parse(silent,result,now,100u),"slowloris deadline");
    check(now-t0>=ShinoM3P::kRequestDeadlineMs,"2000ms bound");
    Client wrap{"GET / HTTP/1.1\r\n"};
    wrap.exposed=0;
    now=UINT32_MAX-20u;
    check(parse(wrap,result,now),"deadline works across millis wrap");
    check(result=="GET / HTTP/1.1","wrap payload exact");
    std::puts("M3P_BOUNDED_FIRST_LINE_HOST_256_AND_DEADLINE_PASS");
}
