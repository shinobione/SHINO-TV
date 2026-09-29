"""Run actual bridge handler sources on host, with explicit dependency seams."""
from pathlib import Path
import json
import os
import subprocess
import tempfile
from v07_cpp_lab_runner import compiler_environment

ROOT = Path(__file__).resolve().parents[1]

def run(conditional: int) -> dict:
    default = ROOT / "experiments/v08_full_bridge/.pio/libdeps/bridge_baseline/ArduinoJson/src"
    arduinojson = Path(os.environ.get("SHINO_ARDUINOJSON_SRC", str(default))).resolve()
    if not (arduinojson / "ArduinoJson.h").is_file():
        raise FileNotFoundError("real ArduinoJson 7.4.3 required; no synthetic JSON fallback")
    if '#define ARDUINOJSON_VERSION "7.4.3"' not in (arduinojson / "ArduinoJson/version.hpp").read_text(encoding="utf-8"):
        raise ValueError("unreviewed ArduinoJson version")
    includes = [ROOT / "experiments/v08_full_bridge/host_shims", ROOT / "firmware/include", arduinojson]
    sources = [ROOT / "tools/v08_m3_bridge_lab.cpp", ROOT / "firmware/src/boot/FslessMetrics.cpp",
               ROOT / "firmware/src/boot/FslessWebUI.cpp"]
    with tempfile.TemporaryDirectory(prefix="v08-m3-bridge-") as td:
        directory = Path(td)
        compiler, env = compiler_environment(directory)
        output = directory / ("bridge.exe" if os.name == "nt" else "bridge")
        if Path(compiler).name.lower() == "cl.exe":
            command = [compiler,"/nologo","/std:c++17","/EHsc","/utf-8",
                       f"/DSHINO_ENABLE_FACTORY_RESTORE={conditional}",
                       *[f"/I{p}" for p in includes], *map(str,sources),"/link",f"/OUT:{output}"]
        else:
            command = [compiler,"-std=c++17","-Wall","-Wextra",
                       f"-DSHINO_ENABLE_FACTORY_RESTORE={conditional}",
                       *[f"-I{p}" for p in includes], *map(str,sources),"-o",str(output)]
        compiled = subprocess.run(command,cwd=directory,env=env,capture_output=True,text=True,timeout=60)
        if compiled.returncode:
            raise RuntimeError(compiled.stdout[-6000:] + compiled.stderr[-6000:])
        executed = subprocess.run([str(output)],env=env,capture_output=True,text=True,timeout=30)
        if executed.returncode:
            raise RuntimeError(executed.stdout + executed.stderr)
        return {"compiler":Path(compiler).name,"result":json.loads(executed.stdout),
                "warnings":compiled.stderr.strip()}

if __name__ == "__main__":
    print(json.dumps([run(0),run(1)],indent=2))
