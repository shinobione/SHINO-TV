"""One-command B5.2 private candidate build: LOCAL ONLY, NO DEVICE ACTION.

The only optional external request is PlatformIO's pinned package install when
--bootstrap-libraries is explicitly used. Never upload private outputs.
"""
import argparse
import hashlib
import json
import subprocess
import sys
from pathlib import Path
from uuid import uuid4

from m9_stagea_build import ENV, ROOT
from shino_b52_clock_build import build as build_b52, private_source_gate
from shino_b5_lan_build import build as build_public_b51
from shino_owner_transition import OWNER, SECRETS

BRANCH = "codex/b52-owner-build-prep"
PINNED = (("ArduinoJson", "7.4.3"),
          ("GFX Library for Arduino", "1.6.4"),
          ("AnimatedGIF", "2.2.0"))


def pinned_libraries(root):
    root = Path(root).resolve()
    for name, version in PINNED:
        props = root / name / "library.properties"
        if not props.is_file() or ("version=" + version) not in props.read_text(encoding="utf-8"):
            return False
    return True


def available_libraries():
    for root in (ROOT / "research-local", ROOT / "experiments", ROOT / "firmware"):
        if root.is_dir():
            for props in root.glob("**/.pio/libdeps/*/ArduinoJson/library.properties"):
                candidate = props.parent.parent
                if pinned_libraries(candidate):
                    yield candidate


def preflight():
    branch = subprocess.check_output(
        ["git", "branch", "--show-current"], cwd=ROOT, text=True).strip()
    if branch != BRANCH:
        raise ValueError("HOLD: wrong branch for B5.2 private candidate")
    head = private_source_gate()
    if not SECRETS.is_file():
        raise ValueError("HOLD: existing owner-local credentials missing; do not regenerate")
    return head


def run(bootstrap_libraries=False, libraries=None):
    head = preflight()  # Before any private read or new artifact.
    if libraries is not None:
        libs = Path(libraries).resolve()
        if not pinned_libraries(libs):
            raise ValueError("HOLD: supplied library directory is not pinned")
    else:
        libs = next(available_libraries(), None)
    if libs is None:
        if not bootstrap_libraries:
            raise ValueError("HOLD: no pinned local libraries; use --bootstrap-libraries")
        # Public inert B5.1 pre-build; PlatformIO may fetch pinned packages.
        reference = ROOT / "research-local" / ("b52-public-deps-" + uuid4().hex[:12])
        build_public_b51(reference, private=False)
        libs = reference / ".pio" / "libdeps" / ENV
        if not pinned_libraries(libs):
            raise ValueError("HOLD: public prerequisites did not install pinned library versions")
    if preflight() != head:
        raise ValueError("HOLD: source changed while preparing libraries")
    output = OWNER / ("b52-clock-candidate-" + uuid4().hex[:12])
    if output.exists():
        raise ValueError("HOLD: candidate directory collision")
    report = build_b52(output, libs, private=True)
    binary = output / ".pio" / "build" / ENV / "firmware.bin"
    manifest = json.loads((output / "release.json").read_text(encoding="utf-8"))
    data = binary.read_bytes()
    size, sha = len(data), hashlib.sha256(data).hexdigest()
    if size != manifest["bytes"] or sha != manifest["sha256"]:
        raise ValueError("HOLD: private firmware BIN/manifest mismatch")
    if (not report["private"] or not report["clock_authority"] or
            report["layout"] != "4m2m" or report["source_commit"] != head or
            report["source_dirty"] or report["physical"] != "NOT_RUN"):
        raise ValueError("HOLD: B5.2 private identity or source mismatch")
    receipt = {"verdict": "PRIVATE_B52_OFFLINE_ONLY_PHYSICAL_HOLD",
               "source_commit": head, "bytes": size, "sha256": sha,
               "layout": "4m2m", "static_ram": report["static_ram"],
               "noinit": report["noinit"], "physical": "NOT_RUN",
               "ota_posts": 0}
    receipt_path = output / "b52-safe-receipt.json"
    with receipt_path.open("x", encoding="utf-8") as stream:
        json.dump(receipt, stream, indent=2)
        stream.write("\n")
    print(json.dumps(receipt, indent=2))
    print("OWNER-LOCAL OUTPUT: " + str(output.relative_to(ROOT)))
    return receipt


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--libraries", type=Path, help="Existing pinned PlatformIO libdeps directory")
    parser.add_argument("--bootstrap-libraries", action="store_true",
                        help="Build inert B5.1 dependency graph if libraries are absent; package downloads possible")
    args = parser.parse_args()
    try:
        run(bootstrap_libraries=args.bootstrap_libraries, libraries=args.libraries)
    except (ValueError, OSError, subprocess.CalledProcessError, RuntimeError):
        # Never print raw exceptions or owner source paths in stdout/stderr.
        print("B52 OWNER BUILD HOLD — preserve candidate and local build logs.", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
