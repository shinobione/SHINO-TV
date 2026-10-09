// Actual StageA + pinned HTTP handler/destructor lifecycle, host loopback only.
static int maintenanceCases(){
 using namespace ShinoInstall;
 auto& owner=M9NormalStageA::maintenance;
 using Owner=std::remove_reference_t<decltype(owner)>;
 const char* id="0123456789abcdef";const char* build="aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa";
 uint8_t key[32];std::memset(key,0x73,sizeof key); // Host-only inert consent.
 check(!owner.request({id,build,key,false}),"owner consent required");
 check(!owner.request({nullptr,build,key,true}),"identity required");
 uint8_t zero[32]{};check(!owner.request({id,build,zero,true}),"no default zero key");
 const std::string path="/api/v1/bridge/metrics";
 const std::string payload=R"({"ok":true,"gpu_available":true,"cpu_usage":22.5,"gpu_usage":34.5,"memory_used_gb":8,"memory_total_gb":16,"gpu_vram_mb":2048,"gpu_temp_c":56,"gpu_power":120})";
 for(unsigned cycle=0;cycle<12;++cycle){
  auto challenge=transact(request("/status"));
  check(status(transact(request(path,digest(challenge,"POST",path),payload,"","POST")),200),"StageA sample before maintenance");
  unsigned beforePosts=posts;
  // Active unfinished HTTP plus queued accepted contexts must all be aborted.
  Peer active;active.send("GET /status HTTP/1.1\r\n");server.handleClient();
  Peer queued1,queued2;server.getServer().hasClient();
  check(owner.request({id,build,key,true}),"trusted maintenance request queued");
  check(!owner.request({id,build,key,true}),"duplicate request rejected");
  check(uploadObjects==0 && liveSockets>0,"no destruction inside request callback");
  M9NormalStageA::loop();
  check(owner.mode()==Owner::Uploading && uploadObjects==1,"real controller switches once");
  check(liveSockets==0 && contexts==destroyed,"HTTP active and queued contexts released");
  check(posts==beforePosts,"telemetry paused during maintenance");
  host_ms+=6001;M9NormalStageA::loop();
  check(FslessMetrics::stale(),"TTL advances honestly while paused");
  uploadFail=true;M9NormalStageA::loop();uploadFail=false;
  check(owner.mode()==Owner::Normal && uploadObjects==0,"abort reconstructs one normal owner");
  // Old nonce must not authenticate the reconstructed owner; fresh challenge works.
  check(status(transact(request("/status",digest(challenge,"GET","/status"))),401),"old nonce invalid after reconnect");
  challenge=transact(request("/status"));
  check(status(transact(request("/status",digest(challenge,"GET","/status"))),200),"fresh Digest after reconnect");
  check(status(transact(request(path,digest(challenge,"POST",path),payload,"","POST")),200),"one shot telemetry recovery");
 }
 check(owner.request({id,build,key,true}),"cancel pending");owner.cancel();check(owner.mode()==Owner::Normal,"pending cancel preserves normal");
 uploadBegin=false;check(owner.request({id,build,key,true}),"begin fail requested");M9NormalStageA::loop();uploadBegin=true;
 check(owner.mode()==Owner::Normal && uploadObjects==0,"listener begin fail reconstructs normal");
 check(owner.request({id,build,key,true}),"active cancel requested");M9NormalStageA::loop();owner.cancel();check(owner.mode()==Owner::Normal,"active cancel restores");
 check(owner.request({id,build,key,true}),"floor fail requested");lab_heap=20479;M9NormalStageA::loop();lab_heap=32000;
 check(owner.mode()==Owner::Hold && uploadObjects==0 && liveSockets==0,"unsafe restore is terminal HOLD");
 check(!owner.request({id,build,key,true}),"HOLD cannot silently retry");
 std::cout<<"{\"checks\":"<<checks<<",\"cycles\":12,\"active_and_queued_clients_released\":true,\"real_stagea_handlers\":true,\"real_core_destructor\":true,\"radio_sdk_upload_pump\":\"MOCKED\",\"device_contacts\":0}";
 return 0;
}
