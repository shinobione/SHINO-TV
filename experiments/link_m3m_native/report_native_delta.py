"""M3-M: compare only two inert Xtensa ELFs using actual files and tools."""
import hashlib
import json
from pathlib import Path
import subprocess

ROOT=Path(__file__).resolve().parent
TOOL=Path.home()/".platformio/packages/toolchain-xtensa/bin"
PROFILES=("m3m_existing_m3l","m3m_with_native_metrics")

def cmd(name,*args):
    exe=TOOL/name
    if not exe.is_file():raise RuntimeError("No pinned Xtensa executable "+name)
    return subprocess.check_output([str(exe),*map(str,args)],text=True,timeout=40)

def measure(name):
    folder=ROOT/".pio"/"build"/name
    elf=folder/"firmware.elf"
    binary=folder/"firmware.bin"
    if not elf.is_file() or not binary.is_file():
        raise RuntimeError("Missing real compiled artifact "+name)
    values=cmd("xtensa-lx106-elf-size","-B",elf).splitlines()
    if len(values)!=2:raise RuntimeError("Unexpected ELF format")
    fields=values[1].split()
    if len(fields)<6 or any(not k.isdecimal() for k in fields[:3]):
        raise RuntimeError("Unknown ELF size fields")
    text,data,bss=map(int,fields[:3])
    symbols=cmd("xtensa-lx106-elf-nm","-C",elf)
    for symbol in ("m3m_compiled_common",):
        if symbol not in symbols:raise RuntimeError("Common graph optimized away")
    if ("m3m_compiled_real_adapter" in symbols)!=(name==PROFILES[1]):
        raise RuntimeError("Real adapter not uniquely retained on B graph")
    traces=[]
    for f in folder.rglob("*.su"):
        for line in f.read_text(errors="replace").splitlines():
            cols=line.split("\t")
            if len(cols)<3:continue
            try:stack=int(cols[1])
            except ValueError:continue
            traces.append((stack,cols[0],cols[2]))
    if not traces:raise RuntimeError("No compiler stack annotations")
    raw=binary.read_bytes()
    relevant=[{"frame_bytes":a,"symbol":n,"type":t} for a,n,t in sorted(traces,reverse=True)
              if "m3m_" in n or "ActualMetricsHandler" in n or "ShinoM3C" in n][:30]
    return {"scope":"INERT_XTENSA_ESP8266_3_1_2",
            "bin_bytes":len(raw),"bin_sha256":hashlib.sha256(raw).hexdigest(),
            "text_bytes":text,"data_bytes":data,"bss_bytes":bss,
            "stack_annotations":relevant,
            "frame_sums":"NOT A COMPLETE CALL CHAIN",
            "runtime_heap_cont_wdt":"NOT MEASURED"}

if __name__=="__main__":
    a,b=[measure(n) for n in PROFILES]
    keys=("bin_bytes","text_bytes","data_bytes","bss_bytes")
    result={
        "base_inert":a,"add_metrics_handler_inert":b,
        "diff_B_minus_A":{k:b[k]-a[k] for k in keys},
        "native_firstboot_route_parity":"HOLD — handler extraction only",
        "digest_in_native":"NOT IMPLEMENTED — denied in inert build",
        "real_WiFiServer_begin":"NEVER CALLED",
        "real_smalltv":"NO ACCESS, NO INSTALLATION, NO OTA",
        "whole_firmware_heap_cont_wdt":"NOT MEASURED"
    }
    print(json.dumps(result,indent=2,sort_keys=True))
    (ROOT/"m3m_inert_native_handler_receipt.json").write_text(
        json.dumps(result,indent=2,sort_keys=True)+"\n",encoding="utf-8")
