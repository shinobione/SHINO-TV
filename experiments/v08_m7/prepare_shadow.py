"""Equivalent full firmware links, tracked PUBLIC source only. No upload."""
from pathlib import Path
import sys
Import('env')
project=Path(env['PROJECT_DIR']).resolve();repo=project.parents[1]
sys.path.insert(0,str(repo/'tools'))
import v08_m6a_overlay as legacy
import v08_m7_overlay as media
# Reuse tracked-copy + inert-public-policy generator in this namespace.
old=repo/'experiments/v08_full_bridge/prepare_shadow.py'
text=old.read_text(encoding='utf-8')
text=text.replace('from v08_native_overlay import materialize','from v08_m7_overlay import materialize' if env['PIOENV']=='media_compile' else 'from v08_m6a_overlay import materialize')
text=text.replace('if env["PIOENV"] == "bridge_preparse":','if True:')
exec(compile(text,str(old),'exec'))
env.Prepend(CPPPATH=[str(project/'native')])
bridge=shadow/'src/boot/FirstBootBridge.cpp'
append='\nvoid m7CompileOnly() { server.handleClient(); }\n'
if env['PIOENV']=='media_compile':
    append='''
#include <MediaIngress.h>
static m7::Authority m7Authority(0);
static m7::Receiver m7Receiver;
static m7::Ingress m7Ingress(m7Authority,m7Receiver,"tv.test",[]()->uint32_t{return millis();});
void m7CompileOnly() { server.setOfflineMedia(&m7Ingress); server.handleClient(); }
'''
bridge.write_text(bridge.read_text(encoding='utf-8')+append,encoding='utf-8')
main=shadow/'src/main.cpp';value=main.read_text(encoding='utf-8')
value=value.replace('void setup() { if (shinoResearchDisabled) shinoResearchSetup(); }','extern void m7CompileOnly();\nvoid setup() { if (shinoResearchDisabled) { m7CompileOnly(); shinoResearchSetup(); } }')
main.write_text(value,encoding='utf-8')
