"""B5 4m2m LAN/OTA opt-in build. Never changes B4 sources or contacts devices.

The normal HTTP OTA receiver is copied into a new disposable source graph,
then receives only exact-anchor HomeLAN additions. Public CI images are inert;
owner-private releases require a new, separately approved physical decision.
"""
import argparse
import hashlib
import json
import shutil
import subprocess
from pathlib import Path

from m9_stagea_build import ROOT, ENV
from shino_http_ota_build import (
    prepare as prepare_b4, materialize_http as materialize_b4,
    descriptor, elf_layout, stack_frames,
)
from shino_owner_transition import OWNER, load
from m9_signed_release import validate_image
from shino_wifi_resources import one


def once(source, old, replacement):
    if source.count(old)!=1:raise ValueError("B5 anchor drift")
    return source.replace(old,replacement,1)


def materialize_http(core,destination):
    """Retain B4's pinned, bounded parser and add two unique B5 headers."""
    headers=materialize_b4(core,destination)
    parser=headers/"Parsing-impl.h"
    data=parser.read_text(encoding="utf-8")
    data=once(data,
      '"X-Shino-Nonce","X-Shino-Proof"};',
      '"X-Shino-Nonce","X-Shino-Proof","Origin","X-Shino-Lan-Intent"};')
    data=once(data,"i<11;++i","i<13;++i")
    parser.write_text(data,encoding="utf-8",newline="\n")
    return headers


def patch_normal(source):
    source=once(source,'#include "ShinoRelease.h"',
          '#include "ShinoRelease.h"\n#include "B5Lan.h"')
    source=once(source,
          'WiFiManager network("","","SHINO-TV-StageA",SHINO_SETUP_AP_PSK);',
          '// B5 operates AP/STA via the separate, opt-in 4m2m controller.')
    source=once(source,'WiFi.getMode()==WIFI_AP&&uint32_t(millis()-uploadStart)<120000',
          'B5Lan::permitted(server)&&uint32_t(millis()-uploadStart)<120000')
    source=once(source,'enum class Route:uint8_t{Closed,Normal,MetricsGet,MetricsPost,Identity,Upload};',
          'enum class Route:uint8_t{Closed,Normal,MetricsGet,MetricsPost,Identity,Upload,LanIntent,LanProvision,LanStatus};')
    source=once(source,
          'if(path=="/api/v1/update/status"||path=="/api/v1/m9/maintenance/result")return Route::Identity;',
          'if(path=="/api/v1/update/status"||path=="/api/v1/m9/maintenance/result")return Route::Identity;\n'
          '        if(path=="/api/v1/lan/status")return Route::LanStatus;\n'
          '        if(path=="/api/v1/lan/intent")return Route::LanIntent;')
    source=once(source,'if(path=="/api/v1/update")return Route::Upload;',
          'if(path=="/api/v1/update")return Route::Upload;\n'
          '        if(path=="/api/v1/lan/provision")return Route::LanProvision;')
    source=once(source,
          'bool localPeer(){const auto p=server.client().remoteIP();return WiFi.getMode()==WIFI_AP&&server.client().localIP()==WiFi.softAPIP()&&p[0]==192&&p[1]==168&&p[2]==4&&p[3]>1&&p[3]<255;}',
          'bool localPeer(){return B5Lan::permitted(server);}')
    source=once(source,'const Route selected=route();uint32_t bytes=0;',
          'const Route selected=route();uint32_t bytes=0;\n'
          '    if(!B5Lan::permitted(server)){respond(403,"{\\\"error\\\":\\\"NETWORK_POLICY\\\"}");return false;}')
    return source


def add_b5_routes(source):
    source=once(source,
        'if(selected==Route::MetricsPost&&(bytes<16||bytes>384||server.header("Content-Type")!="application/json")){',
        'if(selected==Route::LanProvision&&(!B5Lan::apPeer(server)||bytes<3||bytes>99||'
        'server.header("Content-Type")!="application/octet-stream")){'
        'respond(403,"{\\\"error\\\":\\\"PROVISION_AP_ONLY\\\"}");return false;}\n'
        '    if(selected==Route::MetricsPost&&(bytes<16||bytes>384||server.header("Content-Type")!="application/json")){')
    marker='bool deferRequest(){server.keepAlive(false);requestPending=true;return false;}'
    handlers=r"""
__attribute__((noinline)) void lanStatus() {
    ResponseLease lease;if(!lease){respond(503,"{\"error\":\"RESPONSE_BUSY\"}");return;}
    const String ip=B5Lan::address().toString();
    const int n=std::snprintf(responseBody,sizeof(responseBody),
       "{\"state\":\"%s\",\"lan_ip\":\"%s\",\"sta_online\":%s,\"ota_protocol\":\"shino-http-ota-1\","
       "\"credential_state\":\"%s\",\"connection\":\"%s\",\"provision\":\"%s\",\"firmware\":\"B5.1\"}",
       B5Lan::state(),ip.c_str(),B5Lan::online()?"true":"false",
       B5Lan::storageState(),B5Lan::connectionState(),B5Lan::provisionState());
    if(n<0||size_t(n)>=sizeof(responseBody)){respond(500,"{\"error\":\"LAN_BOUND\"}");return;}
    respond(200,responseBody);
}
__attribute__((noinline)) void lanIntent() {
    char token[33]{};
    if(!B5Lan::intentStart(server,token)){respond(403,"{\"error\":\"INTENT_AP_ONLY\"}");return;}
    char reply[64]{};
    std::snprintf(reply,sizeof(reply),"{\"intent\":\"%s\"}",token);
    respond(200,reply);
    HomeLan::wipe(token,sizeof(token));
    HomeLan::wipe(reply,sizeof(reply));
}
__attribute__((noinline)) void lanProvision() {
    if(!B5Lan::apPeer(server)){respond(403,"{\"error\":\"AP_ONLY\"}");return;}
    uint32_t n=0;if(!length(n)||n<3||n>99){respond(413,"{\"error\":\"FRAMING\"}");return;}
    uint32_t at=0;
    auto& peer=server.client();
    while(at<n&&uint32_t(millis()-server.requestStarted())<2000&&peer.connected()) {
        const size_t count=std::min(size_t(peer.available()),size_t(n-at));
        if(count) {
            const int got=peer.read(transferBuffer+at,count);
            if(got<=0)break;
            at+=uint32_t(got);
        } else yield();
    }
    if(at!=n || uint32_t(millis()-server.requestStarted())>=2000 ||
       !peer.connected()) {
        HomeLan::wipe(transferBuffer,sizeof(transferBuffer));
        B5Lan::cancelIntent();
        respond(409,"{\"error\":\"PROVISION_BODY_INCOMPLETE\"}");
        return;
    }
    if(peer.available()) {
        HomeLan::wipe(transferBuffer,sizeof(transferBuffer));B5Lan::cancelIntent();
        respond(409,"{\"error\":\"PROVISION_BODY_EXTRA\"}");return;
    }
    const auto result=B5Lan::provision(server,transferBuffer,n,
                                     server.header("X-Shino-Lan-Intent").c_str());
    HomeLan::wipe(transferBuffer,sizeof(transferBuffer));
    if(result==B5Lan::ProvisionCode::Verified) {
        respond(200,"{\"saved\":true,\"readback_verified\":true}");
    } else {
        char error[96]{};
        std::snprintf(error,sizeof(error),"{\"error\":\"%s\"}",B5Lan::codeName(result));
        respond(409,error);
    }
}
"""
    # Raw above is authored exactly as C++ output with quoted JSON.
    source=once(source,marker,handlers+'\n'+marker)
    source=once(source,
        'case Route::Identity:identity();break;',
        'case Route::Identity:identity();break;\n'
        '        case Route::LanStatus:lanStatus();break;\n'
        '        case Route::LanIntent:lanIntent();break;\n'
        '        case Route::LanProvision:lanProvision();break;')
    source=once(source,
        'WiFi.persistent(false);apReady=network.startAccessPointMode();if(!apReady)return;',
        'apReady=B5Lan::begin("SHINO-TV-StageA",SHINO_SETUP_AP_PSK);if(!apReady)return;')
    source=once(source,
        '"X-Shino-Build","X-Shino-Nonce","X-Shino-Proof");',
        '"X-Shino-Build","X-Shino-Nonce","X-Shino-Proof","Origin","X-Shino-Lan-Intent");')
    source=once(source,
        'if(requestPending)serviceRequest();\n    const auto now=millis();',
        'if(requestPending)serviceRequest();\n'
        '    B5Lan::poll(uploadBusy);\n'
        '    const auto now=millis();')
    return source


def prepare(directory,private=False):
    directory=Path(directory).resolve()
    if private and OWNER.resolve() not in directory.parents:
        raise ValueError("B5 private graph must remain owner-local")
    directory,device,build_id=prepare_b4(directory,load() if private else None)
    if not private:
        # Distinct public successor identity for exact B5 -> B5.1 RAM OTA tests.
        release=directory/"include/ShinoRelease.h"
        release.write_text(once(release.read_text(encoding="utf-8"),
            '#define SHINO_OTA_BUILD "'+build_id+'"',
            '#define SHINO_OTA_BUILD "'+'b'*64+'"'),encoding="utf-8")
        build_id="b"*64
    normal=directory/"src/boot/M9NormalStageA.cpp"
    normal.write_text(add_b5_routes(patch_normal(normal.read_text(encoding="utf-8"))),
                      encoding="utf-8")
    # Keep old prototype untouched. The generated copy alone uses 4m2m.
    header=directory/"include/boot/HomeLanPolicy.h"
    policy=header.read_text(encoding="utf-8")
    policy=once(policy,"fsStart==0x100000","fsStart==0x200000")
    header.write_text(policy,encoding="utf-8")
    shutil.copyfile(ROOT/"ota/lan/B5Lan.h",directory/"include/B5Lan.h")
    shutil.copyfile(ROOT/"ota/lan/B5Lan.cpp",directory/"src/boot/B5Lan.cpp")
    # The build is the same pinned Core with an additional header pair.
    script=directory/"scripts/phase_t_build.py"
    code=script.read_text(encoding="utf-8")
    code=once(code,"from shino_http_ota_build import materialize_http as materialize",
                   "from shino_b5_lan_build import materialize_http as materialize")
    script.write_text(code,encoding="utf-8")
    return directory,device,build_id


def build(directory,private=False):
    import shutil as _shutil
    pio=_shutil.which("pio") or _shutil.which("platformio")
    if not pio:raise ValueError("PlatformIO unavailable")
    directory,device,build_id=prepare(directory,private)
    with (directory/"build.log").open("x",encoding="utf-8") as log:
        run=subprocess.run([pio,"run","-d",str(directory),"-e",ENV],
               cwd=ROOT,stdin=subprocess.DEVNULL,stdout=log,stderr=subprocess.STDOUT,timeout=1200)
    if run.returncode:
        raise RuntimeError("B5 public compile failed; inspect ignored build.log")
    return inspect_build(directory,device,build_id,private)


def inspect_build(directory,device,build_id,private=False):
    """Verify an already-compiled graph without rebuilding any old artifact."""
    directory=Path(directory)
    bin_path=directory/".pio/build"/ENV/"firmware.bin"
    raw=bin_path.read_bytes()
    validate_image(raw)
    if raw.count(descriptor(device,build_id).encode())!=1:
        raise ValueError("Missing B5 descriptor")
    resource=one(directory)
    layout=elf_layout(bin_path.with_suffix(".elf"))
    frames=stack_frames(directory)
    if resource["noinit"]!=56:raise ValueError("Unexpected B5 RTC/noinit")
    from shino_http_ota_stack import audit
    stack=audit(directory)
    (directory/"stack-paths.json").write_text(json.dumps(stack,indent=2)+"\n")
    if not 64000<=len(raw)<=0xFEFF0:
        raise ValueError("B5 OTA image exceeds capacity")
    manifest=dict(schema=1,family="SHINO-StageA",layout="4m2m",
        protocol="shino-http-ota-1",device=device,bytes=len(raw),
        sha256=hashlib.sha256(raw).hexdigest(),build_id=build_id)
    (directory/"release.json").write_text(json.dumps(manifest,indent=2)+"\n")
    result=dict(manifest,firmware="B5.1",source_commit=subprocess.check_output(
        ["git","rev-parse","HEAD"],cwd=ROOT,text=True).strip(),
        private=private,static_ram=resource["static_ram"],noinit=resource["noinit"],
        layout_symbols=layout,stack_frames=frames,
        ota_memory_native_measured=False,physical="NOT_RUN",
        device_contacts=0,ota_posts=0,
        b4_source_unchanged=True,sta_dhcp=True,protected_ap_recovery=True,
        lan_ota_source_present=True,lan_ota_physical_verified=False)
    result["source_dirty"]=bool(subprocess.check_output(["git","status","--porcelain"],cwd=ROOT,text=True).strip())
    result["lan_inputs_sha256"]={p:hashlib.sha256((ROOT/p).read_bytes()).hexdigest() for p in
        ("ota/lan/B5Lan.cpp","ota/lan/B5Lan.h","tools/shino_b5_lan_build.py")}
    from shino_b51_lan_resources import audit as audit_lan
    result["lan_stack"]=audit_lan(directory)
    (directory/"report.json").write_text(json.dumps(result,indent=2)+"\n")
    if not private:print(json.dumps(result))
    return result


if __name__=="__main__":
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument("directory",type=Path)
    p.add_argument("--private",action="store_true",
                   help="PRIVATE ignored owner-local build ONLY. Never install.")
    a=p.parse_args()
    build(a.directory,a.private)
