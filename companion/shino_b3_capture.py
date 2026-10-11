"""B3 owner-only 4m2m resource transcript capture. Read-only, offline by default.

All live operations are bounded authenticated GETs to the pinned SHINO private
AP. No POST, OTA, flash, reset, telemetry injection, network discovery, retries,
or background process. Private JSON output is restricted to ignored research-local.
"""
import argparse
import json
import os
from pathlib import Path
import sys
import time

from shino_digest_coord import CoordinatedReader
from shino_qualify import read_json, QualificationFailure
from shino_update import DEFAULT_IDENTITY, Transport, inspect, load_identity

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "tools"))
from shino_b3_resource_evidence import review, EvidenceHold

IDENTITY = "/api/v1/update/status"
NORMAL = "/api/v1/m9/normal/status"
GETS_PER_CYCLE = 3
CYCLES = 11
INTERVAL_SECONDS = 20
RETAIN_IDENTITY = ("protocol", "device", "build_id", "sha256", "bytes",
                   "boot_id", "ota_enabled", "fs_ok")
RETAIN_STATUS = (
    "config_loaded_readonly", "private_ap_ready", "mounted",
    "inventory_exact", "config_seed_exact", "resource_measurements_valid",
    "design_floors_observed", "heap_floor", "block_floor",
    "fragmentation_ceiling", "continuation_floor",
    "rejected_sample_count", "resource_sample_count",
    "runtime_cont_stack_min", "lowest_heap", "lowest_block",
    "highest_fragmentation_percent", "setup_cont_stack_start",
    "setup_cont_stack_min", "fs_config_cont_stack_start",
    "fs_config_cont_stack_min", "runtime_cont_stack_start",
)


class CaptureHold(ValueError):
    pass


def _subset(source, keys):
    if type(source) is not dict or any(key not in source for key in keys):
        raise CaptureHold("MISSING_REQUIRED_STATUS_FIELDS")
    return {key: source[key] for key in keys}


def _identity_matches(first, second, release):
    keys = ("protocol", "device", "build_id", "sha256", "bytes", "boot_id")
    if any(first.get(key) != second.get(key) for key in keys):
        raise CaptureHold("IDENTITY_CHANGED_WITHIN_CHECKPOINT")
    for key in ("device", "build_id", "sha256", "bytes", "protocol"):
        if first.get(key) != release.get(key):
            raise CaptureHold("RELEASE_OR_PROTOCOL_MISMATCH")
    if any(status.get("ota_enabled") is not True or status.get("fs_ok") is not True
           for status in (first, second)):
        raise CaptureHold("EXPECTED_PRIVATE_NORMAL_NOT_RUNNING")
    if first.get("boot_id") != second.get("boot_id"):
        raise CaptureHold("UNEXPECTED_REBOOT")


def collect(io, release, *, reader=read_json, sleep=time.sleep,
            cycles=CYCLES, interval=INTERVAL_SECONDS):
    if type(cycles) is not int or not 3 <= cycles <= 12:
        raise CaptureHold("INVALID_CYCLE_COUNT")
    if type(interval) is not int or not 1 <= interval <= 30:
        raise CaptureHold("INVALID_READ_INTERVAL")
    if (cycles - 1) * interval < 180:
        raise CaptureHold("CAPTURE_WINDOW_BELOW_180_SECONDS")
    observations = []
    for cycle in range(1, cycles + 1):
        before = reader(io, IDENTITY, cycle)
        # Stop immediately on a changed boot/build; never combine two
        # different firmware lifetimes in a single resource transcript.
        if observations:
            _identity_matches(observations[-1]["identity"], before, release)
        normal = reader(io, NORMAL, cycle)
        after = reader(io, IDENTITY, cycle)
        _identity_matches(before, after, release)
        if normal.get("mode") != "M9_NORMAL_STAGE_A":
            raise CaptureHold("INVALID_NORMAL_PROFILE")
        checkpoint = dict(identity=_subset(before, RETAIN_IDENTITY),
                          status=_subset(normal, RETAIN_STATUS))
        observations.append(checkpoint)
        if cycle < cycles:
            sleep(interval)
    return dict(schema=1, source="OWNER_CAPTURED_READONLY_STATUS",
                expected_manifest={key: release[key] for key in
                                   ("layout", "protocol", "device",
                                    "build_id", "sha256", "bytes")},
                observations=observations)


def private_output(path):
    path = Path(path)
    base = (ROOT / "research-local").resolve()
    # Never write a capture into tracked source, arbitrary directories or
    # through a symlink to a tracked file.
    resolved_parent = path.parent.resolve()
    if base != resolved_parent and base not in resolved_parent.parents:
        raise CaptureHold("OUTPUT_MUST_BE_IN_IGNORED_RESEARCH_LOCAL")
    if path.suffix.lower() != ".json" or path.is_symlink() or path.exists():
        raise CaptureHold("OUTPUT_MUST_BE_NEW_PRIVATE_JSON")
    return path


def save_private(path, report):
    path = private_output(path)
    # The directory must already exist; no implicit directory creation.
    data = (json.dumps(report, separators=(",", ":"), allow_nan=False) + "\n").encode("utf-8")
    if len(data) > 32768:
        raise CaptureHold("CAPTURE_EXCEEDS_LOCAL_REPORT_CAP")
    flags = os.O_WRONLY | os.O_CREAT | os.O_EXCL
    if hasattr(os, "O_BINARY"):
        flags |= os.O_BINARY
    fd = os.open(path, flags, 0o600)
    with os.fdopen(fd, "wb") as stream:
        stream.write(data)
    return path


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--authorize-read", action="store_true")
    parser.add_argument("--bin", type=Path)
    parser.add_argument("--manifest", type=Path)
    parser.add_argument("--identity", type=Path, default=DEFAULT_IDENTITY)
    parser.add_argument("--output", type=Path)
    args = parser.parse_args(argv)

    if not args.authorize_read:
        print(json.dumps(dict(status="PRINT_ONLY_NO_DEVICE_CONTACT",
                              total_gets_if_authorized=GETS_PER_CYCLE*CYCLES,
                              intended_window_seconds=(CYCLES-1)*INTERVAL_SECONDS,
                              device_contacts=0, ota_authorized=False)))
        return 0

    if args.bin is None or args.manifest is None or args.output is None:
        print('{"status":"CAPTURE_HOLD","reason":"LOCAL_INPUT_REQUIRED",'
              '"ota_authorized":false}')
        return 2
    try:
        target = private_output(args.output)
        release, _raw = inspect(args.bin, args.manifest)  # local checksum only
        del _raw
        credentials = load_identity(args.identity)
        if credentials["device"] != release["device"]:
            raise CaptureHold("OWNER_IDENTITY_MISMATCH")
        io = Transport(credentials)  # fixed private AP 192.168.4.1
        io.reader = CoordinatedReader(io.reader, io.host)
        transcript = collect(io, release)
        save_private(target, transcript)
        try:
            result = review(transcript)
            code = 0
        except EvidenceHold:
            result = dict(status="RESOURCE_HOLD", ota_authorized=False,
                          physical_qualification="HOLD")
            code = 2
        # No device, build, boot, nonce, URL, password or private path on stdout.
        print(json.dumps({key: result[key] for key in
                          ("status", "physical_qualification", "ota_authorized")
                          if key in result}))
        return code
    except (CaptureHold, QualificationFailure, ValueError, OSError,
            KeyError, TypeError):
        print('{"status":"CAPTURE_HOLD","reason":"CAPTURE_OR_LOCAL_IO_REJECTED",'
              '"ota_authorized":false}')
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
