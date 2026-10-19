"""M3-Q: reuse source-pinned M3-P Core copy, never global Core/device."""
from pathlib import Path
import sys
from SCons.Script import Import, COMMAND_LINE_TARGETS
Import("env")
if env.subst("$PIOENV") not in ("m3p_only_inert", "m3q_headers_inert"):
    raise RuntimeError("M3Q: prohibited PlatformIO environment")
if any(term in target.lower() for target in COMMAND_LINE_TARGETS
       for term in ("upload", "erase", "buildfs", "program")):
    raise RuntimeError("M3Q: refuse upload/erase/fs/program")
project = Path(env.subst("$PROJECT_DIR"))
sys.path.insert(0, str(project.parent/"link_m3p_parser"))
from patch_core_parser import materialize
core = env.PioPlatform().get_package_dir("framework-arduinoespressif8266")
headers = materialize(core, project/".pio/m3q-venv/ESP8266WebServer")
env.Prepend(CPPPATH=[str(headers),str(project),str(project.parent/"link_m3p_parser")])
