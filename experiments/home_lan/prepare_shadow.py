"""P0/P1 matched full graphs, public fixtures, volatile disabled boot, no upload."""
from pathlib import Path
import sys
Import('env')
project=Path(env['PROJECT_DIR']).resolve(); repo=project.parents[1]
old=repo/'experiments/artwork_pilot/prepare_shadow.py'
value=old.read_text(encoding='utf-8')
value=value.replace("project/'native/ArtworkAdapter.inc'","repo/'experiments/artwork_pilot/native/ArtworkAdapter.inc'")
exec(compile(value,str(old),'exec'))
import shutil
for name in ('include/boot/HomeLan.h','include/boot/HomeLanPolicy.h','src/boot/HomeLan.cpp'):
    source=repo/'firmware'/name; target=shadow/name
    target.parent.mkdir(parents=True,exist_ok=True); shutil.copyfile(source,target)
env.Prepend(CPPPATH=[str(repo/'experiments/artwork_pilot/native'),str(repo/'experiments/v08_m8r/native')])
if env['PIOENV']=='p0_compile':
    (shadow/'include/MediaIngress.h').unlink(missing_ok=True)
if env['PIOENV']!='p0_compile':
    sys.path.insert(0,str(repo/'tools'))
    from home_lan_overlay import materialize
    overlay=project/'.pio/pinned_overlay'
    materialize(overlay)
    value=bridge.read_text(encoding='utf-8')
    value+='''
bool homeLanMediaBusy() { return m7Receiver.pending || (m7Ingress.phaseCode()>0 && m7Ingress.phaseCode()<4); }
'''
    bridge.write_text(value,encoding='utf-8')
    if env['PIOENV']=='p1_oem_compile':
        policy=shadow/'include/shino_private_policy.h'
        policy.write_text(policy.read_text(encoding='utf-8').replace('#define SHINO_ENABLE_FACTORY_RESTORE 0','#define SHINO_ENABLE_FACTORY_RESTORE 1'),encoding='utf-8')
    # A trusted per-request authority is chosen from the accepted local socket,
    # never a Host supplied by a peer; signatures still cover the actual Host.
    source=(repo/'experiments/v08_m8r/native/MediaIngress.h').read_text(encoding='utf-8')
    source=source.replace('  void cancel() {','  void setExpectedHost(const char* host) { expectedHost=host; }\n  void cancel() {')
    (shadow/'include/MediaIngress.h').write_text(source,encoding='utf-8')
    env.Prepend(CPPPATH=[str(shadow/'include')])
    (shadow/'include/project_version.h').write_text('#pragma once\n#define PROJECT_VER_STR "P1-OFFLINE-UNSTARTED"\n',encoding='utf-8')
