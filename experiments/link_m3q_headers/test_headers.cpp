#include "M3QBoundedHeaders.h"
#include <string>
#include <cstdio>
#include <cstdlib>
#include <cstdint>
using namespace ShinoM3Q;
static void need(bool b,const char* why){if(!b){std::fprintf(stderr,"M3Q_FAIL %s\n",why);std::exit(3);}}
struct Fake {
 std::string wire; size_t pos=0,exposed=0; bool live=true; unsigned reads=0;
 int available()const{return static_cast<int>(exposed-pos);}
 bool connected()const{return live;}
 int read(){++reads;return pos<exposed?static_cast<unsigned char>(wire[pos++]):-1;}
};
static const std::string goodHeaders=
 "Host: 192.168.1.70\r\n"
 "Content-Type: application/json\r\n"
 "Content-Length: 120\r\n"
 "Connection: close\r\n"
 "X-Shino-Device: abcdef0123456789\r\n"
 "X-Shino-Boot: abcdef0123456789abcdef0123456789\r\n"
 "X-Shino-Revision: 3\r\n"
 "X-Shino-Mode: AUTO\r\n"
 "X-Shino-Tx: abcdef0123456789abcdef0123456789\r\n"
 "X-Shino-Body-Sha256: "+std::string(64,'a')+"\r\n"
 "X-Shino-Proof: "+std::string(64,'b')+"\r\n\r\n";
static State parse(const std::string& s,bool fragments=false,uint32_t start=0,
                   uint32_t tick=1,bool alive=true,size_t* consumed=nullptr) {
 Fake f;f.wire=s;f.exposed=fragments?0:s.size();f.live=alive;
 HeaderGuard guard;uint32_t t=start;
 State r=readHeaders(f,guard,[&]{return t;},[&]{t+=tick;if(fragments&&f.exposed<f.wire.size())++f.exposed;},start);
 if(consumed)*consumed=f.pos;
 return r;
}
static std::string replace(const std::string& s,const std::string& from,const std::string& to) {
 auto i=s.find(from);need(i!=std::string::npos,"fixture anchor");auto x=s;x.replace(i,from.size(),to);return x;
}
int main(){
 size_t got=0;
 need(parse(goodHeaders+"BODY_MUST_BE_UNREAD",false,0,1,true,&got)==State::ReadyForAuth,"exact schema");
 need(got==goodHeaders.size(),"do not read body byte");
 need(parse(goodHeaders,true)==State::ReadyForAuth,"fragmented input");
 need(parse(goodHeaders,true,0,4u)==State::Rejected,"fragmented slowloris deadline");
 need(parse(replace(goodHeaders,"Host: ","Host: ")+std::string("\0",1))==State::ReadyForAuth,"no body read on embedded NUL body");
 need(parse(replace(goodHeaders,"Host: ","Host: ").substr(0,5)+std::string("\0",1)+goodHeaders)==State::Rejected,"NUL in header");
 need(parse(goodHeaders,true,UINT32_MAX-400u)==State::ReadyForAuth,"millis wrap");
 need(parse(goodHeaders.substr(0,goodHeaders.size()-2))==State::Rejected,"missing terminator");
 need(parse("")==State::Rejected,"silent slowloris absolute deadline");
 need(parse("Host: x\r\n",true,0,1,false)==State::Rejected,"EOF while incomplete");
 need(parse(replace(goodHeaders,"Host: ","host: "))==State::ReadyForAuth,"header name case-folded");
 need(parse(replace(goodHeaders,"Host: 192", "Host: 192\r\nHost: 192"))==State::Rejected,"duplicate Host");
 need(parse(replace(goodHeaders,"Content-Length: 120", "Content-Length: 000120"))==State::Rejected,"leading zero CL");
 need(parse(replace(goodHeaders,"Content-Length: 120", "Content-Length: 241"))==State::Rejected,"oversize body CL");
 need(parse(replace(goodHeaders,"Content-Length: 120", "Content-Length: 4294967295"))==State::Rejected,"overflow CL");
 need(parse(replace(goodHeaders,"Content-Length: 120", "Content-Length: 12,12"))==State::Rejected,"ambiguous CL");
 need(parse(replace(goodHeaders,"Connection: close", "Transfer-Encoding: chunked"))==State::Rejected,"TE unsupported");
 need(parse(replace(goodHeaders,"Connection: close", "Expect: 100-continue"))==State::Rejected,"Expect unsupported");
 need(parse(replace(goodHeaders,"Connection: close", "Origin: http://x"))==State::Rejected,"Origin unauthorized by current M3C profile");
 need(parse(replace(goodHeaders,"Host: "," Host: "))==State::Rejected,"obs-fold invalid");
 need(parse(replace(goodHeaders,"Host: ","Host:\t"))==State::Rejected,"tabs invalid");
 need(parse(replace(goodHeaders,"Host: ","Host:  "))==State::Rejected,"multiple spaces");
 need(parse(replace(goodHeaders,"Host: ","Host: ") .substr(0,1)+"\n"+goodHeaders)==State::Rejected,"LF without CR");
 need(parse(replace(goodHeaders,"Host: ","Host:\rX"))==State::Rejected,"CR not followed by LF");
 need(parse(replace(goodHeaders,"Host: ","Host: ")+"\0") == State::ReadyForAuth,"body not inspected");
 need(parse(replace(goodHeaders,"Host: ","Host: ")+std::string("\0",1))==State::ReadyForAuth,"body may contain zero unread");
 need(parse(replace(goodHeaders,"Host: ","Host: ")+"BODY") == State::ReadyForAuth,"trailing body not read");
 need(parse(replace(goodHeaders,"Host: 192.168.1.70", "Host: "+std::string(330,'a')))==State::Rejected,"line cap");
 need(parse(replace(goodHeaders,"Host: 192.168.1.70", "Host: "+std::string(314,'a')))==State::ReadyForAuth,"line exact 320 boundary");
 need(parse(replace(goodHeaders,"Host: 192.168.1.70", "Host: "+std::string(315,'a')))==State::Rejected,"line 321 boundary");
 need(parse(goodHeaders+std::string(1000,'a'))==State::ReadyForAuth,"no inspect body even if large");
 need(parse(replace(goodHeaders,"X-Shino-Proof: "+std::string(64,'b'),"X-Shino-Proof: "+std::string(64,'b')+"\r\nX-Shino-Proof: "+std::string(64,'b')))==State::Rejected,"duplicate proof");
 need(parse(replace(goodHeaders,"X-Shino-Proof: "+std::string(64,'b'),"X-Shino-Proof: "+std::string(63,'b')+"g"))==State::Rejected,"bad hex");
 need(sizeof(HeaderGuard)<=512,"instance memory bound");
 std::puts("M3Q_HOST_BOUNDED_HEADERS_PASS");
}
