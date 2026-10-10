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
import json
from urllib.parse import quote
from urllib.request import Request, urlopen

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
        "tools/shino_wifi_*", "tools/shino_maintenance_*",
        "tools/shino_small_buffer_*", "tools/shino_transition_*",
        "tools/shino_owner_*", "tools/shino_arm_*",
        "tools/shino_memory_*", "tools/shino_probe_*",
        "tools/shino_m9_*", "tools/shino_xtensa_*",
        "tools/test_shino_wifi_*", "tools/test_shino_maintenance_*",
        "tools/test_shino_owner_*", "tools/test_shino_m9_*",
        "tools/test_shino_transition_*", "tools/test_shino_xtensa_*",
        "tools/test_shino_small_buffer_*", "tools/test_shino_probe_*",
        "tools/m9_*",
        "companion/shino_install.py", "companion/test_shino_install.py",
        "companion/shino_maintenance_control.py",
        "companion/test_shino_maintenance_control.py",
        "tools/ci_scope.py", "tools/test_ci_scope.py",
    ),
}



SCOPE.update({
    "ci-core": (
        "**"
    ),
    "ci-legacy": (),
    "ci-home": (
        "experiments/home_lan/**",
        "tools/home_lan*",
        "companion/provision_home_wifi.py",
        "companion/test_provision_home_wifi.py",
        "companion/shino_link.py",
        "companion/test_shino_link.py"
    ),
    "ci-artwork": (
        "experiments/artwork_pilot/**",
        "tools/artwork_pilot*",
        "simulator/**"
    ),
    "ci-v07": (
        "experiments/v07*/**",
        "tools/v07*"
    ),
    "ci-crypto": (
        "tools/test_v08_crypto_lab.js",
        "experiments/v08_protocol/**"
    ),
    "ci-preparse": (
        "experiments/v08_preparse/**",
        "tools/v08_source_executed_preparse.py",
        "tools/v08_native_size_report.py"
    ),
    "ci-bridge": (
        "experiments/v08_full_bridge/**",
        "experiments/v08_m6a/**",
        "tools/v08_m3*",
        "tools/v08_m5*",
        "tools/v08_m6a*"
    ),
    "ci-windows": (
        "companion/**",
        "tools/shino_link*",
        "tools/test_media*"
    )
})

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


def duplicate_open_pr_push(event):
    """Skip duplicate push validation only after a positive GitHub PR lookup.

    Fail open on missing permissions, network errors or unexpected API data.
    """
    if event != "push":
        return False
    repo = os.getenv("GITHUB_REPOSITORY", "")
    branch = os.getenv("GITHUB_REF_NAME", "")
    token = os.getenv("GITHUB_TOKEN", "")
    if repo.count("/") != 1 or not branch or not token or branch == "main":
        return False
    owner = repo.split("/", 1)[0]
    url = ("https://api.github.com/repos/" + quote(repo, safe="/")
           + "/pulls?state=open&head=" + quote(owner + ":" + branch, safe="")
           + "&per_page=100")
    try:
        req = Request(url, headers={
            "Authorization": "Bearer " + token,
            "Accept": "application/vnd.github+json",
            "X-GitHub-Api-Version": "2022-11-28",
            "User-Agent": "SHINO-CI-readonly-scope"})
        with urlopen(req, timeout=8) as response:
            result = json.load(response)
        return isinstance(result, list) and any(
            item.get("state") == "open"
            and item.get("head", {}).get("ref") == branch
            and item.get("head", {}).get("repo", {}).get("full_name") == repo
            for item in result if isinstance(item, dict))
    except (OSError, ValueError, TypeError, KeyError):
        return False


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--group", choices=sorted(SCOPE), required=True)
    parser.add_argument("--skip-duplicate-check", action="store_true")
    args = parser.parse_args()
    event = os.getenv("GITHUB_EVENT_NAME", "")
    changed = changed_files(event, os.getenv("BASE_SHA"), os.getenv("HEAD_SHA"))
    relevant = args.group == "ci-core" or changed is None or in_scope(args.group, changed)
    duplicate = not args.skip_duplicate_check and duplicate_open_pr_push(event)
    relevant = relevant and not duplicate
    value = "true" if relevant else "false"
    print(f"SHINO CI scope: {args.group}, event={event}, files="
          f"{'UNKNOWN/RUN' if changed is None else len(changed)}, "
          f"duplicate_push={duplicate}, relevant={value}")
    output = os.getenv("GITHUB_OUTPUT")
    if output:
        with open(output, "a", encoding="utf-8") as stream:
            stream.write(f"relevant={value}\n")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
