"""M3-R inert overlay of exactly pinned M3-P Core. No device actions."""
from pathlib import Path
import sys
from SCons.Script import Import, COMMAND_LINE_TARGETS
Import("env")
if env.subst("$PIOENV") != "m3r_inert_single_parser":
    raise RuntimeError("M3R: unapproved environment")
if any(forbidden in target.lower() for target in COMMAND_LINE_TARGETS
       for forbidden in ("upload", "erase", "program", "buildfs")):
    raise RuntimeError("M3R: prohibited upload/program/erase/fs operation")
project = Path(env.subst("$PROJECT_DIR"))
sys.path.insert(0,str(project.parent/"link_m3p_parser"))
from patch_core_parser import materialize
core=env.PioPlatform().get_package_dir("framework-arduinoespressif8266")
clone=materialize(core,project/".pio/m3r-venv/ESP8266WebServer")
env.Prepend(CPPPATH=[str(clone),str(project.parent/"link_m3p_parser")])
