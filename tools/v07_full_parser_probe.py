"""Execute exact pinned _parseRequest text with an explicit host dependency shim.

The shim is deliberately not an ESP8266/TCP/heap emulator. It records parser
decisions before simulated allocation and interruption. Source hashes are
checked by v07_pinned_core_probe before text extraction.
"""
from __future__ import annotations

import json
from pathlib import Path

from v07_cpp_lab_runner import build_and_run
from v07_pinned_core_probe import _between, pinned_sources


PREFIX = r'''
#include <algorithm>
#include <cctype>
#include <cstdint>
#include <cstdlib>
#include <iostream>
#include <string>
#include <vector>
#include <functional>
#define F(x) x
#define FPSTR(x) x
#define DBGWS(...) ((void)0)
#define HTTP_MAX_POST_WAIT 5000
using std::size_t;
static size_t peak_string=0;
class String {
 public:
  std::string s;
  String() = default;
  String(const char* p) : s(p) {}
  String(std::string p) : s(std::move(p)) {}
  const char* c_str() const { return s.c_str(); }
  const char* buffer() const { return s.c_str(); }
  size_t length() const { return s.size(); }
  bool isEmpty() const { return s.empty(); }
  void clear() { s.clear(); }
  int indexOf(char c, size_t start = 0) const { auto p=s.find(c,start); return p==s.npos ? -1 : int(p); }
  String substring(size_t start, size_t end = std::string::npos) const {
    return s.substr(std::min(start,s.size()), end==std::string::npos ? end : end-start);
  }
  void trim() { auto a=s.find_first_not_of(" \t\r\n"), b=s.find_last_not_of(" \t\r\n"); s=a==s.npos ? "" : s.substr(a,b-a+1); }
  bool equalsIgnoreCase(const char* v) const { std::string other(v); if(s.size()!=other.size()) return false;
    for(size_t i=0;i<s.size();++i) if(std::tolower((unsigned char)s[i])!=std::tolower((unsigned char)other[i])) return false; return true; }
  bool startsWith(const char* p) const { return s.rfind(p,0)==0; }
  void replace(const char* from,const char* to) { auto p=s.find(from); if(p!=s.npos) s.replace(p,strlen(from),to); }
  String& operator+=(char c) { s+=c; if(s.size()>peak_string)peak_string=s.size(); return *this; }
  String& operator+=(const String& v) { s+=v.s; return *this; }
  bool operator==(const char* v) const { return s==v; }
  long toInt(void) const;
};
const char Content_Type[] = "Content-Type";
namespace mime { enum {txt=0}; struct Entry { const char* mimeType; }; static Entry mimeTable[]={{"text/plain"}};
  static String getContentType(const String&) { return String("text/plain"); } }
enum HTTPMethod { HTTP_ANY, HTTP_GET, HTTP_HEAD, HTTP_POST, HTTP_PUT, HTTP_PATCH, HTTP_DELETE, HTTP_OPTIONS };
enum { CLIENT_REQUEST_CAN_CONTINUE=0, CLIENT_REQUEST_IS_HANDLED=1, CLIENT_MUST_STOP=2, CLIENT_IS_GIVEN=3 };
struct Stream { std::string input; size_t at=0; int timedRead(){return at<input.size()? (unsigned char)input[at++] : -1;}
  String readStringUntil(char terminator); };
struct S2Stream { String& output; explicit S2Stream(String& s):output(s){} };
struct FakeClient:Stream {
  size_t requested=0; int timeout=0; bool short_read=false;
  size_t sendSize(S2Stream& dest,size_t n,int t){requested=n;timeout=t;
    size_t available=input.size()-at; size_t count=std::min(n,available);
    if(short_read && count) --count;
    dest.output.s.assign(input.data()+at,count); at+=count; return count;}
  void flush() {}
};
struct FakeServer { using ClientType=FakeClient; };
struct RequestArgument { String key,value; };
struct Header { String key,value; };
struct Handler { Handler* next(){return nullptr;} bool canHandle(HTTPMethod,const String&){return false;} };
namespace esp8266webserver {
template<typename ServerType> class ESP8266WebServerTemplate {
 public:
  using ClientType=typename ServerType::ClientType;
  using ClientFuture=int;
  using RequestHandlerType=Handler;
  int _headerKeysCount=2, _currentVersion=0, _currentArgCount=0;
  Header _currentHeaders[2]={{"Content-Length",""},{"Authorization",""}};
  String _currentUri,_hostHeader; bool _chunked=false,_keepAlive=false,_currentArgsHavePlain=false;
  HTTPMethod _currentMethod=HTTP_GET;
  Handler* _firstHandler=nullptr; Handler* _currentHandler=nullptr;
  RequestArgument _args[1]; RequestArgument* _currentArgs=_args;
  std::function<int(const String&,const String&,ClientType*,String(*)(const String&))> _hook;
  ClientFuture _parseRequest(ClientType&);
  bool _collectHeader(const char*,const char*);
  void _parseArguments(const String&) { _currentArgCount=0; }
  bool _parseForm(ClientType&,const String&,uint32_t) { return false; }
};
'''

SUFFIX = r'''
}
static int failed=0,checks=0;
static void check(bool condition,const char* label){++checks;if(!condition){++failed;std::cerr<<"FAIL "<<label<<"\n";}}
static std::string request(std::string length,std::string extra="",std::string body="x"){
  return "POST /api/v2/bridge/media HTTP/1.1\r\nHost: unit.invalid\r\nContent-Length: "+length+
    "\r\nAuthorization: Basic bogus\r\n"+extra+"\r\n"+body;
}
int main(){
  using esp8266webserver::ESP8266WebServerTemplate;
  using Server=ESP8266WebServerTemplate<FakeServer>;
  auto run=[](std::string text,bool partial=false,bool deny=false){
    Server s; FakeClient c; c.input=std::move(text); c.short_read=partial;
    if(deny) s._hook=[](const String&,const String&,FakeClient*,String(*)(const String&)){return CLIENT_MUST_STOP;};
    int result=s._parseRequest(c);return std::pair<int,size_t>(result,c.requested);
  };
  check(run(request("1")).second==1,"ordinary body read");
  check(run(request("1","Content-Length: 50000\r\n")).second==50000,"duplicate last length wins");
  check(run(request("-1")).second==uint32_t(-1),"negative wraps request size");
  check(run(request("1000000")).second==1000000,"million byte request");
  check(run(request("1","Transfer-Encoding: chunked\r\n")).second==1,"transfer encoding ignored");
  check(run(request("1","", ""),true).first==CLIENT_MUST_STOP,"partial read stops");
  check(run(request("1000000"),false,true).second==0,"hook before body read");
  std::string huge(5000,'x'); huge+="\r\n\r\n";
  check(run(huge).second==0,"oversized line processed without body");
  check(peak_string>=5000,"request line accumulated 5000 bytes");
  std::string large_header(5000,'y');
  run(request("1","X-Long: "+large_header+"\r\n"));
  check(peak_string>=5008,"header line accumulated beyond 5000 bytes");
  Server duplicate; FakeClient dc; dc.input=request("1","Authorization: Basic second\r\n");
  duplicate._parseRequest(dc);
  check(duplicate._currentHeaders[1].value.s=="Basic second","duplicate authorization overwrites collected value");
  std::cout<<"{\"exact_parser_checks\":"<<checks<<",\"failed\":"<<failed
    <<",\"max_read_string_bytes\":"<<peak_string<<"}\n";
  return failed?1:0;
}
'''


def harness() -> str:
    sources = pinned_sources()
    parser = sources["libraries/ESP8266WebServer/src/Parsing-impl.h"]
    stream = sources["stream"]
    wstring = sources["cores/esp8266/WString.cpp"]
    helper = _between(parser, "template <typename ServerType>\nstatic bool readBytesWithTimeout", "template <typename ServerType>\ntypename ESP8266WebServerTemplate")
    request = _between(parser, "template <typename ServerType>\ntypename ESP8266WebServerTemplate", "template <typename ServerType>\nbool ESP8266WebServerTemplate")
    collect = _between(parser, "template <typename ServerType>\nbool ESP8266WebServerTemplate<ServerType>::_collectHeader", "template <typename ServerType>\nstruct storeArgHandler")
    read_until = _between(stream, "String Stream::readStringUntil(char terminator) {", "// read what can be read")
    to_int = _between(wstring, "long String::toInt(void) const {", "float String::toFloat")
    # The following prefix contains the only shim types; the functions remain byte-for-byte extracted.
    prefix = PREFIX.replace("#include <algorithm>", "#include <algorithm>\n#include <cstring>")
    prefix = prefix.replace("namespace esp8266webserver {\n", to_int + read_until + "namespace esp8266webserver {\n")
    return prefix + helper + request + collect + SUFFIX


if __name__ == "__main__":
    print(json.dumps(build_and_run(Path("v07_exact_parser.cpp"), generated=harness()), indent=2))
