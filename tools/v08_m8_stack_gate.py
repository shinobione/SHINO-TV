"""Offline Mission 8 gate on the exact linked Mission 7 SDK call chain.

Checks actual Xtensa prologues/calls, including linked assembly scratch space.
This is a reachable-path static lower bound, never a physical high-water trace.
No candidate activation, flash, network, credentials, or stack enlargement.
"""
import hashlib
import json
import os
import re
import subprocess
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
PACKAGE = Path.home() / ".platformio/packages"
BIN = PACKAGE / "toolchain-xtensa/bin"
BUILD = ROOT / "experiments/v08_m7/.pio/build"


def run_tool(name, *args):
    return subprocess.check_output([str(BIN / ("xtensa-lx106-elf-" + name + (".exe" if os.name == "nt" else ""))),
                                    *map(str, args)], text=True)


def digest(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def inspect():
    elf = BUILD / "media_compile/firmware.elf"
    disassembly = run_tool("objdump", "-d", "-C", elf)
    matches = list(re.finditer(r"^([0-9a-f]+) <(.+)>:$", disassembly, re.M))
    functions = {}
    for i, match in enumerate(matches):
        stop = matches[i + 1].start() if i + 1 < len(matches) else len(disassembly)
        functions[match[2]] = {"address": match[1],
                              "lines": disassembly[match.end():stop].strip().splitlines()}
    frames = {
        "br_ecdsa_i15_vrfy_raw": (720, "0x2d0"),
        "api_muladd$part$0": (528, "0x210"),
        "p256_mul": (1264, "0x4d0"),
        "p256_add": (624, "0x270"),
        "mul_f256": (192, "192"),
        "mul20": (1056, "0x400"),
        "m7::Ingress::parse()": (784, "0x310"),
        "bool m7::Ingress::poll<WiFiClient>(WiFiClient&)": (736, "0x2e0"),
    }
    evidence = []
    for name, (frame, immediate) in frames.items():
        lines = functions[name]["lines"][:12]
        prologue = "\n".join(lines)
        assert re.search(r"movi\s+a9, " + re.escape(immediate) + r"\s*$", prologue, re.M), name
        assert re.search(r"sub\s+a1, a1, a9", prologue), name
        extra = 32 if name in ("mul20", "p256_mul") else 0
        if extra:
            assert re.search(r"addi\s+a1, a1, -32", prologue), name
        assert int(immediate, 0) + extra == frame, name
        evidence.append({"function": name, "frame_bytes": frame,
                         "address": functions[name]["address"], "prologue": lines})
    edges = []
    for caller, callee in (
        ("bool m7::Ingress::poll<WiFiClient>(WiFiClient&)", "m7::Ingress::parse()"),
        ("m7::Ingress::parse()", "br_ecdsa_i15_vrfy_raw"),
        ("api_muladd$part$0", "p256_mul"),
        ("p256_mul", "p256_add"), ("p256_add", "mul_f256"),
        ("mul_f256", "mul20")):
        calls = [line for line in functions[caller]["lines"]
                 if "call0" in line and "<" + callee + ">" in line]
        assert calls, (caller, callee)
        edges.append({"caller": caller, "callee": callee, "calls": calls})
    # The verifier dispatches through the supplied br_ec_impl. Prove that this
    # exact linked implementation's offset-24 muladd pointer is api_muladd.
    symbols = run_tool("nm", "-S", elf).splitlines()
    ec = next(line.split() for line in symbols if line.endswith(" br_ec_p256_m15"))
    assert int(ec[1], 16) == 28
    ec_address = int(ec[0], 16)
    dump = run_tool("objdump", "-s", "--start-address=" + hex(ec_address),
                    "--stop-address=" + hex(ec_address + 28), elf)
    groups = []
    for line in dump.splitlines():
        match = re.match(r"^\s*[0-9a-f]+\s+((?:[0-9a-f]{8}\s+){1,4})", line)
        if match:
            groups.extend(match[1].split())
    ec_data = bytes.fromhex("".join(groups))
    assert len(ec_data) == 28
    assert int.from_bytes(ec_data[24:28], "little") == int(functions["api_muladd"]["address"], 16)
    tail = [line for line in functions["api_muladd"]["lines"]
            if re.search(r"jx\s+a9", line)]
    assert tail, "muladd tail dispatch changed"
    literal = next(re.search(r"l32r\s+a9, ([0-9a-f]+)", line)
                   for line in functions["api_muladd"]["lines"] if "l32r" in line)
    address = int(literal[1], 16)
    tail_dump = run_tool("objdump", "-s", "--start-address=" + hex(address),
                         "--stop-address=" + hex(address + 4), elf)
    value = re.search(r"^\s*" + literal[1] + r"\s+([0-9a-f]{8})", tail_dump, re.M)
    assert value and int.from_bytes(bytes.fromhex(value[1]), "little") == int(
        functions["api_muladd$part$0"]["address"], 16)
    raw = "\n".join(functions["br_ecdsa_i15_vrfy_raw"]["lines"])
    assert re.search(r"l32i\.n\s+a8, a15, 24", raw)
    assert re.search(r"callx0\s+a8", raw)
    cont = PACKAGE / "framework-arduinoespressif8266/cores/esp8266/cont.h"
    assert "#define CONT_STACKSIZE 4096" in cont.read_text()
    flags = (ROOT / "experiments/v08_m7/platformio.ini").read_text()
    assert "CONT_STACKSIZE" not in flags
    crypto = sum(value[0] for name, value in frames.items() if not name.startswith(("m7::", "bool m7::")))
    chain = sum(value[0] for value in frames.values())
    assert crypto == 4384 and chain == 5904 and crypto > 4096
    sections = {}
    for environment in ("legacy_compile", "media_compile"):
        path = BUILD / environment
        row = run_tool("size", path / "firmware.elf").splitlines()[1].split()
        sections[environment] = {**dict(zip(("text", "data", "bss"), map(int, row[:3]))),
            "bin_bytes": (path / "firmware.bin").stat().st_size,
            "elf_sha256": digest(path / "firmware.elf"),
            "bin_sha256": digest(path / "firmware.bin")}
    return {"gate": "BLOCKED__NATIVE_STACK_PATH_EXCEEDS_CONT_STACK",
        "evidence_kind": "linked Xtensa static reachable-path lower bound, NOT device high-water",
        "source_parent": "84129daa7359c73e738272b1c01131b3292dc315",
        "head_at_analysis": subprocess.check_output(["git", "rev-parse", "HEAD"], cwd=ROOT, text=True).strip(),
        "instrumented_mission8_candidate_built": False,
        "sections": sections, "frames": evidence, "direct_edges": edges,
        "indirect_edge": {"implementation": "br_ec_p256_m15", "muladd_offset": 24,
            "linked_pointer_dump": dump, "api_muladd_tail": tail,
            "tail_literal_dump": tail_dump},
        "cont_stack_bytes": 4096, "crypto_path_lower_bound_bytes": crypto,
        "receiver_and_crypto_path_lower_bound_bytes": chain,
        "omitted": ["application loop", "handleClient owner", "continuation entry", "additional callees"],
        "cont_header_sha256": digest(cont), "device_writes": 0}


if __name__ == "__main__":
    print(json.dumps(inspect(), indent=2))
