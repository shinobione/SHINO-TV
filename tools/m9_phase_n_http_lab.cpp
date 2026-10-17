// Real pinned Core parser/Digest over host loopback; no owner/device transport.
#include <HostSocket.h>
#include <ESP8266WiFi.h>
#include <iostream>
uint32_t host_ms=0;
void yield(){std::this_thread::yield();}
#include "pinned_stream.inc"
#include <ESP8266WebServer.h>
#include "boot/M9NormalHttpPolicy.h"
static unsigned checks=0,handlers=0,posts=0,gets=0,notFound=0,policy404=0;
struct ObservedServer:ESP8266WebServer {
 using ESP8266WebServer::ESP8266WebServer;
 void trace(int policy,const char* phase="prebody") {
  std::cerr<<"phase="<<phase<<" policy="<<policy<<" method="<<int(_currentMethod)<<" uri="<<_currentUri
   <<" handler="<<bool(_currentHandler)<<" args="<<_currentArgCount
   <<" plain="<<int(_currentArgsHavePlain)<<" plain_nonempty="<<(_currentArgs&&!arg("plain").isEmpty())
   <<" post_args="<<_postArgsLen<<" realm_stagea="<<(_srealm=="SHINO-StageA")
   <<" nonce_present="<<bool(_snonce.length())<<" opaque_present="<<bool(_sopaque.length())<<'\n';
 }
#ifdef M9_ACTUAL_STAGE_A
 void setStageAPrebody(std::function<bool()> fn) {
  ESP8266WebServer::setStageAPrebody([this,fn](){
   const bool authorized=header("Authorization").startsWith("Digest ")&&authenticate("shino","PUBLIC-INERT-LAB-HTTP-FIXTURE");
   bool ok=fn();int policy=M9NormalHttpPolicy::classify(method()==HTTP_GET,method()==HTTP_POST,uri().c_str(),
    header("Content-Length").c_str(),header("Content-Type").c_str(),header("Transfer-Encoding").c_str());
   if(!ok&&authorized&&policy==404)++policy404;
   trace(authorized?policy:401);return ok;
  });
 }
 void on(const char* path,HTTPMethod method,std::function<void()> fn) {
  ESP8266WebServer::on(path,method,[this,method,fn](){
   ++handlers;if(method==HTTP_POST)++posts;else ++gets;trace(200,"handler");fn();
  });
 }
 void onNotFound(std::function<void()> fn) {
  ESP8266WebServer::onNotFound([this,fn](){++notFound;trace(-404,"fallback");fn();});
 }
#endif
};
#ifdef M9_ACTUAL_STAGE_A
#include "stage_composition.inc"
static auto& server=M9NormalStageA::service.raw();
#else
static ObservedServer server(80);
#endif
static void check(bool ok,const char* name){++checks;if(!ok){std::cerr<<name<<'\n';std::exit(1);}}
struct Peer {
 Socket fd=INVALID_SOCKET;
 Peer(){fd=socket(AF_INET,SOCK_STREAM,0);sockaddr_in a{};a.sin_family=AF_INET;a.sin_addr.s_addr=htonl(INADDR_LOOPBACK);a.sin_port=htons(server.getServer().port);
 if(connect(fd,reinterpret_cast<sockaddr*>(&a),sizeof a))throw std::runtime_error("loopback connect");}
 void send(const std::string& s){size_t at=0;while(at<s.size()){int n=::send(fd,s.data()+at,int(s.size()-at),0);if(n<=0)throw std::runtime_error("send");at+=n;}}
 std::string receive(){std::string out;for(unsigned i=0;i<30;++i){fd_set set;FD_ZERO(&set);FD_SET(fd,&set);timeval t{0,1000};
 if(select(int(fd)+1,&set,nullptr,nullptr,&t)>0){char b[2048];int n=recv(fd,b,sizeof b,0);if(n<=0)break;out.append(b,n);
  auto split=out.find("\r\n\r\n"),length=out.find("Content-Length: ");
  if(split!=out.npos&&length!=out.npos&&out.size()>=split+4+std::stoul(out.substr(length+16)))break;
 }}return out;}
 ~Peer(){closeSocket(fd);}
};
static std::string transact(const std::string& text){
 std::cerr<<text.substr(0,text.find('\r'))<<'\n';
 for(unsigned i=0;i<4;++i)server.handleClient(); // Natural cleanup after the preceding peer closes.
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
 const auto h1=md5("shino:SHINO-StageA:PUBLIC-INERT-LAB-HTTP-FIXTURE"),h2=md5(String(method)+":"+path.c_str());
 const auto proof=md5(String(h1)+":"+n.c_str()+":00000001:test:auth:"+h2.c_str());
 return "Authorization: Digest username=\"shino\", realm=\"SHINO-StageA\", nonce=\""+n+"\", uri=\""+path+"\", response=\""+proof+"\", opaque=\""+o+"\", qop=auth, nc=00000001, cnonce=\"test\"\r\n";
}
static bool status(const std::string& s,unsigned n){return s.find("HTTP/1.1 "+std::to_string(n)+" ")==0;}
int main(int argc,char**) try {
#ifdef _WIN32
 WSADATA w;WSAStartup(MAKEWORD(2,2),&w);
#endif
#ifdef M9_ACTUAL_STAGE_A
 ConfigManager config;
 M9NormalStageA::beforeSetup();M9NormalStageA::begin(config);M9NormalStageA::afterSetup();
#else
 server.collectHeaders("Authorization","Content-Length","Content-Type","Transfer-Encoding");
 server.setStageAPrebody([](){
  server.trace(0);
  server.keepAlive(false);
  if(!server.header("Authorization").startsWith("Digest ") || !server.authenticate("shino","PUBLIC-INERT-LAB-HTTP-FIXTURE")){
   server.requestAuthentication(DIGEST_AUTH,"SHINO-StageA");return false;}
  int result=M9NormalHttpPolicy::classify(server.method()==HTTP_GET,server.method()==HTTP_POST,server.uri().c_str(),
   server.header("Content-Length").c_str(),server.header("Content-Type").c_str(),server.header("Transfer-Encoding").c_str());
  if(result!=200){if(result==404)++policy404;server.trace(result);server.send(result,"application/json","{}");return false;}return true;
 });
 auto get=[](){++handlers;++gets;server.send(200,"application/json","{}");};
 server.on("/status",HTTP_GET,get);
 server.on("/api/v1/m9/normal/status",HTTP_GET,get);
 server.on("/api/v1/m9/normal/resources",HTTP_GET,get);
 server.onNotFound([](){++notFound;server.trace(-404);server.send(404,"application/json","{}");});
 server.on("/api/v1/bridge/metrics",HTTP_POST,[](){check(server.arg("plain").length()<=384,"bounded actual body");++handlers;++posts;server.send(200,"application/json","{}");});
 server.begin();
#endif
 const std::string path="/api/v1/bridge/metrics",body(32,'x');
 if(argc>1) {
  lab_real_clock=true;std::atomic<bool> done=false;std::atomic<int> advance{-1};
  std::thread control([&](){std::string line;while(std::getline(std::cin,line)){
   if(line=="stop")break;advance=std::stoi(line);
  }done=true;});
  std::cout<<server.getServer().port<<std::endl;
  while(!done){
   int tick=advance.exchange(-1);if(tick>=0)host_ms+=unsigned(tick);
#ifdef M9_ACTUAL_STAGE_A
   M9NormalStageA::loop();
#else
   server.handleClient();
#endif
   if(tick>=0){
#ifdef M9_ACTUAL_STAGE_A
    std::cout<<"{\"stale\":"<<(FslessMetrics::stale()?"true":"false")<<",\"received\":"<<(FslessMetrics::snapshot().received?"true":"false")<<"}"<<std::endl;
#else
    std::cout<<"{}"<<std::endl;
#endif
   }
   std::this_thread::sleep_for(std::chrono::milliseconds(1));}
  control.join();std::cout<<"{\"posts\":"<<posts<<",\"gets\":"<<gets<<",\"not_found\":"<<notFound<<",\"policy404\":"<<policy404<<"}";
  return 0;
 }
 auto first=transact(request("/status"));
 check(status(transact(request("/status",digest(first,"GET","/status"))),200),"initial authenticated GET");
 for(unsigned i=0;i<100;++i) {
  check(status(transact(request(path,digest(first,"POST",path),body,"","POST")),200),"workload POST");
  host_ms+=2000;
 }
 for(const auto& p:{"/status","/api/v1/m9/normal/status","/api/v1/m9/normal/resources"}) {
  auto c=transact(request(p));
  auto response=transact(request(p,digest(c,"GET",p)));
  if(!status(response,200)){server.trace(-1);std::cerr<<response<<'\n';}
  check(status(response,200),"final fresh-client authenticated GET after workload");
 }
 handlers=0;
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
} catch(const std::exception& e){std::cerr<<"host fixture exception: "<<e.what()<<'\n';return 2;}
