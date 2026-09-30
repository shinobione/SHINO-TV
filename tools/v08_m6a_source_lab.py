"""Execute stock, historical and corrected generated owner/classifier source.

Fake clients establish source decisions only. The socket runner supplies real
timed reads and actual parser/auth/response/bridge composition separately.
"""
from pathlib import Path
import json

import v08_source_executed_preparse as old_lab
import v08_native_overlay as old
import v08_m6a_overlay as new
from v07_pinned_core_probe import _between, pinned_sources
from v07_cpp_lab_runner import build_and_run

SUFFIX = r'''
}
static int checks=0, failures=0;
static void check(bool ok,const char* name){++checks;if(!ok){++failures;std::cerr<<"FAIL "<<name<<"\n";}}
int main(){
 using Server=esp8266webserver::ESP8266WebServerTemplate<FakeServer>;
 {
  Server s;FakeClient slow,ready;ready.input="GET / HTTP/1.1\r\n\r\n";
  s._server.queue={slow,ready};fake_ms=0;s.handleClient();fake_ms=30;s.handleClient();
  check(s._currentStatus==HC_WAIT_READ,"grace inclusive30");fake_ms=31;s.handleClient();
  check((LAB_STOCK || LAB_CORRECTED)?s._currentStatus==HC_NONE:s._currentStatus==HC_WAIT_READ,"contention at31");
  if(!LAB_STOCK && !LAB_CORRECTED){fake_ms=2000;s.handleClient();}
  s.handleClient();check(s.handled==1 && s._server.next==2,"next owner dispatch");
 }
 {
  Server s;FakeClient slow;s._server.queue.push_back(slow);
  for(int i=0;i<5;i++)s._server.queue.push_back(FakeClient());
  fake_ms=0;s.handleClient();fake_ms=31;s.handleClient();
  check((LAB_STOCK || LAB_CORRECTED)?s._currentStatus==HC_NONE:s._currentStatus==HC_WAIT_READ,"full queue at31");
 }
#if !LAB_STOCK
 for(const char* target:{"/?x=100%","/?x=%GG","/?x=%2","/?x=%00%ff","/?q=/api/v2/bridge/media","/api/v2/bridge/mediax","/other/api/v2/bridge/media"}){
  Server s;FakeClient c;c.input=std::string("GET ")+target+" HTTP/1.1\r\n";fake_ms=0;s._v08Started=0;
  auto r=s._v08ReadFirstLine(c);if(r==Server::V08_LINE_PENDING)r=s._v08ReadFirstLine(c);
  check(LAB_CORRECTED?r==Server::V08_LINE_LEGACY:r!=Server::V08_LINE_LEGACY,"R6 legacy differential");
 }
 for(const char* target:{"/api/v2/bridge/media","/api/v2/bridge/media/begin/x","/api/v2/bridge/%6dedia","/api%2fv2%2fbridge%2fmedia","/api/v2/bridge/media%","/api/v2/bridge/media%GG","/api/v2/bridge/%256dedia","/api//v2/bridge/media","/api/v2/bridge/./media","/api/v2/bridge/media;begin=x","/api/v2/bridge/media%20begin"}){
  Server s;FakeClient c;c.input=std::string("POST ")+target+" HTTP/1.1\r\nContent-Length: 9\r\n\r\nuntouched";fake_ms=0;s._v08Started=0;
  auto r=s._v08ReadFirstLine(c);if(r==Server::V08_LINE_PENDING)r=s._v08ReadFirstLine(c);
  if(LAB_CORRECTED)check(r==Server::V08_LINE_MEDIA || r==Server::V08_LINE_REJECT,"R6 alias terminal");
  check(c.input.substr(c.at).rfind("Content-Length:",0)==0,"headers/body unread");
 }
 for(size_t n:{130u,131u}){
  Server s;FakeClient c;c.input="GET /"+std::string(n-16,'x')+" HTTP/1.1\r\n";fake_ms=0;s._v08Started=0;
  auto r=Server::V08_LINE_PENDING;while(r==Server::V08_LINE_PENDING){auto before=c.at;r=s._v08ReadFirstLine(c);check(c.at-before<=64,"64 read slice");}
  check(n==130?r==Server::V08_LINE_LEGACY:r==Server::V08_LINE_REJECT,"wire130/131 cap");
 }
 {
  Server s;FakeClient c;c.input="GET /";s._v08Started=UINT32_MAX-1000u;fake_ms=998;
  check(s._v08ReadFirstLine(c)==Server::V08_LINE_PENDING,"absolute wrap1999");fake_ms=999;
  check(s._v08ReadFirstLine(c)==Server::V08_LINE_REJECT,"absolute wrap2000");
 }
#endif
#if LAB_CORRECTED
 {
  Server s;FakeClient c;c.input="GET / HTTP/1.1\r\n";s._v08Started=0;fake_ms=1999;read_tick_step=1;
  check(s._v08ReadFirstLine(c)==Server::V08_LINE_REJECT && c.at==1,"deadline crosses inside read slice");read_tick_step=0;
 }
 {
  Server s;FakeClient slow,ready;slow.input="GET /";ready.input="GET / HTTP/1.1\r\n\r\n";
  s._server.queue={slow,ready};fake_ms=UINT32_MAX-10u;s.handleClient();fake_ms=19;s.handleClient();
  check(s._currentStatus==HC_WAIT_READ,"partial wrap30");fake_ms=20;s.handleClient();
  check(s._currentStatus==HC_NONE,"partial wrap31");
 }
 {
  Server s;FakeClient c;c.input="GET /";s._server.queue={c};fake_ms=0;s.handleClient();
  s._currentClient.live=false;s.handleClient();check(s._currentStatus==HC_NONE && s.handled==0,"partial FIN no dispatch");
 }
#endif
 std::cout<<"{\"checks\":"<<checks<<",\"failed\":"<<failures<<"}\n";return failures?1:0;
}
'''


def source(variant: str) -> str:
    text = old_lab.harness()
    text = old.once(text, old_lab.SUFFIX, SUFFIX, 'source test body')
    text = text.replace('#define HTTP_MAX_DATA_AVAILABLE_WAIT 1000',
                        '#define HTTP_MAX_DATA_AVAILABLE_WAIT 30')
    text = text.replace('#define HTTP_MAX_CLOSE_WAIT 1000', '#define HTTP_MAX_CLOSE_WAIT 2000')
    text = text.replace('static uint32_t fake_ms=0;',
                        'static uint32_t fake_ms=0, read_tick_step=0;')
    text = text.replace('int read() { return at<input.size()',
                        'int read() { fake_ms+=read_tick_step; return at<input.size()')
    text = text.replace('bool hasMaxPendingClients() const { return false; }',
                        'bool hasMaxPendingClients() const { return queue.size()-next>=5; }')
    old.materialize(); new.materialize()
    previous = (old.OUTPUT/'ESP8266WebServer-impl.h').read_text(encoding='utf-8')
    marker = 'template <typename ServerType>\nvoid ESP8266WebServerTemplate<ServerType>::handleClient()'
    finish = 'template <typename ServerType>\nvoid ESP8266WebServerTemplate<ServerType>::close()'
    if variant == 'corrected':
        candidate = (new.OUTPUT/'ESP8266WebServer-impl.h').read_text(encoding='utf-8')
        text = old.once(text, old.METHODS, new.METHODS, 'source reader')
        text = old.once(text, _between(previous,marker,finish), _between(candidate,marker,finish), 'source owner')
    elif variant == 'stock':
        pinned = pinned_sources()
        text = old.once(text, _between(previous,marker,finish),
                        _between(pinned['libraries/ESP8266WebServer/src/ESP8266WebServer-impl.h'],marker,finish), 'stock owner')
        text = text.replace('ClientFuture _parseRequest(ClientType&,const char*);',
                            'ClientFuture _parseRequest(ClientType&);')
        text = text.replace('#define SHINO_V08_PREPARSE_EXPERIMENT 1', '')
    return f'#define LAB_STOCK {int(variant=="stock")}\n#define LAB_CORRECTED {int(variant=="corrected")}\n' + text


def run():
    return {variant: build_and_run(Path(f'v08_m6a_{variant}.cpp'), generated=source(variant))
            for variant in ('stock','previous','corrected')}


if __name__ == '__main__':
    print(json.dumps(run(),indent=2))
