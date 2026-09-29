"""Report linked baseline/candidate size for the isolated, unstarted sketch."""
from __future__ import annotations

import json
import os
from pathlib import Path
import re
import subprocess

ROOT = Path(__file__).resolve().parents[1] / "experiments/v08_preparse/.pio/build"
TOOL = Path.home() / ".platformio/packages/toolchain-xtensa/bin" / (
    "xtensa-lx106-elf-size.exe" if os.name == "nt" else "xtensa-lx106-elf-size"
)


def one(environment: str) -> dict[str, int]:
    build = ROOT / environment
    elf = build / "firmware.elf"
    image = build / "firmware.bin"
    if not (TOOL.is_file() and elf.is_file() and image.is_file()):
        raise FileNotFoundError(f"missing compiler or linked result for {environment}")
    output = subprocess.check_output([str(TOOL), str(elf)], text=True)
    fields = re.match(r"\s*(\d+)\s+(\d+)\s+(\d+)\s+(\d+)\s+", output.splitlines()[1])
    if not fields:
        raise ValueError("unrecognized Xtensa size output")
    text, data, bss, _ = map(int, fields.groups())
    return {"text": text, "data": data, "bss": bss, "bin": image.stat().st_size}


if __name__ == "__main__":
    baseline = one("baseline_compile")
    candidate = one("preparse_compile")
    delta = {key: candidate[key] - baseline[key] for key in baseline}
    print(json.dumps({"baseline": baseline, "candidate": candidate, "delta": delta}, indent=2))
