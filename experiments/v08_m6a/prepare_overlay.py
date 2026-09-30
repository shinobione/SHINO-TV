"""Separate opt-in compile project; installed Core is fingerprinted, untouched."""
from pathlib import Path
import sys

Import('env')
project = Path(env['PROJECT_DIR']).resolve()
sys.path.insert(0,str(project.parents[1]/'tools'))
if env['PIOENV'] == 'previous_compile':
    from v08_native_overlay import materialize
    overlay = project/'.pio/previous_overlay'
else:
    from v08_m6a_overlay import materialize
    overlay = project/'.pio/pinned_overlay'
materialize(overlay)
env.Append(CPPPATH=[str(overlay)])
