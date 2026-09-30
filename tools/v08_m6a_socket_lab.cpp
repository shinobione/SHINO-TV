// Offline PC only. Actual pinned WebServer templates + unchanged bridge source.
#include <HostSocket.h>
#include <iostream>
#include <new>
#include <functional>
#include <map>
void* operator new(size_t n){if(void* p=std::malloc(n?n:1)){allocs++;return p;}throw std::bad_alloc();}
void operator delete(void* p)noexcept{if(p){frees++;std::free(p);}}
void* operator new[](size_t n){return ::operator new(n);}
void operator delete[](void* p)noexcept{::operator delete(p);}
void operator delete(void* p,size_t)noexcept{::operator delete(p);}
void operator delete[](void* p,size_t)noexcept{::operator delete(p);}
uint32_t host_ms=0;
void yield(){std::this_thread::yield();}
#include "pinned_stream.inc"
#include <ESP8266WebServer.h>
#include "../firmware/src/boot/FirstBootBridge.cpp"
using Clock=std::chrono::steady_clock;
static int checks=0,failed=0;
static double worstPollUs=0,maxDispatchUs=0,maxClientLifetimeUs=0,readyWaitUs=0,realReadyWaitMs=0,deadlineHandoffUs=0,worstFirstResponseUs=0;
static size_t maxPollBytes=0,maxPreparseOnlyBytes=0,polls=0;
static std::map<size_t,size_t> pollByteHistogram;
static void check(bool ok,const char* name){checks++;if(!ok){failed++;std::cerr<<"FAIL "<<name<<"\n";}}
static double poll(){auto at=Clock::now();lab_poll_origin=at;lab_poll_active=true;lab_first_write_us=-1;auto before=bytesRead.load();server.handleClient();double us=std::chrono::duration<double,std::micro>(Clock::now()-at).count();lab_poll_active=false;worstFirstResponseUs=std::max(worstFirstResponseUs,lab_first_write_us);auto count=bytesRead.load()-before;worstPollUs=std::max(worstPollUs,us);maxPollBytes=std::max(maxPollBytes,count);pollByteHistogram[count]++;polls++;return us;}
struct Peer {
 Socket fd=INVALID_SOCKET;
 Clock::time_point born=Clock::now();
 Peer(){fd=socket(AF_INET,SOCK_STREAM,0);if(fd==INVALID_SOCKET)throw std::runtime_error("peer socket");trackSocket();sockaddr_in a{};a.sin_family=AF_INET;a.sin_addr.s_addr=htonl(INADDR_LOOPBACK);a.sin_port=htons(server.getServer().port);if(connect(fd,reinterpret_cast<sockaddr*>(&a),sizeof a))throw std::runtime_error("loopback connect");}
 void send(const std::string& s){size_t at=0;while(at<s.size()){
#ifdef _WIN32
 int n=::send(fd,s.data()+at,int(s.size()-at),0);
#else
 int n=::send(fd,s.data()+at,s.size()-at,MSG_NOSIGNAL);
#endif
 if(n<=0)throw std::runtime_error("peer send");at+=n;}}
 std::string receive(int waitMs=100){std::string out;auto end=Clock::now()+std::chrono::milliseconds(waitMs);while(Clock::now()<end){fd_set f;FD_ZERO(&f);FD_SET(fd,&f);timeval t{0,1000};if(select(int(fd)+1,&f,nullptr,nullptr,&t)>0){char b[8192];int n=recv(fd,b,sizeof b,0);if(n<=0)break;out.append(b,n);if(out.find("\r\n\r\n")!=out.npos){auto p=out.find("Content-Length: ");if(p!=out.npos && out.size()>=out.find("\r\n\r\n")+4+std::stoul(out.substr(p+16)))break;}}}return out;}
 void fin(){shutdown(fd,SD_SEND);}
 bool readable(){fd_set f;FD_ZERO(&f);FD_SET(fd,&f);timeval t{};return select(int(fd)+1,&f,nullptr,nullptr,&t)>0;}
 void close(bool reset=false){if(fd!=INVALID_SOCKET){if(reset){linger l{1,0};setsockopt(fd,SOL_SOCKET,SO_LINGER,reinterpret_cast<const char*>(&l),sizeof l);}closeSocket(fd);fd=INVALID_SOCKET;liveSockets--;maxClientLifetimeUs=std::max(maxClientLifetimeUs,std::chrono::duration<double,std::micro>(Clock::now()-born).count());}}
 ~Peer(){close();}
};
static void arrival(){auto end=Clock::now()+std::chrono::milliseconds(500);while(Clock::now()<end){server.getServer().harvest();if(server.client().available())return;for(auto& c:server.getServer().pending)if(c.available())return;std::this_thread::sleep_for(std::chrono::milliseconds(1));}throw std::runtime_error("loopback arrival timeout");}
static void clearOwner(){server.client().stop();server.client()=WiFiClient();server.getServer().pending.clear();poll();}
static const String auth=String("Authorization: Basic ")+base64::encode(String(SHINO_RESCUE_HTTP_USER)+":"+SHINO_RESCUE_HTTP_PASSWORD,false)+"\r\n";
static std::string req(std::string target="/",std::string headers="",std::string body="",std::string method="GET"){
 return method+" "+target+" HTTP/1.1\r\nHost: loopback.invalid\r\n"+headers+(method=="POST"?"Content-Type: application/json\r\nContent-Length: "+std::to_string(body.size())+"\r\n":"")+"\r\n"+body;
}
static std::string transact(const std::string& text){clearOwner();Peer p;auto at=Clock::now();p.send(text);arrival();auto written=bytesWritten.load();for(int i=0;i<8;i++){poll();if(bytesWritten.load()>written || !server.client())break;}std::string out=p.receive();maxDispatchUs=std::max(maxDispatchUs,std::chrono::duration<double,std::micro>(Clock::now()-at).count());return out;}
static bool status(const std::string& s,int code){return s.find("HTTP/1.1 "+std::to_string(code)+" ")==0;}
static const std::string sample=R"({"ok":true,"gpu_available":true,"cpu_usage":12,"gpu_usage":34,"memory_used_gb":5,"memory_total_gb":16,"gpu_vram_mb":123,"gpu_temp_c":67,"gpu_power":80})";
static std::string cookieFrom(const std::string& r){auto p=r.find("Set-Cookie: ");if(p==r.npos)return "";auto end=r.find(';',p);return r.substr(p+12,end-p-12);}
static std::string md5(const String& s){MD5Builder m;m.begin();m.add(s);m.calculate();return m.toString();}
static std::string parameter(const std::string& s,const std::string& key){auto p=s.find(key+"=\"");if(p==s.npos)return "";p+=key.size()+2;return s.substr(p,s.find('"',p)-p);}
static std::string digestHeader(const std::string& challenge,const std::string& method,const std::string& signedUri){auto nonce=parameter(challenge,"nonce"),opaque=parameter(challenge,"opaque");std::string realm="SHINO-FirstBoot",nc="00000001",cnonce="public-fixture";auto h1=md5(String(SHINO_RESCUE_HTTP_USER)+":"+realm.c_str()+":"+SHINO_RESCUE_HTTP_PASSWORD);auto h2=md5(String(method)+":"+signedUri.c_str());auto response=md5(String(h1)+":"+nonce.c_str()+":"+nc.c_str()+":"+cnonce.c_str()+":auth:"+h2.c_str());return "Authorization: Digest username=\"lab\", realm=\""+realm+"\", nonce=\""+nonce+"\", uri=\""+signedUri+"\", response=\""+response+"\", opaque=\""+opaque+"\", qop=auth, nc="+nc+", cnonce=\""+cnonce+"\"\r\n";}
int main(){
#ifdef _WIN32
 WSADATA w;WSAStartup(MAKEWORD(2,2),&w);
#endif
 FirstBootBridge::run();
 check(md5("abc")=="900150983cd24fb0d6963f7d28e17f72","host MD5 provider known answer");
 check(server.getServer().port!=0 && !WiFi.persisted,"actual route registration over ephemeral loopback");
 auto denied=transact(req());check(status(denied,401) && denied.find("WWW-Authenticate: Digest")!=denied.npos,"actual Digest challenge response");
 auto dashboard=transact(req("/",auth));check(status(dashboard,200) && dashboard.find("SHINO")!=dashboard.npos,"unchanged dashboard dispatch and actual response");
 check(dashboard.find("Content-Security-Policy:")!=dashboard.npos && dashboard.find("HttpOnly; SameSite=Strict")!=dashboard.npos,"actual browser security headers");
 auto cookie=cookieFrom(dashboard);check(cookie.size()==51,"actual session token fixture");
 check(status(transact(req("/ui.js","Cookie: "+cookie+"\r\n")),200),"session script dispatch");
 check(status(transact(req("/api/v1/bridge/metrics","Cookie: "+cookie+"\r\n")),200),"session metrics GET dispatch");
 auto before=FslessMetrics::snapshot();check(status(transact(req("/api/v1/bridge/metrics","Cookie: "+cookie+"\r\n",sample,"POST")),401) && FslessMetrics::snapshot().lastReceivedMs==before.lastReceivedMs,"cookie POST denied preserves state");
 host_ms=100;auto goodResponse=transact(req("/api/v1/bridge/metrics",auth,sample,"POST"));auto good=FslessMetrics::snapshot();
 check(status(goodResponse,200) && goodResponse.find("RAM_SAMPLE_ACCEPTED")!=goodResponse.npos,"actual metric acceptance response");
 check(good.cpu==12 && good.gpu==34 && good.memoryGb==5 && good.gpuTempC==67 && good.lastReceivedMs==100,"four actual numeric metrics and timestamp");
 paintNativeDashboard();check(String(lastNumbers[0])=="12.0%" && String(lastNumbers[1])=="34.0%" && String(lastNumbers[2])=="5.0 GB" && String(lastNumbers[3])=="67.0","actual four-card formatting inert graphics");
 host_ms=6100;check(!FslessMetrics::stale(),"6000ms fresh");host_ms=6101;check(FslessMetrics::stale(),"6001ms stale");
 for(auto body:{std::string(385,'x'),std::string("{broken}"),std::string("{\"invalid\":true}")}){auto r=transact(req("/api/v1/bridge/metrics",auth,body,"POST"));check((status(r,413)||status(r,422)) && FslessMetrics::snapshot().lastReceivedMs==100,"invalid metrics preserves timestamp");}
 for(auto target:{"/api/v1/bridge/status","/api/v1/bridge/fs-plan","/api/v1/bridge/ota/capabilities"}){auto r=transact(req(target,auth));check(status(r,200) && r.find("\"mode\"")!=r.npos,"actual diagnostic JSON response");}
 check(status(transact(req("/api/v1/bridge/status")),401),"session does not grant diagnostics");
 check(status(transact(req("/api/v1/bridge/factory-return",auth)),200) && FactoryRollback::statuses==1,"inert OEM status delegation");
 auto oem=transact(req("/api/v1/bridge/factory-return",auth,"{}","POST"));
#if SHINO_ENABLE_FACTORY_RESTORE
 check(status(oem,200) && oem.find("inert_oem_completion")!=oem.npos && FactoryRollback::completions==1,"conditional actual OEM completion dispatch inert");
 // Actual multipart parser invokes actual route callbacks, which delegate only to inert OEM seams.
 std::string multipart="--lab-boundary\r\nContent-Disposition: form-data; name=\"image\"; filename=\"fixture.txt\"\r\nContent-Type: text/plain\r\n\r\nPUBLIC\r\n--lab-boundary--\r\n";
 auto uploadReq=[&](std::string h){return "POST /api/v1/bridge/factory-return HTTP/1.1\r\nHost: loopback.invalid\r\n"+h+"Content-Type: multipart/form-data; boundary=lab-boundary\r\nContent-Length: "+std::to_string(multipart.size())+"\r\n\r\n"+multipart;};
 transact(uploadReq(""));check(FactoryRollback::uploads==3 && !FactoryRollback::uploadAuthorized && FactoryRollback::completions==1,"denied multipart upload callbacks before completion auth");
 auto ur=transact(uploadReq(auth));check(status(ur,200) && FactoryRollback::uploads==6 && FactoryRollback::uploadAuthorized && FactoryRollback::completions==2,"authorized multipart callback composition inert");
 check(FactoryRollback::events==std::vector<int>({100,UPLOAD_FILE_START,UPLOAD_FILE_WRITE,UPLOAD_FILE_END,UPLOAD_FILE_START,UPLOAD_FILE_WRITE,UPLOAD_FILE_END,100}),"actual denied/accepted multipart ordering upload precedes completion");
#else
 check(status(oem,404) && FactoryRollback::completions==0,"default OEM POST absent");
#endif
 check(status(transact(req("/","Authorization: Basic!"+std::string(auth.substr(21)))),200),"R7 Basic prefix weakness characterized");
 auto challenge=transact(req("/api/v1/bridge/status"));auto d=digestHeader(challenge,"GET","/unrelated-signed-uri");
 check(status(transact(req("/api/v1/bridge/status",d)),200),"R7 Digest URI mismatch accepted known failure");
 check(status(transact(req("/api/v1/bridge/fs-plan",d)),200),"R7 same Digest nc replay across target accepted known failure");
 auto postChallenge=transact(req("/api/v1/bridge/metrics","",sample,"POST"));auto pd=digestHeader(postChallenge,"POST","/different");
 check(status(transact(req("/api/v1/bridge/metrics",pd,sample,"POST")),200),"actual Digest POST with substituted URI");
 auto changed=sample;changed.replace(changed.find("12"),2,"13");check(status(transact(req("/api/v1/bridge/metrics",pd,changed,"POST")),200) && FslessMetrics::snapshot().cpu==13,"R7 same Digest proof permits body modification and replay");
 check(status(transact(req("/api/v1/bridge/status",auth+"Authorization: Basic invalid\r\n")),401),"duplicate Authorization last value wins on wire");
 check(status(transact(req("/api/v1/bridge/status","Authorization: Basic invalid\r\n"+auth)),200),"duplicate Authorization reversed accepted");
 cookie=cookieFrom(transact(req("/",auth)));
 check(status(transact(req("/api/v1/bridge/metrics","Cookie: "+cookie+"\r\n")),200),"fresh cookie control for duplicate tests");
 check(status(transact(req("/api/v1/bridge/metrics","Cookie: "+cookie+"; "+cookie+"\r\n")),403),"duplicate session names rejected on wire");
 check(status(transact(req("/api/v1/bridge/metrics","Cookie: invalid\r\nCookie: "+cookie+"\r\n")),200),"R7 duplicate Cookie header last value valid accepted");
 check(status(transact(req("/api/v1/bridge/metrics","Cookie: "+cookie+"\r\nCookie: invalid\r\n")),403),"duplicate Cookie header reversed denied");
 // Baseline comparison: actual pinned 30ms ready-client grace, not prior synthetic 1000ms constant.
 clearOwner();host_ms=0;{Peer slow,ready;poll();auto waiting=Clock::now();ready.send(req("/api/v1/bridge/status",auth));arrival();host_ms=31;poll();
#if LAB_OVERLAY && !LAB_CORRECTED
 check(bool(server.client()),"R5 overlay retains idle owner past actual stock grace");host_ms=1999;poll();check(bool(server.client()),"overlay retains until absolute deadline");host_ms=2000;poll();check(!server.client(),"overlay releases at 2000ms");
#else
 check(!server.client(),"stock drops idle owner at31ms ready competitor");
#endif
 poll();check(status(ready.receive(),200),"ready competitor eventually dispatched");readyWaitUs=std::chrono::duration<double,std::micro>(Clock::now()-waiting).count();}
 // Repeat with actual wall-clock ticks. The one-poll scheduling cadence is 1ms.
 clearOwner();lab_real_clock=true;lab_clock_origin=Clock::now();{Peer slow,ready;poll();auto waiting=Clock::now();ready.send(req("/api/v1/bridge/status",auth));arrival();while(!ready.readable() && Clock::now()-waiting<std::chrono::milliseconds(2500)){poll();std::this_thread::sleep_for(std::chrono::milliseconds(1));}realReadyWaitMs=std::chrono::duration<double,std::milli>(Clock::now()-waiting).count();check(status(ready.receive(),200),"real clock competing ready response");check((LAB_OVERLAY && !LAB_CORRECTED)?realReadyWaitMs>=1900 && realReadyWaitMs<2500:realReadyWaitMs>=25 && realReadyWaitMs<500,"actual stock versus overlay contention wall wait");}lab_real_clock=false;
 // A full host pending queue also releases stock by its ready grace but not the overlay.
 clearOwner();host_ms=0;{Peer slow;poll();std::vector<std::unique_ptr<Peer>> pending;for(int i=0;i<5;i++)pending.emplace_back(new Peer());server.getServer().harvest();check(server.getServer().hasMaxPendingClients(),"host pending queue fixture full");
#if LAB_CORRECTED
 auto n=stops.load();host_ms=30;poll();check(bool(server.client()) && stops==n,"R5 full queue exact30 retained");host_ms=31;poll();check(!server.client() && stops==n+1,"R5 full queue exactly one terminal stop at31");
#else
 host_ms=31;poll();check((LAB_OVERLAY && !LAB_CORRECTED)?bool(server.client()):!server.client(),"full host queue same R5 retention change");
#endif
 }

#if LAB_CORRECTED
 // A 64-byte slice still has buffered bytes: stock no-data preemption does not apply.
 clearOwner();host_ms=0;{Peer p,ready;p.send("GET /"+std::string(100,'x'));arrival();poll();ready.send(req("/api/v1/bridge/status",auth));arrival();host_ms=31;auto n=stops.load();poll();check(!server.client() && stops==n+1,"R5 drained second partial slice interrupted once");poll();check(status(ready.receive(),200),"R5 sliced partial competitor dispatch");}
 // No ready data and a non-full queue do not trigger the fast grace.
 clearOwner();host_ms=0;{Peer p,waiting;p.send("GET /");arrival();poll();host_ms=31;poll();check(bool(server.client()),"R5 idle competitor alone keeps absolute policy");host_ms=2000;poll();check(!server.client(),"R5 no-ready competitor absolute deadline");}
#endif
 // Real slow first line: delayed continuation rather than fake readStringUntil behavior.
 clearOwner();host_ms=0;{Peer p;p.send("GET /");arrival();
#if LAB_OVERLAY
 auto n=bytesRead.load();poll();check(bytesRead.load()-n==5 && bool(server.client()),"partial line five bytes retained");host_ms=1001;poll();check(bool(server.client()),"partial owner with no competitor retained at1001");p.send(" HTTP/1.1\r\n"+std::string(auth)+"\r\n");arrival();poll();check(status(p.receive(),200),"partial first line completed real socket");
#else
 std::thread trickle([&]{std::this_thread::sleep_for(std::chrono::milliseconds(40));p.send(" HTTP/1.1\r\n"+std::string(auth)+"\r\n");});auto us=poll();trickle.join();check(us>=30000 && status(p.receive(),200),"stock parser blocks awaiting line continuation");
#endif
 }
 // Header read remains blocking after overlay hands off a complete line.
 clearOwner();{Peer p;p.send("GET /api/v1/bridge/status HTTP/1.1\r\nAuth");arrival();std::thread t([&]{std::this_thread::sleep_for(std::chrono::milliseconds(35));p.send(std::string(auth.substr(4))+"\r\n");});auto us=poll();t.join();check(us>=25000 && status(p.receive(),200),"partial trickled header blocks poll and dispatches");}
#if LAB_OVERLAY
 clearOwner();lab_real_clock=true;lab_clock_origin=Clock::now();{Peer p;p.send("GET /api/v1/bridge/status HTTP/1.1\r\nAuth");arrival();std::thread t([&]{std::this_thread::sleep_for(std::chrono::milliseconds(2100));p.send(std::string(auth.substr(4))+"\r\n");});deadlineHandoffUs=poll();t.join();check(deadlineHandoffUs>=2000000 && status(p.receive(),200),"R7 first-line deadline does not bound blocking header handoff");}lab_real_clock=false;
#endif
 // Body buffering before unauthorized handler is preserved, including >384 bytes.
 auto n=bytesRead.load();auto oversized=transact(req("/api/v1/bridge/metrics","",std::string(4096,'x'),"POST"));check(status(oversized,401) && bytesRead.load()-n>=4096,"R7 actual 4096 body bytes consumed before auth denial");
 // FIN/half-close and RST: complete bytes can dispatch; partial media never falls through.
 clearOwner();{Peer p;p.send(req("/api/v1/bridge/status",auth));arrival();p.fin();poll();check(status(p.receive(),200),"complete request half-close still responds");}
 for(auto cut:{std::string(""),std::string("GET /"),std::string("GET /api/v2/bridge/media HTTP/1.1\r")}){clearOwner();Peer p;p.send(cut);if(!cut.empty())arrival();p.fin();poll();clearOwner();check(!server.client(),"early FIN terminal cleanup");}
 clearOwner();{Peer p;p.send("GET /");arrival();p.close(true);std::this_thread::sleep_for(std::chrono::milliseconds(2));poll();clearOwner();check(!server.client(),"partial request RST cleanup");}
 clearOwner();{Peer p;p.send(req("/api/v1/bridge/status",auth));arrival();p.close(true);poll();clearOwner();check(!server.client(),"buffered request RST cleanup");}
 for(bool reset:{false,true}){clearOwner();Peer p;p.send("POST /api/v1/bridge/metrics HTTP/1.1\r\n"+std::string(auth)+"Content-Length: 10\r\n\r\nshort");arrival();if(reset)p.close(true);else p.fin();auto b=FslessMetrics::snapshot().lastReceivedMs;poll();check(FslessMetrics::snapshot().lastReceivedMs==b,"interrupted body cannot mutate metrics");clearOwner();}
 clearOwner();{Peer p;p.send("GET /api/v1/bridge/status HTTP/1.1\r\n"+std::string(auth)+"X-Incomplete:");arrival();p.fin();poll();check(status(p.receive(),200),"R7 incomplete terminal header still dispatches known framing weakness");}
 // Buffered pipelines and delayed second requests use actual dispatch, unread bytes remain in TCP.
 clearOwner();{Peer p;p.send(req("/api/v1/bridge/status",auth)+req("/api/v1/bridge/fs-plan",auth));arrival();poll();auto r=p.receive();check(status(r,200) && server.client().available()>0,"pipeline unread second request preserved");poll();auto second=p.receive();check(status(second,200) && second.find("READ_ONLY_FS_MIGRATION_PLAN")!=second.npos,"pipeline second actual dispatch");}
 clearOwner();{Peer p;p.send(req("/api/v1/bridge/status",auth));arrival();poll();auto r=p.receive();check(r.find("Connection: keep-alive")!=r.npos,"actual keepalive response");p.send(req("/api/v1/bridge/fs-plan",auth));arrival();poll();check(status(p.receive(),200),"delayed pipeline dispatch");}
 clearOwner();{Peer p;p.send(req("/api/v1/bridge/status",auth+"Connection: close\r\n"));arrival();poll();check(p.receive().find("Connection: close")!=std::string::npos,"explicit close response");host_ms+=HTTP_MAX_CLOSE_WAIT+1;poll();check(!server.client(),"close wait terminal release");}
 clearOwner();{Peer p,other;p.send(req("/api/v1/bridge/status",auth));other.send(req("/api/v1/bridge/fs-plan",auth));arrival();poll();check(p.receive().find("Connection: close")!=std::string::npos,"competition disables response keepalive");poll();poll();check(status(other.receive(),200),"competing complete requests both served");}
 // Host shared ownership is explicit; SDK reference counting remains unqualified.
 clearOwner();{Peer p;p.send(req("/api/v1/bridge/status",auth));arrival();poll();p.receive();auto alias=server.client();auto weak=std::weak_ptr<Context>(alias.ctx);server.client().stop();server.client()=WiFiClient();check(!weak.expired() && !alias.connected(),"host alias holds stopped context");alias=WiFiClient();check(weak.expired(),"host final alias cleanup");}
 bool give=false;WiFiClient handed;server.addHook([&](const String&,const String& uri,WiFiClient* c,ESP8266WebServer::ContentTypeFunction){if(give && uri=="/lab-given"){handed=*c;return ESP8266WebServer::CLIENT_IS_GIVEN;}return ESP8266WebServer::CLIENT_REQUEST_CAN_CONTINUE;});
 clearOwner();{Peer p;give=true;p.send(req("/lab-given"));arrival();auto stopCount=stops.load();poll();check(!server.client() && handed.connected() && stops==stopCount,"actual CLIENT_IS_GIVEN transfer preserves held connection");handed.stop();handed=WiFiClient();give=false;}
#if LAB_OVERLAY
 clearOwner();host_ms=0;{Peer slow,ready;slow.send("GET /");arrival();poll();ready.send(req("/api/v1/bridge/status",auth));arrival();
#if LAB_CORRECTED
 auto terminalStops=stops.load();auto state=FslessMetrics::snapshot();host_ms=30;poll();check(bool(server.client()) && stops==terminalStops,"R5 partial owner retained at exact30 grace");host_ms=31;poll();check(!server.client() && stops==terminalStops+1,"R5 partial owner one terminal stop at31");poll();check(status(ready.receive(),200),"R5 ready served next poll after31");check(FslessMetrics::snapshot().lastReceivedMs==state.lastReceivedMs,"R5 interrupted owner preserves application state");
#else
 host_ms=1001;poll();check(bool(server.client()) && !ready.readable(),"R5 exact partial-owner ready-competitor at1001ms");host_ms=2000;poll();check(!server.client(),"R5 exact partial owner deadline release");poll();check(status(ready.receive(),200),"R5 exact ready client dispatch after release");
#endif
}
 // Media deny-all, conservative over-reservation and exact first-line byte boundaries including CRLF.
 auto mediaBefore=FslessMetrics::snapshot();auto beforeMediaBytes=bytesRead.load();auto mediaStops=stops.load();auto media=transact(req("/api/v2/bridge/media",auth,std::string(4096,'x'),"POST"));check(media.empty() && bytesRead.load()-beforeMediaBytes==std::string("POST /api/v2/bridge/media HTTP/1.1\r\n").size(),"media deny consumes first line only leaves headers body unread");poll();check(stops==mediaStops+2,"media close once plus explicit test setup stop");
 for(auto target:{"/api/v2/bridge/media","/api/v2/bridge/mediax","/?q=/api/v2/bridge/media","/api/v2/bridge/%6dedia","/api/v2/bridge/%256dedia"}){auto r=transact(req(target,auth));
#if LAB_CORRECTED
 if(std::string(target)=="/api/v2/bridge/mediax")check(status(r,404),"R6 mediax outside namespace raw404");else if(std::string(target)=="/?q=/api/v2/bridge/media")check(status(r,200),"R6 media query value reaches dashboard");else check(r.empty(),"R6 namespace alias denied terminally");
#else
 if(std::string(target).find("%256d")!=std::string::npos)check(status(r,404),"nested encoding retained raw routes");else check(r.empty(),"media and over-reservation terminal deny without response");
#endif
}
 for(auto target:{"/?x=100%","/?x=%00","/?x=%ff","/?x=%2","/?x=%20","/?x=%25"}){auto r=transact(req(target,auth));bool accepted=LAB_CORRECTED || std::string(target)=="/?x=%20" || std::string(target)=="/?x=%25";check(accepted?status(r,200):r.empty(),"R6 escape compatibility classification");}
 for(size_t len:{130u,131u}){clearOwner();Peer p;std::string line="GET /"+std::string(len-16,'x')+" HTTP/1.1\r\n";check(line.size()==len,"boundary fixture exact length");p.send(line+std::string(auth)+"\r\n");arrival();for(int i=0;i<3;i++){auto b=bytesRead.load(),w=bytesWritten.load();poll();if(w==bytesWritten.load())maxPreparseOnlyBytes=std::max(maxPreparseOnlyBytes,bytesRead.load()-b);}auto r=p.receive();check(len==130?status(r,404):r.empty(),"130 accepted 131 denied");}
 // Every split of CRLF/percent escape and terminal media followed by legacy.
 for(auto text:{std::string("GET /api/v2/bridge/%6dedia HTTP/1.1\r\n"),std::string("GET /api/v2/bridge/media HTTP/1.1\r\n")})for(size_t split=1;split<text.size();split++){clearOwner();Peer p;p.send(text.substr(0,split));arrival();poll();p.send(text.substr(split)+std::string(auth)+"\r\n");arrival();poll();check(p.receive(5).empty(),"split media deny-all");}
 clearOwner();host_ms=UINT32_MAX-1000u;{Peer p;p.send("GET /");arrival();poll();host_ms=998;poll();check(bool(server.client()),"wrap elapsed1999 pending");host_ms=999;poll();check(!server.client(),"wrap elapsed2000 terminal");}
 clearOwner();host_ms=0;{Peer p;p.send("GET /");arrival();poll();for(host_ms=100;host_ms<2000;host_ms+=100){p.send("x");arrival();poll();}host_ms=2000;poll();check(!server.client(),"trickling does not extend absolute line deadline");}
 clearOwner();host_ms=0;{Peer p;p.send(req("/api/v2/bridge/media",auth)+req("/api/v1/bridge/status",auth));arrival();poll();check(p.receive().empty() && !server.client(),"media then legacy pipeline terminal no fallthrough");}
 clearOwner();{Peer p;p.send(req("/api/v1/bridge/status",auth)+req("/api/v2/bridge/media",auth));arrival();poll();check(status(p.receive(),200),"legacy before media response");poll();check(p.receive().empty() && !server.client(),"legacy then media pipeline terminal");}
 check(FslessMetrics::snapshot().cpu==mediaBefore.cpu && FslessMetrics::snapshot().lastReceivedMs==mediaBefore.lastReceivedMs,"all denied media preserves actual metric state");
#else
 check(status(transact(req("/?x=100%",auth)),200),"R6 stock accepts unrelated literal percent query");
#endif

 // R6 same public request vectors in stock, previous and corrected composition.
 for(auto target:{"/?literal=100%","/?bad=%GG&short=%2","/?x=%00%ff","/?x=%2fapi%2fv2%2fbridge%2fmedia","/ui.js?cache=100%","/api/v1/bridge/status?q=/api/v2/bridge/media"}) {
   auto r=transact(req(target,auth));check((!LAB_OVERLAY || LAB_CORRECTED)?status(r,200):r.empty(),"R6 legacy query differential");
 }
 for(auto target:{"/api/v2/bridge/mediax","/other/api/v2/bridge/media","/api/v2/bridge/media.json"}) {
   auto r=transact(req(target,auth));check((!LAB_OVERLAY || LAB_CORRECTED)?status(r,404):r.empty(),"R6 segment and anchored path differential");
 }
 for(auto target:{"/api/v2/bridge/media","/api/v2/bridge/media/","/api/v2/bridge/media/begin/x?bad=%GG","/api/v2/bridge/%6Dedia","/api%2fv2%2fbridge%2fmedia","/api/v2/bridge/%256dedia","/api//v2/bridge/media","/api/v2/bridge/./media","/api/v2/bridge/media%2fbegin","/api/v2/bridge/media%00","/api/v2/bridge/media%","/api/v2/bridge/media%2","/api/v2/bridge/media%GG","/api/v2/bridge/media%3fx","/api/v2/bridge/media;begin=x","/api/v2/bridge/media%20begin"}) {
   auto state=FslessMetrics::snapshot();auto r=transact(req(target,auth));
   if(LAB_CORRECTED)check(r.empty() && !server.client(),"R6 reserved and ambiguous aliases terminal deny");
   check(FslessMetrics::snapshot().cpu==state.cpu && FslessMetrics::snapshot().lastReceivedMs==state.lastReceivedMs,"R6 path differential preserves state");
 }
#if LAB_CORRECTED
 // Partial FIN reaches one stop without test cleanup masking the result.
 clearOwner();host_ms=0;{Peer p;p.send("GET /");arrival();poll();auto n=stops.load();p.fin();std::this_thread::sleep_for(std::chrono::milliseconds(2));poll();poll();check(!server.client() && stops==n+1,"R5 partial FIN exactly one terminal stop");}
 clearOwner();host_ms=0;{Peer p;poll();auto n=stops.load();p.fin();std::this_thread::sleep_for(std::chrono::milliseconds(2));poll();poll();check(!server.client() && stops==n+1,"R5 empty FIN exactly one terminal stop");}
 // Grace subtraction and absolute deadline are independently wrap-safe.
 clearOwner();host_ms=UINT32_MAX-10u;{Peer p,ready;p.send("GET /");arrival();poll();ready.send(req("/api/v1/bridge/status",auth));arrival();host_ms=19;poll();check(bool(server.client()),"R5 wrapped elapsed30 retains");host_ms=20;poll();check(!server.client(),"R5 wrapped elapsed31 releases");poll();check(status(ready.receive(),200),"R5 wrapped competitor dispatch");}
 // A delayed partial request on an existing keep-alive owner is interrupted.
 clearOwner();host_ms=0;{Peer p;p.send(req("/api/v1/bridge/status",auth));arrival();poll();p.receive();host_ms=10;p.send("GET /");arrival();poll();Peer ready;ready.send(req("/api/v1/bridge/fs-plan",auth));arrival();host_ms=30;poll();check(bool(server.client()),"R5 keepalive exact30 retained");host_ms=31;poll();check(!server.client(),"R5 keepalive partial released at31");poll();check(status(ready.receive(),200),"R5 keepalive competitor served");}
#endif
 host_ms=UINT32_MAX-1000u;check(status(transact(req("/api/v1/bridge/metrics",auth,sample,"POST")),200),"wrapped freshness sample accepted");host_ms=4999;check(!FslessMetrics::stale(),"wrapped elapsed6000 fresh");host_ms=5000;check(FslessMetrics::stale(),"wrapped elapsed6001 stale");
 clearOwner();host_ms=7200000;check(status(transact(req("/api/v1/bridge/metrics","Cookie: "+cookie+"\r\n")),403),"actual session absolute expiration");
 auto feeds=ESP.feeds,ticks=FactoryRollback::ticks;FirstBootBridge::loop();check(ESP.feeds==feeds+1 && FactoryRollback::ticks==ticks+1,"actual application loop returns to inert OEM tick and watchdog");
 clearOwner();server.getServer().close();check(contexts==destroyed && liveSockets==0,"all host socket contexts and descriptors cleaned");
 std::cout<<"{\"checks\":"<<checks<<",\"failed\":"<<failed<<",\"polls\":"<<polls<<",\"max_poll_bytes\":"<<maxPollBytes<<",\"max_preparse_only_bytes\":"<<maxPreparseOnlyBytes<<",\"worst_poll_us\":"<<worstPollUs<<",\"worst_poll_to_first_response_write_us\":"<<worstFirstResponseUs<<",\"deadline_handoff_us\":"<<deadlineHandoffUs<<",\"max_transaction_us\":"<<maxDispatchUs<<",\"max_peer_lifetime_us\":"<<maxClientLifetimeUs<<",\"max_context_lifetime_us\":"<<maxContextLifetimeUs<<",\"ready_client_injected_clock_wall_wait_us\":"<<readyWaitUs<<",\"ready_client_real_clock_wait_ms\":"<<realReadyWaitMs<<",\"allocations\":"<<allocs<<",\"deallocations\":"<<frees<<",\"contexts_created\":"<<contexts<<",\"contexts_destroyed\":"<<destroyed<<",\"explicit_stops\":"<<stops<<",\"bytes_read\":"<<bytesRead<<",\"bytes_written\":"<<bytesWritten<<",\"peak_live_sockets\":"<<peakSockets<<",\"stock_ready_grace_ms\":"<<HTTP_MAX_DATA_AVAILABLE_WAIT<<",\"overlay_ready_release_tick_ms\":"<<((LAB_OVERLAY && !LAB_CORRECTED)?2000:31)<<",\"poll_byte_histogram\":{";bool comma=false;for(auto [count,frequency]:pollByteHistogram){if(comma)std::cout<<',';std::cout<<'"'<<count<<"\":"<<frequency;comma=true;}std::cout<<"}}\n";
 return failed?1:0;
}
