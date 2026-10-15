"""One-command B5.3 LEAN OWNER-PRIVATE offline build (never installs).

No device/network IO except optional public PlatformIO dependency bootstrap.
Existing owner credentials are borrowed read-only from exactly one worktree.
All generated private content is confined to ignored research-local/m9-owner.
"""
import argparse
import hashlib
import json
import subprocess
import sys
from pathlib import Path
from uuid import uuid4

from m9_stagea_build import ENV, ROOT
from shino_b53_lean_build import build as build_lean
from shino_b52_clock_build import private_source_gate
from shino_b5_lan_build import build as build_public_b51
from shino_b52_owner_candidate import (
    available_libraries, pinned_libraries, owner_credentials,
)
import shino_owner_transition as owner_identity
from shino_owner_transition import OWNER

BRANCH="feature/shino-tv-b53-lean-qualification"


def preflight():
    """Fail closed before accessing a private credential or creating artifacts."""
    branch=subprocess.check_output(
        ["git","branch","--show-current"],cwd=ROOT,text=True).strip()
    if branch!=BRANCH:
        raise ValueError("HOLD: not on B5.3 lean qualification branch")
    head=private_source_gate()  # Includes full tracked/untracked clean check
    if not head or len(head)!=40:
        raise ValueError("HOLD: unknown source SHA")
    origin=subprocess.check_output(
        ["git","rev-parse","refs/remotes/origin/"+BRANCH],cwd=ROOT,text=True).strip()
    if head!=origin:
        raise ValueError("HOLD: checkout diverged from remote-tracking SHA")
    owner_credentials()  # Only unique, non-symlink, existing private identity
    return head


def run(*,libraries=None,bootstrap_libraries=False):
    head=preflight()
    if libraries is None:
        libs=next(available_libraries(),None)
    else:
        libs=Path(libraries).resolve()
    if libs is None or not pinned_libraries(libs):
        if not bootstrap_libraries or libraries is not None:
            raise ValueError("HOLD: pinned libraries absent or invalid")
        reference=ROOT/"research-local"/("b53-lean-public-deps-"+uuid4().hex[:12])
        build_public_b51(reference,private=False)
        libs=reference/".pio"/"libdeps"/ENV
        if not pinned_libraries(libs):
            raise ValueError("HOLD: pinned PlatformIO dependencies unavailable")
    if preflight()!=head:
        raise ValueError("HOLD: source HEAD changed during preflight")
    output=OWNER/("b53-lean-private-"+uuid4().hex[:12])
    if output.exists() or output.is_symlink():
        raise ValueError("HOLD: candidate output collision")
    old_secrets=owner_identity.SECRETS
    try:
        # No duplication, rotation or output of owner credentials.
        owner_identity.SECRETS=owner_credentials()
        report=build_lean(output,libs,private=True)
    finally:
        owner_identity.SECRETS=old_secrets
    raw=(output/".pio"/"build"/ENV/"firmware.bin").read_bytes()
    release=json.loads((output/"release.json").read_text(encoding="utf-8"))
    actual_size=len(raw)
    actual_sha=hashlib.sha256(raw).hexdigest()
    if actual_size!=release["bytes"] or actual_sha!=release["sha256"]:
        raise ValueError("HOLD: BIN and release.json differ")
    if (report["bytes"]!=actual_size or report["sha256"]!=actual_sha or
        report["source_commit"]!=head or report["source_dirty"] or
        report["layout"]!="4m2m" or release["layout"]!="4m2m" or
        not report["private"] or not report["private_build"] or
        not report["clock_authority"] or not report["lean_variant"] or
        report["weather_network_source"] or report["weather_configured"] or
        report["noinit"]!=56 or report["physical"]!="NOT_RUN" or
        report["ota_posts"]!=0 or report["device_contacts"]!=0):
        raise ValueError("HOLD: private B5.3 release or resource qualification mismatch")
    # Verify the PRIVATE generated graph, not a public/inert neighbor.
    source=output/"src"/"boot"/"M9NormalStageA.cpp"
    normal=source.read_text(encoding="utf-8")
    if ("B53Sntp::begin();" not in normal or
        "B52Clock::step(now)" not in normal or
        "B53WeatherHttps" in normal or
        (output/"src"/"boot"/"B53WeatherHttps.cpp").exists()):
        raise ValueError("HOLD: lean source graph mismatch")
    if preflight()!=head:
        raise ValueError("HOLD: source changed during private build")
    receipt={"verdict":"B53_LEAN_PRIVATE_OFFLINE_ONLY_PHYSICAL_HOLD",
             "source_commit":head,"bytes":actual_size,"sha256":actual_sha,
             "layout":"4m2m","static_ram":report["static_ram"],
             "noinit":report["noinit"],"weather_network_source":False,
             "physical":"NOT_RUN","ota_posts":0}
    path=output/"b53-lean-safe-receipt.json"
    with path.open("x",encoding="utf-8") as handle:
        json.dump(receipt,handle,indent=2)
        handle.write("\n")
    print(json.dumps(receipt,indent=2))
    print("OWNER-LOCAL OUTPUT: "+str(output.relative_to(ROOT)))
    return receipt


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--libraries",type=Path,
                        help="Existing pinned PlatformIO libdeps path")
    parser.add_argument("--bootstrap-libraries",action="store_true",
                        help="May download pinned dependencies for PUBLIC preparatory build")
    a=parser.parse_args()
    try:
        run(libraries=a.libraries,bootstrap_libraries=a.bootstrap_libraries)
    except (ValueError,OSError,RuntimeError,subprocess.CalledProcessError,KeyError):
        # No raw paths, IDs, tokens or build logs printed on private failures.
        print("B53 LEAN OWNER BUILD HOLD - preserve logs and private files.",file=sys.stderr)
        return 1
    return 0


if __name__=="__main__":
    raise SystemExit(main())
