"""B5.3 public-inert graph: B5.2 authenticated PC clock + native SNTP fallback."""
import argparse,configparser,hashlib,json,os,shutil,subprocess
from pathlib import Path
from shino_b52_clock_build import prepare as prepare_b52,ROOT,ENV
from shino_b5_lan_build import once,inspect_build
from shino_b53_layout import patch_design
SOURCE=ROOT/"experiments/b53_autonomous"
PINNED=(("ArduinoJson","7.4.3"),("GFX Library for Arduino","1.6.4"),("AnimatedGIF","2.2.0"))
def patch_clock(raw):
    raw=once(raw,'#include "B52Clock.h"','#include "B52Clock.h"\n#include "B53Sntp.h"')
    raw=once(raw,'bool clockChanged=true,lastValid=false;\nuint32_t lastMinute=0,lastGeneration=0;',
             'bool clockChanged=true;\nuint8_t lastAuthority=255;\nuint32_t lastMinute=0,lastGeneration=0;')
    before="""    const auto s=clockState.snapshot(now);
    const uint32_t minute=s.valid?s.utc/60:0;
    if(clockChanged||s.valid!=lastValid||minute!=lastMinute||s.generation!=lastGeneration){
        renderer.setClock(clockState.view(now));
        clockChanged=false;lastValid=s.valid;lastMinute=minute;lastGeneration=s.generation;
    }"""
    after="""    B53Sntp::poll(now);
    const auto pc=clockState.snapshot(now);
    uint32_t ntpUtc=0;
    const bool fallback=!pc.valid && B53Sntp::current(now,ntpUtc);
    const uint8_t authority=pc.valid?1:(fallback?2:0);
    const uint32_t minute=pc.valid?pc.utc/60:(fallback?ntpUtc/60:0);
    if(clockChanged||authority!=lastAuthority||minute!=lastMinute||
       pc.generation!=lastGeneration){
        ArtworkPilot::ClockData selected{};
        if(pc.valid)selected=clockState.view(now);
        else if(fallback)B53Sntp::view(now,selected);
        renderer.setClock(selected);
        clockChanged=false;lastAuthority=authority;lastMinute=minute;
        lastGeneration=pc.generation;
    }"""
    raw=once(raw,before,after)
    return once(raw,'void refreshMetrics(){',
        'void setWeather(const ArtworkPilot::WeatherData& sample){renderer.setWeather(sample);}\nvoid refreshMetrics(){')
def patch_scene(raw):
    raw=once(raw,'enum class ClockSource : uint8_t { Unknown, PairedPc };',
             'enum class ClockSource : uint8_t { Unknown, PairedPc, Sntp };')
    raw=once(raw,'            } else c.text(8,12,scene == Scene::Offline ? "PC OFFLINE" : "SHINO // TV",LABEL);',
             '            } else if (clock.source == ClockSource::Sntp)\n'
             '                c.text(8,12,clockFresh(now) ? "NTP EUROPE/PARIS" : "NTP CLOCK EXPIRED",LABEL);\n'
             '            else c.text(8,12,scene == Scene::Offline ? "WAITING NTP / PC" : "SHINO // TV",LABEL);')
    return once(raw,'scene == Scene::Offline ? "WAITING FOR PC" : "TIME NOT SYNCED"',
                'scene == Scene::Offline ? "WAITING NTP" : "TIME NOT SYNCED"')
def prepare(destination):
    destination=Path(destination).resolve()
    if destination.exists():raise ValueError("New B5.3 public output required")
    dest,device,build_id=prepare_b52(destination,private=False)
    for path,func in ((dest/"src/boot/B52Clock.cpp",patch_clock),
                      (dest/"include/display/SceneEngine.h",lambda raw:patch_design(patch_scene(raw)))):
        path.write_text(func(path.read_text(encoding="utf-8")),encoding="utf-8",newline="\n")
    normal=dest/"src/boot/M9NormalStageA.cpp"
    marker='apReady=B5Lan::begin("SHINO-TV-StageA",SHINO_SETUP_AP_PSK);if(!apReady)return;'
    source=once(normal.read_text(encoding="utf-8"),'#include "B52Clock.h"',
                '#include "B52Clock.h"\n#include "B53Sntp.h"')
    source=once(source,'#include "B53Sntp.h"',
                '#include "B53Sntp.h"\n#include "B53WeatherHttps.h"')
    source=once(source,marker,marker+'\n    B53Sntp::begin();\n    B53WeatherHttps::begin("","");')
    source=once(source,'B52Clock::step(now);',
                'B53WeatherHttps::poll(now,uploadBusy,requestPending,FslessMetrics::stale());\n        B52Clock::step(now);')
    normal.write_text(source,
                      encoding="utf-8",newline="\n")
    shutil.copyfile(SOURCE/"native/B53Sntp.cpp",dest/"src/boot/B53Sntp.cpp")
    shutil.copyfile(SOURCE/"native/B53Sntp.h",dest/"include/B53Sntp.h")
    shutil.copyfile(SOURCE/"include/B53AutonomyPolicy.h",dest/"include/B53AutonomyPolicy.h")
    shutil.copyfile(SOURCE/"include/B53Layout.h",dest/"include/B53Layout.h")
    header=dest/"include/B52Clock.h"
    header.write_text(once(header.read_text(encoding="utf-8"),'void refreshMetrics();',
        'void setWeather(const ArtworkPilot::WeatherData& sample);\nvoid refreshMetrics();'),
        encoding="utf-8",newline="\n")
    for name,where in (("B53WeatherHttps.cpp","src/boot/B53WeatherHttps.cpp"),
        ("B53WeatherHttps.h","include/B53WeatherHttps.h"),
        ("B53WeatherCA.h","include/B53WeatherCA.h")):
        shutil.copyfile(SOURCE/"native"/name,dest/where)
    for name in ("B53WeatherFrame.h","B53WeatherGate.h"):
        shutil.copyfile(SOURCE/"include"/name,dest/"include"/name)
    return dest,device,build_id
def build(directory,libraries):
    libs=Path(libraries).resolve()
    for name,version in PINNED:
        p=libs/name/"library.properties"
        if not p.is_file() or "version="+version not in p.read_text(encoding="utf-8"):
            raise ValueError("B5.3 missing pinned library "+name)
    dest,device,build_id=prepare(directory)
    ini=configparser.ConfigParser(interpolation=None);ini.read(dest/"platformio.ini")
    ini["env:esp12e"]["lib_deps"]=""
    ini["env:"+ENV]["lib_extra_dirs"]+="\n"+libs.as_posix()
    with (dest/"platformio.ini").open("w",encoding="utf-8") as out:ini.write(out)
    pio=shutil.which("pio") or shutil.which("platformio")
    if not pio:raise ValueError("PlatformIO unavailable")
    env=dict(os.environ,PLATFORMIO_SETTING_ENABLE_TELEMETRY="no",
        PLATFORMIO_SETTING_CHECK_PLATFORMIO_INTERVAL="0",
        PLATFORMIO_SETTING_CHECK_PLATFORMS_INTERVAL="0",
        PLATFORMIO_SETTING_CHECK_LIBRARIES_INTERVAL="0")
    with (dest/"build.log").open("x",encoding="utf-8") as log:
        result=subprocess.run([pio,"run","-d",str(dest),"-e",ENV],cwd=ROOT,
            env=env,stdin=subprocess.DEVNULL,stdout=log,stderr=subprocess.STDOUT,timeout=1200)
    if result.returncode:raise RuntimeError("B5.3 public compile failed: see build.log")
    report=inspect_build(dest,device,build_id,private=False)
    report.update(firmware="B5.3-SNTP-PUBLIC-INERT",private_build=False,
        native_sntp_source=True,weather_network_source=True,weather_configured=False,
        ota_memory_native_measured=False,clock_authority=False,
        physical="NOT_RUN",device_contacts=0,ota_posts=0)
    (dest/"report.json").write_text(json.dumps(report,indent=2)+"\n",encoding="utf-8")
    return report
if __name__=="__main__":
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument("directory",type=Path);p.add_argument("--libraries",type=Path,required=True)
    a=p.parse_args();r=build(a.directory,a.libraries)
    print(json.dumps({"status":"PUBLIC_INERT_COMPILE_PASS","bytes":r["bytes"],
          "sha256":r["sha256"],"layout":r["layout"],"physical":"NOT_RUN"}))
