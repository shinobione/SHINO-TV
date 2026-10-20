"""PlatformIO INERT-only gate. All device targets fail before opening a port."""
from pathlib import Path
import hashlib,json
from SCons.Script import Import,COMMAND_LINE_TARGETS
Import('env')
if env.subst('$PIOENV') not in ('b54_inert_base','b54_inert_handoff'):
 raise RuntimeError('Unknown INERT environment')
if any(t for t in COMMAND_LINE_TARGETS if any(s in t.lower() for s in ('upload','erase','program','buildfs','monitor','debug','test'))):
 raise RuntimeError('INERT: all hardware/FS/debug/test targets prohibited')
root=Path(env.subst('$PROJECT_DIR'));manifest=json.loads((root/'INERT_INPUTS.json').read_text())
for name,pin in manifest.items():
 if hashlib.sha256((root/name).read_bytes()).hexdigest()!=pin:raise RuntimeError('INERT input drift: '+name)
env.Append(CXXFLAGS=['-include',str(root/'include/Updater.h')])
def refuse(*args,**kwargs):raise RuntimeError('INERT: no physical uploader exists')
env.Replace(UPLOADCMD=refuse,UPLOAD_PORT='INERT_NO_PORT')
def make_unbootable(source,target,env):
 path=Path(env.subst('$BUILD_DIR'))/'firmware.bin';raw=path.read_bytes()
 if raw[0]!=0xe9:raise RuntimeError('Unexpected input ESP image header')
 receipt=dict(bytes=len(raw),raw_source_bin_sha256=hashlib.sha256(raw).hexdigest(),scope='RAW_IMAGE_MEASURED_IN_MEMORY_THEN_MADE_NONBOOTABLE')
 raw=b'\0'+raw[1:];path.write_bytes(raw)
 receipt['inert_bin_sha256']=hashlib.sha256(raw).hexdigest();receipt['bootable']=False
 (path.parent/'inert-bin.json').write_text(json.dumps(receipt,indent=2))
env.AddPostAction('$BUILD_DIR/${PROGNAME}.bin',make_unbootable)
