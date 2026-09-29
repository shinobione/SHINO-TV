"""Additional Mission 3 tests of the actual generated pinned owner/parser path.

Mission 2's 37 checks are kept intact and rerun before these additional checks.
Dispatch is still a fake route sink; bridge handlers execute in a separate lab.
"""
from pathlib import Path
import json
from v07_cpp_lab_runner import build_and_run
from v08_source_executed_preparse import harness

EXTRA = r'''
  {
    for(const char* uri:{"/", "/ui.js", "/api/v1/bridge/metrics", "/api/v1/bridge/status",
      "/api/v1/bridge/fs-plan", "/api/v1/bridge/ota/capabilities", "/api/v1/bridge/factory-return"}){
      Server s; FakeClient c;
      c.input=std::string("GET ")+uri+" HTTP/1.1\r\nHost: unit.invalid\r\nCookie: SHINO_READ_SESSION=x\r\n\r\n";
      s._v08Started=fake_ms;
      check(s._v08ReadFirstLine(c)==Server::V08_LINE_LEGACY,"actual bridge route line accepted");
      const size_t at=c.at;
      check(c.input.substr(at).rfind("Host:",0)==0,"unread headers preserved at handoff");
      check(s._parseRequest(c,s._v08FirstLine)==CLIENT_REQUEST_CAN_CONTINUE && s._currentUri.s==uri,"exact bridge route URI parsed");
      check(c.at==c.input.size(),"no duplicated/lost header consumption");
    }
  }
  {
    Server s; FakeClient c;
    c.input="GET /"+std::string(114,'x')+" HTTP/1.1\r\nHost: unit.invalid\r\n\r\n";
    s._v08Started=fake_ms;
    check(s._v08ReadFirstLine(c)==Server::V08_LINE_PENDING,"130-byte slice one");
    check(s._v08ReadFirstLine(c)==Server::V08_LINE_PENDING,"130-byte slice two");
    check(s._v08ReadFirstLine(c)==Server::V08_LINE_LEGACY && c.at==130,"130-byte exact wire cap accepted");
    check(c.input.substr(c.at).rfind("Host:",0)==0,"cap boundary preserves headers");
    Server other; FakeClient d; d.input="GET /"+std::string(115,'x')+" HTTP/1.1\r\n";
    other._v08Started=fake_ms;other._v08ReadFirstLine(d);other._v08ReadFirstLine(d);
    check(other._v08ReadFirstLine(d)==Server::V08_LINE_REJECT,"131-byte line rejects before generic parser");
  }
  {
    for(const char* uri:{"/api/v2/bridge/media", "/api/v2/bridge/media/begin/abc", "/api/v2/bridge/mediax",
       "/api/v2/bridge/%6dedia/commit/abc", "/?x=/api/v2/bridge/media"}){
      Server s; FakeClient c;c.input=std::string("GET ")+uri+" HTTP/1.1\r\nContent-Length: 999999\r\n\r\nbody";
      s._v08Started=fake_ms;auto result=s._v08ReadFirstLine(c);
      if(result==Server::V08_LINE_PENDING)result=s._v08ReadFirstLine(c);
      check(result==Server::V08_LINE_MEDIA,"namespace candidates including conservative over-reservation denied");
      check(c.input.substr(c.at).rfind("Content-Length:",0)==0,"media headers/body never read");
    }
  }
  {
    Server s;FakeClient c;c.input="POST /api/v1/bridge/metrics HTTP/1.1\r\nContent-Length: 3\r\nContent-Type: application/json\r\nAuthorization: Basic public\r\n\r\n{}";
    s._v08Started=fake_ms;s._v08ReadFirstLine(c);
    check(s._parseRequest(c,s._v08FirstLine)==CLIENT_MUST_STOP,"partial legacy body uses stock cleanup decision");
    check(c.requested==3,"stock body request unchanged before handler auth");
  }
  {
    Server s;FakeClient c;c.input="POST /api/v1/bridge/metrics HTTP/1.1\r\nContent-Length: 2\r\nContent-Type: application/json\r\nAuthorization: Basic first\r\nAuthorization: Basic second\r\n\r\n{}GET / HTTP/1.1\r\nHost: unit.invalid\r\n\r\n";
    s._v08Started=fake_ms;s._v08ReadFirstLine(c);
    check(s._parseRequest(c,s._v08FirstLine)==CLIENT_REQUEST_CAN_CONTINUE,"legacy POST parsed");
    check(s._currentHeaders[1].value.s=="Basic second","historical duplicate Authorization last wins retained");
    check(c.input.substr(c.at).rfind("GET /",0)==0,"body exact boundary preserves pipeline");
    s._v08FirstLength=0;s._v08Started=fake_ms;
    check(s._v08ReadFirstLine(c)==Server::V08_LINE_LEGACY,"pipeline GET handed off once");
  }
  {
    Server s;FakeClient partial,ready;partial.input="GET /";ready.input="GET /ui.js HTTP/1.1\r\nHost: unit.invalid\r\n\r\n";
    s._server.queue.push_back(partial);s._server.queue.push_back(ready);s.handleClient();
    fake_ms=1000;s._currentClient.input+="ui";s.handleClient();
    check(s._server.next==1 && s.handled==0,"progress does not admit competing owner");
    fake_ms=1999;s._currentClient.input+=".j";s.handleClient();
    fake_ms=2000;s.handleClient();check(s._currentStatus==HC_NONE,"progress cannot extend absolute first-line deadline");
    fake_ms=2001;s.handleClient();check(s.handled==1 && s.lastUri.s=="/ui.js","next owner after terminal cleanup");fake_ms=0;
  }
  {
    Server s;FakeClient c;c.input="GET / HTTP/1.0\r\nHost: unit.invalid\r\n\r\n";s._server.queue.push_back(c);s.handleClient();
    check(s.handled==1 && !s._keepAlive,"HTTP/1.0 legacy close boundary");
  }
'''

if __name__ == "__main__":
    source = harness()
    anchor = '  std::cout << "{\\"source_executed_checks\\":"'
    assert source.count(anchor) == 1
    source = source.replace(anchor, EXTRA + anchor)
    print(json.dumps(build_and_run(Path("v08_m3_exact_parser.cpp"),generated=source),indent=2))
