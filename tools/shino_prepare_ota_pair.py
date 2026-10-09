"""Prepare one private A/B qualification packet. Offline; no hardware APIs."""
import argparse
import hashlib
import json
import subprocess
from pathlib import Path
from shino_http_ota_build import build,ROOT,ENV
from shino_owner_transition import OWNER,load


def prepare(directory):
    directory=Path(directory).resolve()
    if OWNER.resolve() not in directory.parents or directory.exists():raise ValueError("Fresh owner-local packet directory required")
    if subprocess.check_output(["git","branch","--show-current"],cwd=ROOT,text=True).strip()!="feature/shino-tv-m9-flash-layout-liberation":raise ValueError("Wrong branch")
    if subprocess.check_output(["git","status","--porcelain"],cwd=ROOT,text=True).strip():raise ValueError("Commit reviewed source before private pair")
    config=load();protected={}
    old=OWNER/"transition-build/.pio/build"/ENV/"firmware.bin"
    for path in (old,OWNER/"owner-credentials.json",OWNER/"transition-report.json",OWNER/"transition-manifest.json"):
        protected[str(path.relative_to(ROOT))]=hashlib.sha256(path.read_bytes()).hexdigest()
    directory.mkdir(parents=True)
    a=build(directory/"A",True);b=build(directory/"B",True)
    if a["sha256"]==b["sha256"] or a["build_id"]==b["build_id"]:raise ValueError("A/B must differ")
    for name in ("A","B"):
        raw=(directory/name/".pio/build"/ENV/"firmware.bin").read_bytes()
        for field in ("ap_psk","api_token","digest_password"):
            if config[field].encode() not in raw:raise ValueError("Owner credentials not retained in candidate")
        if hashlib.sha256(config["maintenance_password"].encode()).digest() not in raw:raise ValueError("Update key differs")
    for path,sha in protected.items():
        if hashlib.sha256((ROOT/path).read_bytes()).hexdigest()!=sha:raise ValueError("Protected owner file changed")
    updater=ROOT/"companion/shino_update.py"
    launcher=f'@echo off\ncd /d "{ROOT}"\npython "{updater}" --gui --manifest "{directory/"B/release.json"}" --receipt "{directory/"OTA-B-receipt.json"}"\n'
    (directory/"UPDATE-B.cmd").write_text(launcher,encoding="utf-8")
    for name,report in (("A",a),("B",b)):
        launcher=(f'@echo off\ncd /d "{ROOT}"\n'
                  f'echo SHINO qualification {name}: lectures HTTP seulement, LINK doit fonctionner.\n'
                  f'echo SHA-256 {report["sha256"]}\n'
                  'choice /C ON /N /M "Autoriser ces lectures appareil (O/N) ? "\nif errorlevel 2 exit /b 1\n'
                  f'python "{ROOT/"companion/shino_qualify.py"}" --bin "{directory/name/".pio/build"/ENV/"firmware.bin"}" '
                  f'--manifest "{directory/name/"release.json"}" --authorize-read --receipt "{directory/(name+"-readonly-receipt.json")}"\npause\n')
        (directory/("QUALIFY-"+name+".cmd")).write_text(launcher,encoding="utf-8")
    packet=dict(status="OFFLINE_READY_PHYSICAL_NOT_RUN",A=a,B=b,source_commit=a["source_commit"],protected_files_unchanged=True,
                serial_port="COM8",device_contacts=0,physical_authorized=False,
                sequence=["Fresh private 4MiB PRE readback and exact identity/size check under separate physical approval",
                          "One UART app-only write of exact A at address 0; independent POST protects application tail, LittleFS and SDK tail",
                          "Release GPIO0, boot A normally; read-only qualification with LINK and stable authenticated GET/POST",
                          "If A qualifies, one authenticated Wi-Fi upload of exact B; no repeated upload",
                          "Confirm new boot, full SHA256/build ID, LittleFS inventory/payload hashes, fresh metrics and future OTA capability",
                          "Only after physical acceptance: disconnect CH340 and close enclosure"],
                stop_on=["Reset/corruption","Memory floor failure","Identity or LittleFS mismatch","Uncertain write/boot","Unavailable recovery"],
                recovery="Private 4MiB backup and UART are the recovery path; no automatic rollback; no recovery write authorized")
    (directory/"qualification-packet.json").write_text(json.dumps(packet,indent=2)+"\n",encoding="utf-8")
    print("PRIVATE_A_B_PACKET_READY — PHYSICAL_NOT_RUN")
    print("A",a["bytes"],a["sha256"]);print("B",b["bytes"],b["sha256"])
    return packet


if __name__=="__main__":
    p=argparse.ArgumentParser(description=__doc__);p.add_argument("directory",type=Path);a=p.parse_args();prepare(a.directory)
