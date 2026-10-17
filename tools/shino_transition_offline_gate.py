"""SHINO M9 full-transition reproducible, DEVICE-DISCONNECTED local review.

Only disposable public-fixture builds, real host shims, and source/ELF audit.
Never opens COM, probes a SmallTV, flashes, changes RTC/FS or enables OTA.
A local PASS is NOT permission to flash an observation image.
"""
import json
import shutil
import subprocess
import sys
import tempfile
import traceback
from pathlib import Path

from m9_stagea_build import ROOT, ENV
from shino_maintenance_build import prepare as maintenance_build
from shino_transition_build import prepare as transition_build
from shino_transition_resources import run as resource_audit

OUTDIR = ROOT / "research-local"
RESULT = OUTDIR / "m9-transition-review.json"
LOG = OUTDIR / "m9-transition-review.log"


def execute(label, command):
    print("[SHINO M9 OFFLINE]", label, flush=True)
    with LOG.open("a", encoding="utf-8") as stream:
        stream.write("\n## " + label + "\n")
        stream.flush()
        proc = subprocess.run(command, cwd=ROOT, stdin=subprocess.DEVNULL,
                              stdout=stream, stderr=subprocess.STDOUT,
                              timeout=1200, check=False)
    if proc.returncode:
        raise RuntimeError(label + " failed (exit " + str(proc.returncode) + ")")
    

def main():
    OUTDIR.mkdir(exist_ok=True)
    LOG.write_text("M9 public, disposable, device-disconnected review\n", encoding="utf-8")
    if RESULT.exists():
        RESULT.unlink()
    pio = shutil.which("pio") or shutil.which("platformio")
    if not pio:
        raise RuntimeError("PlatformIO 6.1.18 is required in PATH (no hardware needed).")
    version = subprocess.check_output(["git", "rev-parse", "HEAD"], cwd=ROOT,
                                      text=True).strip()
    dirty = subprocess.check_output(["git", "status", "--porcelain"], cwd=ROOT,
                                    text=True).strip()
    if dirty:
        raise RuntimeError("Working tree has changes; refuse an ambiguous qualification.")
    with tempfile.TemporaryDirectory(prefix="m9-disposable-", dir=OUTDIR) as temp:
        root = Path(temp)
        baseline, candidate = root / "baseline", root / "candidate"
        maintenance_build(baseline, small_buffer=True)
        transition_build(candidate)
        for label, location in (("matched native baseline", baseline),
                                ("public dry-run + dormant OTA transition", candidate)):
            execute(label, [pio, "run", "-d", str(location), "-e", ENV])
        execute("Windows authentication and CAP identity regression",
                [sys.executable, str(ROOT / "companion/test_shino_maintenance_control.py")])
        execute("real Native/Core RAM-only probe + public INSTALL refusal",
                [sys.executable, str(ROOT / "tools/shino_probe_offline.py")])
        audit = resource_audit(baseline, candidate)
    assert audit["verdict"] == "NO_GO_FOR_PHYSICAL_INSTALL"
    assert not audit["qualified_live"] and not audit["physical_flash_authorized"]
    assert not audit["public_install_enabled"]
    assert audit["buffer_bytes"] == 256
    assert audit["delta"]["noinit"] == 0
    assert audit["physical_memory_high_water"] == "NOT_MEASURED"
    for k in ("device_contacts", "serial_io", "flash_writes", "rtc_writes",
              "device_filesystem_writes", "reboots"):
        assert audit[k] == 0, k
    report = dict(status="PASS_OFFLINE_PHYSICAL_NO_GO", git_head=version,
                  resource_audit=audit, tests="PASS",
                  private_device_access=False, uart_install_permitted=False,
                  network_ota_install_permitted=False,
                  ci_exact_head="CHECK_GITHUB_SEPARATELY")
    RESULT.write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({"status": report["status"], "git_head": version,
                      "delta": audit["delta"], "physical": "NOT_RUN",
                      "result": str(RESULT), "log": str(LOG)}, indent=2))
    return 0


if __name__ == "__main__":
    try:
        sys.exit(main())
    except Exception as exc:
        OUTDIR.mkdir(exist_ok=True)
        with LOG.open("a", encoding="utf-8") as log:
            log.write("\nFAIL: " + repr(exc) + "\n")
            log.write(traceback.format_exc())
        RESULT.write_text(json.dumps(
            {"status": "NO_GO_OFFLINE_INCOMPLETE", "error": str(exc),
             "physical_flash_authorized": False, "device_contacts": 0},
            indent=2) + "\n", encoding="utf-8")
        print("SHINO qualification stopped: " + str(exc), file=sys.stderr)
        print("Logs: " + str(LOG), file=sys.stderr)
        sys.exit(2)
