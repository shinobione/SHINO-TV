"""Prepare owner-local B5 Home LAN candidate from exact installed B4, OFFLINE.

No device operations, no OTA or serial commands; never publish local binaries,
identities, Wi-Fi passwords, credentials, owner dumps or one-shot receipts.
"""
import argparse
import hashlib
import json
import subprocess
import sys
from pathlib import Path
from shino_b5_lan_build import ROOT,ENV,build
from shino_owner_transition import OWNER,load

B4_SHA="b174e76089dce68f2e75697d4f8c5de9a8e7f93b4679cdf99e9c2756cd5ac1d5"
B4_BYTES=407552
BRANCH="feature/shino-tv-b3-telemetry-scratch-experiment"


def prepare(output:Path):
    output=output.resolve()
    if output.exists() or output.is_symlink() or output.parent!=OWNER.resolve():
        raise ValueError("Fresh owner-private candidate directory required")
    if subprocess.check_output(["git","branch","--show-current"],cwd=ROOT,text=True).strip()!=BRANCH:
        raise ValueError("Wrong review branch")
    if subprocess.check_output(["git","status","--porcelain"],cwd=ROOT,text=True).strip():
        raise ValueError("Dirty tracked checkout: STOP")
    head=subprocess.check_output(["git","rev-parse","HEAD"],cwd=ROOT,text=True).strip()
    # Verify installed receiver source stays untouched, even though B5 is opt-in.
    old=subprocess.check_output(["git","show",
        "61daba160446fb0ce00bf87d9a247821b29b0e33:ota/firmware/Normal.cpp"],cwd=ROOT)
    if (ROOT/"ota/firmware/Normal.cpp").read_bytes().replace(b"\r\n",b"\n")!=old.replace(b"\r\n",b"\n"):
        raise ValueError("B4 OTA receiver source changed")
    sys.path.insert(0,str(ROOT/"companion"))
    from shino_update import inspect
    current=OWNER/"b4-owner-20261011-165008"/"B4"
    current_bin=current/".pio/build"/ENV/"firmware.bin"
    current_manifest=current/"release.json"
    prior,raw=inspect(current_bin,current_manifest)
    identity=load()
    if (prior["sha256"]!=B4_SHA or len(raw)!=B4_BYTES or
        prior["device"]!=identity["device"]):
        raise ValueError("Installed B4 packet mismatch")
    output.mkdir(mode=0o700)
    candidate=output/"B5"
    new=build(candidate,private=True)
    release,raw=inspect(candidate/".pio/build"/ENV/"firmware.bin",candidate/"release.json")
    if (release["device"]!=identity["device"] or release["sha256"]==B4_SHA or
        release["build_id"]==prior["build_id"] or not new["layout_symbols"]==
        {"_FS_start":0x40400000,"_FS_end":0x405FA000,"_EEPROM_start":0x405FB000}):
        raise ValueError("B5 mismatch / flash layout")
    stage=0x200000-((len(raw)+4095)&~4095)
    if stage<((len(current_bin.read_bytes())+4095)&~4095)+4096:
        raise ValueError("Staging collides with installed B4")
    result=dict(status="B5_PRIVATE_CANDIDATE_OFFLINE_ONLY",
        installed_B4_sha256=B4_SHA,candidate_B5_sha256=release["sha256"],
        candidate_B5_bytes=len(raw),staging_start=stage,static_ram=new["static_ram"],
        ota_offline_gate="HOLD",physical_authorized=False,
        native_ota_memory_measured=False,device_contacts=0,flash_writes=0)
    (output/"B5-OFFLINE-REVIEW.json").write_text(json.dumps(result,indent=2)+"\n")
    return result


if __name__=="__main__":
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument("--output",type=Path,required=True)
    a=p.parse_args()
    try:
        r=prepare(a.output)
        print(json.dumps(r,indent=2))
    except (ValueError,OSError,RuntimeError):
        print("B5_OFFLINE_HOLD: source, private BIN, build or layout gate refused")
        raise SystemExit(2)
