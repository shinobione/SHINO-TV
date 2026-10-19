"""Fail-closed ELF/BIN comparison, inert Core M3-P-only vs M3-Q reader."""
from pathlib import Path
import hashlib
import json
import subprocess
HERE=Path(__file__).resolve().parent
TOOLS=Path.home()/".platformio/packages/toolchain-xtensa/bin"
NAMES=("m3p_only_inert","m3q_headers_inert")
def execute(name,*args):
    p=TOOLS/name
    if not p.is_file():raise RuntimeError("Missing Xtensa tool "+name)
    return subprocess.check_output([str(p),*map(str,args)],text=True,timeout=60)
def inspect(name):
    folder=HERE/".pio/build"/name
    elf=folder/"firmware.elf"
    binary=folder/"firmware.bin"
    if not elf.is_file() or not binary.is_file():raise RuntimeError("Missing build "+name)
    sizes=execute("xtensa-lx106-elf-size","-B",elf).splitlines()
    if len(sizes)!=2:raise RuntimeError("Invalid size header")
    words=sizes[1].split()
    if len(words)<6 or any(not p.isdecimal() for p in words[:3]):
        raise RuntimeError("Invalid native section sizes")
    symbols=execute("xtensa-lx106-elf-nm","-C",elf)
    if "m3q_link_actual_core" not in symbols or not (
       "ShinoM3P::readFirstLine" in symbols or "_ZN8ShinoM3P13readFirstLine" in symbols):
        raise RuntimeError("Pinned M3-P Core linkage absent from native ELF")
    has_reader=("ShinoM3Q::readHeaders" in symbols or
                "_ZN8ShinoM3Q11readHeaders" in symbols)
    if has_reader!=(name==NAMES[1]):
        raise RuntimeError("M3-Q bounded header reader optimized away or baseline contaminated")
    frames=[]
    for file in folder.rglob("*.su"):
        for line in file.read_text(errors="replace").splitlines():
            row=line.split("\t")
            if len(row)<3:continue
            try:depth=int(row[1])
            except ValueError:continue
            if "ShinoM3Q" in row[0] or "m3q_" in row[0]:
                frames.append({"bytes":depth,"function":row[0][-150:],"kind":row[2]})
    if has_reader and not frames:raise RuntimeError("M3-Q stack codegen absent")
    bits=binary.read_bytes()
    return {"bin_bytes":len(bits),"bin_sha256_INERT_ONLY":hashlib.sha256(bits).hexdigest(),
            "elf_text_bytes":int(words[0]),"elf_data_bytes":int(words[1]),
            "elf_bss_bytes":int(words[2]),"m3q_reader_linked":has_reader,
            "stack_codegen_frames":frames[:32]}
left,right=(inspect(name) for name in NAMES)
keys=("bin_bytes","elf_text_bytes","elf_data_bytes","elf_bss_bytes")
result={"m3p_only":left,"m3q_added":right,
        "delta":{k:right[k]-left[k] for k in keys},
        "scope":"INERT XTENSA ONLY: not full B5.3, not actual SmallTV",
        "physical_CONT_heap_WDT_TCP":"NOT_VERIFIED",
        "HMAC_read_body_change_display":"NOT_IMPLEMENTED"}
(HERE/"m3q_inert_elf_receipt.json").write_text(
    json.dumps(result,sort_keys=True,indent=2)+"\n",encoding="utf-8")
print(json.dumps(result,sort_keys=True,indent=2))
