// SPDX-License-Identifier: GPL-3.0-or-later
// Normal StageA services plus one persistent HTTP application-only updater.
#include "boot/ShinoBootProfile.h"
#include "boot/M9NormalStageA.h"
#include "boot/M9NormalResources.h"
#include "boot/M9NormalStatusJson.h"
#include "boot/M9LittleFsMountProbe.h"
#include "boot/FslessMetrics.h"
#include "config/ConfigManager.h"
#include "display/DisplayManager.h"
#include "wireless/WiFiManager.h"
#include <ESP8266WebServer.h>
#include "ShinoHttpOta.h"
#include "ShinoRelease.h"
static_assert(SHINO_BOOT_PROFILE==1 && SHINO_M9_NORMAL_QUALIFICATION==1 &&
              SHINO_ENABLE_FACTORY_RESTORE==0 && SHINO_ENABLE_NATIVE_SIGNED_OTA==0 &&
              SHINO_ENABLE_FS_MIGRATION==0,"Dedicated application-only normal firmware");
#if defined(ARDUINO_SIGNING) && ARDUINO_SIGNING
#error "This HMAC release profile cannot use global RSA signing"
#endif
namespace M9NormalDashboard {void render();}
namespace M9NormalStageA {
namespace {
ESP8266WebServer server(80);
WiFiManager network("","","SHINO-TV-StageA",SHINO_SETUP_AP_PSK);
struct CoreSource {
    void resetStack(){ESP.resetFreeContStack();}
    uint32_t stack(){return ESP.getFreeContStack();}
    void heap(M9NormalResources::Heap& h){ESP.getHeapStats(&h.free,&h.largest,&h.fragmentation);}
    uint32_t now(){return millis();}
} core;
M9NormalResources::Observer<CoreSource> observer(core);
bool begun=false,configReady=false,apReady=false,dirty=true,lastStale=true;
uint32_t lastDraw=0,uploadStart=0,uploadLast=0;
uint32_t uploadSamples=0;
char nonce[33]{},boot[33]{},runningSha[65]{};
const char* lastUpdate="NONE";
// Volatile read retains the complete public compile graph, with authority false
// and no setter. Owner builds initialize the same graph with private authority.
volatile const bool otaPermitted=SHINO_OTA_PRIVATE;
ShinoHttpOta::Budget minima{UINT32_MAX,UINT32_MAX,UINT32_MAX,0};
alignas(ShinoHttpOta::Transfer) uint8_t transferStorage[sizeof(ShinoHttpOta::Transfer)];
alignas(4) uint8_t transferBuffer[512];
ShinoHttpOta::Release incoming;
// One synchronous HTTP handler owns this scratch until respond() returns,
// including SDK yields. Reject nested use before changing its contents.
char responseBody[768];
bool responseBusy=false;
bool uploadBusy=false,uploadVerifying=false;
class UploadLease {
    bool held_;
public:
    UploadLease():held_(!uploadBusy){if(held_)uploadBusy=true;}
    ~UploadLease(){if(held_){uploadBusy=false;uploadVerifying=false;}}
    explicit operator bool()const{return held_;}
};
class ResponseLease {
    bool held_;
public:
    ResponseLease():held_(!responseBusy){if(held_)responseBusy=true;}
    ~ResponseLease(){if(held_)responseBusy=false;}
    explicit operator bool()const{return held_;}
    ResponseLease(const ResponseLease&)=delete;
    ResponseLease& operator=(const ResponseLease&)=delete;
};
constexpr char descriptor[]="SHINO-HTTP-OTA-1|" SHINO_OTA_DEVICE "|" SHINO_OTA_BUILD "|4m2m|APP_ONLY";
void randomNonce(char* out){uint8_t bytes[16];for(unsigned i=0;i<4;++i){uint32_t r=os_random();std::memcpy(bytes+4*i,&r,4);}ShinoHttpOta::encode(bytes,16,out);}
ShinoHttpOta::Budget budget(){ShinoHttpOta::Budget b{};ESP.getHeapStats(&b.heap,&b.block,&b.frag);b.stack=ESP.getFreeContStack();return b;}
bool uploadHealthy(){
    ++uploadSamples;
    const auto b=budget();minima.heap=std::min(minima.heap,b.heap);minima.block=std::min(minima.block,b.block);
    minima.stack=std::min(minima.stack,b.stack);minima.frag=std::max(minima.frag,b.frag);
    return b.safe()&&WiFi.getMode()==WIFI_AP&&uint32_t(millis()-uploadStart)<120000&&
           server.client().connected()&&(!uploadVerifying||!server.client().available());
}
void respond(int code,const char* body){
    server.sendHeader(F("Cache-Control"),F("no-store"));server.sendHeader(F("X-Content-Type-Options"),F("nosniff"));
    server.send(code,"application/json",body);
}
bool auth(){
    if(server.header("Authorization").startsWith("Digest ")&&server.authenticate(SHINO_RESCUE_HTTP_USER,SHINO_RESCUE_HTTP_PASSWORD))return true;
    server.requestAuthentication(DIGEST_AUTH,"SHINO-StageA");return false;
}
enum class Route:uint8_t{Closed,Normal,MetricsGet,MetricsPost,Identity,Upload};
Route route(){
    // String values stay owned by this function, before any authentication.
    const String path=server.uri();const auto method=server.method();
    if(method==HTTP_GET){
        if(path=="/status"||path=="/api/v1/m9/normal/status"||path=="/api/v1/m9/normal/resources")return Route::Normal;
        if(path=="/api/v1/bridge/metrics")return Route::MetricsGet;
        if(path=="/api/v1/update/status"||path=="/api/v1/m9/maintenance/result")return Route::Identity;
    }
    if(method==HTTP_POST){
        if(path=="/api/v1/bridge/metrics")return Route::MetricsPost;
        if(path=="/api/v1/update")return Route::Upload;
    }
    return Route::Closed;
}
bool length(uint32_t& n){
    const String s=server.header("Content-Length");n=0;
    if(s.isEmpty())return server.method()==HTTP_GET;
    for(size_t i=0;i<s.length();++i){if(s[i]<'0'||s[i]>'9'||n>ShinoHttpOta::MaxImage/10)return false;n=n*10+uint32_t(s[i]-'0');}
    return n<=ShinoHttpOta::MaxImage;
}
bool headerHex(const char* name,char* out,size_t n){const String s=server.header(name);if(!ShinoHttpOta::hex(s.c_str(),n))return false;std::memcpy(out,s.c_str(),n+1);return true;}
bool localPeer(){const auto p=server.client().remoteIP();return WiFi.getMode()==WIFI_AP&&server.client().localIP()==WiFi.softAPIP()&&p[0]==192&&p[1]==168&&p[2]==4&&p[3]>1&&p[3]<255;}
__attribute__((noinline)) void upload(uint32_t bytes){
    UploadLease lease;if(!lease){respond(503,"{\"error\":\"UPDATE_BUSY\"}");return;}
    incoming={};incoming.bytes=bytes;
    char* signature=reinterpret_cast<char*>(transferBuffer);char* requestNonce=signature+65;
    if(!otaPermitted||!configReady||!localPeer()||server.header("Content-Type")!="application/octet-stream"||
       !headerHex("X-Shino-SHA256",incoming.sha,64)||!headerHex("X-Shino-Build",incoming.build,64)||
       !headerHex("X-Shino-Nonce",requestNonce,32)||!headerHex("X-Shino-Proof",signature,64)||
       !ShinoHttpOta::equal(requestNonce,nonce,32)){
        respond(403,"{\"error\":\"UPDATE_AUTH_OR_COMPATIBILITY\"}");return;
    }
    uploadStart=uploadLast=millis();uploadSamples=0;minima={UINT32_MAX,UINT32_MAX,UINT32_MAX,0};
    auto* transfer=new(transferStorage) ShinoHttpOta::Transfer(uploadHealthy);
    const bool admitted=transfer->begin(incoming,SHINO_OTA_DEVICE,SHINO_OTA_BUILD,nonce,signature,ShinoReleaseKey,ESP.getSketchSize(),budget(),true);
    randomNonce(nonce); // One request token; no ARM state, retries or persisted state.
    if(!admitted){transfer->~Transfer();lastUpdate="REFUSED";respond(503,"{\"error\":\"UPDATE_REFUSED\"}");return;}
    lastUpdate="RECEIVING";bool ok=true;
    auto& client=server.client();client.setNoDelay(true);
    // Header/body split: the Core parser has not allocated a plain body String.
    while(transfer->received()<bytes){
        if(!client.connected()||uint32_t(millis()-uploadLast)>=5000||!uploadHealthy()){ok=false;break;}
        size_t count=std::min(size_t(512),std::min(size_t(client.available()),size_t(bytes-transfer->received())));
        if(transfer->received()==0&&count<4)count=0;
        if(count){
            const int n=client.read(transferBuffer,count);
            if(n<=0||!transfer->add(transferBuffer,size_t(n),budget())){ok=false;break;}
            uploadLast=millis();
        }
        ESP.wdtFeed();yield();
    }
    uploadVerifying=true;
    if(ok)ok=client.connected()&&!client.available()&&uploadHealthy()&&transfer->finish(budget());
    transfer->~Transfer();
    if(!ok){lastUpdate="FAILED_NO_COMMIT";respond(422,"{\"error\":\"UPDATE_FAILED_NO_COMMIT\"}");dirty=true;return;}
    lastUpdate="STAGED";
    char* receipt=reinterpret_cast<char*>(transferBuffer);std::snprintf(receipt,sizeof(transferBuffer),
        "{\"status\":\"STAGED_PENDING_BOOT\",\"heap_min\":%u,\"block_min\":%u,\"stack_min\":%u,\"frag_max\":%u,\"samples\":%u}",
        unsigned(minima.heap),unsigned(minima.block),unsigned(minima.stack),unsigned(minima.frag),unsigned(uploadSamples));
    respond(200,receipt);
    client.flush(1000);client.stop();delay(100);ESP.restart();
}
bool beforeBody(){
    server.keepAlive(false);
    const Route selected=route();uint32_t bytes=0;
    if(selected==Route::Upload){
        // HMAC binds the complete image identity and this one boot/request nonce.
        // It is the sole OTA credential; Digest remains normal telemetry auth.
        if(!server.header("Transfer-Encoding").isEmpty()||!server.header("Expect").isEmpty()||!length(bytes))respond(400,"{\"error\":\"HTTP_FRAMING\"}");
        else upload(bytes);
        return false;
    }
    if(!auth())return false;
    if(selected==Route::Closed){respond(404,"{\"error\":\"ROUTE_CLOSED\"}");return false;}
    if(!server.header("Transfer-Encoding").isEmpty()||!server.header("Expect").isEmpty()||!length(bytes)){
        respond(400,"{\"error\":\"HTTP_FRAMING\"}");return false;
    }
    if(server.method()==HTTP_GET&&bytes!=0){respond(400,"{\"error\":\"GET_BODY\"}");return false;}
    if(selected==Route::MetricsPost&&(bytes<16||bytes>384||server.header("Content-Type")!="application/json")){
        respond(413,"{\"error\":\"TELEMETRY_BOUND\"}");return false;
    }
    if(!configReady){respond(503,"{\"error\":\"READONLY_CONFIG_HOLD\"}");return false;}
    return true;
}
struct HttpSink {
    void begin(size_t bytes){server.sendHeader(F("Cache-Control"),F("no-store"));server.setContentLength(bytes);server.send(200,"application/json","");}
    void write(const char* p,size_t n){server.sendContent(p,n);}
};
void status(){
    // The legacy emit(s, sink) keeps a 512-byte JSON array on continuation
    // stack. This physical GET is part of the normal A qualification sequence
    // and its historical high-water survives into the next identity request.
    // Reuse the already-allocated 768-byte response workspace, sharing the
    // exact same reentrancy lease used by the identity/metrics endpoints.
    static_assert(sizeof(responseBody)>=M9NormalStatusJson::BUFFER_BYTES,
                  "Shared response scratch must fit every normal-status chunk");
    ResponseLease lease;if(!lease){respond(503,"{\"error\":\"RESPONSE_BUSY\"}");return;}
    const M9NormalStatusJson::Snapshot s{observer.status(),M9LittleFsMountProbe::status(),configReady,apReady};
    size_t total=0;
    for(unsigned i=0;i<4;++i){
        const int n=M9NormalStatusJson::part(responseBody,sizeof(responseBody),i,s);
        if(n<0||size_t(n)>=sizeof(responseBody)){respond(500,"{\"error\":\"STATUS_BOUND\"}");return;}
        total+=size_t(n);
    }
    HttpSink sink;sink.begin(total);
    for(unsigned i=0;i<4;++i){
        const int n=M9NormalStatusJson::part(responseBody,sizeof(responseBody),i,s);
        if(n<0||size_t(n)>=sizeof(responseBody)){
            // Header was already sent: terminate an inconsistent stream, do
            // not add a second JSON response or expose an invalid buffer span.
            server.client().stop();return;
        }
        sink.write(responseBody,size_t(n));
    }
}
void identity(){
    ResponseLease lease;if(!lease){respond(503,"{\"error\":\"RESPONSE_BUSY\"}");return;}
    const auto b=budget();const auto& f=M9LittleFsMountProbe::status();
    const int count=std::snprintf(responseBody,sizeof(responseBody),
        "{\"protocol\":\"shino-http-ota-1\",\"descriptor\":\"%s\",\"device\":\"%s\",\"build_id\":\"%s\","
        "\"boot_id\":\"%s\",\"nonce\":\"%s\",\"sha256\":\"%s\",\"bytes\":%u,\"ota_enabled\":%s,"
        "\"fs_ok\":%s,\"fs_files\":%u,\"fs_bytes\":%u,\"metrics_fresh\":%s,"
        "\"heap\":%u,\"block\":%u,\"stack\":%u,\"frag\":%u,\"last_update\":\"%s\","
        "\"ota_heap_min\":%u,\"ota_block_min\":%u,\"ota_stack_min\":%u,\"ota_frag_max\":%u}",
        descriptor,SHINO_OTA_DEVICE,SHINO_OTA_BUILD,boot,nonce,runningSha,unsigned(ESP.getSketchSize()),
        SHINO_OTA_PRIVATE?"true":"false",f.mounted&&f.inventory_exact&&f.config_seed_exact?"true":"false",
        unsigned(f.checked_file_count),unsigned(f.checked_payload_bytes),!FslessMetrics::stale()?"true":"false",
        unsigned(b.heap),unsigned(b.block),unsigned(b.stack),unsigned(b.frag),lastUpdate,
        unsigned(minima.heap==UINT32_MAX?0:minima.heap),unsigned(minima.block==UINT32_MAX?0:minima.block),
        unsigned(minima.stack==UINT32_MAX?0:minima.stack),unsigned(minima.frag));
    if(count<0||size_t(count)>=sizeof(responseBody)){respond(500,"{\"error\":\"IDENTITY_BOUND\"}");return;}
    respond(200,responseBody);
}
void telemetry(){
    const String payload=server.arg("plain");JsonDocument doc;
    if(deserializeJson(doc,payload)){respond(422,"{\"error\":\"JSON\"}");return;}
    String error;if(!FslessMetrics::apply(doc.as<JsonVariantConst>(),error)){respond(422,"{\"error\":\"TELEMETRY\"}");return;}
    dirty=true;respond(200,"{\"status\":\"RAM_SAMPLE_ACCEPTED\",\"persisted\":false}");
}
void metrics(){
    ResponseLease lease;if(!lease){respond(503,"{\"error\":\"RESPONSE_BUSY\"}");return;}
    JsonDocument doc;FslessMetrics::describe(doc);
    if(measureJson(doc)>=sizeof(responseBody)){respond(500,"{\"error\":\"METRICS_BOUND\"}");return;}
    serializeJson(doc,responseBody,sizeof(responseBody));respond(200,responseBody);
}
bool hashRunning(){
    const uint32_t size=ESP.getSketchSize();if(size<64000||size>ShinoHttpOta::MaxImage)return false;
    br_sha256_context h;br_sha256_init(&h);
    for(uint32_t at=0;at<size;at+=sizeof(transferBuffer)){
        const uint32_t n=std::min(uint32_t(sizeof(transferBuffer)),size-at);
        if(!ESP.flashRead(at,reinterpret_cast<uint32_t*>(transferBuffer),n))return false;
        br_sha256_update(&h,transferBuffer,n);yield();
    }
    uint8_t digest[32];br_sha256_out(&h,digest);ShinoHttpOta::encode(digest,32,runningSha);return true;
}
} // namespace
void beforeSetup(){observer.beforeSetup();}
void begin(ConfigManager& config){
    if(begun)return;
    begun=true;DisplayManager::begin(0);observer.beforeFs();M9LittleFsMountProbe::begin();
    const auto& f=M9LittleFsMountProbe::status();configReady=config.loadMountedReadOnly(f.mounted&&f.inventory_exact&&f.config_seed_exact);
    observer.afterFs();if(configReady)config.setApiToken(SHINO_BOOTSTRAP_API_TOKEN);
    if(!hashRunning())configReady=false;
    randomNonce(boot);randomNonce(nonce);
    WiFi.persistent(false);apReady=network.startAccessPointMode();if(!apReady)return;
    server.collectHeaders("Authorization","Content-Length","Content-Type","Transfer-Encoding","Expect", "X-Shino-SHA256","X-Shino-Build","X-Shino-Nonce","X-Shino-Proof");
    server.setStageAPrebody(beforeBody);
    server.on("/status",HTTP_GET,status);server.on("/api/v1/m9/normal/status",HTTP_GET,status);server.on("/api/v1/m9/normal/resources",HTTP_GET,status);
    server.on("/api/v1/bridge/metrics",HTTP_POST,telemetry);server.on("/api/v1/bridge/metrics",HTTP_GET,metrics);
    server.on("/api/v1/update/status",HTTP_GET,identity);server.on("/api/v1/m9/maintenance/result",HTTP_GET,identity);
    server.onNotFound([](){respond(404,"{\"error\":\"ROUTE_CLOSED\"}");});server.begin();
    if(configReady)M9NormalDashboard::render();
}
void afterSetup(){observer.afterSetup();}
void loop(){
    if(apReady)server.handleClient();
    const auto now=millis();const bool stale=FslessMetrics::stale();
    if(configReady&&apReady&&uint32_t(now-lastDraw)>=250&&(dirty||stale!=lastStale)){
        M9NormalDashboard::render();lastDraw=now;lastStale=stale;dirty=false;
    }
    ESP.wdtFeed();yield();observer.poll();
}
} // namespace M9NormalStageA
