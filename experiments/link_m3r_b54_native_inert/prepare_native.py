"""Owner-authorized INERT native projection, never a production builder."""
import argparse,hashlib,importlib.util,json,os,shutil,subprocess,sys
from pathlib import Path
HERE=Path(__file__).resolve().parent
REPO=HERE.parents[1]
FRAMEWORK_PINS={
 'ESP8266WebServer.h':'167b098fa4f964fc92ae9b89d531a69e3984561d4ca0729ab857f8f36d52dd67',
 'ESP8266WebServer-impl.h':'19934c7352eea30acb6d30ab6314d1b794fa5311d88fd3cdc7edaa6cdb7bb150',
 'Parsing-impl.h':'f8fe756b04222f20c49813ea63f0c8a90a99034255324de84349e32755afe818'}
LOGGER_PINS={'Logger.h':'4f95ce59ed8bc3652bb0c94988a1350d97b4f544d1df2b2560d21ffe0d85c9ef','Logger.cpp':'8bad5d91e0b08675c5ea6fcddd1b90287b01ff6b85275af5503feee637050252'}
GUARD='''#pragma once
#if !defined(ESP8266) || !defined(SHINO_M3R_NATIVE_INERT) || SHINO_M3R_NATIVE_INERT != 1
#error "Dedicated native INERT composition only; never an owner release"
#endif
'''

def sha(raw):return hashlib.sha256(raw).hexdigest()
def write(path,text):path.parent.mkdir(parents=True,exist_ok=True);path.write_text(text,encoding='utf-8',newline='\n')
def load_module(path,name):
 spec=importlib.util.spec_from_file_location(name,path);m=importlib.util.module_from_spec(spec);spec.loader.exec_module(m);return m

def prepare(source,output,core,cache=None):
 source,output,core=map(lambda p:Path(p).resolve(),(source,output,core))
 if output.exists():raise ValueError('Fresh output required; never overwrite')
 public=load_module(REPO/'experiments/link_m3r_b54_handoff/materialize.py','host_materialize')
 # Reuse all source, overlay and M3 identity guards from increment 3.
 public.prepare(source,output/'validated')
 if json.loads((core/'package.json').read_text())['version']!='3.30102.0':raise ValueError('Core package drift')
 for name,pin in FRAMEWORK_PINS.items():
  if sha((core/'libraries/ESP8266WebServer/src'/name).read_bytes())!=pin:raise ValueError('Stock Core source drift: '+name)
 native=output/'validated/patched/native';base=output/'validated/base/native'
 upstream=base/'core/Updater.upstream.cpp'
 if upstream.read_bytes().replace(b'\r\n',b'\n')!=(core/'cores/esp8266/Updater.cpp').read_bytes().replace(b'\r\n',b'\n'):raise ValueError('Updater upstream mismatch')
 project=output/'project';project.mkdir()
 provenance={}
 def copy(src,dest):
  raw=src.read_bytes().replace(b'\r\n',b'\n');dest.parent.mkdir(parents=True,exist_ok=True);dest.write_bytes(raw)
  provenance[dest.relative_to(project).as_posix()]=dict(input_sha256=sha(raw),output_sha256=sha(raw))
 # New INERT binding headers replace no file in the validated/public trees.
 policies={'ShinoRelease.h','shino_private_policy.h','B54LanPrivate.h'}
 for p in (native/'include').rglob('*'):
  if p.is_file() and p.relative_to(native/'include').as_posix() not in policies:copy(p,project/'include'/p.relative_to(native/'include'))
 policy=(base/'include/shino_private_policy.h').read_text().split('#endif\n',1)[1]
 write(project/'include/shino_private_policy.h',GUARD+policy)
 write(project/'include/ShinoRelease.h',GUARD+'''#include <stdint.h>
#define SHINO_OTA_DEVICE "0123456789abcdef"
#define SHINO_OTA_BUILD "cccccccccccccccccccccccccccccccccccccccccccccccccccccccccccccccc"
#define SHINO_OTA_PRIVATE 0
static constexpr uint8_t ShinoReleaseKey[32]={};
''')
 write(project/'include/B54LanPrivate.h',GUARD+'''#include <pgmspace.h>
#define SHINO_WEATHER_OWNER 1
static const uint8_t B54LanKey[32] PROGMEM={1,2,3,4,5,6,7,8,9,10,11,12,13,14,15,16,17,18,19,20,21,22,23,24,25,26,27,28,29,30,31,32};
''')
 # Full services referenced by StageA; no original main/setup, WiFiManager task or web UI runner.
 sources=['boot/M9NormalStageA.cpp','boot/M9NormalDashboard.cpp','boot/M9LittleFsMountProbe.cpp',
          'boot/B5Lan.cpp','boot/FslessMetrics.cpp','boot/B52Clock.cpp','boot/B53Sntp.cpp',
          'boot/B53Integrated.cpp','boot/B54LanNative.cpp','config/ConfigManager.cpp',
          'config/SecureStorage.cpp','display/DisplayManager.cpp','display/Gif.cpp']
 for name in sources:copy(native/'src'/name,project/'src'/name)
 for p in (native/'http').rglob('*'):
  if p.is_file():copy(p,project/'lib/StageAHTTP/src'/p.relative_to(native/'http'))
 write(project/'lib/StageAHTTP/library.json',json.dumps(dict(name='PinnedStageAHTTP',version='1.0.0',build=dict(flags=['-fstack-usage']))))
 copy(native/'core/Updater.cpp',project/'src/Updater512.cpp')
 copy(native/'core/Updater.h',project/'include/Updater.h')
 copy(native/'linker/eagle.flash.4m2m.ld',project/'eagle.flash.4m2m.ld')
 # Public Logger absent from #72: pin the existing 83a21d0 #85 blobs.
 for name,pin in LOGGER_PINS.items():
  raw=(REPO/'firmware/lib/Logger'/name).read_bytes().replace(b'\r\n',b'\n')
  if sha(raw)!=pin:raise ValueError('Public Logger source drift: '+name)
  copy(REPO/'firmware/lib/Logger'/name,project/'lib/Logger'/name)
 write(project/'lib/Logger/library.json',json.dumps(dict(name='PinnedPublicLogger',version='1.0.0')))
 for path in (output/'validated/patched/experiments').rglob('*'):
  if path.is_file():copy(path,project/'include/experiments'/path.relative_to(output/'validated/patched/experiments'))
 copy(output/'validated/patched/host/M3RB54Lab.inc',project/'include/M3RB54Lab.inc')
 # Replace only the explicit HOST opt-in guards in the DERIVED copy. The
 # original six-file overlay, original HOST compile-error and global Core stay intact.
 for name in ('src/boot/M9NormalStageA.cpp','lib/StageAHTTP/src/Parsing-impl.h'):
  p=project/name;before=p.read_bytes();text=before.decode()
  old='#if defined(SHINO_M3R_B54_HOST_HANDOFF) && SHINO_M3R_B54_HOST_HANDOFF == 1'
  expected=4 if name.startswith('src/') else 1
  if text.count(old)!=expected:raise ValueError('Native guard anchors changed')
  text=text.replace(old,'#if SHINO_M3R_NATIVE_HANDOFF == 1')
  if name.startswith('src/'):
   guard='#ifndef HOST_MOCK\n#error "Increment 2 is HOST-only. No production key, display writer or firmware activation."\n#endif'
   if text.count(guard)!=1:raise ValueError('Original HOST guard drift')
   text=text.replace(guard,'#if !defined(SHINO_M3R_NATIVE_INERT) || SHINO_M3R_NATIVE_INERT != 1\n#error "Native INERT linking only; no production activation"\n#endif')
  write(p,text);provenance[name]=dict(input_sha256=sha(before),output_sha256=sha(p.read_bytes()),transformation='explicit_native_inert_opt_in_only')
 write(project/'src/inert_entry.cpp',GUARD+'''#include <Arduino.h>
#include "config/ConfigManager.h"
#include "boot/M9NormalStageA.h"
#include "experiments/link_m3c_crypto/M3CAuthenticatedIngress.h"
ConfigManager configManager;
extern "C" {
// Retained by -u only. setup/loop never reference or call it.
void __attribute__((used,noinline)) shino_m3r_stagea_link_probe(){
 M9NormalStageA::beforeSetup();M9NormalStageA::begin(configManager);
 M9NormalStageA::afterSetup();M9NormalStageA::loop();
}
extern const uint32_t shino_native_gate_size PROGMEM __attribute__((used))=sizeof(ShinoM3C::Gate);
}
void setup(){}
void loop(){}
''')
 shutil.copyfile(HERE/'inert_guard.py',project/'inert_guard.py')
 deps='''lib_deps =
 bblanchon/ArduinoJson@7.4.3
 moononournation/GFX Library for Arduino@1.6.4
 bitbank2/AnimatedGIF@2.2.0
'''
 if cache:
  # Optional reuse of existing PUBLIC dependency source cache; never binaries.
  for folder,version in [('ArduinoJson','7.4.3'),('GFX Library for Arduino','1.6.4'),('AnimatedGIF','2.2.0')]:
   src=Path(cache)/folder;meta=(src/'library.properties').read_text()
   if '\nversion='+version+'\n' not in '\n'+meta:raise ValueError('Dependency version drift')
   shutil.copytree(src,project/'lib'/folder,ignore=shutil.ignore_patterns('.git','.pio','*.a','*.o','*.bin','*.elf'))
  deps=''
 ini='''[platformio]
default_envs=b54_inert_base, b54_inert_handoff
[env]
platform=espressif8266@4.2.1
platform_packages=platformio/framework-arduinoespressif8266@3.30102.0
board=esp12e
framework=arduino
board_build.flash_mode=dio
board_build.flash_size=4MB
board_build.ldscript=eagle.flash.4m2m.ld
upload_protocol=custom
extra_scripts=pre:inert_guard.py
build_flags=
 -DARDUINOJSON_POOL_CAPACITY=8
 -DSHINO_BOOT_PROFILE=1
 -DSHINO_M9_NORMAL_QUALIFICATION=1
 -DSHINO_M3R_NATIVE_INERT=1
 -DSHINO_B53_AUTONOMY_EXPERIMENTAL=1
 -DSHINO_B53_DIAGNOSTIC_OFF=1
 -DSHINO_B54_LAN_WEATHER=1
 -DSHINO_UPDATER_FLASH_BUFFER_512=1
 -DSHINO_M3C_INCREMENTAL_HMAC=1
 -DPIO_FRAMEWORK_ARDUINO_LWIP2_LOW_MEMORY_LOW_FLASH
 -fstack-usage
 -Wl,-u,shino_m3r_stagea_link_probe
 -Wl,-u,shino_native_gate_size
'''+deps+'''[env:b54_inert_base]
build_flags=${env.build_flags} -DSHINO_M3R_NATIVE_HANDOFF=0
[env:b54_inert_handoff]
build_flags=${env.build_flags} -DSHINO_M3R_NATIVE_HANDOFF=1
'''
 write(project/'platformio.ini',ini)
 # Closed hashes of every generated input, including independent binding headers.
 inventory={p.relative_to(project).as_posix():sha(p.read_bytes()) for p in project.rglob('*') if p.is_file()}
 write(project/'INERT_INPUTS.json',json.dumps(inventory,indent=2))
 write(output/'native-projection.json',json.dumps(dict(scope='INERT_NATIVE_COMPOSITION_NEVER_CALLED',source_commit=public.PUBLIC_COMMIT,provenance=provenance,core_pins=FRAMEWORK_PINS),indent=2))
 return project

if __name__=='__main__':
 a=argparse.ArgumentParser();a.add_argument('--source-review',required=True);a.add_argument('--output',required=True);a.add_argument('--core',required=True);a.add_argument('--dependency-cache');x=a.parse_args()
 print(prepare(x.source_review,x.output,x.core,x.dependency_cache))
