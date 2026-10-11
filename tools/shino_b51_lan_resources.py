"""Bounded B5.1 LAN compiler frames and resolved Xtensa paths; native HOLD."""
import json
import re
import shutil
import subprocess
from pathlib import Path
from m9_stagea_build import ENV
from shino_http_ota_stack import HEAD,frame
from v07_pinned_core_probe import core_root


def audit(directory):
    root=Path(directory)/".pio/build"/ENV
    tool=shutil.which("xtensa-lx106-elf-objdump")
    if not tool:
        suffix=".exe" if __import__("os").name=="nt" else ""
        tool=core_root().parent/"toolchain-xtensa/bin"/("xtensa-lx106-elf-objdump"+suffix)
    assembly=subprocess.check_output([str(tool),"-dC",str(root/"firmware.elf")],text=True)
    heads=list(HEAD.finditer(assembly));nodes={}
    for i,h in enumerate(heads):nodes[h[2]]=assembly[h.end():heads[i+1].start() if i+1<len(heads) else len(assembly)]
    caps={"handler":("::lanProvision()",256),"provision":("B5Lan::provision(",384),
          "sdk_read":("B5Lan::(anonymous namespace)::Sdk::read(",64),
          "sdk_write":("B5Lan::(anonymous namespace)::Sdk::write(",64),
          "connect":("B5Lan::(anonymous namespace)::connectSaved()",192),
          "load":("B5Lan::(anonymous namespace)::loadSaved()",192),
          "status":("::lanStatus()",128),"intent":("::lanIntent()",176)}
    su="\n".join(p.read_text() for p in root.rglob("*.su"));measured={}
    # Xtensa GCC's $constprop/$isra symbols are not demangled by this binutils.
    # Match their exact mangled function prefix, then independently check .su.
    clones={"sdk_read":"_ZN5B5Lan12_GLOBAL__N_13Sdk4read",
            "sdk_write":"_ZN5B5Lan12_GLOBAL__N_13Sdk5write",
            "connect":"_ZN5B5Lan12_GLOBAL__N_112connectSaved"}
    for key,(marker,cap) in caps.items():
        hits=[(n,b) for n,b in nodes.items() if (marker in n or n.startswith(clones.get(key,"!"))) and "::__pstr__" not in n]
        if len(hits)!=1:raise ValueError("Missing/ambiguous LAN symbol: "+marker)
        name,body=hits[0];cost=frame(body)
        su_marker=marker.replace("(anonymous namespace)","{anonymous}")
        rows=[line.rsplit("\t",2) for line in su.splitlines() if su_marker in line]
        # GCC reports unsigned char* rather than uint8_t*; function marker
        # deliberately stops before argument spellings.
        if len(rows)!=1 or rows[0][-1]!="static" or int(rows[0][-2])!=cost or cost>cap:
            raise ValueError("LAN .su/frame cap disagreement: "+key)
        measured[key]=dict(function=name,frame=cost,cap=cap)
    root_cost=0
    for marker in ("loop_wrapper()","M9NormalStageA::loop()","::serviceRequest()"):
        hits=[b for n,b in nodes.items() if marker in n and "::__pstr__" not in n]
        if len(hits)!=1:raise ValueError("Missing LAN dispatch frame")
        root_cost+=frame(hits[0])
    # Application frames through the SDK adapter only. The SDK wrappers,
    # internal persistence helpers, ROM/allocator and IRQ/lwIP are additional;
    # this is deliberately not labelled as a whole-native path bound.
    known=max(root_cost+measured["handler"]["frame"]+measured["provision"]["frame"]+
              measured[k]["frame"] for k in ("sdk_read","sdk_write"))
    if known>2048:raise ValueError("Known LAN path exceeds unchanged free-stack floor")
    return dict(frames=measured,known_application_provision_path_bytes=known,sdk_temporary_payload_bytes=0x49c,
                sdk_reserved_heap_bytes=1216,required_heap_before_sdk=21696,
                required_block_before_sdk=17600,required_stack=2048,max_fragmentation=25,
                whole_native_upper_bound=False,physical="NOT_RUN")


if __name__=="__main__":
    import argparse
    parser=argparse.ArgumentParser(description=__doc__);parser.add_argument("directory",type=Path)
    print(json.dumps(audit(parser.parse_args().directory),indent=2))
