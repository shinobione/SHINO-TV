"""Resolved OTA source paths, .su and linked Xtensa prologues.

Reports compiled path costs, not a bound on ROM/SDK/IRQ/native high water.
Indirect hash targets are resolved from the linked SHA256 vtable. A missing
symbol or changed commit graph is an error, never an implicit zero frame.
"""
import argparse
import hashlib
import json
import re
import shutil
import struct
import subprocess
from pathlib import Path
from m9_stagea_build import ENV
from m9_stagea_resources import symbols_with_data
from v07_pinned_core_probe import core_root


HEAD=re.compile(r"(?m)^([0-9a-fA-F]+) <(.+)>:\s*$")


def frame(body):
    registers={}
    for line in body.splitlines()[:22]:
        m=re.search(r"\bmovi(?:\.n)?\s+(a\d+),\s*(-?(?:0x[0-9a-f]+|\d+))",line)
        if m:registers[m[1]]=int(m[2],0)
        m=re.search(r"\baddi(?:\.n)?\s+a1,\s*a1,\s*(-\d+)",line)
        if m:return -int(m[1])
        m=re.search(r"\bsub\s+a1,\s*a1,\s*(a\d+)",line)
        if m:
            if m[1] not in registers:raise ValueError("Unresolved Xtensa stack allocation")
            return registers[m[1]]
    if re.search(r"\b(?:addi(?:\.n)?|sub)\s+a1,",body):
        raise ValueError("Stack prologue not resolved")
    return 0


def audit(directory):
    directory=Path(directory);root=directory/".pio/build"/ENV;elf=root/"firmware.elf"
    tool=shutil.which("xtensa-lx106-elf-objdump")
    if not tool:
        suffix=".exe" if __import__('os').name=="nt" else ""
        tool=core_root().parent/"toolchain-xtensa/bin"/("xtensa-lx106-elf-objdump"+suffix)
    assembly=subprocess.check_output([str(tool),"-dC",str(elf)],text=True)
    heads=list(HEAD.finditer(assembly));nodes={}
    for i,h in enumerate(heads):
        body=assembly[h.end():heads[i+1].start() if i+1<len(heads) else len(assembly)]
        nodes[h[2]]=dict(address=int(h[1],16),body=body)
    def select(marker):
        matches=[(name,v) for name,v in nodes.items() if marker in name and "+0x" not in name and "::__pstr__" not in name]
        if len(matches)!=1:raise ValueError("Ambiguous/missing compiled symbol: "+marker+" "+str([n for n,_ in matches]))
        name,value=matches[0];return name,frame(value["body"])
    markers={
        "wrapper":"loop_wrapper()","loop":"M9NormalStageA::loop()",
        "http":"::handleClient()","parser":"::_parseRequest(",
        "before_body":"::beforeBody()","upload":"M9NormalStageA::(anonymous namespace)::upload(unsigned int)",
        "begin":"Transfer::begin(","proof":"ShinoHttpOta::proof(",
        "key_init":"br_hmac_key_init","process_key":"process_key",
        "sha_round":"br_sha2small_round","finish":"Transfer::finish(",
        "readback":"Transfer::stagedImage()","segments":"Transfer::segments(",
        "read":"Transfer::read(","flash_read":"EspClass::flashRead(unsigned int, unsigned int*",
        "end":"UpdaterClass::end(bool)","verify_end":"UpdaterClass::_verifyEnd()",
        "rtc_write":"eboot_command_write","core_write":"UpdaterClass::write(unsigned char*",
        "core_flush":"UpdaterClass::_writeBuffer()","observer":"::uploadHealthy()",
    }
    selected={key:select(marker) for key,marker in markers.items()}
    values=symbols_with_data(elf)
    vtable=values["br_sha256_vtable"]["data"]
    pointers=struct.unpack_from("<3I",vtable,8)
    resolved={}
    for label,pointer in zip(("sha_init","sha_update","sha_out"),pointers):
        matches=[(n,v) for n,v in nodes.items() if v["address"]==pointer]
        if len(matches)!=1:raise ValueError("Unresolved linked SHA256 vtable target")
        name,value=matches[0];selected[label]=(name,frame(value["body"]));resolved[label]=name
    # Cross-check compiler metadata against independent machine prologues.
    su="\n".join(p.read_text(errors="replace") for p in root.rglob("*.su"))
    for key in ("loop","before_body","upload","begin","proof","finish","readback","segments","read","end","core_write","core_flush"):
        marker=("UpdaterClass::write(uint8_t*" if key=="core_write" else
                "::upload(uint32_t)" if key=="upload" else markers[key])
        rows=[line.rsplit("\t",2) for line in su.splitlines() if marker in line]
        if len(rows)!=1 or rows[0][2]!="static" or int(rows[0][1])!=selected[key][1]:
            raise ValueError(".su/prologue disagreement: "+key)
    finish_body=nodes[selected["finish"][0]]["body"]
    staging_body=nodes[selected["readback"][0]]["body"]
    if "Transfer::segments(" in staging_body:raise ValueError("Nested verifier stack regression")
    if len(re.findall(r"call0[^\n]*Transfer::segments\(",finish_body))!=2:
        raise ValueError("Two segment validations must be reached from finish")
    if "UpdaterClass::end(bool)" not in finish_body:raise ValueError("Missing real Core commit call")
    root_path=["wrapper","loop","http","parser","before_body","upload"]
    paths={
        "hmac_key_sha256":root_path+["begin","proof","key_init","process_key","sha_update","sha_round"],
        "staging_sha256":root_path+["finish","readback","sha_update","sha_round"],
        "segment_word_read":root_path+["finish","segments","read","flash_read"],
        "core_verify_before_commit":root_path+["finish","end","verify_end","flash_read"],
        "rtc_command_commit":root_path+["finish","end","rtc_write"],
        "last_chunk_core_flush":root_path+["core_write","core_flush"],
        "segment_resource_observation":root_path+["finish","segments","observer"],
    }
    costs={label:dict(compiled_bytes=sum(selected[k][1] for k in path),
        functions=[dict(name=selected[k][0],frame=selected[k][1]) for k in path]) for label,path in paths.items()}
    if max(v["compiled_bytes"] for v in costs.values())>2048:
        raise ValueError("Known compiled OTA path exceeds the unchanged 2048-byte reserve")
    return dict(status="COMPILED_PATHS_PASS_NOT_NATIVE_HIGH_WATER",paths=costs,
        sha256_vtable_targets=resolved,elf_sha256=hashlib.sha256(elf.read_bytes()).hexdigest(),
        nested_verification=False,core_commit_reachable=True,
        continuation_bytes=4096,required_free_bytes=2048,
        whole_native_upper_bound=False,
        unresolved_boundaries=["ROM MD5Update", "SPI SDK/ROM callees", "lwIP and allocator peaks",
                               "SDK callbacks/interrupt stack and postcommit libc/response/restart"],
        reentrancy="One cooperative persistent server; transfer owned until synchronous upload returns; no server handler scheduled by yield",
        resource_gate="Fresh historical continuation/heap/block checks during receiving, each verifier block and immediately before end(false)",
        physical="NOT_RUN",device_contacts=0)


if __name__=="__main__":
    parser=argparse.ArgumentParser(description=__doc__);parser.add_argument("directory",type=Path)
    print(json.dumps(audit(parser.parse_args().directory),indent=2))
