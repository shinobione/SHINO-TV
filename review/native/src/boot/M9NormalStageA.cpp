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
#include "B5Lan.h"
#include "B52Clock.h"
#include "B53Sntp.h"
#include "B53Diagnostic.h"
#include "B53Integrated.h"
#include "B54LanNative.h"
#include "B54LanStatusPath.h"
#include <new> // placement new for per-request telemetry scratch
#include <cstddef>
static_assert(SHINO_BOOT_PROFILE==1 && SHINO_M9_NORMAL_QUALIFICATION==1 &&
              SHINO_ENABLE_FACTORY_RESTORE==0 && SHINO_ENABLE_NATIVE_SIGNED_OTA==0 &&
              SHINO_ENABLE_FS_MIGRATION==0,"Dedicated application-only normal firmware");
#if defined(ARDUINO_SIGNING) && ARDUINO_SIGNING
#error "This HMAC release profile cannot use global RSA signing"
#endif
namespace M9NormalDashboard {void render();}
namespace M9NormalStageA {
namespace {
// The pinned parser owns header collection only. Its pre-body hook returns
// CLIENT_REQUEST_IS_HANDLED; Core retains the client/headers until this loop's
// synchronous dispatch completes. No Core source, second listener or task.
class NormalHttpServer final:public ESP8266WebServer {
public:
    NormalHttpServer():ESP8266WebServer(80){}
    uint32_t requestStarted()const{return _stageAStarted;}
    int diagnosticPage()const{
        static const char prefix[] PROGMEM="/api/v1/m9/normal/journal/";
        const String& path=uri();
        if(path.length()!=sizeof(prefix)||memcmp_P(path.c_str(),prefix,sizeof(prefix)-1))return -1;
        const char page=path[sizeof(prefix)-1];
        return page>='0'&&page<='2'?page-'0':-1;
    }
    size_t retainedRequestBytes()const{
        size_t n=_currentUri.length()+_hostHeader.length()+_responseHeaders.length();
        for(int i=0;i<_headerKeysCount;++i)n+=_currentHeaders[i].value.length();
        return n;
    }
    bool waitingPeer(){return _server.hasClient();}
    bool incoming(){return _server.hasClient()||_currentClient.connected();}
    void poll(){
        if(incoming())B53Integrated::critical();
        // A refused POST may still have an unread body. Preserve Core's close
        // grace instead of closing under a client reading its 401, and never
        // reinterpret those body bytes as another request. A pending peer
        // releases this slot immediately, as in the pinned Core.
        if(_currentStatus==HC_WAIT_CLOSE){
            if(_currentClient.connected()&&!_server.hasClient()&&uint32_t(millis()-_statusChange)<=HTTP_MAX_CLOSE_WAIT){yield();return;}
            _currentClient.stop();_currentClient=ClientType();_currentStatus=HC_NONE;
        }
        ESP8266WebServer::handleClient();
    }
    void finishRequest(){
        _finalizeResponse();
        _currentStatus=HC_WAIT_CLOSE;_statusChange=millis();
        _currentHandler=nullptr;_currentUpload.reset();
        delete[] _currentArgs;_currentArgs=nullptr;_currentArgCount=_currentArgsHavePlain=0;
        _currentUri=String();_hostHeader=String();_responseHeaders=String();
        for(int i=0;i<_headerKeysCount;++i)_currentHeaders[i].value=String();
    }
};
NormalHttpServer server;
// B5 operates AP/STA via the separate, opt-in 4m2m controller.
B53Diagnostic::Journal diagnosticJournal;
struct CoreSource {
    void resetStack(){ESP.resetFreeContStack();}
    uint32_t stack(){return ESP.getFreeContStack();}
    void heap(M9NormalResources::Heap& h){
        const uint32_t mark=micros();
        ESP.getHeapStats(&h.free,&h.largest,&h.fragmentation);
        if(diagnosticJournal.started()){
            const uint32_t stack=ESP.getFreeContStack();
            diagnosticJournal.capture(micros(),h.free,h.largest,h.fragmentation,stack,uint32_t(micros()-mark));
            diagnosticJournal.captureCost(uint32_t(micros()-mark));
            B53Integrated::observe(h.free,h.largest,h.fragmentation,stack);
        }
    }
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
alignas(std::max_align_t) char responseBody[768];
bool responseBusy=false;
bool uploadBusy=false,uploadVerifying=false;
bool requestPending=false,httpBusy=false;
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
// ArduinoJson uses small pools in this entire, separately compiled graph.
// The existing response buffer is its bounded arena; the existing transfer
// buffer holds bounded JSON input or serialized metrics. ArduinoJson 7.4.3
// copies strings even for mutable input; released string-builder blocks must
// therefore be reused within the arena, not leaked by a bump allocator.
// No allocator fallback and no extra arena BSS. All objects die before the
// lease releases either buffer. OTA cannot run concurrently with dispatch.
static_assert(ARDUINOJSON_POOL_CAPACITY==8,"Bounded normal JSON pool geometry");
class JsonArena final:public ArduinoJson::Allocator {
    static constexpr size_t Alignment=alignof(double)>alignof(void*)?alignof(double):alignof(void*);
    struct alignas(Alignment) Block {size_t size;}; // low bit marks a free block
    static size_t size(const Block* b){return b->size&~size_t(1);}
    static Block* next(Block* b){return reinterpret_cast<Block*>(reinterpret_cast<char*>(b+1)+size(b));}
    static bool inside(Block* b){return reinterpret_cast<char*>(b)<responseBody+sizeof(responseBody);}
public:
    JsonArena(){new(responseBody) Block{(sizeof(responseBody)-sizeof(Block))|1};}
    size_t bytesUsed()const{
        size_t n=0;
        for(auto* b=reinterpret_cast<Block*>(responseBody);inside(b);b=next(b))if(!(b->size&1))n+=size(b)+sizeof(Block);
        return n;
    }
    void* allocate(size_t n)override{
        if(!n||n>sizeof(responseBody))return nullptr;
        n=(n+Alignment-1)&~(Alignment-1);
        for(auto* b=reinterpret_cast<Block*>(responseBody);inside(b);b=next(b)){
            if(!(b->size&1)||size(b)<n)continue;
            const size_t old=size(b);
            if(old>=n+sizeof(Block)+Alignment){b->size=n;new(next(b)) Block{(old-n-sizeof(Block))|1};}
            else b->size=old;
            return b+1;
        }
        return nullptr; // NEVER fall back to heap
    }
    void deallocate(void* p)override{
        if(!p)return;
        (static_cast<Block*>(p)-1)->size|=1;
        for(auto* b=reinterpret_cast<Block*>(responseBody);inside(b);){
            auto* following=next(b);
            if((b->size&1)&&inside(following)&&(following->size&1))b->size=(size(b)+sizeof(Block)+size(following))|1;
            else b=following;
        }
    }
    void* reallocate(void* p,size_t n)override{
        if(!p)return allocate(n);
        if(!n){deallocate(p);return nullptr;}
        auto* b=static_cast<Block*>(p)-1;const size_t old=size(b);
        if(n<=old){
            n=(n+Alignment-1)&~(Alignment-1);
            if(old>=n+sizeof(Block)+Alignment){
                b->size=n;auto* tail=new(next(b)) Block{(old-n-sizeof(Block))|1};
                deallocate(tail+1);
            }
            return p;
        }
        void* replacement=allocate(n);if(!replacement)return nullptr;
        std::memcpy(replacement,p,old);deallocate(p);return replacement;
    }
};
struct TelemetryScratch {
    JsonArena arena;
    JsonDocument doc{&arena};
    String error;
};
alignas(TelemetryScratch) unsigned char telemetryScratchStorage[sizeof(TelemetryScratch)];
class TelemetryScratchLease {
    ResponseLease responseLease_;
    TelemetryScratch* scratch_;
public:
    TelemetryScratchLease():responseLease_(),
        scratch_(responseLease_?new(telemetryScratchStorage) TelemetryScratch():nullptr){}
    ~TelemetryScratchLease(){if(scratch_)scratch_->~TelemetryScratch();}
    explicit operator bool()const{return scratch_!=nullptr;}
    TelemetryScratch* operator->(){return scratch_;}
    TelemetryScratchLease(const TelemetryScratchLease&)=delete;
    TelemetryScratchLease& operator=(const TelemetryScratchLease&)=delete;
};
constexpr char descriptor[]="SHINO-HTTP-OTA-1|" SHINO_OTA_DEVICE "|" SHINO_OTA_BUILD "|4m2m|APP_ONLY";
void randomNonce(char* out){uint8_t bytes[16];for(unsigned i=0;i<4;++i){uint32_t r=os_random();std::memcpy(bytes+4*i,&r,4);}ShinoHttpOta::encode(bytes,16,out);}
ShinoHttpOta::Budget budget(){ShinoHttpOta::Budget b{};ESP.getHeapStats(&b.heap,&b.block,&b.frag);b.stack=ESP.getFreeContStack();return b;}
bool uploadHealthy(){
    ++uploadSamples;
    const auto b=budget();minima.heap=std::min(minima.heap,b.heap);minima.block=std::min(minima.block,b.block);
    minima.stack=std::min(minima.stack,b.stack);minima.frag=std::max(minima.frag,b.frag);
    return b.safe()&&B5Lan::permitted(server)&&uint32_t(millis()-uploadStart)<120000&&
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
enum class Route:uint8_t{Closed,Normal,MetricsGet,MetricsPost,Identity,Upload,LanIntent,LanProvision,LanStatus,ClockSync,ClockStatus,WeatherStatus,WeatherReceive};
Route route(){
    // Borrow Core's URI only while this synchronous request owns its headers.
    const String& path=server.uri();const auto method=server.method();
    if(method==HTTP_GET){
        if(B54LanWeather::statusPath(path.c_str(),path.length()))return Route::WeatherStatus;
        if(server.diagnosticPage()>=0)return Route::Normal;
        if(path=="/status"||path=="/api/v1/m9/normal/status"||path=="/api/v1/m9/normal/resources")return Route::Normal;
        if(path=="/api/v1/bridge/metrics")return Route::MetricsGet;
        if(path=="/api/v1/update/status"||path=="/api/v1/m9/maintenance/result")return Route::Identity;
        if(path=="/api/v1/lan/status")return Route::LanStatus;
        if(path=="/api/v1/clock/status")return Route::ClockStatus;
        if(path=="/api/v1/lan/intent")return Route::LanIntent;
    }
    if(method==HTTP_POST){
        if(path=="/api/v1/weather")return Route::WeatherReceive;
        if(path=="/api/v1/bridge/metrics")return Route::MetricsPost;
        if(path=="/api/v1/update")return Route::Upload;
        if(path=="/api/v1/lan/provision")return Route::LanProvision;
        if(path=="/api/v1/clock/sync")return Route::ClockSync;
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
bool localPeer(){return B5Lan::permitted(server);}
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
#include "B54LanHttp.inc"
__attribute__((noinline)) bool beforeBody(){
    server.keepAlive(false);
    const Route selected=route();uint32_t bytes=0;
    if(!B5Lan::permitted(server)){respond(403,"{\"error\":\"NETWORK_POLICY\"}");return false;}
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
    if(selected==Route::LanProvision&&(!B5Lan::apPeer(server)||bytes<3||bytes>99||server.header("Content-Type")!="application/octet-stream")){respond(403,"{\"error\":\"PROVISION_AP_ONLY\"}");return false;}
    if(selected==Route::ClockSync&&(bytes!=B52Clock::FRAME_BYTES||server.header("Content-Type")!="application/octet-stream")){respond(413,"{\"error\":\"CLOCK_FRAME_BOUND\"}");return false;}
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
__attribute__((noinline)) void diagnosticStatus(unsigned page){
    ResponseLease lease;if(!lease){respond(503,"{\"error\":\"RESPONSE_BUSY\"}");return;}
    const uint32_t mark=micros();
    const size_t n=diagnosticJournal.encode(page,responseBody,sizeof(responseBody));
    diagnosticJournal.encodeCost(uint32_t(micros()-mark));
    if(!n){respond(400,"{\"error\":\"DIAG_PAGE\"}");return;}
    respond(200,responseBody);
}
__attribute__((noinline)) void status(){
    const int page=server.diagnosticPage();
    if(page>=0){diagnosticStatus(unsigned(page));return;}
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
__attribute__((noinline)) void identity(){
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
__attribute__((noinline)) void telemetry(){
    TelemetryScratchLease scratch;
    if(!scratch){respond(503,"{\"error\":\"RESPONSE_BUSY\"}");return;}
    // Read only AFTER Digest/framing/config admission and AFTER parser unwind.
    // Retain the original total 2s header+body deadline and 384-byte bound.
    uint32_t bytes=0;if(!length(bytes)||bytes<16||bytes>384){respond(413,"{\"error\":\"TELEMETRY_BOUND\"}");return;}
    size_t received=0;auto& client=server.client();
    while(received<bytes){
        if(uint32_t(millis()-server.requestStarted())>=2000||!client.connected()){client.stop();return;}
        const size_t n=std::min(size_t(client.available()),size_t(bytes-received));
        if(n){const int count=client.read(transferBuffer+received,n);if(count<=0){client.stop();return;}received+=size_t(count);}
        else yield();
    }
    if(uint32_t(millis()-server.requestStarted())>=2000){client.stop();return;}
    transferBuffer[bytes]=0;
    if(deserializeJson(scratch->doc,reinterpret_cast<char*>(transferBuffer),bytes,
                       DeserializationOption::NestingLimit(1))){
        respond(422,"{\"error\":\"JSON\"}");return;
    }
    if(!FslessMetrics::apply(scratch->doc.as<JsonVariantConst>(),scratch->error)){
        respond(422,"{\"error\":\"TELEMETRY\"}");return;
    }
    B53Integrated::linkAccepted(uint32_t(millis()-server.requestStarted()));
    dirty=true;respond(200,"{\"status\":\"RAM_SAMPLE_ACCEPTED\",\"persisted\":false}");
}
__attribute__((noinline)) void metrics(){
    TelemetryScratchLease scratch;if(!scratch){respond(503,"{\"error\":\"RESPONSE_BUSY\"}");return;}
    FslessMetrics::describe(scratch->doc);
    if(scratch->doc.overflowed()||measureJson(scratch->doc)>=sizeof(transferBuffer)){respond(500,"{\"error\":\"METRICS_BOUND\"}");return;}
    serializeJson(scratch->doc,reinterpret_cast<char*>(transferBuffer),sizeof(transferBuffer));
    respond(200,reinterpret_cast<char*>(transferBuffer));
}

__attribute__((noinline)) void lanStatus() {
    ResponseLease lease;if(!lease){respond(503,"{\"error\":\"RESPONSE_BUSY\"}");return;}
    const String ip=B5Lan::address().toString();
    const int n=std::snprintf(responseBody,sizeof(responseBody),
       "{\"state\":\"%s\",\"lan_ip\":\"%s\",\"sta_online\":%s,\"ota_protocol\":\"shino-http-ota-1\","
       "\"credential_state\":\"%s\",\"connection\":\"%s\",\"provision\":\"%s\",\"firmware\":\"B5.4-LAN\"}",
       B5Lan::state(),ip.c_str(),B5Lan::online()?"true":"false",
       B5Lan::storageState(),B5Lan::connectionState(),B5Lan::provisionState());
    if(n<0||size_t(n)>=sizeof(responseBody)){respond(500,"{\"error\":\"LAN_BOUND\"}");return;}
    respond(200,responseBody);
}
__attribute__((noinline)) void lanIntent() {
    char token[33]{};
    if(!B5Lan::intentStart(server,token)){respond(403,"{\"error\":\"INTENT_AP_ONLY\"}");return;}
    char reply[64]{};
    std::snprintf(reply,sizeof(reply),"{\"intent\":\"%s\"}",token);
    respond(200,reply);
    HomeLan::wipe(token,sizeof(token));
    HomeLan::wipe(reply,sizeof(reply));
}
__attribute__((noinline)) void lanProvision() {
    if(!B5Lan::apPeer(server)){respond(403,"{\"error\":\"AP_ONLY\"}");return;}
    uint32_t n=0;if(!length(n)||n<3||n>99){respond(413,"{\"error\":\"FRAMING\"}");return;}
    uint32_t at=0;
    auto& peer=server.client();
    while(at<n&&uint32_t(millis()-server.requestStarted())<2000&&peer.connected()) {
        const size_t count=std::min(size_t(peer.available()),size_t(n-at));
        if(count) {
            const int got=peer.read(transferBuffer+at,count);
            if(got<=0)break;
            at+=uint32_t(got);
        } else yield();
    }
    if(at!=n || uint32_t(millis()-server.requestStarted())>=2000 ||
       !peer.connected()) {
        HomeLan::wipe(transferBuffer,sizeof(transferBuffer));
        B5Lan::cancelIntent();
        respond(409,"{\"error\":\"PROVISION_BODY_INCOMPLETE\"}");
        return;
    }
    if(peer.available()) {
        HomeLan::wipe(transferBuffer,sizeof(transferBuffer));B5Lan::cancelIntent();
        respond(409,"{\"error\":\"PROVISION_BODY_EXTRA\"}");return;
    }
    const auto result=B5Lan::provision(server,transferBuffer,n,
                                     server.header("X-Shino-Lan-Intent").c_str());
    HomeLan::wipe(transferBuffer,sizeof(transferBuffer));
    if(result==B5Lan::ProvisionCode::Verified) {
        respond(200,"{\"saved\":true,\"readback_verified\":true}");
    } else {
        char error[96]{};
        std::snprintf(error,sizeof(error),"{\"error\":\"%s\"}",B5Lan::codeName(result));
        respond(409,error);
    }
}

#include "B52ClockHttp.inc"
bool deferRequest(){server.keepAlive(false);requestPending=true;return false;}
__attribute__((noinline)) void serviceRequest(){
    B53Integrated::critical();
    requestPending=false;
    server.client().setTimeout(HTTP_MAX_SEND_WAIT);
    server.setContentLength(CONTENT_LENGTH_NOT_SET);
    if((route()==Route::WeatherStatus||route()==Route::WeatherReceive)?weatherPrebody():beforeBody())switch(route()){
        case Route::WeatherStatus:weatherStatus();break;
        case Route::WeatherReceive:weatherReceive();break;
        case Route::Normal:status();break;
        case Route::MetricsGet:metrics();break;
        case Route::MetricsPost:telemetry();break;
        case Route::Identity:identity();break;
        case Route::LanStatus:lanStatus();break;
        case Route::ClockSync:clockSync();break;
        case Route::ClockStatus:clockStatus();break;
        case Route::LanIntent:lanIntent();break;
        case Route::LanProvision:lanProvision();break;
        default:respond(404,"{\"error\":\"ROUTE_CLOSED\"}");break;
    }
    server.finishRequest();
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
    apReady=B5Lan::begin("SHINO-TV-StageA",SHINO_SETUP_AP_PSK);if(!apReady)return;
    B53Sntp::begin();
    server.collectHeaders("Authorization","Content-Length","Content-Type","Transfer-Encoding","Expect", "X-Shino-SHA256","X-Shino-Build","X-Shino-Nonce","X-Shino-Proof","Origin","X-Shino-Lan-Intent");
    server.setStageAPrebody(deferRequest);server.begin();
    if(configReady)B52Clock::refreshMetrics();
}
void afterSetup(){observer.afterSetup();diagnosticJournal.start(micros());B53Integrated::begin(diagnosticJournal);B54LanNative::begin(diagnosticJournal,boot);}
void loop(){
    // No yielding callback may reenter parsing/dispatch while a request owns
    // headers, scratch or the Core Updater. Drain the pending request BEFORE
    // the next handleClient(), including failures and disconnected peers.
    if(httpBusy){diagnosticJournal.lost();return;}
    httpBusy=true;
    diagnosticJournal.enter(micros());
    if(apReady)server.poll();
    if(requestPending)serviceRequest();
    if(WiFi.status()!=WL_CONNECTED)B53Integrated::critical();
    B5Lan::poll(uploadBusy);
    const auto now=millis();const bool stale=FslessMetrics::stale();
    if(configReady&&apReady&&uint32_t(now-lastDraw)>=250&&(dirty||stale!=lastStale)){
        B52Clock::refreshMetrics();lastDraw=now;lastStale=stale;dirty=false;
    }
    if(configReady&&apReady){
        B53Integrated::poll(uploadBusy,requestPending||server.incoming(),!FslessMetrics::stale());
        B54LanNative::poll();
        B52Clock::step(now);
    }
    ESP.wdtFeed();yield();observer.poll();
    diagnosticJournal.leave(micros());
    httpBusy=false;
}
} // namespace M9NormalStageA
