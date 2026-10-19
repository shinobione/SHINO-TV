"""Native ESP8266 Core 3.1.2 untouched server vs isolated bounded source overlay."""
import hashlib
import json
import subprocess
from pathlib import Path
HERE=Path(__file__).resolve().parent
TOOLS=Path.home()/".platformio/packages/toolchain-xtensa/bin"
VARIANTS=("unpatched_core_control","bounded_core_inert")
def tool(name,*args):
    path=TOOLS/name
    if not path.is_file():raise RuntimeError("Missing pinned Xtensa tool "+name)
    return subprocess.check_output([str(path),*map(str,args)],text=True,timeout=60)
def one(name):
    folder=HERE/".pio"/"build"/name
    elf,binary=folder/"firmware.elf",folder/"firmware.bin"
    if not elf.is_file() or not binary.is_file():raise RuntimeError("Missing ELF/BIN "+name)
    cols=tool("xtensa-lx106-elf-size","-B",elf).splitlines()
    if len(cols)!=2:raise RuntimeError("Unexpected ELF size shape")
    pieces=cols[1].split()
    if len(pieces)<6 or any(not x.isdecimal() for x in pieces[:3]):
        raise RuntimeError("Bad ELF sizes")
    symbols=tool("xtensa-lx106-elf-nm","-C",elf)
    if "m3p_link_actual_parser" not in symbols:
        raise RuntimeError("Real Core handleClient graph optimized away")
    # Xtensa GCC -Os may clone the noinline template into a local
    # `.isra` symbol; GNU nm -C does not always demangle the suffix,
    # but the exact mangled namespace+function prefix stays in ELF.
    has_bound=("ShinoM3P::readFirstLine" in symbols or
               "_ZN8ShinoM3P13readFirstLine" in symbols)
    if has_bound!=(name==VARIANTS[1]):
        raise RuntimeError("HOLD: patched Core parser not really linked in the correct variant")
    frames=[]
    for file in folder.rglob("*.su"):
        for line in file.read_text(errors="replace").splitlines():
            p=line.split("\t")
            if len(p)<3:continue
            try:depth=int(p[1])
            except ValueError:continue
            if "ShinoM3P" in p[0] or "m3p_" in p[0]:
                frames.append({"frame_bytes":depth,"function":p[0][-190:],"kind":p[2]})
    if has_bound and not frames:
        raise RuntimeError("No parser stack frames in compiler output")
    blob=binary.read_bytes()
    return {
        "bin_size":len(blob),"bin_sha256_inert_only":hashlib.sha256(blob).hexdigest(),
        "elf_text_bytes":int(pieces[0]),"elf_data_bytes":int(pieces[1]),
        "elf_bss_bytes":int(pieces[2]),
        "bounded_parser_symbol_retained":has_bound,
        "stack_frames":frames[:30]}
base,patched=map(one,VARIANTS)
keys=("bin_size","elf_text_bytes","elf_data_bytes","elf_bss_bytes")
data={"unpatched":base,"source_bounded":patched,
      "delta_bounded_minus_unpatched":{k:patched[k]-base[k] for k in keys},
      "note":"INERT ESP8266 SOURCE OVERLAY TEST — NO SMALLTV, NO FLASH",
      "full_product_stack_heap_WDT":"NOT MEASURED",
      "legacy_header_parsing":"STILL UNBOUNDED, REQUIRED FURTHER AUDIT",
      "HMAC_display_ACK":"NOT IMPLEMENTED"}
out=HERE/"m3p_bounded_core_elf_receipt.json"
out.write_text(json.dumps(data,indent=2,sort_keys=True)+"\n",encoding="utf8")
print(json.dumps(data,indent=2,sort_keys=True))
