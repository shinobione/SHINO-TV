"""Actual inert Xtensa code size, never free heap/physical CONT."""
from pathlib import Path
import subprocess,json,hashlib
here=Path(__file__).resolve().parent
tool=Path.home()/".platformio/packages/toolchain-xtensa/bin"
def execute(t,*a):
    p=tool/t
    if not p.is_file():raise RuntimeError("xtensa tool absent "+t)
    return subprocess.check_output([str(p),*map(str,a)],text=True,timeout=40)
def snapshot(kind):
    b=here/".pio"/"build"/kind
    elf=b/"firmware.elf"; image=b/"firmware.bin"
    if not elf.is_file() or not image.is_file():raise RuntimeError("Not built "+kind)
    size=execute("xtensa-lx106-elf-size","-B",elf).splitlines()
    if len(size)!=2:raise RuntimeError("Bad size output")
    nums=size[1].split()
    if len(nums)<6 or not all(x.isdecimal() for x in nums[:3]):
        raise RuntimeError("Unparseable size")
    symbols=execute("xtensa-lx106-elf-nm","-C",elf)
    has="m3o_compile_native_hook" in symbols
    if has!=(kind=="core_hook_inert"):raise RuntimeError("Hook call graph removed or leaked")
    binary=image.read_bytes()
    frames=[]
    for f in b.rglob("*.su"):
        for line in f.read_text(errors="replace").splitlines():
            x=line.split("\t")
            if len(x)<3:continue
            try:n=int(x[1])
            except ValueError:continue
            if "M3O" in x[0] or "m3o_" in x[0]:
                frames.append({"stack_frame_bytes":n,"function":x[0][-200:],
                               "kind":x[2]})
    if has and not frames:raise RuntimeError("No annotated hook frame")
    return {
        "bin_bytes":len(binary),
        "bin_sha256_inert_only":hashlib.sha256(binary).hexdigest(),
        "text_bytes":int(nums[0]),"data_bytes":int(nums[1]),"bss_bytes":int(nums[2]),
        "stack_annotations":frames[:30],
        "scope":"ESP8266 CORE 3.1.2 INERT, NO SERVER BEGIN, NO PRODUCT"
    }
a=snapshot("core_baseline");b=snapshot("core_hook_inert")
keys=("bin_bytes","text_bytes","data_bytes","bss_bytes")
report={
    "baseline":a,"hook_compiled_not_registered_at_runtime":b,
    "delta":{k:b[k]-a[k] for k in keys},
    "physical_heap_CONT_boot_WDT":"NOT MEASURED",
    "real_socket_lifetime":"NOT MEASURED",
    "line_length_memory_DOS":"HOLD: ORIGINAL CORE UNBOUNDED STRING BEFORE HOOK",
    "LCD_mode_change":"NOT IMPLEMENTED"
}
print(json.dumps(report,indent=2,sort_keys=True))
(here/"m3o_inert_handoff_cost.json").write_text(
 json.dumps(report,indent=2,sort_keys=True)+"\n",encoding="utf8")
