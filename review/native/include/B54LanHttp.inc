// Inserted ONLY into the generated B5.4-LAN graph; uses the existing server.
__attribute__((noinline)) void weatherError(int code,const __FlashStringHelper* body){
 server.sendHeader(F("Cache-Control"),F("no-store"));server.sendHeader(F("X-Content-Type-Options"),F("nosniff"));
 server.send_P(code,PSTR("application/json"),reinterpret_cast<PGM_P>(body));
}
class WeatherLease {
 bool held_;
public:
 WeatherLease():held_(B54LanNative::acquire()){}
 ~WeatherLease(){if(held_)B54LanNative::release();}
 explicit operator bool()const{return held_;}
};
__attribute__((noinline)) bool weatherHealthy(){
 M9NormalResources::Heap h{};core.heap(h);
 const auto stack=ESP.getFreeContStack();
 return !uploadBusy&&!diagnosticJournal.frozen()&&WiFi.status()==WL_CONNECTED&&
  !B5Lan::apPeer(server)&&h.free>=20480&&h.largest>=16384&&stack>=2048&&h.fragmentation<=25&&
  uint32_t(millis()-server.requestStarted())<2000&&server.client().connected()&&!server.waitingPeer();
}
__attribute__((noinline)) bool weatherPrebody(){
 const bool get=server.method()==HTTP_GET;
 uint32_t bytes=0;
 if(!B54LanNative::ready()||!configReady||!B5Lan::permitted(server)||!weatherHealthy()){
  weatherError(503,F("{\"error\":\"WEATHER_NOT_READY\"}"));return false;
 }
 if(!server.header("Transfer-Encoding").isEmpty()||!server.header("Expect").isEmpty()||
    !server.header("Origin").isEmpty()||!length(bytes)||
    (get?bytes!=0:(bytes!=80||server.header("Content-Length")!="80"||
      server.header("Content-Type")!="application/octet-stream"||server.args()!=0))){
  weatherError(413,F("{\"error\":\"WEATHER_FRAME_BOUND\"}"));return false;
 }
 return true; // Core body String is never reached: the parser already deferred.
}
void weatherBinary(){
 server.sendHeader(F("Cache-Control"),F("no-store"));server.sendHeader(F("X-Content-Type-Options"),F("nosniff"));
 server.setContentLength(80);server.send(200,"application/octet-stream","");
 server.sendContent(reinterpret_cast<const char*>(B54LanNative::buffer()),80);
}
__attribute__((noinline)) void weatherStatus(){
 WeatherLease lease;if(!lease){weatherError(503,F("{\"error\":\"WEATHER_BUSY\"}"));return;}
 uint8_t challenge[8]{};
 const auto& path=server.uri();
 if(!B54LanWeather::statusPath(path.c_str(),path.length(),challenge)){weatherError(400,F("{\"error\":\"CHALLENGE\"}"));return;}
 if(!weatherHealthy()||!B54LanNative::status(2,challenge)||!weatherHealthy()){
  weatherError(503,F("{\"error\":\"WEATHER_HOLD\"}"));return;
 }
 weatherBinary();
}
__attribute__((noinline)) void weatherReceive(){
 WeatherLease lease;if(!lease){weatherError(503,F("{\"error\":\"WEATHER_BUSY\"}"));return;}
 const uint32_t mark=micros();uint32_t last=millis();size_t at=0;
 auto& peer=server.client();
 while(at<80){
  if(!weatherHealthy()||uint32_t(millis()-last)>=300){
   B54LanNative::record(0x100,uint32_t(micros()-mark));weatherError(408,F("{\"error\":\"WEATHER_INTERRUPTED\"}"));return;
  }
  const size_t n=std::min(size_t(peer.available()),size_t(80-at));
  if(n){const int got=peer.read(B54LanNative::buffer()+at,n);if(got<=0)break;at+=size_t(got);last=millis();}
  else{ESP.wdtFeed();yield();}
 }
 if(at!=80||peer.available()||!weatherHealthy()){
  B54LanNative::record(0x101,uint32_t(micros()-mark));weatherError(400,F("{\"error\":\"WEATHER_BODY\"}"));return;
 }
 uint8_t challenge[8];memcpy(challenge,B54LanNative::buffer()+48,8);
 const auto result=B54LanNative::accept();
 B54LanNative::record(uint32_t(result),uint32_t(micros()-mark));
 if(result!=B54LanWeather::Result::Accepted){weatherError(409,F("{\"error\":\"WEATHER_REFUSED\"}"));return;}
 if(!weatherHealthy()||!B54LanNative::status(3,challenge)||!weatherHealthy()){
  B54LanNative::invalidate();weatherError(503,F("{\"error\":\"WEATHER_ACK_HOLD\"}"));return;
 }
 weatherBinary();
}
