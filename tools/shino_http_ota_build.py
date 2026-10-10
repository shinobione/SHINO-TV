"""Build normal SHINO HTTP OTA releases offline; never access hardware.

One source graph, public inert compile or existing owner-local credentials.
New output directories only. No old BIN, backup, package or secret rotation.
"""
import argparse
import configparser
import hashlib
import importlib.util
import json
import secrets
import shutil
import subprocess
import struct
from pathlib import Path

from m9_stagea_build import ROOT, ENV, prepare as stagea
from m9_signed_release import validate_image
from shino_wifi_resources import one
from shino_owner_transition import load, OWNER, PUBLIC


def elf_layout(path):
    raw=Path(path).read_bytes();offset=struct.unpack_from("<I",raw,32)[0]
    entry,count,_=struct.unpack_from("<HHH",raw,46)
    sections=[struct.unpack_from("<10I",raw,offset+i*entry) for i in range(count)];values={}
    for section in sections:
        if section[1]!=2:continue
        names=sections[section[6]];strings=raw[names[4]:names[4]+names[5]]
        for at in range(section[4],section[4]+section[5],section[9]):
            name,value=struct.unpack_from("<II",raw,at);label=strings[name:].split(b"\0",1)[0].decode()
            if label in ("_FS_start","_FS_end","_EEPROM_start"):values[label]=value
    if values!={"_FS_start":0x40400000,"_FS_end":0x405FA000,"_EEPROM_start":0x405FB000}:raise ValueError("Actual ELF is not the reviewed 4m2m layout")
    return values


def materialize_http(core, destination):
    spec=importlib.util.spec_from_file_location("ota_bounded_http",ROOT/"firmware/scripts/m9_normal_webserver.py")
    module=importlib.util.module_from_spec(spec);spec.loader.exec_module(module)
    headers=module.materialize(core,destination)
    parser=headers/"Parsing-impl.h"
    body=parser.read_text(encoding="utf-8")
    anchor="  String methodStr = req.substring(0, addr_start);"
    assert body.count(anchor)==1
    body=body.replace(anchor,anchor+'\n  if(methodStr != "GET" && methodStr != "POST") return CLIENT_MUST_STOP;')
    body=body.replace('"Transfer-Encoding","Connection"};','"Transfer-Encoding","Connection","Expect","X-Shino-SHA256","X-Shino-Build","X-Shino-Nonce","X-Shino-Proof"};')
    body=body.replace('i<6;++i','i<11;++i')
    parser.write_text(body,encoding="utf-8",newline="\n")
    return headers


def descriptor(device,build):
    return f"SHINO-HTTP-OTA-1|{device}|{build}|4m2m|APP_ONLY"


def stack_frames(directory):
    """Pinned compiler frame caps, never a whole-call-chain/device PASS."""
    root=Path(directory)/".pio/build"/ENV
    normal=(root/"src/boot/M9NormalStageA.cpp.su").read_text(encoding="utf-8")
    updater=(root/"FrameworkArduino/Updater.cpp.su").read_text(encoding="utf-8")
    caps={"identity":("::identity()",160),"metrics":("::metrics()",112),
          "normal_status":("::status()",256),
          "hmac_proof":("ShinoHttpOta::proof(",128),"ota_begin":("Transfer::begin(",128),
          "ota_upload":("::upload(uint32_t)",128),"ota_flash_read":("Transfer::read(",192),
          "ota_staging":("Transfer::stagedImage()",416),
          "ota_segments":("Transfer::segments(",352),"ota_finish":("Transfer::finish(",144),
          "core_end":("UpdaterClass::end(bool)",192)}
    measured={}
    for name,(marker,cap) in caps.items():
        source=updater if name=="core_end" else normal
        rows=[line.rsplit("\t",2) for line in source.splitlines() if marker in line]
        if len(rows)!=1 or len(rows[0])!=3 or rows[0][2]!="static":raise ValueError("Missing or unbounded stack frame: "+name)
        measured[name]=int(rows[0][1])
        if measured[name]>cap:raise ValueError(f"Compiled stack frame regressed: {name} {measured[name]} > {cap}")
    return measured


def prepare(directory,config=None):
    directory=Path(directory).resolve()
    if directory.exists():raise ValueError("New output directory required")
    private=config is not None
    if private and OWNER.resolve() not in directory.parents:raise ValueError("Owner sources must remain local and ignored")
    directory=stagea(directory,False)
    for name in ("Normal.cpp","ShinoHttpOta.h"):
        src=ROOT/"ota/firmware"/name
        target=directory/("src/boot/M9NormalStageA.cpp" if name=="Normal.cpp" else "include/ShinoHttpOta.h")
        shutil.copyfile(src,target)
    if private:
        device=config["device"];build=secrets.token_hex(32)
        key=hashlib.sha256(config["maintenance_password"].encode()).digest()
        policy=directory/"include/shino_private_policy.h"
        body=policy.read_text()
        for field in ("ap_psk","api_token","digest_password"):body=body.replace(PUBLIC[field],config[field])
        policy.write_text(body,encoding="utf-8")
    else:device="0123456789abcdef";build="a"*64;key=bytes(32)
    (directory/"include/ShinoRelease.h").write_text(
        '#pragma once\n#define SHINO_OTA_DEVICE "'+device+'"\n#define SHINO_OTA_BUILD "'+build+'"\n'
        +f'#define SHINO_OTA_PRIVATE {int(private)}\n'
        +'static constexpr uint8_t ShinoReleaseKey[32]={'+','.join(str(n) for n in key)+'};\n',encoding="utf-8")
    (directory/"include/project_version.h").write_text('#pragma once\n#define PROJECT_VER "SHINO-HTTP-OTA-1"\nstatic const char PROJECT_VER_STR[]="SHINO-HTTP-OTA-1";\n',encoding="utf-8")
    # Correct the retained normal serializer for this new product graph only.
    status=directory/"include/boot/M9NormalStatusJson.h"
    body=status.read_text()
    body=body.replace('native_ota_writer_enabled\\\":false','native_ota_writer_enabled\\\":'+str(private).lower())
    body=body.replace('rtc_writes_enabled\\\":false','rtc_writes_enabled\\\":'+str(private).lower()+',\\\"rtc_ota_commit_only\\\":true')
    status.write_text(body,encoding="utf-8")
    script=directory/"scripts/phase_t_build.py"
    body=script.read_text()
    start=body.index("sys.path.insert(0,str(Path(env.subst('$PROJECT_DIR'))/'scripts'))")
    body=body[:start]+"from shino_http_ota_build import materialize_http as materialize\n"+body[body.index("headers=materialize",start):]
    body+="""
from shino_wifi_core import materialize as abort_header
p=abort_header(Path(env.subst('$PROJECT_DIR'))/'.pio/ota-core-abort',env.PioPlatform().get_package_dir('framework-arduinoespressif8266'))
env.Prepend(CPPPATH=[str(p),str(Path(env.PioPlatform().get_package_dir('framework-arduinoespressif8266'))/'libraries/ESP8266WiFi/src')])
env.Append(CXXFLAGS=['-include',str(p/'Updater.h'),'-include',str(headers/'ESP8266WebServer.h')])
"""
    script.write_text(body,encoding="utf-8")
    ini=configparser.ConfigParser(interpolation=None);ini.read(directory/"platformio.ini")
    flags=ini["env:"+ENV]["build_flags"]
    flags=flags[:flags.index("\n-DM9_SIGNED_OTA_UNWIRED=1")]
    ini["env:"+ENV]["build_flags"]=flags+"\n-DSHINO_HTTP_OTA=1"
    with (directory/"platformio.ini").open("w",encoding="utf-8") as out:ini.write(out)
    inputs=json.loads((directory/"public-inputs.json").read_text())
    inputs.update(http_ota=True,private_identity=private,stock_updater_buffer=4096,shared_server_abi=True)
    inputs["identity_sha256"]=hashlib.sha256((directory/"include/shino_private_policy.h").read_bytes()).hexdigest()
    (directory/"public-inputs.json").write_text(json.dumps(inputs,indent=2),encoding="utf-8")
    return directory,device,build


def build(directory,private=False):
    # This command has no upload, serial, socket or reboot path.
    pio=shutil.which("pio") or shutil.which("platformio")
    if not pio:raise ValueError("PlatformIO unavailable")
    directory,device,identity=prepare(directory,load() if private else None)
    with (directory/"build.log").open("x",encoding="utf-8") as log:
        run=subprocess.run([pio,"run","-d",str(directory),"-e",ENV],cwd=ROOT,stdin=subprocess.DEVNULL,stdout=log,stderr=subprocess.STDOUT,timeout=1200)
    if run.returncode:raise RuntimeError("Build failed; inspect local build.log")
    binary=directory/".pio/build"/ENV/"firmware.bin";raw=binary.read_bytes();validate_image(raw)
    if raw.count(descriptor(device,identity).encode())!=1:raise ValueError("Embedded release identity missing or ambiguous")
    resources=one(directory)
    layout=elf_layout(binary.with_suffix(".elf"))
    frames=stack_frames(directory)
    if resources["noinit"]!=56:raise ValueError("Unexpected RTC/noinit footprint")
    manifest=dict(schema=1,family="SHINO-StageA",layout="4m2m",protocol="shino-http-ota-1",device=device,
                  bytes=len(raw),sha256=hashlib.sha256(raw).hexdigest(),build_id=identity)
    (directory/"release.json").write_text(json.dumps(manifest,indent=2)+"\n",encoding="utf-8")
    report=dict(manifest,source_commit=subprocess.check_output(["git","rev-parse","HEAD"],cwd=ROOT,text=True).strip(),
                source_dirty=bool(subprocess.check_output(["git","status","--porcelain"],cwd=ROOT,text=True).strip()),
                static_ram=resources["static_ram"],linked_flash=resources["linked_flash"],noinit=resources["noinit"],
                layout_symbols=layout,stack_frames=frames,
                private=private,core_buffer=4096,physical="NOT_RUN",device_contacts=0)
    (directory/"report.json").write_text(json.dumps(report,indent=2)+"\n",encoding="utf-8")
    print(json.dumps(report,ensure_ascii=True))
    return report


if __name__=="__main__":
    parser=argparse.ArgumentParser(description=__doc__);parser.add_argument("directory",type=Path);parser.add_argument("--private",action="store_true")
    opts=parser.parse_args();build(opts.directory,opts.private)
