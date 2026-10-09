"""Actual StageA/parser lifecycle with mocked radio/SDK and upload pump."""
from pathlib import Path
from m9_stagea_build import ROOT
from shino_maintenance_build import controller
from shino_transition_build import authenticated_prebody_snapshot, maintenance_http_policy

def prepare_host(directory,shims,composition,sources):
    arduino=shims/'Arduino.h'
    text=arduino.read_text().replace('*f=32000;*b=30000;*p=2;', '*f=lab_heap;*b=lab_block;*p=lab_frag;').replace('return 4000;', 'return lab_stack;')
    text=text.replace('struct EspFixture {','inline uint32_t lab_heap=32000,lab_block=30000,lab_stack=4000;inline uint8_t lab_frag=2;\nstruct EspFixture {')
    arduino.write_text(text)
    socket=(ROOT/'experiments/v08_socket_dispatch/host_shims/HostSocket.h').read_text()
    socket=socket.replace('void stop(){stops++;','void abort(){stop();}\n void stop(){stops++;')
    # Match pinned native Core: close() does NOT free queued contexts.
    socket=socket.replace('void close(){pending.clear();','void close(){')
    socket=socket.replace('~WiFiServer(){close();}', '~WiFiServer(){close();}')
    socket=socket.replace('struct IPAddress {uint32_t value=1;', 'struct IPAddress {uint32_t value=1;IPAddress()=default;IPAddress(int,int,int,int){} bool operator==(const IPAddress& p)const{return value==p.value;}')
    (shims/'HostSocket.h').write_text(socket)
    (shims/'ESP8266WiFi.h').write_text('''#pragma once
#include <HostSocket.h>
enum {WIFI_AP,WIFI_OFF};
struct WiFiFixture {bool persisted=true;int mode_=WIFI_AP;void persistent(bool b){persisted=b;}void mode(int n){mode_=n;}int getMode(){return mode_;}IPAddress softAPIP(){return {};}bool softAP(const char*,const char*,int,bool,int){return true;}};
inline WiFiFixture WiFi;
''')
    (shims/'ShinoWifiNative.h').write_text('''#pragma once
#include "ShinoWifiPolicy.h"
namespace ShinoInstall {inline unsigned uploadObjects=0,uploadPumps=0,uploadStops=0;inline bool uploadFail=false,uploadBegin=true;
class Native {public:Native(const char*,const char*,const uint8_t*){++uploadObjects;}~Native(){--uploadObjects;}
bool begin(){return uploadBegin;}void pump(){++uploadPumps;}void stop(){++uploadStops;}bool failed(){return uploadFail;}bool committed(){return false;}};}
''')
    wrapper=shims/'web/Webserver.h'
    wrapper.write_text(wrapper.read_text().replace('void begin(){','void quiesce(){server.quiesce();} void begin(){'))
    # Replay the disposable M9 private HTTP route policy against the ACTUAL
    # pinned Core parser and actual StageA controller under loopback only.
    # Maintenance handlers below are read-only stand-ins (status), NOT arming
    # or OTA permission. Separate receiver/HMAC tests own those semantics.
    stage=directory/'maintenance_stagea.cpp'
    source=authenticated_prebody_snapshot(
        controller((ROOT/'firmware/src/boot/M9NormalStageA.cpp').read_text()))
    anchor='    service.on("/api/v1/m9/normal/resources", HTTP_GET, status);'
    assert source.count(anchor)==1
    source=source.replace(anchor,anchor+''.join(
        '\\n    service.on("/api/v1/m9/maintenance/'+route+'", HTTP_GET, status);'
        for route in ("challenge","probe","install","result")))
    stage.write_text(source)
    policy=directory/'boot/M9NormalHttpPolicy.h';policy.parent.mkdir(parents=True,exist_ok=True)
    policy.write_text(maintenance_http_policy(
        (ROOT/'firmware/include/boot/M9NormalHttpPolicy.h').read_text()))
    composition=composition.replace(str((ROOT/'firmware/src/boot/M9NormalStageA.cpp').as_posix()),stage.as_posix())
    (directory/'stage_composition.inc').write_text(composition)
    lab=(ROOT/'tools/m9_phase_n_http_lab.cpp').read_text()
    lab=lab.replace('struct ObservedServer:ESP8266WebServer {', '#include "'+(ROOT/'experiments/shino_wifi_install/include/ShinoReclaimingHttp.h').as_posix()+'"\nstruct ObservedServer:ShinoInstall::ReclaimingHttp {')
    lab=lab.replace('using ESP8266WebServer::ESP8266WebServer;', 'using ShinoInstall::ReclaimingHttp::ReclaimingHttp;')
    lab=lab.replace('static auto& server=M9NormalStageA::service.raw();', '#define server (M9NormalStageA::service().raw())')
    lab=lab.replace('int main(int argc,char**)', '#include "'+(ROOT/'tools/shino_maintenance_http_lab.inc').as_posix()+'"\nint main(int argc,char** argv)')
    lab=lab.replace(' const std::string path="/api/v1/bridge/metrics",body(32,\'x\');',' if(argc==2 && std::string(argv[1])=="--maintenance")return maintenanceCases();\n const std::string path="/api/v1/bridge/metrics",body(32,\'x\');')
    # Include policy header directory for both real cleanup and generic lifetime.
    (shims/'ShinoMaintenance.h').write_text('#include "'+(ROOT/'experiments/shino_wifi_install/include/ShinoMaintenance.h').as_posix()+'"\n')
    (shims/'ShinoWifiPolicy.h').write_text('#include "'+(ROOT/'experiments/shino_wifi_install/include/ShinoWifiPolicy.h').as_posix()+'"\n')
    path=directory/'maintenance_http.cpp';path.write_text(lab)
    return [path,sources[1]]

if __name__=='__main__':
    import json
    from m9_phase_n_http_runner import run
    print(json.dumps(run(maintenance=True),indent=2))
