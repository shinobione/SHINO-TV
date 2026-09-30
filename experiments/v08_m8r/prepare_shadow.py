"""Equivalent full firmware links, tracked PUBLIC source only. No upload."""
from pathlib import Path
import sys
Import('env')
project=Path(env['PROJECT_DIR']).resolve();repo=project.parents[1]
sys.path.insert(0,str(repo/'tools'))
import v08_m6a_overlay as legacy
import v08_m8r_overlay as media
# Reuse tracked-copy + inert-public-policy generator in this namespace.
old=repo/'experiments/v08_full_bridge/prepare_shadow.py'
text=old.read_text(encoding='utf-8')
is_media=env['PIOENV'] in ('media_compile','stack_sensitivity_compile')
text=text.replace('from v08_native_overlay import materialize','from v08_m8r_overlay import materialize' if is_media else 'from v08_m6a_overlay import materialize')
text=text.replace('if env["PIOENV"] == "bridge_preparse":','if True:')
exec(compile(text,str(old),'exec'))
env.Prepend(CPPPATH=[str(project/'native')])
bridge=shadow/'src/boot/FirstBootBridge.cpp'
append='\nvoid m7CompileOnly() { server.handleClient(); }\n'
if is_media:
    from v07_pinned_core_probe import core_root
    import hashlib,json
    bear=core_root()/'tools/sdk/ssl/bearssl'
    crypto_manifest=json.loads((repo/'tools/v08_m8r_bearssl_manifest.json').read_text())
    for name,digest in crypto_manifest.items():
        assert hashlib.sha256((bear/name).read_bytes()).hexdigest()==digest, 'BearSSL source drift: '+name
    def cryptoIncludes(buildenv,node):
        # Match Core's standard *.c.o flash-code linker rule (ordinary .o would
        # consume IRAM). Algorithm and linker/partition script stay unchanged.
        return buildenv.Object('$BUILD_DIR/m8r_m31/ec_p256_m31.c.o',node,
            CPPPATH=buildenv['CPPPATH']+[str(bear/'src'),str(bear/'inc')])
    env.AddBuildMiddleware(cryptoIncludes,'*ec_p256_m31.c')
    # Compile the exact unmodified API implementation shipped in pinned Core.
    env.BuildSources('$BUILD_DIR/m8r_m31',str(bear/'src/ec'),src_filter=['+<ec_p256_m31.c>'])
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
