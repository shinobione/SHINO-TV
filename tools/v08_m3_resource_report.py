"""Native LINK and compiler frame evidence only; never target runtime telemetry."""
from pathlib import Path
import hashlib
import json
import os
import subprocess

ROOT = Path(__file__).resolve().parents[1]
BUILD = ROOT / "experiments/v08_full_bridge/.pio/build"
BIN = Path.home() / ".platformio/packages/toolchain-xtensa/bin"

def tool(name):
    return str(BIN / ("xtensa-lx106-elf-" + name + (".exe" if os.name=="nt" else "")))

def one(name):
    path = BUILD / name
    elf, image = path / "firmware.elf", path / "firmware.bin"
    fields = subprocess.check_output([tool("size"),str(elf)],text=True).splitlines()[1].split()
    sizes = dict(zip(["text","data","bss"],map(int,fields[:3])))
    sizes["bin"] = image.stat().st_size
    symbols = subprocess.check_output([tool("nm"),"-S","-C",str(elf)],text=True)
    assert "FirstBootBridge::run()" in symbols and "FirstBootBridge::loop()" in symbols
    overlay = "::_v08ReadFirstLine(" in symbols
    assert overlay == (name == "bridge_preparse")
    server = [line for line in symbols.splitlines() if line.endswith(" b (anonymous namespace)::server")]
    assert len(server) == 1, "one linked bridge server"
    frames = []
    su = path / "src/boot/FirstBootBridge.cpp.su"
    for line in su.read_text(encoding="utf-8").splitlines():
        if any(key in line for key in ["::_v08ReadFirstLine(","::_parseRequest(","::handleClient()",
              "::authenticate(","::authenticateDigest(","::acceptMetrics()", "::paintNativeDashboard()",
              "::browserSessionValid()","FirstBootBridge::loop()"]):
            function, count, kind = line.rsplit("\t",2)
            frames.append({"function":function.split(":",3)[-1],"frame_bytes":int(count),"kind":kind})
    return {"sizes":sizes,"bridge_server_bytes":int(server[0].split()[1],16),
            "overlay_symbol_present":overlay,"compiler_frames_not_high_water":frames,
            "elf_sha256":hashlib.sha256(elf.read_bytes()).hexdigest()}

if __name__ == "__main__":
    base, candidate = one("bridge_baseline"),one("bridge_preparse")
    print(json.dumps({"evidence":"Xtensa link/compiler; no device runtime", "baseline":base,"experiment":candidate,
        "delta":{k:candidate["sizes"][k]-base["sizes"][k] for k in base["sizes"]}},indent=2))
