"""SHINO B2 HTTP stability observation. Independent from OTA and qualification.

Default PRINT_ONLY; explicit --authorize-read performs at most 3 * 3 bounded
authenticated GETs on the private AP. No retry, POST, flash, reset, or file
receipt. Never use this to override a failed qualification receipt.
"""
import argparse
import json
import sys
import time
from pathlib import Path

from shino_qualify import QualificationFailure, read_json
from shino_update import (
    DEFAULT_IDENTITY, Transport, UpdateError, check_status, inspect, load_identity
)

PATHS = (
    "/api/v1/update/status",
    "/api/v1/m9/normal/status",
    "/api/v1/m9/maintenance/result",
)


def stopped(code, cycle, operation, completed, max_latency_ms=0):
    return {
        "status": "READONLY_HTTP_OBSERVATION_STOP",
        "reason": code,
        "cycle": cycle,
        "operation": operation,
        "successful_gets": completed,
        "max_latency_ms": max_latency_ms,
        "flash_writes": 0,
        "device_reboots": 0,
        "ota_posts": 0,
        "physical_acceptance": False,
        "automatic_retries": 0,
    }


def observe(io, identity, release, *, cycles=2, reader=read_json,
            sleep=time.sleep, clock=time.monotonic):
    if type(cycles) is not int or not 1 <= cycles <= 3:
        raise ValueError("Only one to three cycles are permitted")
    successful = 0
    max_latency_ms = 0
    previous_boot = None
    metrics_fresh = None
    minimum = {"heap": 2**32 - 1, "block": 2**32 - 1, "stack": 2**32 - 1}
    frag_max = 0

    for cycle in range(1, cycles + 1):
        for path in PATHS:
            started = clock()
            try:
                status = reader(io, path, cycle)
            except QualificationFailure as error:
                return stopped(error.diagnostic["code"], cycle, "GET " + path,
                               successful, max_latency_ms)
            except (TimeoutError, OSError, ValueError):
                return stopped("UNEXPECTED_READ_FAILURE", cycle, "GET " + path,
                               successful, max_latency_ms)
            duration_ms = max(0, int((clock() - started) * 1000))
            max_latency_ms = max(max_latency_ms, duration_ms)
            successful += 1

            if path == "/api/v1/m9/normal/status":
                if status.get("mode") != "M9_NORMAL_STAGE_A":
                    return stopped("NORMAL_STATUS_INVALID", cycle, "GET " + path,
                                   successful, max_latency_ms)
                continue

            try:
                check_status(status, identity)
            except (UpdateError, ValueError, KeyError, TypeError):
                return stopped("STATUS_OR_RESOURCE_FLOOR_INVALID", cycle,
                               "GET " + path, successful, max_latency_ms)
            if any(status[field] != release[field] for field in ("sha256", "build_id", "bytes")):
                return stopped("RELEASE_IDENTITY_MISMATCH", cycle,
                               "GET " + path, successful, max_latency_ms)
            if previous_boot is not None and status["boot_id"] != previous_boot:
                return stopped("UNEXPECTED_REBOOT", cycle, "GET " + path,
                               successful, max_latency_ms)
            previous_boot = status["boot_id"]
            metrics_fresh = status.get("metrics_fresh") is True
            for key in minimum:
                minimum[key] = min(minimum[key], status[key])
            frag_max = max(frag_max, status["frag"])
        if cycle < cycles:
            sleep(2)

    return {
        "status": "READONLY_HTTP_OBSERVATION_PASS_NOT_QUALIFICATION",
        "cycles": cycles,
        "successful_gets": successful,
        "max_latency_ms": max_latency_ms,
        "minima": minimum,
        "frag_max": frag_max,
        "metrics_fresh_at_last_read": metrics_fresh,
        "boot_stable": True,
        "release_match": True,
        "flash_writes": 0,
        "device_reboots": 0,
        "ota_posts": 0,
        "physical_acceptance": False,
        "automatic_retries": 0,
    }


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--bin", type=Path, required=True)
    parser.add_argument("--manifest", type=Path, required=True)
    parser.add_argument("--identity", type=Path, default=DEFAULT_IDENTITY)
    parser.add_argument("--cycles", type=int, default=2)
    parser.add_argument("--authorize-read", action="store_true")
    args = parser.parse_args(argv)

    if not 1 <= args.cycles <= 3:
        parser.error("--cycles must be between 1 and 3")
    try:
        release, _ = inspect(args.bin, args.manifest)
        if not args.authorize_read:
            result = {
                "status": "PRINT_ONLY_NO_DEVICE_CONTACT",
                "cycles_if_authorized": args.cycles,
                "max_logical_gets": 3 * args.cycles,
                "flash_writes": 0,
                "ota_posts": 0,
            }
        else:
            identity = load_identity(args.identity)
            if identity["device"] != release["device"]:
                raise UpdateError("Private device mismatch")
            io = Transport(identity)
            result = observe(io, identity, release, cycles=args.cycles)
    except (UpdateError, ValueError, OSError, KeyError, TypeError):
        result = stopped("LOCAL_INPUT_OR_DEVICE_IDENTITY_INVALID", 0, "LOCAL", 0)

    print(json.dumps(result, separators=(",", ":")))
    return 0 if result["status"] in (
        "PRINT_ONLY_NO_DEVICE_CONTACT",
        "READONLY_HTTP_OBSERVATION_PASS_NOT_QUALIFICATION",
    ) else 2


if __name__ == "__main__":
    raise SystemExit(main())
