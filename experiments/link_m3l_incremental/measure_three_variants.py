"""M3-L pinned Xtensa A/B/C codegen: original vs M3-K vs streaming HMAC.

All three are INERT research images, never firmware candidates. Do not
confuse compiler frame annotations with complete runtime CONT watermarks.
No guessed BIN sizes/SHA/heap/stack: derive from actual compilation files.
"""
import hashlib
import json
from pathlib import Path
import subprocess

HERE=Path(__file__).resolve().parent
BUILD=HERE/".pio"/"build"
TOOL=Path.home()/".platformio/packages/toolchain-xtensa/bin"
VARIANTS=("m3l_original","m3l_member_scratch","m3l_incremental")

def run(tool,*args):
    target=TOOL/tool
    if not target.is_file():
        raise RuntimeError("Toolchain executable unavailable: "+tool)
    return subprocess.check_output([str(target),*map(str,args)],
                                   text=True,timeout=30)

def capture(name):
    root=BUILD/name
    elf=root/"firmware.elf"
    binary=root/"firmware.bin"
    if not elf.is_file() or not binary.is_file():
        raise RuntimeError("Missing real inert native A/B/C artifact "+name)
    entries=run("xtensa-lx106-elf-size","-B",elf).splitlines()
    if len(entries)!=2:raise RuntimeError("ELF parser failed "+name)
    numbers=entries[1].split()
    if len(numbers)<6 or not all(x.isdecimal() for x in numbers[:3]):
        raise RuntimeError("ELF section sizes invalid "+name)
    text,data,bss=map(int,numbers[:3])
    symbols=run("xtensa-lx106-elf-nm","-C",elf)
    for symbol in ("m3j_baseline_probe","m3j_crypto_probe"):
        if symbol not in symbols:
            raise RuntimeError("Optimizer removed active proof code: "+symbol)
    samples=[]
    files=list(root.rglob("*.su"))
    for file in files:
        for row in file.read_text(errors="replace").splitlines():
            fields=row.split("\t")
            if len(fields)<3:continue
            try:depth=int(fields[1])
            except ValueError:continue
            if depth<0:raise RuntimeError("Negative stack frame annotation")
            samples.append((depth,fields[0],fields[2]))
    if not samples:raise RuntimeError("No stack annotations "+name)
    def frame(search):
        found=[(depth,symbol,kind) for depth,symbol,kind in samples
               if search in symbol and "BearSslCrypto" in symbol]
        if len(found)!=1 or found[0][2]!="static":
            raise RuntimeError("Non-unique Xtensa stack frame "+name+": "+search+
                               " -> "+str(found))
        return found[0][0]
    signing=frame("ShinoM3C::Gate::authenticateHeader")
    body=frame("ShinoM3C::Gate::bodyByte")
    fragments=[(n,s,t) for n,s,t in samples
               if "BearSslCrypto::hmacFragments" in s]
    # Code can inline crypto, so absence of an independent frame does NOT
    # imply a zero stack cost; DO NOT fabricate a total-call-chain bound.
    raw=binary.read_bytes()
    return {
        "scope":"INERT_XTENSA_CORE_3_1_2_ONLY",
        "bin_bytes":len(raw),"bin_sha256":hashlib.sha256(raw).hexdigest(),
        "text_bytes":text,"data_bytes":data,"bss_bytes":bss,
        "gate_signing_frame_bytes":signing,
        "gate_body_frame_bytes":body,
        "fragment_provider_frames":[
             {"bytes":n,"symbol":s,"type":t} for n,s,t in fragments],
        "stack_trace_files":len(files),
        "top_relevant_frames":[
            {"bytes":n,"symbol":s,"type":t}
            for n,s,t in sorted(samples,reverse=True)
            if "ShinoM3C" in s or "BearSslCrypto" in s
        ][:22]
    }

def diff(a,b):
    return {key:b[key]-a[key] for key in
            ("bin_bytes","text_bytes","data_bytes","bss_bytes",
             "gate_signing_frame_bytes","gate_body_frame_bytes")}

def main():
    a,b,c=(capture(name) for name in VARIANTS)
    if a["gate_signing_frame_bytes"]<=c["gate_signing_frame_bytes"]:
        raise RuntimeError("HOLD: incremental HMAC did not lower original signing frame")
    if c["bss_bytes"]>a["bss_bytes"]:
        raise RuntimeError("HOLD: incremental HMAC increased static BSS")
    if c["gate_body_frame_bytes"]>a["gate_body_frame_bytes"]:
        raise RuntimeError("HOLD: streaming HMAC increased body SHA gate frame")
    if b["bss_bytes"]<=a["bss_bytes"]:
        raise RuntimeError("M3-K control missing expected Gate scratch RAM tradeoff")
    if b["gate_signing_frame_bytes"]>=a["gate_signing_frame_bytes"]:
        raise RuntimeError("M3-K control does not reduce signing stack")
    receipt={
        "original":a,"member_scratch_M3K":b,"streaming_M3L":c,
        "M3K_minus_original":diff(a,b),
        "M3L_minus_original":diff(a,c),
        "M3L_minus_M3K":diff(b,c),
        "decision":"LAB_SOURCE_CODEGEN_ONLY",
        "whole_call_chain_stack":"NOT MEASURED - cannot sum inlined/dynamic calls",
        "runtime_heap_cont_wdt":"NOT MEASURED",
        "single_native_http_owner":"HOLD",
        "credentials_device_ota_littlefs":"NO ACCESS OR ACTION"
    }
    out=HERE/"m3l_derived_three_variant_report.json"
    out.write_text(json.dumps(receipt,indent=2,sort_keys=True)+"\n",encoding="utf-8")
    print(json.dumps(receipt,indent=2,sort_keys=True))

if __name__=="__main__":
    main()
