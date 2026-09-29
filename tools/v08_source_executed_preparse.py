"""Execute the generated pinned-core preparse and parser text with host socket shims.

This executes the exact transformed C++ methods; the fake client is not TCP,
ESP8266 heap, scheduling or watchdog evidence. It never contacts a device.
"""
from __future__ import annotations

import json
from pathlib import Path

from v07_cpp_lab_runner import build_and_run
from v07_full_parser_probe import PREFIX
from v07_pinned_core_probe import _between, pinned_sources
from v08_native_overlay import OUTPUT, materialize


SUFFIX = r'''
}
static int checks=0, failures=0;
static void check(bool ok, const char* name) {
  ++checks; if(!ok) { ++failures; std::cerr << "FAIL " << name << "\n"; }
}
int main() {
  using Server=esp8266webserver::ESP8266WebServerTemplate<FakeServer>;
  auto line=[](Server& s, FakeClient& c, std::string request) {
    c.input=std::move(request); s._v08Started=fake_ms;
    return s._v08ReadFirstLine(c);
  };
  {
    Server s; FakeClient c;
    c.input="GET /api/metrics HTTP/1.1\r\nHost: test\r\n\r\n";
    s._v08Started=fake_ms;
    check(s._v08ReadFirstLine(c)==Server::V08_LINE_LEGACY,"metrics line accepted");
    check(c.at==27,"first line only consumed");
    check(s._parseRequest(c,s._v08FirstLine)==CLIENT_REQUEST_CAN_CONTINUE,"legacy parser handoff");
    check(s._currentUri.s=="/api/metrics","exact legacy URI");
  }
  {
    Server s; FakeClient c;
    c.input="GET / HTTP/1.1\r\nHost: test\r\n\r\n";
    s._v08Started=fake_ms;
    check(s._v08ReadFirstLine(c)==Server::V08_LINE_LEGACY,"dashboard line accepted");
    check(s._parseRequest(c,s._v08FirstLine)==CLIENT_REQUEST_CAN_CONTINUE,"dashboard parser path");
    check(s._currentUri.s=="/","dashboard URI");
  }
  {
    Server s; FakeClient c;
    c.input="POST /api/v2/bridge/media/begin/123 HTTP/1.1\r\nContent-Length: 500000\r\n\r\nsecret";
    s._v08Started=fake_ms;
    check(s._v08ReadFirstLine(c)==Server::V08_LINE_MEDIA,"media terminal classification");
    check(c.at==std::string("POST /api/v2/bridge/media/begin/123 HTTP/1.1\r\n").size(),"media headers and body unread");
  }
  {
    Server s; FakeClient c;
    check(line(s,c,"POST /api/v2/bridge/%6dedia/begin/123 HTTP/1.1\r\n")==Server::V08_LINE_MEDIA,"encoded media namespace reserved");
    Server other; FakeClient d;
    check(line(other,d,"GET /api/%2 HTTP/1.1\r\n")==Server::V08_LINE_REJECT,"malformed escape terminal");
  }
  {
    Server s; FakeClient c; c.input="GET /api/"; s._v08Started=fake_ms;
    check(s._v08ReadFirstLine(c)==Server::V08_LINE_PENDING,"partial line pending");
    c.input+="metrics HTTP/1.1\r\nHost: test\r\n\r\n";
    check(s._v08ReadFirstLine(c)==Server::V08_LINE_LEGACY,"partial line completed");
    check(s._parseRequest(c,s._v08FirstLine)==CLIENT_REQUEST_CAN_CONTINUE,"partial parser handoff");
  }
  {
    Server s; FakeClient c; c.input="GET /api/"; s._v08Started=UINT32_MAX-1000u;
    fake_ms=998u;
    check(s._v08ReadFirstLine(c)==Server::V08_LINE_PENDING,"wrap before absolute deadline");
    fake_ms=999u;
    check(s._v08ReadFirstLine(c)==Server::V08_LINE_REJECT,"wrap absolute deadline");
    fake_ms=0;
  }
  {
    Server s; FakeClient c; c.input=std::string(131,'x')+"\r\n"; s._v08Started=fake_ms;
    check(s._v08ReadFirstLine(c)==Server::V08_LINE_PENDING,"long line first slice");
    check(s._v08ReadFirstLine(c)==Server::V08_LINE_PENDING,"long line second slice");
    check(s._v08ReadFirstLine(c)==Server::V08_LINE_REJECT,"request line cap");
    check(c.at<=131,"bounded bytes consumed");
  }
  {
    Server s; FakeClient c;
    check(line(s,c,"GET /api/metrics HTTP/1.1\n")==Server::V08_LINE_REJECT,"LF-only rejected");
    Server other; FakeClient d;
    check(line(other,d,"GET /api/metrics HTTP/1.1\rX")==Server::V08_LINE_REJECT,"bad CR rejected");
  }
  {
    Server s; FakeClient c; c.input="GET /api/"; s._v08Started=fake_ms; c.live=false;
    check(s._v08ReadFirstLine(c)==Server::V08_LINE_REJECT,"partial FIN cleanup");
  }
  {
    Server s; FakeClient c;
    c.input="GET /api/metrics HTTP/1.1\r\nHost: test\r\n\r\nGET / HTTP/1.1\r\nHost: test\r\n\r\n";
    s._v08Started=fake_ms;
    check(s._v08ReadFirstLine(c)==Server::V08_LINE_LEGACY,"pipeline first line");
    check(s._parseRequest(c,s._v08FirstLine)==CLIENT_REQUEST_CAN_CONTINUE,"pipeline first parser");
    s._v08FirstLength=0; s._v08Started=fake_ms;
    check(s._v08ReadFirstLine(c)==Server::V08_LINE_LEGACY,"pipeline second line");
    check(s._parseRequest(c,s._v08FirstLine)==CLIENT_REQUEST_CAN_CONTINUE,"pipeline second parser");
    check(s._currentUri.s=="/","pipeline second URI");
  }
  {
    Server s; FakeClient c; s._currentClient=c;
    s._v08CloseOnce(); s._v08CloseOnce();
    check(s._currentClient.stops==1,"close once helper");
  }
  {
    Server s; FakeClient slow, ready;
    slow.input="GET /api/";
    ready.input="GET /api/metrics HTTP/1.1\r\nHost: test\r\n\r\n";
    s._server.queue.push_back(slow); s._server.queue.push_back(ready);
    s.handleClient();
    check(s._server.next==1 && s._currentStatus==HC_WAIT_READ,"one acceptor retains partial owner");
    s.handleClient();
    check(s._server.next==1,"competing client not accepted");
    fake_ms=2000;
    s.handleClient();
    check(s._currentStatus==HC_NONE,"absolute deadline releases owner");
    fake_ms=0;
    s.handleClient();
    check(s._server.next==2 && s.handled==1,"queued legacy client handled");
    check(s.lastUri.s=="/api/metrics","legacy dispatch URI");
  }
  {
    Server s; FakeClient c;
    c.input="POST /api/v2/bridge/media/begin/123 HTTP/1.1\r\nContent-Length: 500000\r\n\r\nsecret";
    s._server.queue.push_back(c); s.handleClient();
    check(s.handled==0 && s._currentStatus==HC_NONE,"media cannot fall through handler");
  }
  {
    Server s; FakeClient c;
    c.input="GET /api/metrics HTTP/1.1\r\nHost: test\r\n\r\nGET / HTTP/1.1\r\nHost: test\r\n\r\n";
    s._server.queue.push_back(c); s.handleClient();
    check(s.handled==1 && s._currentStatus==HC_WAIT_CLOSE,"keepalive first request");
    fake_ms=3000;
    s.handleClient();
    check(s.handled==2 && s.lastUri.s=="/","pipeline second dispatch");
    fake_ms=0;
  }
  std::cout << "{\"source_executed_checks\":" << checks << ",\"failed\":" << failures << "}\n";
  return failures ? 1 : 0;
}
'''


def harness() -> str:
    pinned = pinned_sources()
    materialize()
    parser = (OUTPUT / "Parsing-impl.h").read_text(encoding="utf-8")
    implementation = (OUTPUT / "ESP8266WebServer-impl.h").read_text(encoding="utf-8")
    helper = _between(parser, "template <typename ServerType>\nstatic bool readBytesWithTimeout", "template <typename ServerType>\ntypename ESP8266WebServerTemplate")
    request = _between(parser, "template <typename ServerType>\ntypename ESP8266WebServerTemplate", "template <typename ServerType>\nbool ESP8266WebServerTemplate")
    collect = _between(parser, "template <typename ServerType>\nbool ESP8266WebServerTemplate<ServerType>::_collectHeader", "template <typename ServerType>\nstruct storeArgHandler")
    preparse = _between(implementation, "#ifdef SHINO_V08_PREPARSE_EXPERIMENT\ntemplate <typename ServerType>\ntypename ESP8266WebServerTemplate<ServerType>::V08LineResult", "#endif\n\ntemplate <typename ServerType>\nvoid ESP8266WebServerTemplate<ServerType>::handleClient()") + "#endif\n"
    stream = _between(pinned["stream"], "String Stream::readStringUntil(char terminator) {", "// read what can be read")
    wstring = _between(pinned["cores/esp8266/WString.cpp"], "long String::toInt(void) const {", "float String::toFloat")
    prefix = PREFIX.replace("#include <algorithm>", "#define SHINO_V08_PREPARSE_EXPERIMENT 1\n#include <algorithm>\n#include <cstring>")
    prefix = prefix.replace("#define HTTP_MAX_POST_WAIT 5000", "#define HTTP_MAX_POST_WAIT 5000\n#define HTTP_MAX_SEND_WAIT 5000\n#define CONTENT_LENGTH_NOT_SET -1\n#define HTTP_MAX_DATA_WAIT 5000\n#define HTTP_MAX_DATA_AVAILABLE_WAIT 1000\n#define HTTP_MAX_CLOSE_WAIT 1000\nstatic uint32_t fake_ms=0;\nstatic uint32_t millis(){return fake_ms;}\nstatic void yield(){}\nenum HTTPClientStatus { HC_NONE, HC_WAIT_READ, HC_WAIT_CLOSE };")
    prefix = prefix.replace("  void flush() {}", "  bool live=true; int stops=0;\n  explicit operator bool() const { return live; }\n  int available() const { return int(input.size()-at); }\n  int read() { return at<input.size() ? (unsigned char)input[at++] : -1; }\n  bool connected() const { return live; }\n  void stop() { ++stops; live=false; }\n  void setTimeout(int timeoutValue) { timeout=timeoutValue; }\n  void flush() {}")
    prefix = prefix.replace("struct FakeServer { using ClientType=FakeClient; };", """struct FakeServer {
  using ClientType=FakeClient;
  std::vector<FakeClient> queue; size_t next=0;
  FakeClient accept() { if(next<queue.size()) return queue[next++]; FakeClient c; c.live=false; return c; }
  bool hasClientData() const { return next<queue.size() && queue[next].available()>0; }
  bool hasMaxPendingClients() const { return false; }
  bool hasClient() const { return next<queue.size(); }
};""")
    prefix = prefix.replace("  ClientFuture _parseRequest(ClientType&);", """  enum V08LineResult { V08_LINE_PENDING, V08_LINE_LEGACY, V08_LINE_MEDIA, V08_LINE_REJECT };
  V08LineResult _v08ReadFirstLine(ClientType&);
  void _v08CloseOnce();
  char _v08FirstLine[131] = {};
  uint16_t _v08FirstLength=0;
  uint32_t _v08Started=0;
  bool _v08Closed=false;
  ClientType _currentClient;
  FakeServer _server;
  HTTPClientStatus _currentStatus=HC_NONE;
  uint32_t _statusChange=0;
  int _contentLength=0, handled=0;
  String lastUri;
  struct Upload { void reset(){} } _currentUpload;
  void _handleRequest(){ ++handled; lastUri=_currentUri; }
  void handleClient();
  ClientFuture _parseRequest(ClientType&,const char*);""")
    prefix = prefix.replace("namespace esp8266webserver {\n", wstring + stream + "namespace esp8266webserver {\n")
    handle = _between(implementation, "template <typename ServerType>\nvoid ESP8266WebServerTemplate<ServerType>::handleClient()", "template <typename ServerType>\nvoid ESP8266WebServerTemplate<ServerType>::close()")
    return prefix + helper + request + collect + preparse + handle + SUFFIX


if __name__ == "__main__":
    print(json.dumps(build_and_run(Path("v08_exact_preparse.cpp"), generated=harness()), indent=2))
