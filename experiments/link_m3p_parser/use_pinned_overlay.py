"""M3-P isolated ESP8266WebServer override; nothing global or installed."""
from pathlib import Path
import sys
from SCons.Script import Import, COMMAND_LINE_TARGETS
Import("env")
if env.subst("$PIOENV")!="bounded_core_inert":
    raise RuntimeError("M3P overlay cannot be used in another environment")
if any(x in t.lower() for t in COMMAND_LINE_TARGETS for x in
       ("upload","erase","buildfs","program")):
    raise RuntimeError("M3P compile-only: forbidden upload/flash/fs target")
project=Path(env.subst("$PROJECT_DIR"))
sys.path.insert(0,str(project))
from patch_core_parser import materialize
core=env.PioPlatform().get_package_dir("framework-arduinoespressif8266")
headers=materialize(core,project/".pio/m3p-venv/ESP8266WebServer")
env.Prepend(CPPPATH=[str(headers),str(project)])
