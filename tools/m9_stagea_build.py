"""Paired actual StageA public compile copies. Never read private/frozen inputs."""
from pathlib import Path
import argparse,configparser,hashlib,json,shutil,subprocess
ROOT=Path(__file__).resolve().parents[1]
POLICY='''// Public inert identity, not a release or device identity.
#pragma once
#define SHINO_FACTORY_BYTES 494144
#define SHINO_FACTORY_MD5 "00000000000000000000000000000000"
#define SHINO_FACTORY_SHA256 "0000000000000000000000000000000000000000000000000000000000000000"
#define SHINO_ENABLE_FACTORY_RESTORE 0
#define SHINO_ENABLE_NATIVE_SIGNED_OTA 0
#define SHINO_ENABLE_FS_MIGRATION 0
#define SHINO_FS_IMAGE_PRESENT 0
#define SHINO_FS_BYTES 2072576
#define SHINO_FS_SHA256 ""
#define SHINO_FS_MD5 ""
#ifndef SHINO_BOOT_PROFILE
#define SHINO_BOOT_PROFILE 0
#endif
#define SHINO_SETUP_AP_PSK "PUBLIC-INERT-AP-FIXTURE"
#define SHINO_BOOTSTRAP_API_TOKEN "PUBLIC-INERT-TOKEN-FIXTURE-00000000"
#define SHINO_RESCUE_HTTP_USER "shino"
#define SHINO_RESCUE_HTTP_PASSWORD "PUBLIC-INERT-LAB-HTTP-FIXTURE"
'''
ENV='esp12e_m9_4m2m_normal_qualification'

def prepare(directory,integrated):
    directory=Path(directory).resolve()
    assert ROOT/'research-local' in directory.parents,'Disposable workspace copies only'
    assert not (directory/'include/shino_private_policy.h').exists(),'Refuse existing identity'
    tracked=subprocess.run(['git','ls-files','firmware'],cwd=ROOT,capture_output=True,text=True,check=True).stdout.splitlines()
    inputs={}
    for name in tracked:
        source=ROOT/name;relative=Path(name).relative_to('firmware')
        assert 'private' not in relative.parts and relative.name not in ('shino_private_policy.h','private.key')
        target=directory/relative;target.parent.mkdir(parents=True,exist_ok=True)
        data=source.read_bytes();target.write_bytes(data);inputs[name]=hashlib.sha256(data.replace(b'\r\n',b'\n')).hexdigest()
    (directory/'include/shino_private_policy.h').write_text(POLICY,encoding='utf-8')
    (directory/'include/project_version.h').write_text('#pragma once\n#define PROJECT_VER "PUBLIC-T-STAGEA"\nstatic const char PROJECT_VER_STR[]="PUBLIC-T-STAGEA";\n')
    ini=configparser.ConfigParser(interpolation=None);ini.read(directory/'platformio.ini')
    ini['env:esp12e']['extra_scripts']=''
    normal=ini['env:'+ENV]
    normal['extra_scripts']='pre:scripts/m9_normal_qualification_gate.py\npre:scripts/phase_t_build.py'
    normal['build_flags']+='\n-DM9_SIGNED_OTA_UNWIRED=1\n-I'+str(ROOT/'experiments/m9_signed_ota/include').replace('\\','/')+'\n-I'+str(ROOT/'experiments/m9_stagea_ota/include').replace('\\','/')
    # Dependency versions fixed to the same versions in both public graphs.
    ini['env:esp12e']['lib_deps']='bblanchon/ArduinoJson@7.4.3\nmoononournation/GFX Library for Arduino@1.6.4\nbitbank2/AnimatedGIF@2.2.0'
    with (directory/'platformio.ini').open('w',encoding='utf-8') as f:ini.write(f)
    script='''from SCons.Script import COMMAND_LINE_TARGETS,Import
from pathlib import Path
import sys
Import('env')
if any(any(word in str(t).lower() for word in ('upload','buildfs','erase','monitor','program')) for t in COMMAND_LINE_TARGETS):raise RuntimeError('OFFLINE ONLY')
if env.subst('$PIOENV')!='esp12e_m9_4m2m_normal_qualification':raise RuntimeError('Unreviewed graph')
if env.BoardConfig().get('build.arduino.signing',False) or (Path(env.subst('$PROJECT_DIR'))/'private.key').exists():raise RuntimeError('No signing key')
'''
    script+=f"sys.path.insert(0,{str(ROOT/'tools')!r})\n"
    script+=('from m9_stagea_webserver import materialize\n' if integrated else
             "sys.path.insert(0,str(Path(env.subst('$PROJECT_DIR'))/'scripts'))\nfrom m9_normal_webserver import materialize\n")
    script+="headers=materialize(env.PioPlatform().get_package_dir('framework-arduinoespressif8266'),Path(env.subst('$PROJECT_DIR'))/'.pio/m9-normal-libs/ESP8266WebServer')\nenv.Prepend(CPPPATH=[str(headers)])\n"
    (directory/'scripts/phase_t_build.py').write_text(script,encoding='utf-8')
    if integrated:
        path=directory/'src/boot/M9NormalStageA.cpp';text=path.read_text()
        text=text.replace('namespace M9NormalDashboard { void render(); }','void retainM9StageAProof();\nnamespace M9NormalDashboard { void render(); }',1)
        text=text.replace('void loop() {','void loop() {\n    retainM9StageAProof(); // Address reads only; no proof invocation.',1)
        text+='\n#if SHINO_M9_NORMAL_QUALIFICATION == 1\n#include "M9StageALink.inc"\n#endif\n'
        path.write_text(text,encoding='utf-8')
    (directory/'public-inputs.json').write_text(json.dumps(dict(integrated=integrated,firmware_LF_sha256=inputs,identity_sha256=hashlib.sha256(POLICY.encode()).hexdigest()),indent=2))
    return directory

if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('directory',type=Path);p.add_argument('--integrated',action='store_true');a=p.parse_args()
    print(prepare(a.directory,a.integrated))
