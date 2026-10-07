// Real pinned Core parser/Digest over host loopback; no owner/device transport.
#include <HostSocket.h>
#include <ESP8266WiFi.h>
#include <iostream>
uint32_t host_ms=0;
void yield(){std::this_thread::yield();}
#include "pinned_stream.inc"
#include <ESP8266WebServer.h>
#include "boot/M9NormalHttpPolicy.h"
static ESP8266WebServer server(80);
static unsigned checks=0,handlers=0;
static void check(bool ok,const char* name){++checks;if(!ok){std::cerr<<name<<'\n';std::exit(1);}}
struct Peer {
 Socket fd=INVALID_SOCKET;
 Peer(){fd=socket(AF_INET,SOCK_STREAM,0);sockaddr_in a{};a.sin_family=AF_INET;a.sin_addr.s_addr=htonl(INADDR_LOOPBACK);a.sin_port=htons(server.getServer().port);
 if(connect(fd,reinterpret_cast<sockaddr*>(&a),sizeof a))throw std::runtime_error("loopback connect");}
 void send(const std::string& s){size_t at=0;while(at<s.size()){int n=::send(fd,s.data()+at,int(s.size()-at),0);if(n<=0)throw std::runtime_error("send");at+=n;}}
 std::string receive(){std::string out;for(unsigned i=0;i<30;++i){fd_set set;FD_ZERO(&set);FD_SET(fd,&set);timeval t{0,1000};
 if(select(int(fd)+1,&set,nullptr,nullptr,&t)>0){char b[2048];int n=recv(fd,b,sizeof b,0);if(n<=0)break;out.append(b,n);}}return out;}
 ~Peer(){closeSocket(fd);}
};
static std::string transact(const std::string& text){
 server.client().stop();server.client()=WiFiClient();server.getServer().pending.clear();
 Peer peer;peer.send(text);std::this_thread::sleep_for(std::chrono::milliseconds(3));
 for(unsigned i=0;i<8;++i){server.handleClient();if(!server.client()&&i)break;}return peer.receive();
}
static std::string request(const std::string& path,const std::string& auth="",const std::string& body="",const std::string& extra="",const std::string& method="GET",const std::string& length="") {
 return method+" "+path+" HTTP/1.1\r\nHost: public-fixture\r\nConnection: close\r\n"+auth+extra+
 (method=="POST"?"Content-Type: application/json\r\nContent-Length: "+(length.empty()?std::to_string(body.size()):length)+"\r\n":"")+"\r\n"+body;
}
static std::string parameter(const std::string& s,const std::string& key){auto p=s.find(key+"=\"");if(p==s.npos)return "";p+=key.size()+2;return s.substr(p,s.find('"',p)-p);}
static std::string md5(const String& v){MD5Builder m;m.begin();m.add(v);m.calculate();return m.toString();}
static std::string digest(const std::string& challenge,const std::string& method,const std::string& path){
 const std::string n=parameter(challenge,"nonce"),o=parameter(challenge,"opaque");
 const auto h1=md5("lab:SHINO-StageA:PUBLIC-INERT-LAB-HTTP-FIXTURE"),h2=md5(String(method)+":"+path.c_str());
 const auto proof=md5(String(h1)+":"+n.c_str()+":00000001:test:auth:"+h2.c_str());
 return "Authorization: Digest username=\"lab\", realm=\"SHINO-StageA\", nonce=\""+n+"\", uri=\""+path+"\", response=\""+proof+"\", opaque=\""+o+"\", qop=auth, nc=00000001, cnonce=\"test\"\r\n";
}
static bool status(const std::string& s,unsigned n){return s.find("HTTP/1.1 "+std::to_string(n)+" ")==0;}
int main(){
#ifdef _WIN32
 WSADATA w;WSAStartup(MAKEWORD(2,2),&w);
#endif
 server.collectHeaders("Authorization","Content-Length","Content-Type","Transfer-Encoding");
 server.setStageAPrebody([](){
  server.keepAlive(false);
  if(!server.header("Authorization").startsWith("Digest ") || !server.authenticate("lab","PUBLIC-INERT-LAB-HTTP-FIXTURE")){
   server.requestAuthentication(DIGEST_AUTH,"SHINO-StageA");return false;}
  int result=M9NormalHttpPolicy::classify(server.method()==HTTP_GET,server.method()==HTTP_POST,server.uri().c_str(),
   server.header("Content-Length").c_str(),server.header("Content-Type").c_str(),server.header("Transfer-Encoding").c_str());
  if(result!=200){server.send(result,"application/json","{}");return false;}return true;
 });
 server.on("/status",HTTP_GET,[](){++handlers;server.send(200,"application/json","{}");});
 server.on("/api/v1/bridge/metrics",HTTP_POST,[](){check(server.arg("plain").length()<=384,"bounded actual body");++handlers;server.send(200,"application/json","{}");});
 server.begin();const std::string path="/api/v1/bridge/metrics",body(32,'x');
 auto headers=request(path,"",body,"","POST");headers.resize(headers.size()-body.size());
 auto before=bytesRead.load();auto challenge=transact(headers);
 check(status(challenge,401),"Digest unauthorized challenge");check(bytesRead.load()-before==headers.size()&&handlers==0,"unauthorized zero body reads");
 auto auth=digest(challenge,"POST",path);
 auto oversized=request(path,auth,"","","POST","385");before=bytesRead.load();
 check(status(transact(oversized),413)&&handlers==0,"oversized reject before body");check(bytesRead.load()-before==oversized.size(),"oversized zero body reads");
 challenge=transact(request("/status"));auth=digest(challenge,"POST",path);
 check(status(transact(request(path,auth,body,"","POST")),200)&&handlers==1,"real Digest exact authorized bounded body");
 for(const auto& length:{"-1","4294967296","12junk","0","15"}){
  challenge=transact(request("/status"));auth=digest(challenge,"POST",path);
  before=bytesRead.load();auto input=request(path,auth,"","","POST",length);
  check(status(transact(input),413)&&handlers==1,"strict length no handler");check(bytesRead.load()-before==input.size(),"strict length zero body reads");
 }
 challenge=transact(request("/status"));auth=digest(challenge,"POST",path);
 check(transact(request(path,auth,body,"Content-Length: 32\r\n","POST")).empty()&&handlers==1,"duplicate length closed");
 check(status(transact(request(path,auth,"","Transfer-Encoding: chunked\r\n","POST","32")),400)&&handlers==1,"transfer encoding closed");
 check(transact(request(path,auth,"","X-Large: "+std::string(513,'x')+"\r\n","POST","32")).empty(),"bounded header line");
 std::string many;for(unsigned i=0;i<33;++i)many+="X-H: x\r\n";
 check(transact(request(path,auth,"",many,"POST","32")).empty(),"bounded header count");
 check(transact(request("/status?secret=ignored")).empty(),"query/traversal parser closed");
 check(transact(request("/"+std::string(260,'x'))).empty(),"bounded first line");
 for(const auto& p:{"/config.json","/web/../config.json","/%2e%2e/config.json","/api/reboot","/legacyupdate","/api/v1/media/image","/api/v1/ota"}){
  challenge=transact(request("/status"));auth=digest(challenge,"POST",p);
  check(status(transact(request(p,auth,"","","POST","32")),404)&&handlers==1,"closed mutation/static path zero handlers");
 }
 std::cout<<"{\"checks\":"<<checks<<",\"real_core_digest\":true,\"host_loopback_only\":true,\"device_contacts\":0}";
}
