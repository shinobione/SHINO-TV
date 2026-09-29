// Executes unchanged FirstBootBridge.cpp, FslessMetrics.cpp and FslessWebUI.cpp.
// Dispatch/auth decisions and hardware dependencies are host test seams.
#include <iostream>
#include "../firmware/src/boot/FirstBootBridge.cpp"
uint32_t host_ms=0;
static int checks=0,failed=0;
static void check(bool ok,const char* name){checks++;if(!ok){failed++;std::cerr<<"FAIL "<<name<<"\n";}}
static bool unchanged(const FslessMetrics::Snapshot& a,const FslessMetrics::Snapshot& b){
 return a.cpu==b.cpu && a.gpu==b.gpu && a.memoryGb==b.memoryGb && a.gpuTempC==b.gpuTempC && a.lastReceivedMs==b.lastReceivedMs;
}
int main(){
 FirstBootBridge::run();
 check(server.started && !WiFi.persisted,"actual bridge route registration and nonpersistent AP seam");
 check(server.routes.count({"/api/v2/bridge/media",HTTP_POST})==0,"no active media route");
 check(FslessMetrics::stale(),"no sample stale");
 server.dispatch("/",HTTP_GET);check(server.code==401 && server.challenges==1,"dashboard requires auth");
 server.authorized=true;server.dispatch("/",HTTP_GET);
 check(server.code==200 && server.body.find("SHINO")!=String::npos,"actual PROGMEM dashboard bytes");
 String cookie=server.outHeaders["Set-Cookie"];
 check(cookie.find("HttpOnly; SameSite=Strict")!=String::npos,"read cookie flags");
 check(server.outHeaders.count("Content-Security-Policy")==1,"dashboard CSP");
 cookie=cookie.substring(0,cookie.indexOf(';'));server.headers["Cookie"]=cookie;server.authorized=false;
 int auth=server.authCalls, challenges=server.challenges;
 server.dispatch("/ui.js",HTTP_GET);check(server.code==200 && server.authCalls==auth,"session script read without auth challenge");
 server.dispatch("/api/v1/bridge/metrics",HTTP_GET);check(server.code==200 && server.challenges==challenges,"metrics read session preserves nonce");
 server.plain=R"({"ok":true,"gpu_available":true,"cpu_usage":12,"gpu_usage":34,"memory_used_gb":5,"memory_total_gb":16,"gpu_vram_mb":123,"gpu_temp_c":67,"gpu_power":80})";
 auto before=FslessMetrics::snapshot();server.dispatch("/api/v1/bridge/metrics",HTTP_POST);
 check(server.code==401 && unchanged(before,FslessMetrics::snapshot()),"cookie cannot authorize metrics POST");
 server.authorized=true;host_ms=100;server.dispatch("/api/v1/bridge/metrics",HTTP_POST);
 auto good=FslessMetrics::snapshot();check(server.code==200 && good.cpu==12 && good.gpu==34 && good.memoryGb==5 && good.gpuTempC==67,"four actual numeric metrics");
 check(good.lastReceivedMs==100 && !FslessMetrics::stale(),"accepted freshness timestamp");
 paintNativeDashboard();check(String(lastNumbers[0])=="12.0%" && String(lastNumbers[1])=="34.0%" && String(lastNumbers[2])=="5.0 GB" && String(lastNumbers[3])=="67.0","actual four-card formatting with no-op gfx");
 for(const auto& bad: {String(385,'x'),String("{\"invalid\":true}"),String("{this is not json}")}){
   server.plain=bad;server.dispatch("/api/v1/bridge/metrics",HTTP_POST);
   check((server.code==413 || server.code==422) && unchanged(good,FslessMetrics::snapshot()),"malformed payload leaves metrics/freshness intact");
 }
 host_ms=6100;check(!FslessMetrics::stale(),"6000ms inclusive freshness");host_ms=6101;check(FslessMetrics::stale(),"6001ms stale boundary");
 FirstBootBridge::loop();check(lastNumbers[0][0]==0 && lastNumbers[1][0]==0 && lastNumbers[2][0]==0 && lastNumbers[3][0]==0,"stale neutral four cards");
 check(ESP.feeds==1 && FactoryRollback::ticks==1 && server.loops==1,"actual loop delegation ordering seams");
 server.authorized=false;server.clientFixture.peer.value=2;server.dispatch("/api/v1/bridge/metrics",HTTP_GET);
 check(server.code==403,"cookie bound to peer");server.clientFixture.peer.value=1;
 server.headers["Cookie"]=cookie+"; "+cookie;server.dispatch("/api/v1/bridge/metrics",HTTP_GET);check(server.code==403,"duplicate read cookie rejects");
 server.headers["Cookie"]=String(257,'x');server.dispatch("/api/v1/bridge/metrics",HTTP_GET);check(server.code==403,"cookie length cap");
 server.headers["Cookie"]=cookie;host_ms=7200000;server.dispatch("/api/v1/bridge/metrics",HTTP_GET);check(server.code==403,"read session absolute expiration");
 check(server.challenges==challenges+1,"background failures do not rotate Digest challenge");
 for(const char* path:{"/api/v1/bridge/status","/api/v1/bridge/fs-plan","/api/v1/bridge/factory-return"}){
  server.dispatch(path,HTTP_GET);check(server.code==401,"diagnostic/OEM auth required");
 }
 check(FactoryRollback::statuses==0,"denied OEM status has no delegation");
 server.authorized=true;server.dispatch("/api/v1/bridge/factory-return",HTTP_GET);check(FactoryRollback::statuses==1,"authorized OEM status delegation only");
#if SHINO_ENABLE_FACTORY_RESTORE
 check(server.routes.count({"/api/v1/bridge/factory-return",HTTP_POST})==1,"conditional OEM POST registration");
 server.authorized=false;server.dispatch("/api/v1/bridge/factory-return",HTTP_POST);check(FactoryRollback::completions==0,"conditional OEM completion denied");
 auto& route=server.routes.at({"/api/v1/bridge/factory-return",HTTP_POST});route.upload();check(FactoryRollback::uploads==1 && !FactoryRollback::uploadAuthorized,"upload receives denied auth decision");
 server.authorized=true;server.dispatch("/api/v1/bridge/factory-return",HTTP_POST);route.upload();check(FactoryRollback::completions==1 && FactoryRollback::uploadAuthorized,"conditional authorized delegation with inert OEM seam");
#else
 check(server.routes.count({"/api/v1/bridge/factory-return",HTTP_POST})==0,"default OEM POST absent");
#endif
 server.dispatch("/api/v1/bridge/status",HTTP_GET);check(server.code==200 && server.body.find("FIRST_BOOT_BRIDGE")!=String::npos,"actual status JSON");
 server.dispatch("/api/v1/bridge/fs-plan",HTTP_GET);check(server.code==200 && server.body.find("READ_ONLY_FS_MIGRATION_PLAN")!=String::npos,"actual FS-plan JSON");
 server.dispatch("/api/v1/bridge/ota/capabilities",HTTP_GET);check(server.code==200 && server.body.find("\"native_ota_writer_compiled\":false")!=String::npos,"read-only OTA capability JSON");
 check(unchanged(good,FslessMetrics::snapshot()),"all unrelated handlers preserve metrics timestamp");
 std::cout<<"{\"actual_bridge_checks\":"<<checks<<",\"failed\":"<<failed<<",\"conditional_oem\":"<<SHINO_ENABLE_FACTORY_RESTORE<<"}\n";
 return failed?1:0;
}
