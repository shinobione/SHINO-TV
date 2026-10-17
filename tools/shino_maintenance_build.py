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
    if small_buffer:
        # A materialized source file in .pio is NOT linked automatically by PIO.
        # Override only this disposable project's framework package and storage.
        # The physical/global Core package is preserved byte-for-byte.
        import configparser
        from shino_local_framework import prepare as local_framework, platformio_local_uri
        local=local_framework(directory)
        ini=directory/'platformio.ini'
        conf=configparser.ConfigParser(interpolation=None)
        conf.read(ini)
        env_name='env:esp12e_m9_4m2m_normal_qualification'
        conf[env_name]['platform_packages']='framework-arduinoespressif8266 @ '+platformio_local_uri(local)
        conf['platformio']['packages_dir']=str((directory/'.pio/isolated-packages').resolve())
        conf[env_name]['build_flags']+='\n    -DSHINO_SMALL_OTA_BUFFER=1\n    -DSHINO_MEMORY_TRACE=1\n    -DSHINO_MAINTENANCE_PROBE=1'
        with ini.open('w',encoding='utf-8') as out:conf.write(out)
    else:
        script=directory/'scripts/phase_t_build.py'
        script.write_text(script.read_text()+"\nfrom shino_wifi_core import materialize as updater\np=updater(Path(env.subst('$PROJECT_DIR'))/'.pio/shino-updater',env.PioPlatform().get_package_dir('framework-arduinoespressif8266'))\nenv.Prepend(CPPPATH=[str(p)])\nenv.Append(CXXFLAGS=['-include',str(p/'Updater.h')])\n")
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
