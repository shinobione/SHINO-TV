"""Prepare one private A/B qualification packet. Offline; no hardware APIs."""
import argparse
import hashlib
import json
import shutil
import subprocess
from pathlib import Path
from shino_http_ota_build import build,ROOT,ENV
from shino_owner_transition import OWNER,load


def prepare_uart(directory):
    """Bind a private copy of the existing single-attempt writer; never run it."""
    directory=Path(directory).resolve()
    if OWNER.resolve() not in directory.parents:raise ValueError("Owner-local packet required")
    report=json.loads((directory/"A/report.json").read_text(encoding="utf-8"))
    from m9_stage1_readback_verify import candidate_bytes
    binary=directory/"A/.pio/build"/ENV/"firmware.bin"
    data,inspected=candidate_bytes(binary,report["sha256"])
    if len(data)!=report["bytes"] or report["private"] is not True:raise ValueError("Exact private A required")
    bound=directory/"uart-A";bound.mkdir() # A fresh copy, no change to historical tools.
    names=("m9_single_attempt_app_write.py","m9_single_attempt_physical_runner.py",
           "m9_executor_preflight.py","m9_stage1_readback_verify.py","m9_first_migration.py",
           "m9_rtc_neutralization.py","m9_flash_layout.py","m9_phase_l_sources.json","m9_executor_sources.json")
    from m9_executor_preflight import check_hashes
    pins=json.loads((ROOT/"tools/m9_phase_l_sources.json").read_text(encoding="utf-8"))
    check_hashes(ROOT/"tools",pins["executor_helpers_sha256_lf"])
    for name in names:shutil.copyfile(ROOT/"tools"/name,bound/name)
    rounded=inspected["sector_rounded_write_extent"];blocks=rounded//4096
    target=bound/"m9_single_attempt_app_write.py";body=target.read_text(encoding="utf-8")
    replacements={"FROZEN_BYTES = 399264":f'FROZEN_BYTES = {len(data)}',
                  "FROZEN_SHA256 = '78a8d2d50409974fc775dd3dc9f3dbec4ac8eda839f6d9b338cadf35aab2467c'":f'FROZEN_SHA256 = {report["sha256"]!r}',
                  "ROUNDED_END = 0x062000":f'ROUNDED_END = {rounded:#x}',"BLOCK_COUNT = 98":f'BLOCK_COUNT = {blocks}'}
    for old,new in replacements.items():
        if body.count(old)!=1:raise ValueError("Existing writer binding drift")
        body=body.replace(old,new)
    target.write_text(body,encoding="utf-8")
    runner=bound/"m9_single_attempt_physical_runner.py"
    runner.write_text(runner.read_text(encoding="utf-8").replace("rounded_extent='0x000000..0x061FFF'",f"rounded_extent='0x000000..0x{rounded-1:06X}'"),encoding="utf-8")
    pins["executor_helpers_sha256_lf"][target.name]=hashlib.sha256(body.replace("\r\n","\n").encode()).hexdigest()
    (bound/"m9_phase_l_sources.json").write_text(json.dumps(pins,indent=2)+"\n",encoding="utf-8")
    from m9_rtc_neutralization import LOCAL_PYTHON
    argv=[LOCAL_PYTHON,"-I",str(runner),"--candidate",str(binary),"--expected-sha256",report["sha256"],"--port","COM8",
          "--stub-audit-root",str(ROOT/"research-local/m9-phase-c")]
    reader=[LOCAL_PYTHON,"-I","-m","esptool","--chip","esp8266","--port","COM8","--baud","115200",
            "--stub-version","2","--before","no-reset","--after","no-reset-stub","--connect-attempts","1","read-flash","0","0x400000"]
    commands=dict(status="PRINT_ONLY_NO_COMMAND_EXECUTED",physical_authorized=False,candidate_sha256=report["sha256"],
                  target=0,rounded_end=rounded,begin_count=1,data_blocks=blocks,finish_count=1,automatic_retries=0,
                  uart_audit_argv=argv,uart_execute_argv=argv+["--execute","--owner-go","GO SINGLE ATTEMPT "+report["sha256"]],
                  fresh_pre_argv=reader+[str(directory/"PRE-4MiB.bin")],fresh_post_argv=reader+[str(directory/"POST-4MiB.bin")],
                  verify_post_argv=[LOCAL_PYTHON,"-I",str(bound/"m9_stage1_readback_verify.py"),str(binary),str(directory/"PRE-4MiB.bin"),str(directory/"POST-4MiB.bin"),"--expected-sha256",report["sha256"]],
                  source_sha256_lf={p.name:hashlib.sha256(p.read_bytes().replace(b"\r\n",b"\n")).hexdigest() for p in bound.iterdir()},
                  prerequisites=["Explicit owner permission for exact A, COM8 and PRE/POST reads", "Manually established ROM download mode with GPIO0 LOW", "Fresh private PRE, exact installed image and same 4MiB device verified", "Independent POST verification before manual normal boot"],
                  stop="Any missing acknowledgement, uncertain write or identity mismatch: stop; no retry or recovery write")
    (directory/"uart-commands.json").write_text(json.dumps(commands,indent=2)+"\n",encoding="utf-8")
    return commands


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
                  f'--manifest "{directory/name/"release.json"}" --authorize-read --receipt "{directory/(name+"-readonly-receipt.json")}"\n'
                  'set "SHINO_QUALIFY_EXIT=%ERRORLEVEL%"\n'
                  'if not "%SHINO_QUALIFY_EXIT%"=="0" echo Qualification interrompue : voir le diagnostic ci-dessus.\n'
                  'pause\nexit /b %SHINO_QUALIFY_EXIT%\n')
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
    prepare_uart(directory)
    print("PRIVATE_A_B_PACKET_READY — PHYSICAL_NOT_RUN")
    print("A",a["bytes"],a["sha256"]);print("B",b["bytes"],b["sha256"])
    return packet


if __name__=="__main__":
    p=argparse.ArgumentParser(description=__doc__);p.add_argument("directory",type=Path);p.add_argument("--prepare-uart-only",action="store_true")
    a=p.parse_args()
    if a.prepare_uart_only:prepare_uart(a.directory);print("UART_COMMANDS_PREPARED_OFFLINE_NO_PORT_OPEN")
    else:prepare(a.directory)
