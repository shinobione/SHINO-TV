"""Pinned Core/RSA state-machine execution in RAM only; no owner files/device."""
from pathlib import Path
import hashlib
import json
import os
import subprocess
import tempfile
import shutil
from m9_signed_fixture_image import inert_image
from m9_signed_release import verify, geometry, LINKER_MAX_APP_BYTES
from v07_pinned_core_probe import core_root
from v08_m8r_runner import compiler_environment

ROOT = Path(__file__).resolve().parent.parent
GRAPH = ROOT/"experiments/m9_signed_ota"


def source_gate():
    core = core_root()
    pins = json.loads((ROOT/"tools/m9_signed_core_sources.json").read_text())
    for name, digest in pins.items():
        if hashlib.sha256((core/name).read_bytes().replace(b"\r\n",b"\n")).hexdigest() != digest:
            raise ValueError("Pinned signing Core source drift: "+name)
    from m9_phase_o_qualification import source_gate as frozen_sources
    assert frozen_sources()["firmware_files_checked"] == 113
    stage = (ROOT/"firmware/src/boot/M9NormalStageA.cpp").read_text()
    assert "SHINO_ENABLE_NATIVE_SIGNED_OTA == 0" in stage
    for name in subprocess.check_output(["git","ls-files","firmware","companion","tools/m9_single_attempt*"],cwd=ROOT,text=True).splitlines():
        # Phase S has no edits to any deployed graph, sender or physical writer.
        old = subprocess.check_output(["git","show","7455f6b353f1733a78f2a6d25503edb063f7befb:"+name],cwd=ROOT)
        assert (ROOT/name).read_bytes().replace(b"\r\n",b"\n") == old.replace(b"\r\n",b"\n"), name
    assert stage.count("service.begin()") == 1 and stage.count("Webserver service;") == 1
    assert "M9Signed" not in stage
    # Independently verify reviewed header clone differs only by namespace,
    # reused result types, class name, include and 4m2m cap; old caps untouched.
    original = (ROOT/"firmware/include/boot/NativeOtaRawHeaderGate.h").read_text()
    start = original.index("class RawOtaHeaderGate final")
    tail = original[start:].replace("class RawOtaHeaderGate final","class HeaderGate final").replace("494144u + 256u + 4u","0xFEFF0u + 256u + 4u")
    actual = (GRAPH/"include/M9SignedHttp.h").read_text()
    assert actual[actual.index("class HeaderGate final"):] == tail
    return dict(pinned_core_files=len(pins), firmware_LF_pins=113, stage_a_single_owner=True,
                stage_a_ota_route=False, installed_sources_unchanged=True, device_contacts=0)


def run():
    source = source_gate()
    core = core_root(); bear = core/"tools/sdk/ssl/bearssl"
    with tempfile.TemporaryDirectory(prefix="m9-signed-public-") as td:
        p = Path(td)
        fixtures=GRAPH/"fixtures"
        manifest=json.loads((fixtures/"manifest.json").read_text())
        for name,pin in manifest.items():
            data=(fixtures/name).read_bytes()
            assert len(data)==pin['bytes'] and hashlib.sha256(data).hexdigest()==pin['sha256'],name
            shutil.copyfile(fixtures/name,p/name)
        raw=(p/"raw.inert").read_bytes();assert raw==inert_image()
        package,der = (p/"signed.inert").read_bytes(),(p/"public.der").read_bytes()
        sha = lambda b: hashlib.sha256(b).hexdigest()
        verified = verify(package,der,raw_sha256=sha(raw),key_sha256=sha(der),package_sha256=sha(package),current_bytes=399264)
        compiler,env = compiler_environment(p);msvc = Path(compiler).name.lower() == "cl.exe"
        generated = p/"core";generated.mkdir()
        for name in ("Updater.cpp","Updater.h","Updater_Signing.h"):
            body = (core/"cores/esp8266"/name).read_text()
            if name == "Updater.h":body = body.replace("  private:","  public:") # host reset seam only
            (generated/name).write_text(body)
        eboot = core/"bootloaders/eboot"
        h = (eboot/"eboot_command.h").read_text().replace("#define RTC_MEM ((volatile uint32_t*)0x60001200)",
                   "extern volatile uint32_t m9_host_rtc[32];\n#define RTC_MEM m9_host_rtc")
        h = '#ifdef __cplusplus\nextern "C" {\n#endif\n'+h+'\n#ifdef __cplusplus\n}\n#endif\n'
        (generated/"eboot_command.h").write_text(h)
        (generated/"eboot_command.c").write_bytes((eboot/"eboot_command.c").read_bytes())
        for name in ("c_types.h","spi_flash.h","user_interface.h"):(generated/name).write_text("#pragma once\n")
        signing = (core/"libraries/ESP8266WiFi/src/BearSSLHelpers.cpp").read_text()
        first = signing.index("// SHA256 hash for updater")
        last = signing.index("\n#if !CORE_MOCK\n\n",first)
        (generated/"signing.cpp").write_text('#include <BearSSLHelpers.h>\nnamespace BearSSL {\n'+signing[first:last]+"\n}\n")
        inc = [generated,GRAPH/"host",GRAPH/"include",ROOT/"firmware/include",ROOT/"experiments/v08_m7/host_shims",bear/"inc",bear/"src"]
        crypto = [*sorted((bear/"src/int").glob("i15_*.c")),*sorted((bear/"src/codec").glob("*.c")),
                  bear/"src/hash/sha2small.c",bear/"src/x509/pkey_decoder.c",*[bear/"src/rsa"/n for n in ("rsa_i15_pub.c","rsa_i15_pkcs1_vrfy.c","rsa_pkcs1_sig_unpad.c","rsa_default_pkcs1_vrfy.c")],generated/"eboot_command.c"]
        definitions = ["BR_INT128=0","BR_UMUL128=0","BR_LOMUL=1","BR_SLOW_MUL15=1","HOST_MOCK=1","CORE_MOCK=1","M9_SIGNED_OTA_UNWIRED=1","SHINO_ENABLE_FACTORY_RESTORE=0","SHINO_ENABLE_NATIVE_SIGNED_OTA=0"]
        if msvc:
            command = [compiler,"/nologo","/TC","/O2","/c",*["/D"+x for x in definitions],*["/I"+str(x) for x in inc],*map(str,crypto)]
        else:
            command = ["gcc","-O2","-c",*["-D"+x for x in definitions],*["-I"+str(x) for x in inc],*map(str,crypto)]
        compiled = subprocess.run(command,cwd=p,env=env,capture_output=True,text=True,timeout=120)
        if compiled.returncode:raise RuntimeError(compiled.stdout+compiled.stderr)
        objects = [p/(x.stem+(".obj" if msvc else ".o")) for x in crypto]
        sources = [ROOT/"tools/m9_signed_core_lab.cpp",generated/"Updater.cpp",generated/"signing.cpp"]
        exe = p/("lab.exe" if msvc else "lab")
        if msvc:
            command = [compiler,"/nologo","/std:c++20","/EHsc","/O2",*["/D"+x for x in definitions],*["/I"+str(x) for x in inc],*map(str,sources),*map(str,objects),"/link","/OUT:"+str(exe)]
        else:
            command = [compiler,"-std=c++17","-O2","-Wall","-Wextra",*["-D"+x for x in definitions],*["-I"+str(x) for x in inc],*map(str,sources),*map(str,objects),"-o",str(exe)]
        compiled = subprocess.run(command,cwd=p,env=env,capture_output=True,text=True,timeout=120)
        if compiled.returncode:raise RuntimeError(compiled.stdout+compiled.stderr)
        executed = subprocess.run([str(exe),str(p)],cwd=p,env=env,capture_output=True,text=True,timeout=120)
        if executed.returncode:raise RuntimeError(executed.stdout+executed.stderr)
        result = json.loads(executed.stdout)
        return dict(SIGNED_OTA_OFFLINE_GATE="PASS_UNWIRED_ONLY",production_integration="HOLD",
                    source=source,native_core=result,release=verified,public_fixture_raw_bytes=len(raw),
                    public_fixture_raw_sha256=sha(raw),public_fixture_signed_bytes=len(package),
                    public_fixture_signed_sha256=sha(package),public_der_sha256=sha(der),
                    geometry_max_to_max=geometry(LINKER_MAX_APP_BYTES,LINKER_MAX_APP_BYTES),
                    ephemeral_private_keys_never_written=True,permission_to_flash=False,
                    device_contacts=0,serial_io=0,flash_writes=0,rtc_writes=0,reboots=0,device_filesystem_writes=0)


if __name__ == "__main__":
    print(json.dumps(run(),indent=2))
