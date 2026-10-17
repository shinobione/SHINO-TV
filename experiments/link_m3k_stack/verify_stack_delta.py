"""M3-K actual Xtensa A/B stack-vs-BSS tradeoff. Two INERT ESP8266 ELFs.

Does NOT certify heap/largest-block/CONT at runtime or a deployable BIN.
Never embed expected sizes or guessed compilation outcomes in source.
"""
import hashlib
import json
from pathlib import Path
import re
import subprocess
import sys

BASE=Path(__file__).resolve().parent
BUILD=BASE/".pio"/"build"
NAMES=("m3k_original","m3k_gate_scratch")
TOOL=Path.home()/".platformio/packages/toolchain-xtensa/bin"

def capture(tool, *args):
    target=TOOL/tool
    if not target.is_file():
        raise RuntimeError(f"Toolchain missing: {tool}")
    return subprocess.check_output([str(target),*map(str,args)],
                                   text=True,timeout=30)

def one(name):
    folder=BUILD/name
    elf=folder/"firmware.elf"
    binary=folder/"firmware.bin"
    if not elf.is_file() or not binary.is_file():
        raise RuntimeError(f"Missing inert source-built ELF or BIN for {name}")
    raw=binary.read_bytes()
    size_lines=capture("xtensa-lx106-elf-size","-B",elf).splitlines()
    if len(size_lines)!=2:
        raise RuntimeError("Unexpected ELF size output")
    cells=size_lines[1].split()
    if len(cells)<6 or not all(c.isdecimal() for c in cells[:4]):
        raise RuntimeError("Unparseable ELF section counts")
    text, data, bss=map(int,cells[:3])
    if min(text,data,bss)<0: raise RuntimeError("Invalid ELF section sizes")
    symbols=capture("xtensa-lx106-elf-nm","-C",elf)
    # Explicit symbol retention: source can be compiled while optimizer
    # silently discards non-runtime hooks. This gate fails if so.
    if "m3j_baseline_probe" not in symbols:
        raise RuntimeError("Actual FslessMetrics graph optimized away")
    if "m3j_crypto_probe" not in symbols:
        raise RuntimeError("Native M3-C gate graph was eliminated")
    traces=[]
    for item in folder.rglob("*.su"):
        for line in item.read_text(errors="replace").splitlines():
            fields=line.split("\t")
            if len(fields)<3:continue
            try: amount=int(fields[1])
            except ValueError:continue
            traces.append((amount,fields[0][-180:],fields[2]))
    if not traces:
        raise RuntimeError("No compiler-produced -fstack-usage information")
    relevant=[{"frame_bytes":a,"symbol":n,"type":t} for a,n,t in
       sorted(traces,reverse=True)
       if "ShinoM3" in n or "m3j_" in n][:40]
    all_top=[{"frame_bytes":a,"symbol":n,"type":t} for a,n,t in
             sorted(traces,reverse=True)[:12]]
    signing=[a for a,n,t in traces if "ShinoM3C::Gate::authenticateHeader" in n
             and "BearSslCrypto" in n and t=="static"]
    body=[a for a,n,t in traces if "ShinoM3C::Gate::bodyByte" in n
          and "BearSslCrypto" in n and t=="static"]
    if len(signing)!=1 or len(body)!=1:
        raise RuntimeError("Cannot uniquely establish native static stack frame")
    return {
      "hmac_signing_stack_frame_bytes":signing[0],
      "body_hash_stack_frame_bytes":body[0],
      "scope":"INERT_XTENSA_ESP8266_CORE_3_1_2_ONLY",
      "text_bytes":text,"data_bytes":data,"bss_bytes":bss,
      "bin_bytes":len(raw),"bin_sha256_computed":hashlib.sha256(raw).hexdigest(),
      "compiler_stack_trace_files":len(list(folder.rglob("*.su"))),
      "compiler_stack_relevant":relevant,
      "compiler_stack_largest":all_top
    }

def main():
    baseline=one(NAMES[0])
    candidate=one(NAMES[1])
    keys=("text_bytes","data_bytes","bss_bytes","bin_bytes")
    delta={k:candidate[k]-baseline[k] for k in keys}
    signing_delta=(candidate["hmac_signing_stack_frame_bytes"]
                   -baseline["hmac_signing_stack_frame_bytes"])
    if signing_delta>=0:
        raise RuntimeError("M3-K did not reduce Xtensa HMAC function stack; HOLD")
    if candidate["body_hash_stack_frame_bytes"] > baseline["body_hash_stack_frame_bytes"]:
        raise RuntimeError("M3-K unexpectedly increased body hash stack; HOLD")
    report={
       "baseline":baseline, "native_hmac_gate":candidate,
       "candidate_minus_baseline":delta,
       "hmac_signing_stack_frame_delta_bytes":signing_delta,
       "comparison":"TWO INERT XTENSA HMAC IMPLEMENTATIONS A/B, NOT DEVICE FIRMWARE",
       "device_heap_largest_block_cont_wdt":"NOT MEASURED",
       "native_legacy_digest_real_route_parity":"HOLD",
       "real_smalltv_flash_ota":"NO ACTION",
       "security_conclusion":"NOT DEPLOYABLE; CODEGEN ONLY"
    }
    print(json.dumps(report,indent=2,sort_keys=True))
    # External workflow can collect report, but never treat this as OTA consent.
    (BASE/"m3k_derived_stack_tradeoff.json").write_text(
        json.dumps(report,indent=2,sort_keys=True)+"\n",encoding="utf-8")
    return 0
if __name__=="__main__":
    sys.exit(main())
