"""Only measure source-built inert Core 3.1.2 Xtensa outputs of M3-N."""
import hashlib
import json
from pathlib import Path
import subprocess

ROOT=Path(__file__).resolve().parent
TOOL=Path.home()/".platformio/packages/toolchain-xtensa/bin"
PROFILES=("m3n_metrics_baseline","m3n_legacy_digest_gate")
def capture(name,*args):
    exe=TOOL/name
    if not exe.is_file():raise RuntimeError("Pinned tool unavailable "+name)
    return subprocess.check_output([str(exe),*map(str,args)],text=True,timeout=30)
def one(profile):
    folder=ROOT/".pio"/"build"/profile
    elf,binary=folder/"firmware.elf",folder/"firmware.bin"
    if not elf.is_file() or not binary.is_file():raise RuntimeError("Missing ELF/BIN")
    rows=capture("xtensa-lx106-elf-size","-B",elf).splitlines()
    if len(rows)!=2:raise RuntimeError("Noncanonical size command output")
    cells=rows[1].split()
    if len(cells)<6 or any(not x.isdecimal() for x in cells[:3]):
        raise RuntimeError("Cannot parse real ELF size fields")
    t,d,b=map(int,cells[:3])
    symbols=capture("xtensa-lx106-elf-nm","-C",elf)
    if "m3n_common_source_probe" not in symbols:
        raise RuntimeError("common real metrics source optimized away")
    if ("m3n_digest_bearssl_probe" in symbols)!=(profile==PROFILES[1]):
        raise RuntimeError("legacy digest native probe retention unexpected")
    traces=[]
    for f in folder.rglob("*.su"):
        for line in f.read_text(errors="replace").splitlines():
            x=line.split("\t")
            if len(x)<3:continue
            try:n=int(x[1])
            except ValueError:continue
            if any(z in x[0] for z in ("ShinoM3N","m3n_","BearMd5")):
                traces.append({"frame_bytes":n,"symbol":x[0][-200:],"type":x[2]})
    if not traces:raise RuntimeError("No actual compiler stack traces for M3-N")
    blob=binary.read_bytes()
    return {
        "bin_bytes":len(blob),"sha256_of_INERT_bin":hashlib.sha256(blob).hexdigest(),
        "text_bytes":t,"data_bytes":d,"bss_bytes":b,
        "static_stack_frames":sorted(traces,key=lambda v:v["frame_bytes"],reverse=True)[:30],
        "scope":"INERT XTENSA COMPILATION ONLY"
    }
if __name__=="__main__":
    a,b=(one(x) for x in PROFILES)
    fields=("bin_bytes","text_bytes","data_bytes","bss_bytes")
    evidence={
        "A_original_metrics_and_M3L":a,"B_add_digest_bearssl":b,
        "B_minus_A":{x:b[x]-a[x] for x in fields},
        "real_B5_3_product_server_routes":"NOT PORTED",
        "native_digest_verifies_wire_network":"NOT VERIFIED",
        "runtime_heap_CONT_WDT":"NOT MEASURED",
        "physical_device":"NO ACCESS, NO OTA, NO INSTALLATION"
    }
    print(json.dumps(evidence,indent=2,sort_keys=True))
    (ROOT/"m3n_inert_digest_resource_receipt.json").write_text(
        json.dumps(evidence,indent=2,sort_keys=True)+"\n",encoding="utf-8")
