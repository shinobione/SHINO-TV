"""Offline third graph: real StageA + authenticated arm + probe + dormant OTA.

This public-inert variant is intentionally NOT a production firmware artifact.
Installed, frozen StageA files are never touched; private credentials are not
accessed. When an owner-approved image is eventually built, public fixture
identities must be replaced by separately provisioned private material.
"""
import argparse,json,configparser
from pathlib import Path
from shino_maintenance_build import prepare as basic
from m9_stagea_build import ROOT
from shino_wifi_build import ENV

def replace_once(body,src,dst):
    assert body.count(src)==1,(src[:80],body.count(src))
    return body.replace(src,dst)

def maintenance_http_policy(text):
    """Return exact private/public maintenance GET allowlist; fail on drift."""
    return replace_once(text,
      'std::strcmp(path, "/api/v1/bridge/metrics") == 0)) return 200;',
      '''std::strcmp(path, "/api/v1/bridge/metrics") == 0 ||
        std::strcmp(path, "/api/v1/m9/maintenance/challenge") == 0 ||
        std::strcmp(path, "/api/v1/m9/maintenance/probe") == 0 ||
        std::strcmp(path, "/api/v1/m9/maintenance/install") == 0 ||
        std::strcmp(path, "/api/v1/m9/maintenance/result") == 0)) return 200;''')


def prepare(directory):
    directory=basic(directory,small_buffer=True)
    # The public third graph uses a deliberately published HMAC fixture.
    # Build-level interlock keeps INSTALL disabled even after a valid probe.
    ini=directory/'platformio.ini'
    conf=configparser.ConfigParser(interpolation=None)
    conf.read(ini)
    env='env:esp12e_m9_4m2m_normal_qualification'
    conf[env]['build_flags']+='\n    -DSHINO_PUBLIC_INERT_REVIEW=1'
    with ini.open('w',encoding='utf-8') as out:conf.write(out)
    source=directory/'src/boot/M9NormalStageA.cpp'
    body=source.read_text()
    body=replace_once(body,'#include "ShinoMaintenance.h"',
                      '#include "ShinoMaintenance.h"\n#include "ShinoArmGate.h"')
    body=replace_once(body,
      '// Unbound trusted seam: public graph never supplies private consent.\n'
      '__attribute__((weak,noinline)) bool shinoMaintenanceConsent(ShinoInstall::Consent&){return false;}',
      '// This is a PUBLIC-INERT compile graph. No private owner key is read.\n'
      'namespace M9NormalStageA { namespace { bool shinoMaintenanceConsent(ShinoInstall::Consent&); } }')
    body=replace_once(body,
      'namespace M9NormalStageA {\nnamespace {\nstruct CoreSource {',
      '''namespace M9NormalStageA {
namespace {
static constexpr char ReviewDevice[]="0123456789abcdef";
static constexpr char ReviewBuild[]=
    "aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa";
static constexpr char ReviewMaintenanceKey[]=
    "1111111111111111111111111111111111111111111111111111111111111111";
ShinoInstall::ArmGate armGate(ShinoInstall::mac);
bool shinoMaintenanceConsent(ShinoInstall::Consent& c){
    ShinoInstall::ArmRequest p{};
    if(!armGate.consume(p) || !p.dryRun)return false;
    c={p.device,p.build,p.key,true,true};return true;
}
struct CoreSource {''')
    body=replace_once(body,'void metrics() {',
'''void armChallenge(){
    if(!auth())return;
    if(!configReady || !apReady || maintenance.mode()!=decltype(maintenance)::Normal){
        respond(503,"{\\"error\\":\\"MAINTENANCE_UNAVAILABLE\\"}");return;
    }
    uint8_t random[16];for(unsigned i=0;i<4;++i){
        uint32_t r=os_random();std::memcpy(random+4*i,&r,4);
    }
    char nonce[33]{};
    if(!armGate.challenge(random,sizeof(random),millis(),nonce,sizeof(nonce))){
        respond(503,"{\\"error\\":\\"CHALLENGE_REFUSED\\"}");return;
    }
    char payload[192];
    int n=std::snprintf(payload,sizeof(payload),
       "{\\"nonce\\":\\"%s\\",\\"device\\":\\"%s\\",\\"build\\":\\"%s\\"}",
       nonce,ReviewDevice,ReviewBuild);
    if(n<=0 || size_t(n)>=sizeof(payload)){respond(503,"{\\"error\\":\\"BOUND\\"}");return;}
    respond(200,payload);
}
void armMode(bool dryRun){
    if(!auth())return;
    // Published fixture identities are not authority to write flash.
    if(!dryRun){respond(403,"{\\"error\\":\\"PUBLIC_REVIEW_DRY_RUN_ONLY\\"}");return;}
    const String& proof=service().raw().header("X-Shino-Arm");
    if(!configReady || !apReady ||
       !armGate.arm(dryRun,proof.c_str(),millis(),
            maintenance.mode()==decltype(maintenance)::Normal,apReady)){
        respond(403,"{\\"error\\":\\"ARM_DENIED\\"}");return;
    }
    respond(202,dryRun?"{\\"pending\\":\\"PROBE\\"}":"{\\"pending\\":\\"INSTALL\\"}");
}
bool tracePassed(){
    const auto& t=maintenance.measurements();
    if(t.anyFailure())return false;
    for(unsigned i=0;i<ShinoInstall::MemoryTrace::Count;++i){
        const auto p=static_cast<ShinoInstall::TracePoint>(i);
        if(!t.has(p) || t.at(p).failed)return false;
    }
    return true;
}
void armResult(){
    if(!auth())return;
    const auto& t=maintenance.measurements();
    uint32_t h=UINT32_MAX,b=UINT32_MAX,s=UINT32_MAX;
    uint8_t frag=0;uint32_t seen=0;
    for(unsigned i=0;i<ShinoInstall::MemoryTrace::Count;++i){
        const auto& x=t.at(static_cast<ShinoInstall::TracePoint>(i));
        if(!x.samples)continue;++seen;
        h=std::min(h,x.minHeap);b=std::min(b,x.minBlock);
        s=std::min(s,x.minStack);frag=std::max(frag,x.maxFrag);
    }
    char payload[240];
    int n=std::snprintf(payload,sizeof(payload),
     "{\\"probe_qualified\\":%s,\\"phases_seen\\":%u,\\"heap_min\\":%u,"
     "\\"largest_min\\":%u,\\"stack_min\\":%u,\\"frag_max\\":%u,"
     "\\"physical_update_permitted\\":false}",
     armGate.probeQualified()?"true":"false",unsigned(seen),
     unsigned(h==UINT32_MAX?0:h),unsigned(b==UINT32_MAX?0:b),
     unsigned(s==UINT32_MAX?0:s),unsigned(frag));
    if(n<=0 || size_t(n)>=sizeof(payload)){respond(503,"{\\"error\\":\\"BOUND\\"}");return;}
    respond(200,payload);
}
void metrics() {''')
    body=replace_once(body,
      'service.raw().collectHeaders("Authorization", "Content-Length", "Content-Type", "Transfer-Encoding");',
      'service.raw().collectHeaders("Authorization", "Content-Length", "Content-Type", "Transfer-Encoding", "X-Shino-Arm");')
    body=replace_once(body,'    service.onNotFound([]() {',
      '''    service.on("/api/v1/m9/maintenance/challenge", HTTP_GET, armChallenge);
    service.on("/api/v1/m9/maintenance/probe", HTTP_GET, [](){armMode(true);});
    service.on("/api/v1/m9/maintenance/install", HTTP_GET, [](){armMode(false);});
    service.on("/api/v1/m9/maintenance/result", HTTP_GET, armResult);
    service.onNotFound([]() {''')
    body=replace_once(body,'    if (configReady) config.setApiToken(SHINO_BOOTSTRAP_API_TOKEN);',
      '    if (configReady) config.setApiToken(SHINO_BOOTSTRAP_API_TOKEN);\n'
      '    if(!armGate.configure(ReviewDevice,ReviewBuild,ReviewMaintenanceKey))return;')
    body=replace_once(body,'    if (apReady) service().handleClient();',
      '''#if defined(SHINO_MAINTENANCE_PROBE) && SHINO_MAINTENANCE_PROBE
    if(maintenance.takeProbeCompleted())armGate.setProbeResult(tracePassed());
#endif
    if (apReady) service().handleClient();''')
    source.write_text(body)
    policy=directory/'include/boot/M9NormalHttpPolicy.h'
    policy.write_text(maintenance_http_policy(policy.read_text()))
    info=json.loads((directory/'public-inputs.json').read_text())
    info['experimental_auth_arm']=True
    info['public_inert_hmac_credential_only']=True
    info['not_flashable_or_owner_qualified']=True
    info['public_install_denied']=True
    info['trusted_consent_bound']=True
    (directory/'public-inputs.json').write_text(json.dumps(info,indent=2))
    return directory

if __name__=='__main__':
    ap=argparse.ArgumentParser(description=__doc__)
    ap.add_argument('directory',type=Path)
    args=ap.parse_args()
    print(prepare(args.directory))
