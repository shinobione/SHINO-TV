"""Execute pinned authenticate() Basic branch; Digest/encoder dependencies are seams.

This characterizes existing fallback, not media authorization or constant time.
"""
from pathlib import Path
import json
from v07_cpp_lab_runner import build_and_run
from v07_pinned_core_probe import pinned_sources, _between

PREFIX = r'''
#include <string>
#include <cstring>
#include <iostream>
#include <algorithm>
#define F(x) x
#define FPSTR(x) x
struct String:std::string {
 using std::string::string;using std::string::operator=;
 String(std::string s):std::string(std::move(s)){}
 int indexOf(const String& s,size_t at=0)const{auto p=find(s,at);return p==npos?-1:int(p);}
 int indexOf(char c,size_t at=0)const{auto p=find(c,at);return p==npos?-1:int(p);}
 String substring(size_t a,size_t b=npos)const{return substr(a,b==npos?b:b-a);}
 void trim(){auto a=find_first_not_of(" \t\r\n"),b=find_last_not_of(" \t\r\n");assign(a==npos?"":substr(a,b-a+1));}
 bool startsWith(const char* p)const{return rfind(p,0)==0;}
 void concat(const char* p,size_t n){append(p,n);}
 bool equalsConstantTime(const String& s)const{return *this==s;}// semantics only
};
const String emptyString;
const char AUTHORIZATION_HEADER[]="Authorization";
namespace base64 { String encode(const String& raw,bool){
 static const char table[]="ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz0123456789+/";
 String out;unsigned bits=0;int n=0;for(unsigned char c:raw){bits=(bits<<8)|c;n+=8;while(n>=6){n-=6;out+=table[(bits>>n)&63];}}
 if(n)out+=table[(bits<<(6-n))&63];while(out.size()%4)out+='=';return out;
} }
template<class ServerType>class ESP8266WebServerTemplate {
public:
 String authorization;
 bool hasHeader(const char*){return !authorization.empty();}
 String header(const char*){return authorization;}
 String _extractParam(String&,const String&,char='"')const;
 bool authenticate(const char*,const char*);
 String credentialHash(const char*,const String&,const char*){return "DIGEST_NOT_EXECUTED";}
 bool authenticateDigest(const char*,const String&){return false;}
};
'''
SUFFIX = r'''
int main(){ESP8266WebServerTemplate<int> s;int checks=0,failed=0;
 auto check=[&](bool b){checks++;if(!b)failed++;};
 check(!s.authenticate("lab","public-fixture"));
 s.authorization="Basic bGFiOnB1YmxpYy1maXh0dXJl";check(s.authenticate("lab","public-fixture"));
 check(!s.authenticate("lab","different-public-fixture"));
 s.authorization="Bearer public";check(!s.authenticate("lab","public-fixture"));
 // Existing core accepts a six-character prefix beginning Basic. Evidence kept.
 s.authorization="Basic!bGFiOnB1YmxpYy1maXh0dXJl";check(s.authenticate("lab","public-fixture"));
 std::cout<<"{\"pinned_basic_branch_checks\":"<<checks<<",\"failed\":"<<failed<<",\"digest_executed\":false}\n";return failed?1:0;
}
'''
if __name__ == "__main__":
    source = pinned_sources()["libraries/ESP8266WebServer/src/ESP8266WebServer-impl.h"]
    code = _between(source,"template <typename ServerType>\nString ESP8266WebServerTemplate<ServerType>::_extractParam",
        "template <typename ServerType>\nbool ESP8266WebServerTemplate<ServerType>::authenticateDigest")
    print(json.dumps(build_and_run(Path("v08_m3_basic.cpp"),generated=PREFIX+code+SUFFIX),indent=2))
