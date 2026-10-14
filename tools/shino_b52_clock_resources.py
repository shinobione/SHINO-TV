"""Read-only public B5.1/B5.2 ELF/BIN comparison and fixed-clock frame evidence."""
import argparse
import hashlib
import json
import re
import shutil
import subprocess
from pathlib import Path
from m9_stagea_build import ENV,ROOT
from shino_wifi_resources import one
from shino_http_ota_build import elf_layout
from shino_http_ota_stack import audit as ota_audit,HEAD,frame
from v07_pinned_core_probe import core_root

def run(baseline,candidate,anchor=None):
    baseline,candidate=Path(baseline).resolve(),Path(candidate).resolve()
    for folder in (baseline,candidate):
        manifest=json.loads((folder/"release.json").read_text(encoding="utf-8"))
        report=json.loads((folder/"report.json").read_text(encoding="utf-8"))
        raw=(folder/".pio/build"/ENV/"firmware.bin").read_bytes()
        assert report["private"] is False,"PUBLIC artifacts only"
        assert len(raw)==manifest["bytes"] and hashlib.sha256(raw).hexdigest()==manifest["sha256"]
        elf_layout(folder/".pio/build"/ENV/"firmware.elf")
    before,after=one(baseline),one(candidate)
    # Validate the unchanged native B5.1 execution inputs, not a Mission8 proxy.
    for path in ("src/boot/B5Lan.cpp","include/B5Lan.h","src/boot/FslessMetrics.cpp","include/ShinoHttpOta.h"):
        assert (baseline/path).read_bytes().replace(b"\r\n",b"\n")== (candidate/path).read_bytes().replace(b"\r\n",b"\n"),path
    assert before["identity_sha256"]==after["identity_sha256"]
    elf=candidate/".pio/build"/ENV/"firmware.elf"
    compiler=core_root().parent/"toolchain-xtensa/bin"
    suffix=".exe" if __import__("os").name=="nt" else ""
    assembly=subprocess.check_output([str(compiler/("xtensa-lx106-elf-objdump"+suffix)),"-dC",str(elf)],text=True)
    starts=list(HEAD.finditer(assembly));nodes={}
    for i,h in enumerate(starts):
        body=assembly[h.end():starts[i+1].start() if i+1<len(starts) else len(assembly)]
        nodes[h[2]]=body
    def select(marker):
        matches=[(name,body) for name,body in nodes.items() if marker in name and "+0x" not in name and "::__pstr__" not in name]
        if len(matches)!=1:raise ValueError("Missing/ambiguous compiled clock function: "+marker)
        name,body=matches[0]
        return dict(function=name,bytes=frame(body))
    markers={"wrapper":"loop_wrapper()","loop":"M9NormalStageA::loop()","dispatch":"::serviceRequest()",
        "admission":"::beforeBody()","sync_handler":"::clockSync()","decode":"B52Clock::synchronize(",
        "status_handler":"::clockStatus()","render_step":"B52Clock::step(","calendar":"State::civil(",
        "header":"Renderer::paintHeader(","card":"Renderer::paintCard(","text":"::Lcd::text(",
        "challenge":"B52Clock::challenge(","proof_accept":"ClockFreshness::Gate::accept(","proof_tag":"ClockFreshness::tag("}
    compiled={key:select(value) for key,value in markers.items()}
    # Admission is a returned sibling, not an additional live proof frame.
    known_sync=sum(compiled[k]["bytes"] for k in ("wrapper","loop","dispatch","sync_handler","decode","proof_accept","proof_tag"))
    known_draw=sum(compiled[k]["bytes"] for k in ("wrapper","loop","render_step","header","text"))
    # Partial paths: GFX, libc printf and SDK/ROM are NOT silently counted zero.
    su="\n".join(p.read_text(errors="replace") for p in (candidate/".pio/build"/ENV).rglob("*.su"))
    for key in ("sync_handler","status_handler","decode","render_step","calendar","header","card","text","challenge","proof_accept","proof_tag"):
        marker=markers[key]
        rows=[r.rsplit("\t",2) for r in su.splitlines() if marker in r]
        if len(rows)!=1 or rows[0][2]!="static" or int(rows[0][1])!=compiled[key]["bytes"]:
            raise ValueError("Clock .su/prologue disagreement: "+key)
    symbols=subprocess.check_output([str(compiler/("xtensa-lx106-elf-nm"+suffix)),"-SC",str(elf)],text=True)
    assert not any(term in symbols for term in ("m7Receiver","FirstBootBridge::loop","NTPClient::","SceneManager::"))
    objects={}
    for line in symbols.splitlines():
        parts=line.split(maxsplit=3)
        if len(parts)==4 and any(parts[3].endswith(term) for term in ("::renderer","::clockState","::lcd","::freshness")):
            objects[parts[3]]=int(parts[1],16)
    delta={key:after[key]-before[key] for key in ("bin_bytes","static_ram","linked_flash","noinit")}
    source=json.loads((candidate/"report.json").read_text(encoding="utf-8"))
    assert all(hashlib.sha256((ROOT/p).read_bytes()).hexdigest()==digest for p,digest in source["clock_inputs_sha256"].items())
    ota_before,ota_after=ota_audit(baseline),ota_audit(candidate)
    crypto_markers={"key_init":"br_hmac_key_init","process_key":"process_key","hmac_init":"br_hmac_init",
        "hmac_out":"br_hmac_out","sha_init":ota_after["sha256_vtable_targets"]["sha_init"],
        "sha_update":ota_after["sha256_vtable_targets"]["sha_update"],"sha_out":ota_after["sha256_vtable_targets"]["sha_out"],
        "sha_out_body":"sha2small_out","sha_round":"br_sha2small_round","decode_words":"br_range_dec32be",
        "issue":"ClockFreshness::Gate::issue(","entropy":"B52Clock::(anonymous namespace)::entropy(",
        "hardware_random":"EspClass::random(unsigned char*"}
    crypto={k:select(v) for k,v in crypto_markers.items()}
    # SHA256 out is a zero-frame tail jump to sha2small_out; do not treat the
    # callback wrapper as the entire out cost. Targets resolved by ota_audit.
    tag_body=nodes[compiled["proof_tag"]["function"]]
    assert all(name in tag_body for name in ("br_hmac_key_init","br_hmac_init","br_hmac_out"))
    assert "callx0" in nodes[crypto["process_key"]["function"]]
    assert "br_sha2small_round" in nodes[crypto["sha_update"]["function"]]
    assert "br_sha2small_round" in nodes[crypto["sha_out_body"]["function"]]
    proof_paths={
        "hmac_key_sha256":("key_init","process_key","sha_update","sha_round","decode_words"),
        "hmac_output_sha256":("hmac_out","sha_out","sha_out_body","sha_round","decode_words"),
    }
    proof_costs={name:dict(known_compiled_bytes=known_sync+sum(crypto[k]["bytes"] for k in path),
        prefix_bytes=known_sync,descendants=[crypto[k] for k in path]) for name,path in proof_paths.items()}
    assert max(v["known_compiled_bytes"] for v in proof_costs.values())<=2048,"known clock crypto path exceeds reserve; HOLD"
    max_before=max(v["compiled_bytes"] for v in ota_before["paths"].values())
    max_after=max(v["compiled_bytes"] for v in ota_after["paths"].values())
    assert max_after<=2048 and delta["noinit"]==0 and after["noinit"]==56
    reference=one(Path(anchor).resolve()) if anchor else before
    cumulative_static=after["static_ram"]-reference["static_ram"]
    assert 0<=cumulative_static<=2048,"unchanged total offline static increment budget exceeded; HOLD"
    return dict(verdict="PASS_OFFLINE_PHYSICAL_HOLD",baseline=dict(bin_bytes=before["bin_bytes"],
        static_ram=before["static_ram"],sections=before["sections"]),
        candidate=dict(bin_bytes=after["bin_bytes"],static_ram=after["static_ram"],sections=after["sections"],
        bin_sha256=source["sha256"],elf_sha256=hashlib.sha256(elf.read_bytes()).hexdigest()),
        delta=delta,objects=objects,compiler_frames=compiled,
        partial_known_clock_sync_bytes=known_sync,partial_known_clock_draw_bytes=known_draw,
        crypto_frames=crypto,known_clock_proof_paths=proof_costs,sha256_vtable_targets=ota_after["sha256_vtable_targets"],
        partial_paths_exclude=["ROM memcpy/memset/strlen and other indirect ROM calls","libc printf","GFX print/drawChar/SPI descendants",
            "SDK/RNG micros/delayMicroseconds/guard callbacks","lwIP/allocator/IRQ peaks"],
        known_ota_path_max_before=max_before,known_ota_path_max_after=max_after,
        ota_paths_before=ota_before["paths"],ota_paths_after=ota_after["paths"],
        ota_elf_sha256_before=ota_before["elf_sha256"],ota_elf_sha256_after=ota_after["elf_sha256"],
        layout_symbols=elf_layout(elf),
        offline_static_increment_budget=2048,cumulative_static_increment=cumulative_static,offline_static_budget_remaining=2048-cumulative_static,
        floors=dict(ota_admission_heap=25600,execution_heap=20480,
        largest=16384,continuation_stack=2048,fragmentation_max=25),
        actual_native_heap="NOT_MEASURED",actual_native_largest_block="NOT_MEASURED",
        actual_native_fragmentation="NOT_MEASURED",actual_native_stack="NOT_MEASURED",
        host_renderer_additional_heap_allocations=0,device_contacts=0,physical="NOT_RUN",
        baseline_rebuilt=False,music_receiver_integrated=False)

if __name__=="__main__":
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument("baseline",type=Path);p.add_argument("candidate",type=Path)
    p.add_argument("--output",type=Path,required=True);p.add_argument("--anchor",type=Path);a=p.parse_args()
    if a.output.exists():raise ValueError("New report output required")
    report=run(a.baseline,a.candidate,a.anchor)
    a.output.write_text(json.dumps(report,indent=2)+"\n",encoding="utf-8")
    print(json.dumps({k:report[k] for k in ("verdict","baseline","candidate","delta","objects",
        "partial_known_clock_sync_bytes","partial_known_clock_draw_bytes","known_ota_path_max_before","known_ota_path_max_after")},indent=2))

