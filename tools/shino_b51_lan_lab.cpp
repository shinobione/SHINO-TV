// Actual B5/B5.1 and normal HTTP/Core; deterministic SDK/radio seams only.
#include <mutex>
#include <deque>
#define main b4UnusedMain
#include "shino_http_ota_network_lab.cpp"
#undef main

static ESP8266WebServer testServer(0);
static const uint8_t payload[]={'C',8,12,'T','e','s','t','H','o','m','e',
    'F','a','k','e','P','a','s','s','1','2','3','4'};
static void resetRadio(bool empty=true){
    if(empty)testSaved={};
    testReads=testWrites=testCurrents=testConnects=testFailReadAt=0;
    testWriteOk=testCurrentOk=testDhcpOk=testConnectOk=true;
    testWriteAfter=testMismatch=testReadbackFail=testWpa2Applied=false;testDuringWrite=nullptr;testStaHook=nullptr;
    testDhcp=DHCP_STOPPED;WiFi=WiFiFixture();host_ms=100;hostStack=3248;hostBlock=50000;hostFrag=1;ESP.heap=60000;
    testLocal=IPAddress(192,168,4,1);testPeer=IPAddress(192,168,4,2);
    assert(B5Lan::begin("PUBLIC-RECOVERY","PUBLIC-FAKE-AP-KEY"));
}
static std::string token(){char out[33]{};assert(B5Lan::intentStart(testServer,out));return out;}

#ifndef SHINO_B51_LEGACY
static unsigned checks=0,cases=0;
#define CHECK(x) do {++checks;if(!(x)){std::cerr<<"check failed at line "<<__LINE__<<std::endl;return 5;}}while(0)
static int unit(){
    using C=B5Lan::ProvisionCode;
    auto send=[](const std::string& key){return B5Lan::provision(testServer,payload,sizeof(payload),key.c_str());};
    resetRadio();CHECK(std::string(B5Lan::state())=="NO_SAVED_WIFI");CHECK(testWrites==0);++cases;
    auto key=token();CHECK(send(key)==C::Verified);CHECK(testWrites==1);
    CHECK(testSaved.threshold.authmode==AUTH_WPA2_PSK);CHECK(!WiFi.persisted);
    CHECK(std::string(B5Lan::storageState())=="VERIFIED");++cases;
    CHECK(send(key)==C::ApUnavailable);CHECK(testWrites==1);++cases;
    resetRadio(false);CHECK(std::string(B5Lan::state())=="STA_CONNECTING");
    CHECK(testWrites==0 && testCurrents==1 && testConnects==1 && testWpa2Applied);++cases;
    key=token();CHECK(send(key)==C::Verified);CHECK(testWrites==0);++cases;
    resetRadio();key=token();host_ms+=60000;CHECK(send(key)==C::IntentInvalid);CHECK(testWrites==0);++cases;
    resetRadio();key=token();CHECK(send(std::string(32,'z'))==C::IntentInvalid);
    CHECK(send(key)==C::Verified);CHECK(testWrites==1);++cases;
    for(unsigned kind=0;kind<4;++kind){
        resetRadio();key=token();uint8_t bad[sizeof(payload)];memcpy(bad,payload,sizeof(bad));
        if(kind==0)bad[1]=0;else if(kind==1)bad[2]=7;else if(kind==2)bad[3]=0;else bad[11]=0;
        CHECK(B5Lan::provision(testServer,bad,sizeof(bad),key.c_str())==C::PayloadInvalid);
        CHECK(send(key)==C::IntentInvalid);CHECK(testWrites==0);++cases;
    }
    for(unsigned stage=0;stage<6;++stage){
        resetRadio();key=token();C expected=C::MemoryHold;
        if(stage==0){WiFi.staOk=false;expected=C::StaEnableFailed;}
        if(stage==1){testFailReadAt=testReads+1;expected=C::SdkReadFailed;}
        if(stage==2){testWriteOk=false;expected=C::SdkWriteFailed;}
        if(stage==3){testReadbackFail=true;expected=C::ReadbackFailed;}
        if(stage==4){testMismatch=true;expected=C::ReadbackMismatch;}
        if(stage==5)ESP.heap=21695;
        CHECK(send(key)==expected);CHECK(testWrites==(stage>=2&&stage<=4?1u:0u));
        CHECK((WiFi.modeValue&WIFI_AP)!=0);CHECK(send(key)==C::IntentInvalid);++cases;
    }
    resetRadio();key=token();testWriteOk=false;testWriteAfter=true;
    CHECK(send(key)==C::SdkWriteFailed);CHECK(testWrites==1);
    CHECK(std::string(B5Lan::state())=="SAVED_WIFI_UNKNOWN_HOLD");
    resetRadio(false);CHECK(std::string(B5Lan::state())=="STA_CONNECTING");CHECK(testWrites==0);++cases;
    resetRadio();key=token();
    testDuringWrite=[](){
        assert(B5Lan::provision(testServer,payload,sizeof(payload),"00000000000000000000000000000000")==C::ApUnavailable);
    };
    CHECK(send(key)==C::Verified);CHECK(testWrites==1);++cases;
    for(unsigned field=0;field<4;++field){
        resetRadio();key=token();if(field==0)ESP.heap=21695;if(field==1)hostBlock=17599;
        if(field==2)hostStack=2047;if(field==3)hostFrag=26;
        CHECK(send(key)==C::MemoryHold);CHECK(testWrites==0);++cases;
    }
    resetRadio();key=token();ESP.heap=21696;hostBlock=17600;hostStack=2048;hostFrag=25;
    CHECK(send(key)==C::Verified);CHECK(testWrites==1);++cases;
    resetRadio();key=token();const unsigned reads=testReads;
    testStaHook=[](){ESP.heap=21695;};CHECK(send(key)==C::MemoryHold);
    CHECK(testReads==reads && testWrites==0);CHECK((WiFi.modeValue&WIFI_AP)!=0);++cases;
    // DHCP/association failure never disables AP or erases the saved key.
    resetRadio();key=token();CHECK(send(key)==C::Verified);
    for(unsigned failure=0;failure<5;++failure){
        resetRadio(false);testCurrents=testConnects=0;
        if(failure==0)WiFi.staOk=false;if(failure==1)testCurrentOk=false;
        if(failure==2){testDhcp=DHCP_STOPPED;testDhcpOk=false;}if(failure==3)testConnectOk=false;
        if(failure==4)WiFi.wifiStatus=WL_WRONG_PASSWORD;
        CHECK(B5Lan::begin("PUBLIC-RECOVERY","PUBLIC-FAKE-AP-KEY"));CHECK(B5Lan::active());
        host_ms+=20001;B5Lan::poll(false);CHECK(std::string(B5Lan::state())=="AP_RECOVERY_RETRY");
        WiFi.staOk=testCurrentOk=testDhcpOk=testConnectOk=true;
        host_ms+=60001;B5Lan::poll(false);CHECK(std::string(B5Lan::state())=="STA_CONNECTING");
        WiFi.wifiStatus=WL_CONNECTED;WiFi.sta=IPAddress(192,168,1,82);B5Lan::poll(false);
        CHECK(B5Lan::online());WiFi.apPeers=0;host_ms+=15001;B5Lan::poll(false);
        CHECK(WiFi.modeValue==WIFI_STA);
        WiFi.wifiStatus=0;WiFi.sta=IPAddress();B5Lan::poll(false);
        CHECK((WiFi.modeValue&WIFI_AP)!=0 && B5Lan::active());CHECK(testWrites==0);++cases;
    }
    resetRadio();testFailReadAt=testReads+1;
    CHECK(B5Lan::begin("PUBLIC-RECOVERY","PUBLIC-FAKE-AP-KEY"));
    CHECK(std::string(B5Lan::state())=="SAVED_WIFI_UNKNOWN_HOLD");
    char out[33]{};CHECK(!B5Lan::intentStart(testServer,out));CHECK(testWrites==0);++cases;
    resetRadio();testSaved.password[0]='x';
    CHECK(B5Lan::begin("PUBLIC-RECOVERY","PUBLIC-FAKE-AP-KEY"));
    CHECK(std::string(B5Lan::state())=="SAVED_WIFI_INVALID_HOLD");++cases;
    CHECK(ESP.writeCalls==0 && ESP.restarts==0);
    std::cout<<"{\"cases\":"<<cases<<",\"checks\":"<<checks<<",\"sdk_threshold_getter_ignored\":true,\"reconnect_no_persistent_writes\":true,\"flash_rtc_writes\":0}"<<std::endl;
    return 0;
}
static void stats(){
    std::cout<<"{\"reads\":"<<testReads<<",\"sdk_writes\":"<<testWrites<<",\"sta_connects\":"<<testConnects
        <<",\"ap_active\":"<<((WiFi.modeValue&WIFI_AP)?"true":"false")
        <<",\"wpa2_applied\":"<<(testWpa2Applied?"true":"false")
        <<",\"flash_writes\":"<<ESP.writeCalls<<",\"restarts\":"<<ESP.restarts
        <<",\"cards\":"<<DisplayManager::gfx.cards<<"}"<<std::endl;
}
static int serve(){
    if(const char* path=std::getenv("SHINO_TEST_CURRENT_BIN")){
        std::ifstream input(path,std::ios::binary);std::vector<uint8_t> raw{std::istreambuf_iterator<char>(input),{}};
        if(raw.size()<64000||raw.size()>ShinoHttpOta::MaxImage)return 4;
        std::copy(raw.begin(),raw.end(),ESP.flash.begin());ESP.current=uint32_t(raw.size());
    }
    resetRadio();ConfigManager config;M9NormalStageA::beforeSetup();M9NormalStageA::begin(config);M9NormalStageA::afterSetup();
    lab_real_clock=true;std::mutex mutex;std::deque<std::string> commands;bool stop=false,waitingWrite=false;
    uint32_t waitStarted=0;
    std::thread input([&](){std::string command;while(std::getline(std::cin,command)){
        std::lock_guard<std::mutex> lock(mutex);commands.push_back(command);if(command=="stop")break;
    }});
    std::cout<<M9NormalStageA::server.getServer().port<<std::endl;
    while(!stop){
        std::string command;{std::lock_guard<std::mutex> lock(mutex);if(!commands.empty()){command=commands.front();commands.pop_front();}}
        if(!command.empty()){
            if(command=="stats"){stats();continue;}
            if(command=="stop"){stop=true;continue;}
            if(command=="wait write"){waitingWrite=true;waitStarted=millis();command.clear();}
            else {
            if(command=="reset")resetRadio();
            if(command=="boot saved"){WiFi.modeValue=WIFI_OFF;WiFi.wifiStatus=0;WiFi.sta=IPAddress();B5Lan::begin("PUBLIC-RECOVERY","PUBLIC-FAKE-AP-KEY");}
            if(command=="fault read")testFailReadAt=testReads+1;
            if(command=="fault readback")testReadbackFail=true;
            if(command=="fault write")testWriteOk=false;
            if(command=="fault write-after"){testWriteOk=false;testWriteAfter=true;}
            if(command=="fault mismatch")testMismatch=true;
            if(command=="fault sta")WiFi.staOk=false;
            if(command=="fault heap")ESP.heap=21695;
            if(command=="mode lan"){WiFi.wifiStatus=WL_CONNECTED;WiFi.sta=IPAddress(192,168,1,82);testLocal=WiFi.sta;testPeer=IPAddress(192,168,1,10);}
            if(command=="mode ap"){testLocal=IPAddress(192,168,4,1);testPeer=IPAddress(192,168,4,2);}
            if(command=="peer foreign")testPeer=IPAddress(192,168,2,10);
            if(command=="network lost"){WiFi.wifiStatus=0;WiFi.sta=IPAddress();}
            if(command.rfind("advance ",0)==0)host_ms+=uint32_t(std::stoul(command.substr(8)));
            B5Lan::poll(false);std::cout<<"{\"ok\":true}"<<std::endl;
            }
        }
        M9NormalStageA::loop();
        if(waitingWrite&&(testWrites||uint32_t(millis()-waitStarted)>=3000)){
            std::cout<<"{\"write_observed\":"<<(testWrites?"true":"false")<<"}"<<std::endl;waitingWrite=false;
        }
        std::this_thread::sleep_for(std::chrono::milliseconds(1));
    }
    input.join();
    for(size_t at=0x200000;at<ESP.flash.size();++at)assert(ESP.flash[at]==0xff);
    eboot_command command{};assert(ESP.restarts==0 || eboot_command_read(&command)==0);
    stats();return 0;
}
#endif
int main(int argc,char** argv){
#ifdef _WIN32
    WSADATA w{};if(WSAStartup(MAKEWORD(2,2),&w))return 2;
#endif
#ifdef SHINO_B51_LEGACY
    resetRadio();auto key=token();
    const bool verified=B5Lan::provision(testServer,payload,sizeof(payload),key.c_str());
    const bool written=!memcmp(testSaved.ssid,payload+3,8)&&!memcmp(testSaved.password,payload+11,12);
    assert(!verified&&written&&testWrites==1);
    resetRadio(false);assert(std::string(B5Lan::state())=="NO_SAVED_WIFI"&&testConnects==0);
    std::cout<<"{\"store_succeeded_reply_refused\":true,\"reboot_ignores_saved_credentials\":true,\"source\":\"8de4d4556f26d47b62b1f19a6b03216a12f7e718\"}"<<std::endl;return 0;
#else
    return argc>1&&std::string(argv[1])=="unit"?unit():serve();
#endif
}
