"""Prepare a fresh owner-local B5.1 successor packet, OFFLINE ONLY.

Verify retained installed B5 without changing it. Private builds stay ignored;
no socket to SmallTV, OTA, reboot, Wi-Fi provision, flash, RTC or serial access.
"""
import argparse
import json
import re
import subprocess
import sys
from pathlib import Path
from shino_b5_lan_build import ROOT,ENV,build
from shino_owner_transition import OWNER,load

sys.path.insert(0,str(ROOT/"companion"))
from shino_update import inspect,unique

LAYOUT={"_FS_start":0x40400000,"_FS_end":0x405FA000,"_EEPROM_start":0x405FB000}
BRANCH="feature/shino-tv-b3-telemetry-scratch-experiment"


def staging(current_bytes,target_bytes):
    if not all(type(x) is int and 64000<=x<=0xFEFF0 for x in (current_bytes,target_bytes)):
        raise ValueError("Application bounds")
    current=(current_bytes+4095)&~4095;target=(target_bytes+4095)&~4095
    stage=0x200000-target
    if stage<current+4096:raise ValueError("Staging overlap / missing guard")
    return dict(staging_start=stage,staging_end=0x200000,guard_bytes=stage-current,
                littlefs_start=0x200000,sdk_start=0x3fd000,sdk_end=0x400000)


def verify_installed(binary,manifest,report,expected_sha,expected_build,expected_source):
    for value,size in ((expected_sha,64),(expected_build,64),(expected_source,40)):
        if not isinstance(value,str) or not re.fullmatch("[0-9a-f]{"+str(size)+"}",value):
            raise ValueError("Exact installed identity/source required")
    report=Path(report)
    if report.is_symlink() or not report.is_file() or report.stat().st_size>32768:
        raise ValueError("Regular bounded installed report required")
    prior,raw=inspect(binary,manifest) # independent BIN SHA, CRC, segments/tag
    proof=json.loads(report.read_text(encoding="utf-8"),object_pairs_hook=unique)
    if (prior["sha256"]!=expected_sha or prior["build_id"]!=expected_build or
        proof.get("source_commit")!=expected_source or proof.get("sha256")!=expected_sha or
        proof.get("build_id")!=expected_build or proof.get("bytes")!=len(raw) or
        proof.get("layout_symbols")!=LAYOUT):
        raise ValueError("Installed B5 file/provenance/layout mismatch")
    return prior


def prepare(output,binary,manifest,report,expected_sha,expected_build,expected_source):
    output=Path(output).resolve()
    if output.exists() or output.is_symlink() or output.parent!=OWNER.resolve():
        raise ValueError("Fresh direct owner-local output required")
    for path in (binary,manifest,report):
        if OWNER.resolve() not in Path(path).resolve().parents:
            raise ValueError("Retained installed packet must be owner-local")
    def git(*args):return subprocess.check_output(["git",*args],cwd=ROOT,text=True).strip()
    if git("branch","--show-current")!=BRANCH or git("status","--porcelain"):
        raise ValueError("Clean exact review branch required")
    head=git("rev-parse","HEAD")
    old=subprocess.check_output(["git","show","61daba160446fb0ce00bf87d9a247821b29b0e33:ota/firmware/Normal.cpp"],cwd=ROOT)
    if (ROOT/"ota/firmware/Normal.cpp").read_bytes().replace(b"\r\n",b"\n")!=old.replace(b"\r\n",b"\n"):
        raise ValueError("Installed OTA receiver source changed")
    prior=verify_installed(binary,manifest,report,expected_sha,expected_build,expected_source)
    identity=load()
    if prior["device"]!=identity["device"]:raise ValueError("Retained owner identity mismatch")
    output.mkdir(mode=0o700);candidate=output/"B5.1"
    new=build(candidate,private=True)
    target,_=inspect(candidate/".pio/build"/ENV/"firmware.bin",candidate/"release.json")
    if (target["device"]!=prior["device"] or target["sha256"]==prior["sha256"] or
        target["build_id"]==prior["build_id"] or new["layout_symbols"]!=LAYOUT or
        new["source_commit"]!=head or new["source_dirty"] or new["firmware"]!="B5.1"):
        raise ValueError("Distinct clean same-device B5.1 required")
    result=dict(status="B51_PRIVATE_CANDIDATE_OFFLINE_ONLY",source_commit=head,
                installed_sha256=prior["sha256"],installed_build_id=prior["build_id"],installed_bytes=prior["bytes"],
                candidate_sha256=target["sha256"],candidate_build_id=target["build_id"],candidate_bytes=target["bytes"],
                static_ram=new["static_ram"],**staging(prior["bytes"],target["bytes"]),
                ota_offline_gate="HOLD_NATIVE_MEMORY",physical_authorized=False,
                native_ota_memory_measured=False,device_contacts=0,flash_writes=0,
                credential_writes=0,physical="NOT_RUN")
    (output/"B51-OFFLINE-REVIEW.json").write_text(json.dumps(result,indent=2)+"\n",encoding="utf-8")
    (output/"OWNER-QUALIFICATION.md").write_text(
        "# B5.1 — qualification physique HOLD\n\n"
        "Aucune operation appareil autorisee par ce paquet. Conserver tous les anciens recus et .attempt.\n"
        "Lire docs/SHINO_B51_HOME_LAN_RECOVERY.md du commit source indique dans B51-OFFLINE-REVIEW.json.\n"
        "Approuver separement le BIN/hash exact et UNE OTA B5->B5.1, puis la qualification/provisionnement.\n"
        "Le protocole commence par identite B5 et ressources fraiches, pas par un POST Wi-Fi.\n"
        "Apres boot B5.1, verifier d'abord les identifiants SDK deja presents ; ne pas les resaisir si verifies.\n",
        encoding="utf-8")
    return result


def main(argv=None):
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output",type=Path)
    parser.add_argument("--verify-installed-only",action="store_true")
    for name in ("installed-bin","installed-manifest","installed-report"):
        parser.add_argument("--"+name,type=Path,required=True)
    for name in ("expected-current-sha256","expected-current-build-id","expected-current-source"):
        parser.add_argument("--"+name,required=True)
    a=parser.parse_args(argv)
    try:
        args=(a.installed_bin,a.installed_manifest,a.installed_report,a.expected_current_sha256,
              a.expected_current_build_id,a.expected_current_source)
        if a.verify_installed_only:
            prior=verify_installed(*args)
            result={k:prior[k] for k in ("sha256","build_id","bytes","layout")}
            result.update(status="RETAINED_FILES_VERIFIED_NOT_A_LIVE_IDENTITY_READ",device_contacts=0)
        else:
            if a.output is None:raise ValueError("Fresh output required")
            result=prepare(a.output,*args)
        print(json.dumps(result,indent=2));return 0
    except Exception:
        print("B51_OFFLINE_HOLD: identity, source, build or layout gate refused; private details redacted")
        return 2


if __name__=="__main__":raise SystemExit(main())
