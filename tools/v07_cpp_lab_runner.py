"""Compile and execute the offline C++ ingress lab with a host compiler."""
from __future__ import annotations

import json
import os
from pathlib import Path
import shutil
import subprocess
import tempfile


ROOT = Path(__file__).resolve().parent
VSDEV = Path(r"C:\Program Files (x86)\Microsoft Visual Studio\2022\BuildTools\Common7\Tools\VsDevCmd.bat")


def compiler_environment(directory: Path) -> tuple[str, dict[str, str]]:
    for name in ("g++", "clang++"):
        found = shutil.which(name)
        if found:
            return found, os.environ.copy()
    if os.name != "nt" or not VSDEV.is_file():
        raise RuntimeError("No host C++ compiler available")
    batch = directory / "compiler-env.cmd"
    batch.write_text(f'@echo off\ncall "{VSDEV}" -arch=x64 >nul\nset\n', encoding="utf-8")
    result = subprocess.run(["cmd.exe", "/d", "/c", str(batch)], capture_output=True, text=True,
                            timeout=30, check=True)
    env = os.environ.copy()
    for line in result.stdout.splitlines():
        if "=" in line and not line.startswith("="):
            key, value = line.split("=", 1)
            env[key] = value
    compiler = shutil.which("cl.exe", path=env.get("PATH"))
    if not compiler:
        raise RuntimeError("VsDevCmd did not supply cl.exe")
    return compiler, env


def build_and_run(source: Path, *, generated: str | None = None, expect_json: bool = True) -> dict[str, object]:
    with tempfile.TemporaryDirectory(prefix="v07-cpp-lab-") as td:
        directory = Path(td)
        if generated is not None:
            source = directory / source.name
            source.write_text(generated, encoding="utf-8")
        compiler, env = compiler_environment(directory)
        output = directory / ("lab.exe" if os.name == "nt" else "lab")
        if Path(compiler).name.lower() == "cl.exe":
            command = [compiler, "/nologo", "/std:c++17", "/EHsc", "/W4", f"/Fo:{directory / 'lab.obj'}", str(source),
                       "/link", f"/OUT:{output}"]
        else:
            command = [compiler, "-std=c++17", "-Wall", "-Wextra", "-pedantic", str(source), "-o", str(output)]
        compile_result = subprocess.run(command, cwd=ROOT, env=env, capture_output=True, text=True, timeout=60)
        if compile_result.returncode:
            raise RuntimeError(f"C++ compile failed ({compile_result.returncode}):\n"
                               f"{compile_result.stdout[-4000:]}\n{compile_result.stderr[-4000:]}")
        run = subprocess.run([str(output)], cwd=ROOT, env=env, capture_output=True, text=True, timeout=30)
        if run.returncode:
            raise RuntimeError(f"C++ lab failed ({run.returncode}):\n{run.stdout}\n{run.stderr}")
        return {"compiler": Path(compiler).name, "result": json.loads(run.stdout) if expect_json else run.stdout,
                "warnings": (compile_result.stdout + compile_result.stderr).strip()}


if __name__ == "__main__":
    print(json.dumps(build_and_run(ROOT / "v07_bounded_ingress_lab.cpp"), indent=2))
