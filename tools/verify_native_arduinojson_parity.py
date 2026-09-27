"""Execute REAL pinned ArduinoJson + unchanged FslessMetrics.cpp on HOST.

Requires PlatformIO's already-installed exact ArduinoJson 7.4.3 include tree.
No real device, native server, serial port, Flash, Wi-Fi, Digest, OLED/LCD
or OTA write. Independently runs the Python host oracle on identical bytes.
A mismatch is a failed research gate, not permission to patch owner hardware.
"""
import json
from pathlib import Path
import subprocess
import sys
import tempfile

ROOT=Path(__file__).resolve().parent.parent
sys.path.insert(0,str(ROOT/"tools"))
from native_ota_host_json_oracle import HostTelemetryJsonOracle  # noqa: E402

ARDUINOJSON=ROOT/"firmware/.pio/libdeps/esp12e/ArduinoJson/src"
ACTUAL=ROOT/"firmware/src/boot/FslessMetrics.cpp"
STUB=ROOT/"tools/host_arduinojson_stubs"
PROBE=ROOT/"tools/native_ota_real_arduinojson_metrics_probe.cpp"
FIELDS=("cpu_usage","gpu_usage","memory_used_gb","memory_total_gb",
        "gpu_vram_mb","gpu_temp_c","gpu_power")
GOOD={
    "ok":True,"gpu_available":True,
    "cpu_usage":22.5,"gpu_usage":34.5,"memory_used_gb":8,
    "memory_total_gb":16,"gpu_vram_mb":2048,"gpu_temp_c":56,
    "gpu_power":120,
}


def compact(obj):
    return json.dumps(obj,separators=(",",":"),allow_nan=False).encode("utf-8")


def cases():
    # Every input is one JSON line, <=384 bytes unless checking source 413.
    # The general Python oracle and the real source run as a SINGLE sequence:
    # a rejected request must not overwrite a previously valid RAM snapshot.
    payloads=[
        compact(GOOD),
        compact(dict(reversed(list(GOOD.items())))),
        json.dumps(GOOD,indent=None,sort_keys=True).encode(),
        compact({**GOOD,"extra":"unused"}),
        compact({**GOOD,"cpu_usage":2.25e1,"gpu_vram_mb":2.048e3}),
        compact({k:v for k,v in GOOD.items() if k!="memory_total_gb"}),
        compact({**GOOD,"memory_total_gb":None}),
        compact({**GOOD,"gpu_available":False}),
        compact({**GOOD,"cpu_usage":0,"gpu_usage":100,"memory_used_gb":0,
                 "gpu_vram_mb":0,"gpu_temp_c":-40,"gpu_power":0}),
        compact({**GOOD,"cpu_usage":100,"memory_used_gb":256,
                 "memory_total_gb":256,"gpu_vram_mb":65536,
                 "gpu_temp_c":130,"gpu_power":1200}),
    ]
    for delta in (
        {"ok":False},{"ok":"true"},{"gpu_available":"false"},
        {"gpu_available":1},{"cpu_usage":True},{"gpu_usage":"34.5"},
        {"cpu_usage":-0.01},{"cpu_usage":101},{"gpu_usage":-1},
        {"memory_used_gb":257},{"gpu_vram_mb":65537},
        {"gpu_temp_c":-41},{"gpu_temp_c":131},{"gpu_power":1201},
        {"memory_total_gb":0},{"memory_total_gb":7},
        {"memory_total_gb":"16"},{"memory_total_gb":True},
        {"cpu_usage":1e100},{"ok":None}
    ):
        payloads.append(compact({**GOOD,**delta}))
    for missing in ("ok","gpu_available","cpu_usage","gpu_usage",
                    "memory_used_gb","gpu_vram_mb","gpu_temp_c","gpu_power"):
        sample=dict(GOOD);sample.pop(missing)
        payloads.append(compact(sample))
    payloads += [
        b"not-valid-json-xxxx",
        b'{"ok":truue,"gpu_available":true}',
        b'{"ok":true,',
        b'{"ok":NaN,"gpu_available":true}',
        b'{"ok":Infinity,"gpu_available":true}',
        b'{"ok":-Infinity,"gpu_available":true}',
        b'{"ok":true,\xff,"gpu_available":true}',
        b'{"ok":true,"gpu_available":true,"cpu_usage":1e999}',
        b"X"*15,
        b"X"*385,
        b"X"*494404,
        b'{"ok":true}', # incomplete type envelope
        compact(GOOD), # verify former good sample survived invalid sequence
    ]
    return payloads


def verify():
    if not (ARDUINOJSON/"ArduinoJson.h").is_file():
        raise AssertionError("Missing ACTUAL PlatformIO ArduinoJson include tree; run pio build first.")
    version=(ARDUINOJSON/"ArduinoJson/version.hpp").read_text(encoding="utf-8")
    if '#define ARDUINOJSON_VERSION "7.4.3"' not in version:
        raise AssertionError("ArduinoJson not exact tested 7.4.3; do not silently upgrade.")
    if "bblanchon/ArduinoJson@7.4.3" not in (ROOT/"firmware/platformio.ini").read_text():
        raise AssertionError("Actual production dependency is not pinned exact.")
    source=ACTUAL.read_text(encoding="utf-8")
    for required in ('#include "boot/FslessMetrics.h"',
                     "state = next; // Invalid payload never replaces",
                     'bounded(input, "cpu_usage"',
                     'bounded(input, "gpu_power"'):
        if required not in source:raise AssertionError("Actual firmware source drift: "+required)
    with tempfile.TemporaryDirectory(prefix="shino-real-arduinojson-host-") as folder:
        executable=Path(folder)/"real-arduinojson-unmodified-metrics"
        build=subprocess.run([
            "g++","-std=c++17","-O1","-Wall","-Wextra","-Werror","-pedantic",
            "-I",str(STUB),"-I",str(ROOT/"firmware/include"),"-I",str(ARDUINOJSON),
            str(PROBE),str(ACTUAL),"-o",str(executable)],
            capture_output=True,text=True,check=False,timeout=45)
        if build.returncode:
            raise AssertionError("REAL original C++ + ArduinoJson host compile FAILED:\n"+build.stderr)
        payloads=cases()
        actual=subprocess.run([str(executable)],
            input=b"\n".join(payloads)+b"\n",capture_output=True,
            timeout=30,check=False)
        if actual.returncode:
            raise AssertionError("REAL ArduinoJson host run failed "+str(actual.returncode)+
                                 " "+actual.stderr.decode(errors="replace")[:1600])
        lines=actual.stdout.splitlines()
        if len(lines)!=len(payloads):
            raise AssertionError(f"Actual source returned {len(lines)} rows for {len(payloads)} inputs")
        oracle=HostTelemetryJsonOracle()
        for index,(raw,line) in enumerate(zip(payloads,lines)):
            expected=oracle.preview_authenticated_post(raw,100+index)
            observed=json.loads(line)
            if observed["status"]!=expected.status:
                raise AssertionError(
                    f"CASE {index}: REAL ArduinoJson status {observed['status']} != host oracle "
                    f"{expected.status}; INPUT {raw[:110]!r}")
            original=oracle.sample
            for name in FIELDS:
                # ArduinoJson's JSON float serializer may round output; this
                # comparison is for field meaning and recorded state.
                if abs(observed[name]-getattr(original,name))>0.0002:
                    raise AssertionError(
                        f"CASE {index} {name}: REAL {observed[name]} != oracle "
                        f"{getattr(original,name)}")
            for field in ("received","gpu_available","last_received_ms"):
                if observed[field]!=getattr(original,field):
                    raise AssertionError(
                        f"CASE {index} {field}: REAL {observed[field]} != oracle "
                        f"{getattr(original,field)}")
            if observed["real_hardware_write"] is not False:
                raise AssertionError("Host test claimed real hardware mutation")
        print(f"PASS: {len(payloads)} sequential REAL ArduinoJson 7.4.3 + "
              "UNMODIFIED FslessMetrics.cpp cases matched independent host oracle.")
        print("PASS: identical status, previous-good RAM retention, optional total and all 7 fields.")
        print("HOST ONLY: fake millis/String, no network, no owner credentials, NO DEVICE/FLASH.")


if __name__=="__main__":
    verify()
