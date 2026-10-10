"""Scope only expensive optional CI jobs; leave their PR checks present.

The check remains completed (job-level skipped) instead of indefinitely
Pending (workflow-level paths filter). Unknown diffs fail OPEN, not CLOSED.
PRs compare the whole merge-base..head; pushes compare before..after.
Manual workflow_dispatch always performs the full job.
"""
import argparse
import fnmatch
import os
import re
import subprocess

SCOPE = {
    "signed": (
        ".github/workflows/m9-signed-ota.yml",
        "firmware/**", "recovery/**",
        "experiments/m9_signed_ota/**", "experiments/v08_*/**",
        "tools/m9_signed*", "tools/test_m9_signed*",
        "tools/m9_stagea*", "tools/m9_phase*",
        "tools/v07*", "tools/v08*", "tools/ci_scope.py",
        "tools/test_ci_scope.py",
    ),
    "stagea": (
        ".github/workflows/m9-stagea-ota.yml",
        "firmware/**", "recovery/**",
        "experiments/m9_signed_ota/**", "experiments/v08_*/**",
        "tools/m9_*", "tools/v07*", "tools/v08*",
        "tools/ci_scope.py", "tools/test_ci_scope.py",
    ),
    "http": (
        ".github/workflows/shino-http-ota.yml",
        "firmware/**", "ota/**", "recovery/**", "experiments/**",
        "companion/shino_update.py", "companion/test_shino_update.py",
        "companion/shino_link.py", "companion/test_shino_link.py",
        "companion/push_fsless_metrics.py",
        "companion/test_push_fsless_metrics.py",
        "tools/shino_http_ota*", "tools/test_shino_http_ota*",
        "tools/shino_wifi_*", "tools/shino_prepare_ota_pair*",
        "tools/test_shino_prepare_ota_pair*", "tools/m9_*",
        "tools/ci_scope.py", "tools/test_ci_scope.py",
    ),
    "wifi": (
        ".github/workflows/shino-wifi-install.yml",
        "firmware/**", "recovery/**", "experiments/shino_wifi_install/**",
        "tools/shino_*", "tools/test_shino_*", "tools/m9_*",
        "companion/shino_install.py", "companion/test_shino_install.py",
        "companion/shino_maintenance_control.py",
        "companion/test_shino_maintenance_control.py",
        "tools/ci_scope.py", "tools/test_ci_scope.py",
    ),
}


def in_scope(group, changed):
    return any(
        fnmatch.fnmatchcase(path, pattern)
        for path in changed for pattern in SCOPE[group]
    )


def changed_files(event, base, head):
    if event not in ("push", "pull_request"):
        return None  # Always run manual/unknown event types.
    if not all(re.fullmatch(r"[0-9a-fA-F]{40}", s or "") for s in (base, head)):
        return None
    spec = base + ("..." if event == "pull_request" else "..") + head
    try:
        result = subprocess.run(
            ["git", "diff", "--name-only", "-z", spec],
            check=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE, timeout=30,
        )
        return [name.decode("utf-8", "surrogateescape")
                for name in result.stdout.split(b"\0") if name]
    except (OSError, subprocess.CalledProcessError, subprocess.TimeoutExpired):
        return None  # Missing parent/base? Never silently skip the check.


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--group", choices=sorted(SCOPE), required=True)
    args = parser.parse_args()
    event = os.getenv("GITHUB_EVENT_NAME", "")
    changed = changed_files(event, os.getenv("BASE_SHA"), os.getenv("HEAD_SHA"))
    relevant = changed is None or in_scope(args.group, changed)
    value = "true" if relevant else "false"
    print(f"SHINO CI scope: {args.group}, event={event}, files="
          f"{'UNKNOWN/RUN' if changed is None else len(changed)}, relevant={value}")
    output = os.getenv("GITHUB_OUTPUT")
    if output:
        with open(output, "a", encoding="utf-8") as stream:
            stream.write(f"relevant={value}\n")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
