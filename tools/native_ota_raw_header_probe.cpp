// SPDX-License-Identifier: GPL-3.0-or-later
// Host-only raw HTTP parser adversarial scenarios, no socket/Digest/OTA writer.
#include "boot/NativeOtaRawHeaderGate.h"
#include <cstdint>
#include <iostream>
#include <string>
#include <vector>
using ShinoNativeOta::RawOtaHeaderGate;
using ShinoNativeOta::RawOtaHeaderResult;
using ShinoNativeOta::RawOtaRequestKind;
#define CHECK(x) do {if(!(x)){std::cerr<<"FAIL line "<<__LINE__<<" "<<#x<<"\n";return 1;}}while(0)
const std::string TOKEN="0123456789abcdef0123456789abcdef";
std::string req(bool upload, std::string extra="", std::string auth="Authorization: Digest username=\"tester\", nonce=\"example\"\r\n") {
    return std::string("POST /api/v1/bridge/ota/")+(upload?"upload":"arm")+" HTTP/1.1\r\n"+
        "Host: 192.168.4.1\r\nOrigin: http://192.168.4.1\r\n"+
        "Content-Type: "+(upload?std::string("application/octet-stream"):std::string("application/json"))+"\r\n"+
        "Content-Length: "+(upload?std::string("494404"):std::string("100"))+"\r\n"+
        auth+(upload?"X-Shino-Intent: "+TOKEN+"\r\n":"")+extra+"\r\n";
}
bool check(const std::string& s,RawOtaHeaderResult& o) {
    return RawOtaHeaderGate::inspect(s.data(),s.size(),o);
}
bool rejects(std::string s) {RawOtaHeaderResult o{};return !check(s,o);}
int main() {
    RawOtaHeaderResult r{};
    {
        auto s=req(false);
        CHECK(check(s,r));
        CHECK(r.kind==RawOtaRequestKind::Arm);
        CHECK(r.contentLength==100u && r.digestHeaderPresent && !r.intentTokenPresent);
        CHECK(!r.readCookiePresent);
    }
    {
        auto s=req(true,"Cookie: SHINO_READ_SESSION=abc\r\nSec-Fetch-Site: same-origin\r\n");
        CHECK(check(s,r));
        CHECK(r.kind==RawOtaRequestKind::SignedTransport && r.contentLength==494404u);
        CHECK(r.readCookiePresent && r.intentTokenPresent && TOKEN==r.intentToken);
    }
    CHECK(rejects(req(true,"", ""))); // GET-only cookie does not grant Digest auth.
    CHECK(rejects(req(false,"", "")));
    CHECK(rejects(req(true,"Authorization: Digest forged\r\n"))); // duplicate auth
    CHECK(rejects(req(false,"host: evil.invalid\r\n")));
    CHECK(rejects(req(false,"HOST: 192.168.4.1\r\n")));
    CHECK(rejects(req(true,"Content-Length: 494404\r\n")));
    CHECK(rejects(req(true,"cOntent-TypE: application/octet-stream\r\n")));
    CHECK(rejects(req(true,"Origin: http://192.168.4.1\r\n")));
    CHECK(rejects(req(true,"X-Shino-Intent: "+TOKEN+"\r\n")));
    for(const auto& header : {"Transfer-Encoding: chunked\r\n","Expect: 100-continue\r\n",
        "Content-Encoding: gzip\r\n","Upgrade: websocket\r\n",
        "Proxy-Connection: keep-alive\r\n","Trailer: X-Checksum\r\n"}) {
        CHECK(rejects(req(true,header)));
    }
    CHECK(rejects(req(true,"Sec-Fetch-Site: cross-site\r\n")));
    CHECK(rejects(req(true,"Sec-Fetch-Site: none\r\n")));
    CHECK(rejects(req(true,"Origin: null\r\n")));
    CHECK(rejects(req(true,"Bad_Name: value\r\n")));
    CHECK(rejects(req(true,"Continuation\r\n")));
    CHECK(rejects(req(true,"X-Obs: start\r\n next\r\n"))); // obs-fold
    CHECK(rejects(req(true,"X-Obs: hi\tthere\r\n")));
    CHECK(rejects(req(true,"X-Obs: hello\nworld\r\n")));
    CHECK(rejects(req(true,"X-Obs: hello\rworld\r\n")));
    CHECK(rejects(req(true,"X-Obs: x: y\r\n\r\n"))); // duplicated end-of-headers
    for(const auto& host : {"192.168.4.1:80","192.168.4.1.evil","127.0.0.1","192.168.4.2"}) {
        std::string s=req(true);s.replace(s.find("Host: 192.168.4.1"),17,std::string("Host: ")+host);
        CHECK(rejects(s));
    }
    for(const auto& origin : {"https://192.168.4.1","http://evil.com","null","http://192.168.4.1:80"}) {
        std::string s=req(true);s.replace(s.find("Origin: http://192.168.4.1"),27,std::string("Origin: ")+origin);
        CHECK(rejects(s));
    }
    {
        auto s=req(true);s.replace(s.find("Content-Length: 494404"),22,"Content-Length: +494404");
        CHECK(rejects(s));
    }
    for (const auto& v: {"000494404","0","494405","4294967295","1000000000000000","4x404"}) {
        auto s=req(true);
        s.replace(s.find("Content-Length: 494404"),22,std::string("Content-Length: ")+v);
        CHECK(rejects(s));
    }
    for(const auto& badType : {"multipart/form-data","application/octet-stream; charset=utf-8","text/plain"}) {
        auto s=req(true);s.replace(s.find("Content-Type: application/octet-stream"),38,std::string("Content-Type: ")+badType);
        CHECK(rejects(s));
    }
    {
        auto s=req(true);s.replace(s.find("X-Shino-Intent: "+TOKEN),std::string("X-Shino-Intent: ").size()+TOKEN.size(),
                                "X-Shino-Intent: 00000000000000000000000000000000");
        CHECK(rejects(s));
    }
    {
        auto s=req(true);s.replace(s.find(TOKEN),TOKEN.size(),"0123456789ABCDEF0123456789ABCDEF");
        CHECK(rejects(s));
    }
    {
        auto s=req(true);s.replace(s.find("X-Shino-Intent: "+TOKEN),std::string("X-Shino-Intent: ").size()+TOKEN.size(),
                                "X-Shino-Intent: missing");
        CHECK(rejects(s));
    }
    CHECK(rejects(req(false,"X-Shino-Intent: "+TOKEN+"\r\n")));
    {
        auto s=req(true);s.replace(s.find("/upload"),7,"/upload?x=1");
        CHECK(rejects(s));
    }
    {
        auto s=req(true);s+="X-Sneaky: extra\r\n";
        CHECK(rejects(s)); // No body or pipelined requests in header preflight.
    }
    {
        auto s=req(true);s+="X";CHECK(rejects(s));
        s=req(true);s[1]='\0';CHECK(rejects(s));
        s=req(true);s.pop_back();CHECK(rejects(s));
    }
    {
        auto s=req(true);
        s.insert(s.size()-2u,std::string(2050u,'x'));
        CHECK(rejects(s));
    }
    {
        auto s=req(true);
        for(int i=0;i<26;++i)s.insert(s.size()-2u,"X-Header"+std::to_string(i)+": v\r\n");
        CHECK(rejects(s));
    }
    {
        auto s=req(true,"Authorization: Basic dGVzdDp0ZXN0\r\n");
        CHECK(rejects(s)); // duplicate Authorization
        s=req(true,"","Authorization: Basic dGVzdDp0ZXN0\r\n");
        CHECK(rejects(s));
    }
    {
        auto s=req(true);
        const std::string needle="Authorization: Digest username=\"tester\", nonce=\"example\"";
        const auto start=s.find(needle);
        s.replace(start,needle.size(),std::string("Authorization: Digest ")+std::string(670u,'x'));
        CHECK(rejects(s));
    }
    CHECK(!RawOtaHeaderGate::inspect(nullptr,0u,r));
    std::cout<<"PASS: bounded raw header parser rejects duplicate/ambiguous framing, cross-origin, "
                "cookie-only and malformed signed transport; NO DIGEST PROOF/HTTP SOCKET/FLASH.\n";
    return 0;
}
