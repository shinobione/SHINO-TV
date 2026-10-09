"""Callable StageA maintenance graph, trusted consent seam unbound; offline only."""
import argparse,json
from pathlib import Path
from shino_wifi_build import prepare as wifi
from m9_stagea_build import ROOT

def controller(text):
    assert text.count('Webserver service;')==1 and text.count('    service.raw().collectHeaders(')==1
    text=text.replace('namespace M9NormalDashboard { void render(); }',
        '#include "ShinoWifiNative.h"\n#include "ShinoMaintenance.h"\n'
        'namespace M9NormalDashboard { void render(); extern bool firstFrame; }\n'
        '// Unbound trusted seam: public graph never supplies private consent.\n'
        '__attribute__((weak,noinline)) bool shinoMaintenanceConsent(ShinoInstall::Consent&){return false;}')
    text=text.replace('Webserver service;', '''void registerHttp(Webserver& service);
struct MaintenanceHooks {
    ShinoInstall::Budget budget(){uint32_t h,b;uint8_t f;ESP.getHeapStats(&h,&b,&f);return {h,b,ESP.getFreeContStack(),f};}
    bool ap(){return WiFi.getMode()==WIFI_AP && WiFi.softAPIP()==IPAddress(192,168,4,1);}
    void resume(Webserver& service);
};
MaintenanceHooks maintenanceHooks;
ShinoInstall::Maintenance<Webserver,ShinoInstall::Native,MaintenanceHooks> maintenance(maintenanceHooks);
Webserver& service(){return maintenance.http();}''')
    text=text.replace('service.raw()', 'service().raw()')
    start=text.index('    service().raw().collectHeaders(')
    end=text.index('    if (configReady) M9NormalDashboard::render();',start)
    registration=text[start:end].replace('service().raw()','service.raw()')
    text=text[:start]+'    registerHttp(service());\n'+text[end:]
    pos=text.index('} // namespace\nvoid beforeSetup()')
    text=text[:pos]+'''void registerHttp(Webserver& service){
'''+registration+'''}
void MaintenanceHooks::resume(Webserver& service){
    registerHttp(service);dirty=true;lastDraw=millis()-250;
    M9NormalDashboard::firstFrame=true; // Redraw from current, honest TTL state.
}
'''+text[pos:]
    text=text.replace('void loop() {\n    if (apReady) service.handleClient();', '''void loop() {
    ShinoInstall::Consent consent{};
    if(shinoMaintenanceConsent(consent)) maintenance.request(consent);
    if(!maintenance.tick()){EspClass::wdtFeed();yield();return;}
    if (apReady) service().handleClient();''')
    assert 'service.handleClient' not in text and 'maintenance.tick()' in text
    return text

def prepare(directory,small_buffer=False):
    directory=wifi(directory,False)
    script=directory/'scripts/phase_t_build.py'
    script.write_text(script.read_text()+"\nfrom shino_wifi_core import materialize as updater\np=updater(Path(env.subst('$PROJECT_DIR'))/'.pio/shino-updater',env.PioPlatform().get_package_dir('framework-arduinoespressif8266'),small_buffer="+str(bool(small_buffer))+")\nenv.Prepend(CPPPATH=[str(p)])\nenv.Append(CXXFLAGS=['-include',str(p/'Updater.h')])\n")
    if small_buffer:
        ini=directory/'platformio.ini'
        config=ini.read_text()
        marker='-I'+str(ROOT/'experiments/shino_wifi_install/include').replace('\\','/')
        assert marker in config
        ini.write_text(config.replace(marker,marker+'\n    -DSHINO_SMALL_OTA_BUFFER=1\n    -DSHINO_MEMORY_TRACE=1',1))
    header=directory/'include/web/Webserver.h'
    header.write_text(header.read_text().replace('#include <ESP8266WebServer.h>','#include "ShinoReclaimingHttp.h"').replace('    ESP8266WebServer _server;',
        '    ShinoInstall::ReclaimingHttp _server;').replace('    void handleClient();','    void handleClient();\n    void quiesce(){_server.quiesce();}'))
    path=directory/'src/boot/M9NormalStageA.cpp';path.write_text(controller(path.read_text()))
    # Export read-only sizeof evidence, referenced by loop so native linker keeps
    # it. Real switching/pump calls above execute; these are NOT retention stubs.
    path.write_text(path.read_text().replace('void loop() {','''volatile const uint32_t maintenanceSizes[]={sizeof(Webserver),sizeof(ShinoInstall::Native),sizeof(maintenance),sizeof(String),sizeof(esp8266webserver::FunctionRequestHandler<WiFiServer>),sizeof(Uri)};
void loop() {
    (void)maintenanceSizes[0];'''))
    inputs=json.loads((directory/'public-inputs.json').read_text());inputs['maintenance_callable']=True;inputs['trusted_consent_bound']=False
    (directory/'public-inputs.json').write_text(json.dumps(inputs,indent=2))
    return directory
if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('directory',type=Path);a=p.parse_args();print(prepare(a.directory))
