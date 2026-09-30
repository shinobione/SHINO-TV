"""Guarded public links; explicit local private qualification build. No upload."""
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
is_qualification=env['PIOENV']=='qualification_compile'
is_media=env['PIOENV'] in ('media_compile','stack_sensitivity_compile','qualification_compile')
text=text.replace('from v08_native_overlay import materialize','from v08_m8r_overlay import materialize' if is_media else 'from v08_m6a_overlay import materialize')
text=text.replace('if env["PIOENV"] == "bridge_preparse":','if True:')
exec(compile(text,str(old),'exec'))
env.Prepend(CPPPATH=[str(project/'native')])
bridge=shadow/'src/boot/FirstBootBridge.cpp'
append='\nvoid m7CompileOnly() { server.handleClient(); }\n'
if is_media:
    from v07_pinned_core_probe import core_root
    import hashlib,json
    core_manifest=json.loads((repo/'tools/v08_m8r_core_manifest.json').read_text(encoding='utf-8'))
    for name,digest in core_manifest.items():
        assert hashlib.sha256((core_root()/name).read_bytes()).hexdigest()==digest, 'Pinned Core drift: '+name
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
    env.BuildSources('$BUILD_DIR/m8r_thunk',str(project/'native'),src_filter=['+<MediaStackThunk.cpp>'])
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
if is_qualification:
    import os
    from pathlib import Path
    fixture=Path(os.environ.get('SHINO_M8_QUALIFICATION_FIXTURES',str(repo/'research-local/m8thunk-packets.json')))
    point=bytes.fromhex(json.loads(fixture.read_text(encoding='utf-8'))['public_point'])
    assert len(point)==65 and point[0]==4
    (shadow/'include/M8TestKey.h').write_text('#pragma once\nstatic const uint8_t M8_TEST_PUBLIC_POINT[65]={'+','.join(str(b) for b in point)+'};\n',encoding='utf-8')
    private=os.environ.get('SHINO_M8_PRIVATE_POLICY')
    if private:
        policy=Path(private).resolve()
        expected=Path.home()/'SHINO-PRIVATE/review-003/shino_private_policy.h'
        assert policy==expected.resolve() and policy.is_file()
        content=policy.read_text(encoding='utf-8')
        import re
        for name,value in {'SHINO_ENABLE_FACTORY_RESTORE':'1','SHINO_BOOT_PROFILE':'0','SHINO_ENABLE_NATIVE_SIGNED_OTA':'0'}.items():
            assert re.search(r'^\s*#define\s+'+name+r'\s+'+value+r'\s*(?://.*)?$',content,re.M), 'Private policy prerequisite failed: '+name
        (shadow/'include/shino_private_policy.h').write_bytes(policy.read_bytes())
    elif 'SHINO_M8_PRIVATE_INSTALL=1' in str(env.GetProjectOption('build_flags')):
        raise RuntimeError('Private installation policy must be explicitly supplied')
    bridge_text=bridge.read_text(encoding='utf-8')
    assert append in bridge_text
    bridge_text=bridge_text.replace(append,'\n#include "MediaQualification.inc"\n')
    bridge_text='void m8QualRegister();\nvoid m8QualAfterLoop();\n'+bridge_text
    bridge_text=bridge_text.replace('    server.begin();','    m8QualRegister();\n    server.begin();')
    bridge_text=bridge_text.replace('    FactoryRollback::tick();','    m8QualAfterLoop();\n    FactoryRollback::tick();')
    bridge.write_text(bridge_text,encoding='utf-8')
    main.write_text('#include <Arduino.h>\n#include "original_main.inc"\nvoid setup(){shinoResearchSetup();}\nvoid loop(){shinoResearchLoop();}\n',encoding='utf-8')
    (shadow/'include/project_version.h').write_text('#pragma once\n#define PROJECT_VER_STR "V08-M8-STACKTHUNK-QUALIFICATION"\n',encoding='utf-8')
