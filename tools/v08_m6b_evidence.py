"""No-skip host validation and content/head provenance for Mission 6B."""
import hashlib
import json
import os
from pathlib import Path
import subprocess
import sys

from test_v08_m6b_wire import differential

ROOT = Path(__file__).resolve().parents[1]
BASE = "799e69a17730c117e1c599912b0b57919d64cea2"


def run(*args):
    return subprocess.run(args, cwd=ROOT, check=True, capture_output=True, text=True, timeout=60).stdout


def evidence():
    tests = ["tools/test_v08_crypto_lab.js", "tools/test_v08_m3_profile.js",
             "tools/test_v08_m5_known_failures.js", "tools/test_v08_m6b_security.js"]
    node_output = run(os.environ.get("SHINO_NODE", "node"), "--test", "--test-reporter=tap", *tests)
    if "# fail 0" not in node_output or "# skipped 0" not in node_output:
        raise AssertionError(node_output)
    inputs = [*tests, "tools/v08_crypto_vectors.json", "tools/v08_crypto_lab.js",
              "tools/v08_m3_profile.js", "companion/media_wire_v2_host.py",
              "tools/v08_m6b_authority.js", "tools/v08_m6b_security.js", "tools/v08_m6b_profile.js",
              "tools/v08_m6b_wire_probe.js", "tools/test_v08_m6b_wire.py", "tools/v08_m6b_evidence.py",
              ".github/workflows/ci.yml"]
    modified = run("git", "diff", "--name-only", BASE, "--").splitlines()
    allowed = {".github/workflows/ci.yml", "tools/v08_m6b_authority.js", "tools/v08_m6b_security.js",
               "tools/v08_m6b_profile.js", "tools/v08_m6b_wire_probe.js", "tools/v08_m6b_evidence.py",
               "tools/test_v08_m6b_security.js", "tools/test_v08_m6b_wire.py",
               "docs/V08_MISSION_6B_SECURITY_REMEDIATION_REPORT.md",
               "docs/V08_MISSION_6B_FINDINGS_MATRIX.md", "docs/V08_MISSION_6B_GATE.md"}
    if set(modified) - allowed:
        raise AssertionError(modified)
    retained = ["tools/v08_crypto_vectors.json", "tools/v08_crypto_lab.js", "tools/v08_m3_profile.js",
                "tools/test_v08_m5_known_failures.js", "companion/media_wire_v2_host.py",
                "docs/V08_MISSION_4_SECURITY_REVIEW.md", "docs/V08_MISSION_5_FINDINGS_MATRIX.md",
                "docs/V08_MISSION_6A_REMEDIATION_REPORT.md"]
    for p in retained:
        original = subprocess.run(["git", "show", f"{BASE}:{p}"], cwd=ROOT, check=True, capture_output=True).stdout
        current = (ROOT / p).read_bytes()
        # Git working-tree EOL conversion is permitted, content changes are not.
        if original.replace(b"\r\n", b"\n") != current.replace(b"\r\n", b"\n"):
            raise AssertionError(f"historical input changed: {p}")
    return {"base": BASE, "head": run("git", "rev-parse", "HEAD").strip(),
            "working_tree_clean": not run("git", "status", "--porcelain").strip(),
            "node": run(os.environ.get("SHINO_NODE", "node"), "--version").strip(),
            "python": sys.version, "node_tap": node_output, "wire_differential": differential(),
            "input_sha256": {p: hashlib.sha256((ROOT / p).read_bytes()).hexdigest() for p in inputs},
            "historical_preservation": True, "evidence_class": "HOST ONLY; no native runtime or entropy proof"}


if __name__ == "__main__":
    print(json.dumps(evidence(), indent=2, ensure_ascii=True))
