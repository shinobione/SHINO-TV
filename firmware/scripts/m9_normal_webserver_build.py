"""Materialize one environment-local server ABI; no Core package modification."""
from pathlib import Path
import sys
from SCons.Script import Import
Import('env')
if env.subst('$PIOENV')!='esp12e_m9_4m2m_normal_qualification':
    raise RuntimeError('StageA Webserver attached to unreviewed environment')
project=Path(env.subst('$PROJECT_DIR'))
sys.path.insert(0,str(project/'scripts'))
from m9_normal_webserver import materialize
core=env.PioPlatform().get_package_dir('framework-arduinoespressif8266')
headers=materialize(core,project/'.pio/m9-normal-libs/ESP8266WebServer')
env.Prepend(CPPPATH=[str(headers)])
