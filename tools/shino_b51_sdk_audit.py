"""Pin and inspect the actual Core3.1.2 default SDK22x binary, offline."""
import hashlib
import json
import re
import subprocess
from v07_pinned_core_probe import core_root

SDK_SHA="c568a76e32b044c86dfb50ae9cae10b0ceb4aeef66e2dcd435c794525773f2b3"


def run():
    core=core_root();library=core/"tools/sdk/lib/NONOSDK22x_190703/libmain.a"
    if hashlib.sha256(library.read_bytes()).hexdigest()!=SDK_SHA:
        raise ValueError("SDK22x pinned binary drift")
    suffix=".exe" if __import__("os").name=="nt" else ""
    tool=core.parent/"toolchain-xtensa/bin"/("xtensa-lx106-elf-objdump"+suffix)
    raw=subprocess.check_output([str(tool),"-dr","--start-address=0x2284","--stop-address=0x2354",str(library)],text=True)
    match=re.search(r"(?m)^\s*2284:\s+e0c112.*?(?=^\s*2351:)",raw,re.S|re.M)
    if not match:raise ValueError("SDK getter machine-code anchor drift")
    getter=match[0]
    if "pvPortMalloc" not in getter or "0x49c" not in getter or "wifi_get_opmode" in getter:
        raise ValueError("SDK getter allocation/mode evidence drift")
    stores=re.findall(r"\bs(?:8|16|32)i(?:\.n)?\s+a\d+,\s*a13,\s*(\d+)",getter)
    if stores!=["96"]:raise ValueError("SDK getter output stores changed")
    for marker in ("20cd22", "61cd22", "ets_memcpy", "vPortFree"):
        if marker not in getter:raise ValueError("SDK credential-copy evidence drift")
    generic=(core/"libraries/ESP8266WiFi/src/ESP8266WiFiGeneric.cpp").read_text()
    sta=(core/"libraries/ESP8266WiFi/src/ESP8266WiFiSTA.cpp").read_text()
    if "_persistent = persistent;" not in generic or "wifi_station_set_config_current(&conf)" not in sta:
        raise ValueError("Arduino persistence adapter changed")
    return dict(core="3.1.2",sdk="NONOSDK22x_190703",sdk_libmain_sha256=SDK_SHA,
                getter_output="SSID[32], password[64], BSSID flag/address only",
                getter_threshold_populated=False,getter_requires_sta=False,
                sdk_temporary_payload_bytes=0x49c,direct_sdk_persistent_call_not_disabled_by_arduino_flag=True,
                evidence="pinned SDK Xtensa disassembly + Arduino adapter source",physical="NOT_RUN",device_contacts=0)


if __name__=="__main__":print(json.dumps(run(),indent=2))
