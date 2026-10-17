"""Compile/link only. No upload/buildfs/signing tasks or test-key embedding."""
Import("env")
from pathlib import Path
import hashlib,json
if any(t in ("upload","uploadfs","buildfs","erase","monitor") for t in COMMAND_LINE_TARGETS):
    raise RuntimeError("OFFLINE_ONLY_NO_DEVICE_TASK")
core = Path(env.PioPlatform().get_package_dir("framework-arduinoespressif8266"))
assert "#define ARDUINO_SIGNING 0" in (core/"cores/esp8266/Updater_Signing.h").read_text()
assert not (Path(env["PROJECT_DIR"])/"private.key").exists()
pins=Path(env["PROJECT_DIR"]).parents[1]/"tools/m9_signed_core_sources.json"
for name,digest in json.loads(pins.read_text()).items():
    assert hashlib.sha256((core/name).read_bytes().replace(b"\r\n",b"\n")).hexdigest()==digest,name
env.Append(CPPPATH=[str(Path(env["PROJECT_DIR"]).parents[1]/"firmware/include")])
