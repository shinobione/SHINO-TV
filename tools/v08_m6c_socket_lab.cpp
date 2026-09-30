// Shared TCP instrumentation and actual source composition, no fixture edits.
#define main mission6a_historical_main
#include "v08_m6a_socket_lab.cpp"
#undef main

static std::string proof(const std::string& challenge,const std::string& method,const std::string& uri,const std::string& nc="00000001",const std::string& cn="public-fixture") {
 auto n=parameter(challenge,"nonce"),o=parameter(challenge,"opaque");
 auto h1=md5(String(SHINO_RESCUE_HTTP_USER)+":SHINO-FirstBoot:"+SHINO_RESCUE_HTTP_PASSWORD);
 auto h2=md5(String(method)+":"+uri.c_str());
 auto r=md5(String(h1)+":"+n.c_str()+":"+nc.c_str()+":"+cn.c_str()+":auth:"+h2.c_str());
 return "Authorization: Digest username=\"lab\", realm=\"SHINO-FirstBoot\", nonce=\""+n+"\", uri=\""+uri+"\", response=\""+r+"\", opaque=\""+o+"\", qop=auth, nc="+nc+", cnonce=\""+cn+"\"\r\n";
}
static std::string challenge(){return transact(req("/api/v1/bridge/status"));}
static void outcome(const std::string& response,bool,const char* name){check(LAB_R7?!status(response,200):status(response,200),name);}
#if LAB_R7
struct R7Probe:ESP8266WebServer {
 R7Probe():ESP8266WebServer(0){}
 using ESP8266WebServer::_r7Line; using ESP8266WebServer::_r7Body;
 using ESP8266WebServer::_r7Work; using ESP8266WebServer::_v08Started;
};
#endif
int main(){
#ifdef _WIN32
 WSADATA w;WSAStartup(MAKEWORD(2,2),&w);
#endif
 FirstBootBridge::run();
 auto dash=transact(req("/",auth)); check(status(dash,200) && dash.find("SHINO")!=dash.npos,"actual dashboard and CSP session");
 auto cookie=cookieFrom(dash);
 for(auto target:{"/ui.js","/api/v1/bridge/metrics","/api/v1/bridge/ota/capabilities"}) check(status(transact(req(target,"Cookie: "+cookie+"\r\n")),200),"GET browser session routes");
 for(auto target:{"/api/v1/bridge/status","/api/v1/bridge/fs-plan","/api/v1/bridge/ota/capabilities","/api/v1/bridge/factory-return"}) check(status(transact(req(target,auth)),200),"actual protected diagnostics and inert OEM GET");
 check(status(transact(req("/api/v1/bridge/status","Cookie: "+cookie+"\r\n")),401),"status retains authentication policy");
 auto stamp=FslessMetrics::snapshot().lastReceivedMs;
 check(status(transact(req("/api/v1/bridge/metrics","Cookie: "+cookie+"\r\n",sample,"POST")),401) && FslessMetrics::snapshot().lastReceivedMs==stamp,"cookie never authenticates POST");
 host_ms=100; check(status(transact(req("/api/v1/bridge/metrics",auth,sample,"POST")),200),"Basic metrics POST preserved");
 auto s=FslessMetrics::snapshot();check(s.cpu==12 && s.gpu==34 && s.memoryGb==5 && s.gpuTempC==67 && s.lastReceivedMs==100,"four numeric metrics unchanged");
 paintNativeDashboard();check(String(lastNumbers[0])=="12.0%" && String(lastNumbers[1])=="34.0%" && String(lastNumbers[2])=="5.0 GB" && String(lastNumbers[3])=="67.0","four display values unchanged");
 host_ms=6100;check(!FslessMetrics::stale(),"exact6000 fresh");host_ms=6101;check(FslessMetrics::stale(),"exact6001 stale");
 host_ms=UINT32_MAX-1000u;check(status(transact(req("/api/v1/bridge/metrics",auth,sample,"POST")),200),"wrap sample");host_ms=4999;check(!FslessMetrics::stale(),"wrap6000 fresh");host_ms=5000;check(FslessMetrics::stale(),"wrap6001 stale");
 for(auto body:{std::string(385,'x'),std::string("{broken}"),std::string("{\"invalid\":true}")}){auto before=FslessMetrics::snapshot().lastReceivedMs;auto r=transact(req("/api/v1/bridge/metrics",auth,body,"POST"));check((status(r,413)||status(r,422)) && FslessMetrics::snapshot().lastReceivedMs==before,"invalid metrics retain state");}
 outcome(transact(req("/","Authorization: Basic!"+std::string(auth.substr(21)))),true,"Basic! differential");
 auto c=challenge();outcome(transact(req("/api/v1/bridge/status",proof(c,"GET","/different"))),true,"Digest wrong-target differential");
 c=challenge();auto p=proof(c,"GET","/api/v1/bridge/status");check(status(transact(req("/api/v1/bridge/status",p)),200),"valid Digest GET positive control");
 outcome(transact(req("/api/v1/bridge/status",p)),true,"same-target nc replay differential");
 c=challenge();p=proof(c,"GET","/api/v1/bridge/status");check(status(transact(req("/api/v1/bridge/status",p)),200),"nc first proof");
 check(status(transact(req("/api/v1/bridge/status",proof(c,"GET","/api/v1/bridge/status","00000002"))),200),"increasing nc accepted");
 outcome(transact(req("/api/v1/bridge/status",proof(c,"GET","/api/v1/bridge/status","00000001","other"))),true,"cnonce switch cannot reset nc");
 c=challenge();p=proof(c,"GET","/api/v1/bridge/status?x=1");check(status(transact(req("/api/v1/bridge/status?x=1",p)),200),"raw query target positive control");
 c=challenge();outcome(transact(req("/api/v1/bridge/status?x=2",proof(c,"GET","/api/v1/bridge/status?x=1"))),true,"query target binding differential");
 check(LAB_R7?transact(req("/api/v1/bridge/status",auth+"Authorization: Basic invalid\r\n")).empty():status(transact(req("/api/v1/bridge/status",auth+"Authorization: Basic invalid\r\n")),401),"duplicate Authorization valid-first denial");
 outcome(transact(req("/api/v1/bridge/status",String("Authorization: Basic invalid\r\n")+auth)),true,"duplicate Authorization reversed differential");
 c=challenge();p=proof(c,"POST","/api/v1/bridge/metrics");auto changed=sample;changed.replace(changed.find("12"),2,"13");
 check(status(transact(req("/api/v1/bridge/metrics",p,changed,"POST")),200) && FslessMetrics::snapshot().cpu==13,"ACCEPTED LEGACY LIMITATION qop auth altered FIRST-use body");
 outcome(transact(req("/api/v1/bridge/metrics",p,sample,"POST")),true,"POST same proof replay differential");
 auto read=bytesRead.load();std::string body(4096,'x');auto text=req("/api/v1/bridge/metrics","",body,"POST");auto r=transact(text);
 size_t unauthorizedBody=bytesRead.load()-read-(text.size()-body.size());
 check(status(r,401) && unauthorizedBody==4096,"BLOCKED BY ARCHITECTURE 4096 body before401 persists");
 clearOwner();{Peer peer;peer.send("GET /api/v1/bridge/status HTTP/1.1\r\n"+std::string(auth)+"X-Incomplete:");arrival();peer.fin();poll();outcome(peer.receive(),true,"incomplete terminal-header differential");}
 for(auto framing:{std::string("Content-Length: 0\r\nContent-Length: 0\r\n"),std::string("Transfer-Encoding: chunked\r\nContent-Length: 0\r\n"),std::string("Content-Length: -1\r\n"),std::string("Content-Length: 4294967296\r\n")}){
   if(LAB_R7){auto before=bytesRead.load();auto line="POST /api/v1/bridge/metrics HTTP/1.1\r\n"+std::string(auth)+framing+"\r\n"+std::string(20,'x');auto out=transact(line);check(out.empty() && bytesRead.load()-before<line.size(),"ambiguous or excessive framing terminal beforebody");}
 }
 for(auto headers:{std::string("X-Large: ")+std::string(513,'x')+"\r\n",std::string("X-A: ")+std::string(500,'x')+"\r\nX-B: "+std::string(500,'x')+"\r\nX-C: "+std::string(500,'x')+"\r\nX-D: "+std::string(500,'x')+"\r\n"})outcome(transact(req("/api/v1/bridge/status",std::string(auth)+headers)),true,"line and aggregate header cap differential");
 if(LAB_R7){auto count=bytesRead.load();auto out=transact(req("/api/v1/bridge/metrics",auth,std::string(4097,'x'),"POST"));check(out.empty() && bytesRead.load()-count<200,"4097 declaration rejected beforebody");}
 if(LAB_R7){
   std::string headers="Host: loopback.invalid\r\nContent-Type: application/json\r\nContent-Length: 4096\r\n";
   while(headers.size()+2<2048){size_t remaining=2048-2-headers.size();size_t n=std::min(size_t(509),remaining-5);headers+="X: "+std::string(n,'x')+"\r\n";}
   check(headers.size()+2==2048,"exact aggregate header boundary fixture");
   auto before=bytesRead.load();auto out=transact("POST /api/v1/bridge/metrics HTTP/1.1\r\n"+headers+"\r\n"+std::string(4096,'x'));
   check(status(out,401) && bytesRead.load()-before==std::string("POST /api/v1/bridge/metrics HTTP/1.1\r\n").size()+2048+4096,"exact headerbody caps still consume unauthorizedbody BLOCKED");
 }
 c=challenge();outcome(transact(req("/api/v1/bridge/status",proof(c,"GET","/api/v1/bridge/status","00000000"))),true,"zero nc differential");
 if(LAB_R7){c=challenge();p=proof(c,"GET","/api/v1/bridge/status");auto bad=p;auto pos=bad.find("response=\"")+10;bad[pos]=bad[pos]=='a'?'b':'a';check(!status(transact(req("/api/v1/bridge/status",bad)),200),"invalid proof denied");}
 auto oem=transact(req("/api/v1/bridge/factory-return",auth,"{}","POST"));check(status(oem,SHINO_ENABLE_FACTORY_RESTORE?200:404),"conditional ordinary OEM POST policy unchanged inert");
#if SHINO_ENABLE_FACTORY_RESTORE
 std::string multipart="--b\r\nContent-Disposition: form-data; name=\"image\"; filename=\"fixture.txt\"\r\nContent-Type: text/plain\r\n\r\nPUBLIC\r\n--b--\r\n";
 for(auto h:{std::string(""),std::string(auth)}){auto before=FactoryRollback::uploads;auto count=bytesRead.load();auto upload="POST /api/v1/bridge/factory-return HTTP/1.1\r\n"+h+"Content-Type: multipart/form-data; boundary=b\r\nContent-Length: "+std::to_string(multipart.size())+"\r\n\r\n"+multipart;auto out=transact(upload);check(LAB_R7?out.empty() && FactoryRollback::uploads==before && bytesRead.load()-count==upload.size()-multipart.size():FactoryRollback::uploads==before+3 && status(out,h.empty()?401:200),"multipart differential BLOCKED compatibility: zero body callbacks only candidate");}
#endif
 // Pipelining and half-close use complete actual requests, not substitute dispatch.
 clearOwner();{Peer peer;peer.send(req("/api/v1/bridge/status",auth)+req("/api/v1/bridge/fs-plan",auth));arrival();poll();check(status(peer.receive(),200) && server.client().available()>0,"pipeline second unread");poll();check(status(peer.receive(),200),"pipeline second dispatch");}
 clearOwner();{Peer peer;peer.send(req("/api/v1/bridge/status",auth));arrival();peer.fin();poll();check(status(peer.receive(),200),"complete FIN response");}
 clearOwner();{Peer peer;peer.send(req("/api/v1/bridge/status",auth));arrival();poll();check(peer.receive().find("Connection: keep-alive")!=std::string::npos,"keepalive response");peer.send(req("/api/v1/bridge/fs-plan",auth));arrival();poll();check(status(peer.receive(),200),"delayed keepalive next request");}
 clearOwner();{Peer peer;peer.send(req("/api/v1/bridge/status",auth+"Connection: close\r\n"));arrival();poll();check(peer.receive().find("Connection: close")!=std::string::npos,"explicitclose response");host_ms+=HTTP_MAX_CLOSE_WAIT+1;poll();check(!server.client(),"explicitclose release");}
 for(bool reset:{false,true}){clearOwner();Peer peer;peer.send("POST /api/v1/bridge/metrics HTTP/1.1\r\n"+std::string(auth)+"Content-Length: 10\r\n\r\nshort");arrival();if(reset)peer.close(true);else peer.fin();auto before=FslessMetrics::snapshot().lastReceivedMs;poll();check(FslessMetrics::snapshot().lastReceivedMs==before,"interruptedbody state preserved");clearOwner();}
 // Preserve exact no-data R5 policy at 30/31 including rollover.
 for(uint32_t start:{0u,UINT32_MAX-10u}){
   // Stock unsigned long is host-width; only overlays cast subtraction to uint32_t.
   if(start && !LAB_OVERLAY) continue;
   clearOwner();host_ms=start;Peer slow,ready;poll();ready.send(req("/api/v1/bridge/status",auth));arrival();host_ms=start+30u;poll();check(bool(server.client()),"R5exact30 retains");host_ms=start+31u;poll();check(!server.client(),"R5exact31 releases");poll();check(status(ready.receive(),200),"R5competitor served");
 }
 clearOwner();lab_real_clock=true;lab_clock_origin=Clock::now();{Peer slow,ready;poll();auto start=Clock::now();ready.send(req("/api/v1/bridge/status",auth));arrival();while(!ready.readable() && Clock::now()-start<std::chrono::milliseconds(500)){poll();std::this_thread::sleep_for(std::chrono::milliseconds(1));}realReadyWaitMs=std::chrono::duration<double,std::milli>(Clock::now()-start).count();check(status(ready.receive(),200),"real competing ready response");}
 // Historical >2s header hold; candidate absolute cutoff, with no FIN shortcut.
 clearOwner();lab_clock_origin=Clock::now();{Peer peer;peer.send("GET /api/v1/bridge/status HTTP/1.1\r\nAuth");arrival();std::thread thread([&]{std::this_thread::sleep_for(std::chrono::milliseconds(2100));peer.send(std::string(auth.substr(4))+"\r\n");});deadlineHandoffUs=poll();thread.join();check(LAB_R7?peer.receive().empty() && deadlineHandoffUs<2300000:status(peer.receive(),200) && deadlineHandoffUs>=2000000,"absolute deadline or workcap slow header differential HOST timing");}
 if(LAB_R7){clearOwner();lab_clock_origin=Clock::now();Peer peer;peer.send("POST /api/v1/bridge/metrics HTTP/1.1\r\n"+std::string(auth)+"Content-Length: 10\r\n\r\nx");arrival();auto before=FslessMetrics::snapshot().lastReceivedMs;auto us=poll();check(us<2300000 && !server.client() && FslessMetrics::snapshot().lastReceivedMs==before,"absolute deadline or workcap declaredbody HOST only");}
 lab_real_clock=false;
#if LAB_OVERLAY
 clearOwner();host_ms=0;{Peer peer;peer.send("GET /");arrival();auto before=bytesRead.load();poll();check(bytesRead.load()-before==5,"partialline incremental read");host_ms=1999;poll();check(bool(server.client()),"firstline1999 retained");host_ms=2000;poll();check(!server.client(),"firstline2000 terminal");}
 for(int length:{130,131}){std::string text="GET /"+std::string(length-16,'a')+" HTTP/1.1\r\n"+std::string(auth)+"\r\n";auto out=transact(text);check(length==130?status(out,404):out.empty(),"firstline130131 boundary");}
#endif
#if LAB_R7
 // Execute the exact generated readers at deadline boundaries through TCP.
 for(uint32_t start:{0u,UINT32_MAX-1000u})for(uint32_t elapsed:{1999u,2000u}){
   clearOwner();Peer peer;peer.send("\r\nx");arrival();auto client=server.getServer().accept();R7Probe probe;
   probe._v08Started=start;probe._r7Work=8192;host_ms=start+elapsed;String line;size_t budget=2048;auto count=bytesRead.load();
   bool ok=probe._r7Line(client,line,budget);check(ok==(elapsed==1999) && bytesRead.load()-count==(elapsed==1999?2u:0u),"exact generated header reader 1999/2000 with rollover");
   probe._r7Work=8192;host_ms=start+2000;String out;count=bytesRead.load();check(!probe._r7Body(client,1,out) && bytesRead==count,"exact generated body reader deadline no-read rollover");client.stop();
 }
 clearOwner();{Peer peer;peer.send("X: x\r\n");arrival();auto client=server.getServer().accept();R7Probe probe;probe._v08Started=host_ms;probe._r7Work=0;String line;size_t budget=2048;auto count=bytesRead.load();check(!probe._r7Line(client,line,budget) && bytesRead==count,"zero workbudget no read");client.stop();}
#endif
 if(LAB_OVERLAY){auto count=bytesRead.load();auto out=transact(req("/api/v2/bridge/media",auth,std::string(4096,'x'),"POST"));check(out.empty() && bytesRead.load()-count==std::string("POST /api/v2/bridge/media HTTP/1.1\r\n").size(),"media DENY ALL before headersbody");}
 host_ms=7200000;check(status(transact(req("/api/v1/bridge/metrics","Cookie: "+cookie+"\r\n")),403),"absolute session expiry retained");
 auto feeds=ESP.feeds,ticks=FactoryRollback::ticks;FirstBootBridge::loop();check(ESP.feeds==feeds+1 && FactoryRollback::ticks==ticks+1,"actual application loop returns to OEM tick and watchdog inert");
 clearOwner();server.getServer().close();check(contexts==destroyed && liveSockets==0,"all descriptorscontexts cleanup");
 std::cout<<"{\"checks\":"<<checks<<",\"failed\":"<<failed<<",\"max_poll_bytes\":"<<maxPollBytes<<",\"worst_poll_us\":"<<worstPollUs<<",\"header_deadline_poll_us\":"<<deadlineHandoffUs<<",\"body_bytes_before_authorization\":"<<unauthorizedBody<<",\"competing_client_ms\":"<<realReadyWaitMs<<",\"contexts_created\":"<<contexts<<",\"contexts_destroyed\":"<<destroyed<<",\"live_descriptors\":"<<liveSockets<<",\"peak_descriptors\":"<<peakSockets<<"}\n";
 return failed?1:0;
}
