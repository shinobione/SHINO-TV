// Target handlers + real Core HTTP/Digest, loopback TCP, no owner device.
#include <HostSocket.h>
#include <ESP8266WiFi.h>
#include <iostream>
uint32_t host_ms=0;
void yield(){std::this_thread::yield();}
#include "pinned_stream.inc"
#include <ESP8266WebServer.h>
#include "HomeLan_host.inc"
using Clock=std::chrono::steady_clock;
static ESP8266WebServer server(80);
static unsigned checks=0,handlers=0,prebodyCalls=0;static bool busy=false;
static void check(bool ok,const char* name){++checks;if(!ok){std::cerr<<name<<'\n';std::exit(1);}}
struct Peer {
 Socket fd=INVALID_SOCKET;
 Peer(){fd=socket(AF_INET,SOCK_STREAM,0);sockaddr_in a{};a.sin_family=AF_INET;a.sin_addr.s_addr=htonl(INADDR_LOOPBACK);a.sin_port=htons(server.getServer().port);if(connect(fd,reinterpret_cast<sockaddr*>(&a),sizeof a))throw std::runtime_error("loopback connect");}
 void send(const std::string& text){size_t at=0;while(at<text.size()){int n=::send(fd,text.data()+at,int(text.size()-at),0);if(n<=0)throw std::runtime_error("send");at+=n;}}
 std::string receive(){std::string out;for(unsigned i=0;i<30;++i){fd_set set;FD_ZERO(&set);FD_SET(fd,&set);timeval t{0,1000};if(select(int(fd)+1,&set,nullptr,nullptr,&t)>0){char b[2048];int n=recv(fd,b,sizeof b,0);if(n<=0)break;out.append(b,n);}}return out;}
 ~Peer(){closeSocket(fd);}
};
static std::string transact(const std::string& text) {
 server.client().stop();server.client()=WiFiClient();server.getServer().pending.clear();
 Peer peer;peer.send(text);std::this_thread::sleep_for(std::chrono::milliseconds(3));
 for(unsigned i=0;i<8;++i){server.handleClient();if(!server.client()&&i)break;}
 return peer.receive();
}
static std::string request(const std::string& path,const std::string& auth="",const std::string& body="",const std::string& extra="",std::string method="GET",const std::string& host="192.168.4.1") {
 if(path=="/api/v1/bridge/wifi" && method=="GET")method="POST";
 return method+" "+path+" HTTP/1.1\r\nHost: "+host+"\r\nConnection: close\r\n"+auth+extra+(method=="POST"?"Content-Type: "+std::string(path=="/api/v1/bridge/metrics"?"application/json":"application/octet-stream")+"\r\nContent-Length: "+std::to_string(body.size())+"\r\n":"")+"\r\n"+body;
}
static std::string parameter(const std::string& s,const std::string& key){auto p=s.find(key+"=\"");if(p==s.npos)return "";p+=key.size()+2;return s.substr(p,s.find('"',p)-p);}
static std::string md5(const String& v){MD5Builder m;m.begin();m.add(v);m.calculate();return m.toString();}
static std::string digest(const std::string& challenge,const std::string& method,const std::string& path) {
 const std::string n=parameter(challenge,"nonce"),o=parameter(challenge,"opaque");
 const auto h1=md5("lab:SHINO-FirstBoot:PUBLIC-INERT-LAB-HTTP-FIXTURE"),h2=md5(String(method)+":"+path.c_str());
 const auto proof=md5(String(h1)+":"+n.c_str()+":00000001:test:auth:"+h2.c_str());
 return "Authorization: Digest username=\"lab\", realm=\"SHINO-FirstBoot\", nonce=\""+n+"\", uri=\""+path+"\", response=\""+proof+"\", opaque=\""+o+"\", qop=auth, nc=00000001, cnonce=\"test\"\r\n";
}
static bool status(const std::string& s,unsigned n){return s.find("HTTP/1.1 "+std::to_string(n)+" ")==0;}
static const std::string root="/api/v1/bridge/wifi",intentPath=root+"/intent";
static std::string arm() {
 auto challenge=transact(request(intentPath));check(status(challenge,401),"intent Digest challenge");
 auto reply=transact(request(intentPath,digest(challenge,"GET",intentPath)));
 check(status(reply,200),"intent authorized AP");
 auto p=reply.find("{\"intent\":\"");check(p!=reply.npos,"intent bounded response");return reply.substr(p+11,32);
}
int main(){
#ifdef _WIN32
 WSADATA w;WSAStartup(MAKEWORD(2,2),&w);
#endif
 HomeLan::begin("public-lab-ap","PUBLIC-INERT-LAB-AP-FIXTURE");
 server.collectHeaders("Cookie","Origin","Content-Type","Content-Length","Transfer-Encoding","X-Shino-Wifi-Intent");
 server.setHomeLanPrebody([](){++prebodyCalls;return HomeLan::beforeBody(server,"lab","PUBLIC-INERT-LAB-HTTP-FIXTURE",busy);});
 HomeLan::registerRoutes(server,"lab","PUBLIC-INERT-LAB-HTTP-FIXTURE");
 server.on("/api/v1/bridge/metrics",HTTP_POST,[](){++handlers;server.send(200,"application/json","{}");});
 server.begin();
 const std::string body="C\x03\x08" "labfixture1";
 auto headersOnly=[&](const std::string& auth,const std::string& data,const std::string& extra="",const std::string& host="192.168.4.1") {auto req=request(root,auth,data,extra,"POST",host);return req.substr(0,req.size()-data.size());};
 auto before=bytesRead.load();auto reply=transact(headersOnly("",body));
 check(status(reply,401)&&testWrites==0,"unauthorized zero writes");
 check(bytesRead.load()-before==request(root,"",body).size()-body.size(),"unauthorized provisioning zero body reads");
 auto basic="Authorization: Basic "+std::string(base64::encode("lab:PUBLIC-INERT-LAB-HTTP-FIXTURE",false))+"\r\n";
 check(status(transact(headersOnly(basic,body)),401)&&testWrites==0,"Basic forbidden");
 auto token=arm();auto challenge=transact(request(root));
 auto auth=digest(challenge,"POST",root);auto header="X-Shino-Wifi-Intent: "+token+"\r\n";
 reply=transact(request(root,auth,body,header));
 check(status(reply,200)&&testWrites==1,"actual SDK adapter one verified persistent write");
 check(!std::memcmp(testSaved.ssid,"lab",3),"SDK mock stores correct SSID");
 check(reply.find("fixture1")==reply.npos,"secret never echoed");
 HomeLan::poll(false);check(testConnects==1,"saved config automatically connects after apply");
 token=arm();challenge=transact(request(root));auth=digest(challenge,"POST",root);header="X-Shino-Wifi-Intent: "+token+"\r\n";
 check(status(transact(request(root,auth,body,header)),200)&&testWrites==1,"identical config zero extra writes");
 HomeLan::poll(false);
 challenge=transact(request(root));auth=digest(challenge,"POST",root);
 check(status(transact(request(root,auth,body,header)),403)&&testWrites==1,"replayed intent zero writes");
 token=arm();challenge=transact(request(root));auth=digest(challenge,"POST",root);header="X-Shino-Wifi-Intent: "+token+"\r\n";
 check(transact(request(root,auth,body,header+"Content-Length: 13\r\n")).empty()&&testWrites==1,"duplicate length rejected");
 check(transact(request(root,auth,body,header+"Host: attacker\r\n")).empty()&&testWrites==1,"duplicate Host rejected");
 check(status(transact(headersOnly(auth,body,header+"Origin: http://attacker\r\n")),403)&&testWrites==1,"cross-origin zero write");
 busy=true;check(status(transact(headersOnly(auth,body,header)),409)&&testWrites==1,"media busy no storage write");busy=false;
 check(status(transact(headersOnly(auth,std::string(100,'x'),header)),400)&&testWrites==1,"100 bytes rejected before body");
 testLocal=IPAddress(192,168,1,12);testPeer=IPAddress(192,168,1,2);WiFi.sta=testLocal;WiFi.wifiStatus=WL_CONNECTED;
 check(status(transact(headersOnly(auth,body,header,"192.168.1.12")),403)&&testWrites==1,"LAN provisioning denied");
 check(status(transact(request("/api/v1/bridge/factory-return","","","","POST","192.168.1.12")),403),"LAN OEM denied");
 const std::string metrics="{\"fixture\":true}";
 check(status(transact(request("/api/v1/bridge/metrics","",metrics,"","POST","192.168.1.12")),200)&&handlers==1,"LAN metrics same numeric interface");
 auto cross=request("/api/v1/bridge/metrics","",metrics,"Origin: http://192.168.4.1\r\n","POST","192.168.1.12");
 cross.resize(cross.size()-metrics.size());
 check(status(transact(cross),403)&&handlers==1,"cross-interface origin denied before body");
 auto huge=request("/api/v1/bridge/metrics","",std::string(385,'x'),"","POST","192.168.1.12");
 huge.resize(huge.size()-385);
 check(status(transact(huge),400)&&handlers==1,"oversized metrics denied before allocation/body");
 testLocal=IPAddress(192,168,4,1);testPeer=IPAddress(192,168,4,2);
 token=arm();challenge=transact(request(root));auth=digest(challenge,"POST",root);header="X-Shino-Wifi-Intent: "+token+"\r\n";
 check(status(transact(request(root,auth,"F",header)),200)&&testWrites==2,"explicit Forget actual handler");
 HomeLan::poll(false);check(!HomeLan::configured()&&testSaved.ssid[0]==0,"Forget does not retry deleted network");
 const unsigned writes=testWrites;HomeLan::begin("public-lab-ap","PUBLIC-INERT-LAB-AP-FIXTURE");
 check(testWrites==writes&&!HomeLan::configured(),"reboot no flash write");
 server.client().stop();server.close();
 std::cout<<"{\"checks\":"<<checks<<",\"failed\":0,\"simulated_sdk_writes\":"<<testWrites<<",\"device_contacts\":0,\"device_writes\":0}";
}
