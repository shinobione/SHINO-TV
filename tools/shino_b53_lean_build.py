"""B5.3 lean offline build: SNTP + owner's 240px cards, no BearSSL.

Offline 4m2m graphs only. Private images confined to existing ignored owner-local
storage; no device, LAN, OTA, flash or secret emission.
The original weather-enabled B5.3 builder remains entirely unchanged.
"""
import argparse
import configparser
import json
import os
import re
import shutil
import subprocess
from pathlib import Path

from shino_b52_clock_build import prepare as prepare_b52, ROOT, ENV, private_source_gate
from shino_owner_transition import OWNER
from shino_b53_clock_build import patch_clock,patch_scene,PINNED,SOURCE
from shino_b53_layout import patch_design
from shino_b5_lan_build import inspect_build,once


PINNED_PLATFORMIO="6.1.18"

def pinned_platformio():
    """Fail closed unless the first PATH CLI matches the pinned Core."""
    binary=shutil.which("pio") or shutil.which("platformio")
    if not binary:
        raise ValueError("HOLD: pinned PlatformIO executable unavailable")
    try:
        result=subprocess.run([binary,"--version"],stdin=subprocess.DEVNULL,
            stdout=subprocess.PIPE,stderr=subprocess.STDOUT,text=True,
            timeout=10,check=False)
    except (OSError,subprocess.TimeoutExpired) as exc:
        raise ValueError("HOLD: PlatformIO version could not be checked") from exc
    if result.returncode or not re.fullmatch(
            r"PlatformIO Core,\s*version\s*6\.1\.18",
            (result.stdout or "").strip()):
        raise ValueError("HOLD: PlatformIO Core must be 6.1.18")
    return binary

def prepare(directory,private=False):
    dest=Path(directory).resolve()
    if private and OWNER.resolve() not in dest.parents:
        raise ValueError('HOLD: private output must remain under ignored owner-local directory')
    if dest.exists():
        raise ValueError("B5.3 lean requires a NEW public output directory")
    dest,device,build_id=prepare_b52(dest,private=private)
    clock=dest/"src/boot/B52Clock.cpp"
    new=patch_clock(clock.read_text(encoding="utf-8"))
    # No weather producer or setWeather() symbol in this variant.
    new=once(new,"void setWeather(const ArtworkPilot::WeatherData& sample){renderer.setWeather(sample);}\n","")
    clock.write_text(new,encoding="utf-8",newline="\n")

    screen=dest/"include/display/SceneEngine.h"
    screen.write_text(patch_design(patch_scene(screen.read_text(encoding="utf-8"))),
                      encoding="utf-8",newline="\n")

    normal=dest/"src/boot/M9NormalStageA.cpp"
    source=normal.read_text(encoding="utf-8")
    source=once(source,'#include "B52Clock.h"',
                '#include "B52Clock.h"\n#include "B53Sntp.h"')
    marker='apReady=B5Lan::begin("SHINO-TV-StageA",SHINO_SETUP_AP_PSK);if(!apReady)return;'
    source=once(source,marker,marker+"\n    B53Sntp::begin();")
    normal.write_text(source,encoding="utf-8",newline="\n")
    for name,where in (("B53Sntp.cpp","src/boot/B53Sntp.cpp"),
                       ("B53Sntp.h","include/B53Sntp.h")):
        shutil.copyfile(SOURCE/"native"/name,dest/where)
    for name in ("B53AutonomyPolicy.h","B53Layout.h"):
        shutil.copyfile(SOURCE/"include"/name,dest/"include"/name)
    return dest,device,build_id


def build(directory,libraries,private=False):
    if private: private_source_gate()
    pio=pinned_platformio()
    libs=Path(libraries).resolve()
    for name,version in PINNED:
        p=libs/name/"library.properties"
        if not p.is_file() or "version="+version not in p.read_text(encoding="utf-8"):
            raise ValueError("Missing pinned dependency "+name)
    dest,device,build_id=prepare(directory,private=private)
    ini=configparser.ConfigParser(interpolation=None)
    ini.read(dest/"platformio.ini")
    ini["env:esp12e"]["lib_deps"]=""
    ini["env:"+ENV]["lib_extra_dirs"]+="\n"+libs.as_posix()
    with (dest/"platformio.ini").open("w",encoding="utf-8") as f:
        ini.write(f)
    env=dict(os.environ,PLATFORMIO_SETTING_ENABLE_TELEMETRY="no",
             PLATFORMIO_SETTING_CHECK_PLATFORMIO_INTERVAL="0",
             PLATFORMIO_SETTING_CHECK_PLATFORMS_INTERVAL="0",
             PLATFORMIO_SETTING_CHECK_LIBRARIES_INTERVAL="0")
    with (dest/"build.log").open("x",encoding="utf-8") as log:
        process=subprocess.run([pio,"run","-d",str(dest),"-e",ENV],
            cwd=ROOT,env=env,stdin=subprocess.DEVNULL,
            stdout=log,stderr=subprocess.STDOUT,timeout=1200)
    if process.returncode:
        raise RuntimeError("B5.3 lean PUBLIC build failed; inspect build.log")
    report=inspect_build(dest,device,build_id,private=private)
    report.update(firmware="B5.3-LEAN-NTP-OWNER-PRIVATE" if private else "B5.3-LEAN-NTP-PUBLIC-INERT",
                  lean_variant=True,private_build=private,clock_authority=private,
                  native_sntp_source=True,weather_network_source=False,
                  weather_configured=False,physical="NOT_RUN",
                  ota_memory_native_measured=False,device_contacts=0,ota_posts=0)
    (dest/"report.json").write_text(json.dumps(report,indent=2)+"\n",encoding="utf-8")
    return report


if __name__=="__main__":
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument("directory",type=Path)
    parser.add_argument("--libraries",required=True,type=Path)
    parser.add_argument("--private",action="store_true",
                        help="Offline owner-local only: never installs or contacts hardware")
    args=parser.parse_args()
    report=build(args.directory,args.libraries,private=args.private)
    print(json.dumps({"status":"B53_LEAN_OWNER_PRIVATE_OFFLINE" if args.private else "B53_LEAN_PUBLIC_INERT_COMPILE",
          "bytes":report["bytes"],"sha256":report["sha256"],
          "static_ram":report["static_ram"],"layout":report["layout"],
          "physical":"NOT_RUN"},indent=2))
