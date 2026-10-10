"""Execute the receiver reader and real pinned Core flashRead contract, RAM only."""
import hashlib
import json
import subprocess
import tempfile
from pathlib import Path
from shino_wifi_runner import ROOT, build
from v07_pinned_core_probe import core_root


def prepare_host(host):
    core=core_root()
    raw=(core/"cores/esp8266/Esp.cpp").read_bytes().replace(b"\r\n",b"\n")
    pins=json.loads((ROOT/"tools/m9_resource_core_sources.json").read_text())
    if hashlib.sha256(raw).hexdigest()!=pins["cores/esp8266/Esp.cpp"]:
        raise ValueError("Wrong Core Esp.cpp")
    text=raw.decode()
    start=text.index("bool EspClass::flashRead(uint32_t address, uint32_t *data, size_t size) {")
    body=text[start:text.index("\n}\n",start)+3]
    (host/"pinned_flash_read.inc").write_text(body.replace("EspClass::","ReferenceESP::"),encoding="utf-8")


def run():
    with tempfile.TemporaryDirectory(prefix="shino-flash-contract-") as td:
        directory=Path(td)
        exe,env=build(directory,ROOT/"tools/shino_http_ota_flash_lab.cpp",prepare_host)
        p=subprocess.run([str(exe)],env=env,cwd=directory,capture_output=True,text=True,timeout=30)
        if p.returncode:raise RuntimeError(p.stdout+p.stderr)
        result=json.loads(p.stdout)
        assert result["valid_byte_reads"]==320 and result["legacy_footer_rejected"]
        assert result["actual_core_typed_read"] and result["staging_bounds"]
        return result


if __name__=="__main__":print(json.dumps(run(),indent=2))
