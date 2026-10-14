"""B5.2 CLOCK public inert source graph and compile, offline only.

Public builds remain inert. Private builds are explicit and owner-local only,
using B5.1 protected credentials. No device or install actions.
Outputs must be new ignored directories; retained artifacts stay read-only.
"""
import argparse
import configparser
import hashlib
import json
import shutil
import subprocess
from pathlib import Path
from shino_b5_lan_build import prepare as prepare_b51,inspect_build,once,ROOT
from shino_owner_transition import OWNER
from m9_stagea_build import ENV

NATIVE=ROOT/"experiments/b52_clock/native"

def patch_clock(source):
    source=once(source,'#include "B5Lan.h"','#include "B5Lan.h"\n#include "B52Clock.h"')
    # The generated LAN diagnostic must identify the new clock firmware.
    source=once(source,'B5.1','B5.2')
    source=once(source,'Upload,LanIntent,LanProvision,LanStatus};',
        'Upload,LanIntent,LanProvision,LanStatus,ClockSync,ClockStatus};')
    source=once(source,'if(path=="/api/v1/lan/status")return Route::LanStatus;',
        'if(path=="/api/v1/lan/status")return Route::LanStatus;\n'
        '        if(path=="/api/v1/clock/status")return Route::ClockStatus;')
    source=once(source,'if(path=="/api/v1/lan/provision")return Route::LanProvision;',
        'if(path=="/api/v1/lan/provision")return Route::LanProvision;\n'
        '        if(path=="/api/v1/clock/sync")return Route::ClockSync;')
    source=once(source,'if(selected==Route::MetricsPost&&(bytes<16||bytes>384||server.header("Content-Type")!="application/json")){',
        'if(selected==Route::ClockSync&&(bytes!=B52Clock::FRAME_BYTES||server.header("Content-Type")!="application/octet-stream")){'
        'respond(413,"{\\\"error\\\":\\\"CLOCK_FRAME_BOUND\\\"}");return false;}\n'
        '    if(selected==Route::MetricsPost&&(bytes<16||bytes>384||server.header("Content-Type")!="application/json")){')
    source=once(source,'bool deferRequest(){server.keepAlive(false);requestPending=true;return false;}',
        '#include "B52ClockHttp.inc"\n'
        'bool deferRequest(){server.keepAlive(false);requestPending=true;return false;}')
    source=once(source,'case Route::LanStatus:lanStatus();break;',
        'case Route::LanStatus:lanStatus();break;\n'
        '        case Route::ClockSync:clockSync();break;\n'
        '        case Route::ClockStatus:clockStatus();break;')
    source=once(source,'if(configReady)M9NormalDashboard::render();',
        'if(configReady)B52Clock::refreshMetrics();')
    source=once(source,'M9NormalDashboard::render();lastDraw=now;lastStale=stale;dirty=false;',
        'B52Clock::refreshMetrics();lastDraw=now;lastStale=stale;dirty=false;')
    source=once(source,'    ESP.wdtFeed();yield();observer.poll();',
        '    if(configReady&&apReady)B52Clock::step(now);\n'
        '    ESP.wdtFeed();yield();observer.poll();')
    return source

def prepare(directory,private=False):
    directory=Path(directory).resolve()
    if directory.exists():raise ValueError("New B5.2 output directory required")
    if private and OWNER.resolve() not in directory.parents:
        raise ValueError("B5.2 private candidate must remain in ignored owner-local storage")
    directory,device,build_id=prepare_b51(directory,private=private)
    normal=directory/"src/boot/M9NormalStageA.cpp"
    normal.write_text(patch_clock(normal.read_text(encoding="utf-8")),encoding="utf-8",newline="\n")
    for name,target in (("B52Clock.h","include/B52Clock.h"),("ClockFreshness.h","include/ClockFreshness.h"),("B52Clock.cpp","src/boot/B52Clock.cpp"),("B52ClockHttp.inc","include/B52ClockHttp.inc")):
        shutil.copyfile(NATIVE/name,directory/target)
    shutil.copyfile(ROOT/"firmware/include/display/ClockFoundation.h",directory/"include/display/ClockFoundation.h")
    # Public: synthetic identity. Private: preserve the real release identity.
    if not private:
        release=directory/"include/ShinoRelease.h"
        release.write_text(once(release.read_text(encoding="utf-8"),'#define SHINO_OTA_BUILD "'+build_id+'"',
            '#define SHINO_OTA_BUILD "'+'c'*64+'"'),encoding="utf-8")
        build_id="c"*64
    ini=configparser.ConfigParser(interpolation=None);ini.read(directory/"platformio.ini")
    ini["env:"+ENV]["build_src_filter"]+=" -<boot/M9NormalDashboard.cpp>"
    with (directory/"platformio.ini").open("w",encoding="utf-8") as f:ini.write(f)
    return directory,device,build_id

def build(directory,libraries,private=False):
    libraries=Path(libraries).resolve()
    for name,version in (("ArduinoJson","7.4.3"),("GFX Library for Arduino","1.6.4"),("AnimatedGIF","2.2.0")):
        if "version="+version not in (libraries/name/"library.properties").read_text(encoding="utf-8"):
            raise ValueError("Pinned public dependency required: "+name)
    directory,device,build_id=prepare(directory,private=private)
    # Use existing pinned library sources; prevent registry resolution/download.
    ini=configparser.ConfigParser(interpolation=None);ini.read(directory/"platformio.ini")
    ini["env:esp12e"]["lib_deps"]=""
    ini["env:"+ENV]["lib_extra_dirs"]+="\n"+libraries.as_posix()
    with (directory/"platformio.ini").open("w",encoding="utf-8") as f:ini.write(f)
    pio=shutil.which("pio") or shutil.which("platformio")
    if not pio:raise ValueError("PlatformIO unavailable")
    import os
    environment=dict(os.environ,PLATFORMIO_SETTING_ENABLE_TELEMETRY="no",
        PLATFORMIO_SETTING_CHECK_PLATFORMIO_INTERVAL="0",
        PLATFORMIO_SETTING_CHECK_PLATFORMS_INTERVAL="0",
        PLATFORMIO_SETTING_CHECK_LIBRARIES_INTERVAL="0")
    with (directory/"build.log").open("x",encoding="utf-8") as log:
        result=subprocess.run([pio,"run","-d",str(directory),"-e",ENV],
            cwd=ROOT,env=environment,stdin=subprocess.DEVNULL,stdout=log,stderr=subprocess.STDOUT,timeout=1200)
    if result.returncode:raise RuntimeError("Public B5.2 compile failed; inspect new build.log")
    report=inspect_build(directory,device,build_id,private=private)
    report.update(firmware="B5.2-CLOCK-OWNER-PRIVATE" if private else "B5.2-CLOCK-PUBLIC-INERT",
        clock_authority=private,
        clock_protocol="shino-pc-clock-2",clock_frame_bytes=64,clock_max_lease_s=120,
        clock_challenge_ms=2000,
        clock_renderer_heap_allocations=0,private_build=private,
        music_receiver_integrated=False,physical="NOT_RUN")
    report["clock_inputs_sha256"]={p:hashlib.sha256((ROOT/p).read_bytes()).hexdigest() for p in
        ("firmware/include/display/ClockFoundation.h","firmware/include/display/SceneEngine.h",
         "experiments/b52_clock/native/B52Clock.h","experiments/b52_clock/native/ClockFreshness.h","experiments/b52_clock/native/B52Clock.cpp",
         "experiments/b52_clock/native/B52ClockHttp.inc","tools/shino_b52_clock_build.py")}
    (directory/"report.json").write_text(json.dumps(report,indent=2)+"\n")
    return report

if __name__=="__main__":
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument("directory",type=Path)
    p.add_argument("--libraries",type=Path,required=True)
    p.add_argument("--private",action="store_true",
                   help="Owner-local offline candidate only; no install or device access")
    a=p.parse_args()
    result=build(a.directory,a.libraries,private=a.private)
    if a.private:
        print("B52_OWNER_PRIVATE_BUILD_OFFLINE_ONLY — PHYSICAL_NO_GO")
    else:
        print(json.dumps(result,indent=2))

