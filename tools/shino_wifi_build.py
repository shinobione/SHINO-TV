"""Paired actual public StageA graphs; retained addresses, no receiver activation."""
from pathlib import Path
import argparse,configparser,json
from m9_stagea_build import prepare as stagea,ENV,ROOT
def prepare(directory,integrated=False):
    directory=stagea(directory,False)
    ini=configparser.ConfigParser(interpolation=None);ini.read(directory/'platformio.ini')
    ini['env:'+ENV]['build_flags']=ini['env:'+ENV]['build_flags'].replace('-DM9_SIGNED_OTA_UNWIRED=1','')
    ini['env:'+ENV]['build_flags']+='\n-I'+str(ROOT/'experiments/shino_wifi_install/include').replace('\\','/')
    with (directory/'platformio.ini').open('w',encoding='utf-8') as f:ini.write(f)
    if integrated:
        script=directory/'scripts/phase_t_build.py'
        script.write_text(script.read_text()+"\nfrom shino_wifi_core import materialize as updater\np=updater(Path(env.subst('$PROJECT_DIR'))/'.pio/shino-updater',env.PioPlatform().get_package_dir('framework-arduinoespressif8266'))\nenv.Prepend(CPPPATH=[str(p)])\nenv.Append(CXXFLAGS=['-include',str(p/'Updater.h')])\n")
        path=directory/'src/boot/M9NormalStageA.cpp'
        body=path.read_text().replace('namespace M9NormalDashboard { void render(); }','void retainShinoInstall();\nnamespace M9NormalDashboard { void render(); }',1)
        body=body.replace('void loop() {','void loop() {\n    retainShinoInstall(); // Reads addresses only. No receiver, key or writer activation.',1)
        body+='''
#include "ShinoWifiNative.h"
#if defined(ARDUINO_SIGNING) && ARDUINO_SIGNING
#error "Dedicated unsigned private maintenance path only"
#endif
namespace {
alignas(ShinoInstall::Native) uint8_t shinoInstallStorage[sizeof(ShinoInstall::Native)];
ShinoInstall::Native* shinoInstall=nullptr;
__attribute__((noinline)) bool shinoInstallProof(const char* id,const char* build,const uint8_t* privateKey){
    if(shinoInstall || !privateKey)return false;
    shinoInstall=new(shinoInstallStorage) ShinoInstall::Native(id,build,privateKey);return shinoInstall->begin();
}
__attribute__((noinline)) void shinoInstallPump(){if(shinoInstall)shinoInstall->pump();}
decltype(&shinoInstallProof) volatile retainedInstallProof=&shinoInstallProof;
decltype(&shinoInstallPump) volatile retainedInstallPump=&shinoInstallPump;
}
void retainShinoInstall(){auto a=retainedInstallProof;auto b=retainedInstallPump;(void)a;(void)b;}
'''
        path.write_text(body)
    inputs=json.loads((directory/'public-inputs.json').read_text());inputs['integrated']=integrated
    (directory/'public-inputs.json').write_text(json.dumps(inputs,indent=2))
    return directory
if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('directory',type=Path);p.add_argument('--integrated',action='store_true');a=p.parse_args();print(prepare(a.directory,a.integrated))
