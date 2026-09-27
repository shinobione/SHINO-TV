"""One-shot READ-ONLY heap snapshot from the ALREADY INSTALLED FS-less V2 bridge.

Offline by default. Only --measure contacts http://192.168.4.1 via the
EXISTING GET /api/v1/bridge/status endpoint and a private matching-build
Digest credentials file. No POST, OTA routes, firmware/FS write, cookie,
telemetry injection, local report file, automatic loop or background task.

The existing review-002 status reports a single current free-heap integer.
A separately owner-approved opt-in candidate may also carry a bounded,
validated OBSERVED_HEAP_V1 summary on the SAME already-authenticated GET.
Both readings are observations, NOT proof of unobserved peak or concurrency.
"""
from __future__ import annotations

import argparse
import json
from pathlib import Path
from urllib.error import HTTPError, URLError
from urllib.request import (
    HTTPDigestAuthHandler, HTTPPasswordMgrWithDefaultRealm,
    ProxyHandler, Request, build_opener,
)

from push_fsless_metrics import NoRedirect, SenderError, read_credentials

PRIVATE_AP = "192.168.4.1"
STATUS_PATH = "/api/v1/bridge/status"
MAX_STATUS_BYTES = 4096
PHASES = ("idle", "browser_open", "pc_telemetry", "after_load")
HTTP_TIMEOUT_SECONDS = 4.0


class HeapReadError(ValueError):
    pass


def _unique_keys(pairs: list[tuple[str, object]]) -> dict:
    values = {}
    for key, value in pairs:
        if key in values:
            raise HeapReadError("Duplicate JSON key in status response")
        values[key] = value
    return values


def _validate_optional_observation(observation: object) -> dict[str, int | str]:
    """Strictly decode only the optional finite read-only candidate schema."""
    if not isinstance(observation, dict):
        raise HeapReadError("Invalid observed heap object")
    if (observation.get("schema") != "OBSERVED_HEAP_V1" or
        type(observation.get("sampling_interval_ms")) is not int or
        observation["sampling_interval_ms"] != 1000 or
        type(observation.get("max_samples")) is not int or
        observation["max_samples"] != 1024 or
        type(observation.get("sample_count")) is not int):
        raise HeapReadError("Unexpected observed heap schema or cadence")
    count = observation["sample_count"]
    state = observation.get("state")
    expected = "NO_SAMPLES" if count == 0 else (
        "SATURATED" if count == 1024 else "SAMPLING")
    if not 0 <= count <= 1024 or state != expected:
        raise HeapReadError("Unexpected observed heap sample count/state")
    fields = (
        "first_free_heap_bytes", "latest_free_heap_bytes",
        "latest_largest_free_block_bytes", "latest_fragmentation_percent",
        "lowest_observed_free_heap_bytes",
        "lowest_observed_largest_free_block_bytes",
        "highest_observed_fragmentation_percent",
    )
    allowed = {"schema", "sampling_interval_ms", "max_samples",
               "sample_count", "state", *fields}
    if set(observation) - allowed:
        raise HeapReadError("Unexpected observed heap field")
    if count == 0:
        if any(field in observation for field in fields):
            raise HeapReadError("No samples must not fabricate measurements")
        return {"state": state, "sample_count": count}
    if any(type(observation.get(field)) is not int for field in fields):
        raise HeapReadError("Observed heap measurement is missing or not integer")
    first, latest, latest_block, latest_frag, low, low_block, high_frag = (
        observation[field] for field in fields)
    if not (0 < first <= 262144 and 0 < latest <= 262144 and
            0 < low <= min(first, latest) and
            0 < latest_block <= latest and
            0 < low_block <= min(latest_block, low) and
            0 <= latest_frag <= high_frag <= 100):
        raise HeapReadError("Observed heap summary is inconsistent")
    if count == 1 and (first != latest or latest != low or
                       latest_block != low_block or latest_frag != high_frag):
        raise HeapReadError("Single observation cannot have divergent extrema")
    return {"state": state, "sample_count": count,
            "lowest_observed_free_heap_bytes": low,
            "lowest_observed_largest_free_block_bytes": low_block,
            "highest_observed_fragmentation_percent": high_frag}


def validate_status(raw: bytes) -> dict[str, object]:
    if not raw or len(raw) > MAX_STATUS_BYTES:
        raise HeapReadError("Device status JSON missing or too large")
    try:
        document = json.loads(raw.decode("utf-8"), object_pairs_hook=_unique_keys)
    except (UnicodeError, json.JSONDecodeError) as exc:
        raise HeapReadError("Device status JSON invalid") from exc
    if not isinstance(document, dict):
        raise HeapReadError("Device status must be one JSON object")
    # review-002 predates the newer native_ota_writer_compiled JSON key.
    # Require the safety markers shared by BOTH real V2 status versions;
    # when the newer key exists it must independently remain exactly False.
    safety_flags = (
        "physical_flash_installation_authorized",
        "physical_flash_or_application_OTA_writes_performed_by_diagnostics",
        "filesystem_migration_writes_compiled",
        "application_littlefs_begin_called",
        "application_eeprom_commit_called",
    )
    if (document.get("mode") != "FIRST_BOOT_BRIDGE" or
        document.get("pc_metrics_storage") != "RAM_ONLY" or
        any(document.get(field) is not False for field in safety_flags) or
        ("native_ota_writer_compiled" in document and
         document["native_ota_writer_compiled"] is not False)):
        raise HeapReadError("Response is not the expected nonwriting V2 diagnostic")
    heap = document.get("available_heap_bytes")
    size = document.get("running_application_bytes")
    if type(heap) is not int or not 0 < heap < 262144:
        raise HeapReadError("Invalid/missing live free-heap sample")
    if type(size) is not int or not 0 < size < 4194304:
        raise HeapReadError("Invalid/missing running image size")
    result: dict[str, object] = {
        "free_heap_bytes": heap, "running_application_bytes": size}
    if "heap_observation" in document:
        result["heap_observation"] = _validate_optional_observation(
            document["heap_observation"])
    return result


def make_status_opener(username: str, password: str):
    # Exact legacy status realm. Keep this wholly separate from SHINO-OTA.
    endpoint = "http://" + PRIVATE_AP + STATUS_PATH
    passwords = HTTPPasswordMgrWithDefaultRealm()
    passwords.add_password("SHINO-FirstBoot", endpoint, username, password)
    return build_opener(ProxyHandler({}), NoRedirect(), HTTPDigestAuthHandler(passwords))


def read_one_snapshot(opener) -> dict[str, object]:
    endpoint = "http://" + PRIVATE_AP + STATUS_PATH
    request = Request(endpoint, method="GET", headers={
        "Accept": "application/json",
        "Cache-Control": "no-store",
        "Connection": "close",
        "User-Agent": "SHINO-ReadOnly-Heap-Snapshot/1",
    })
    try:
        with opener.open(request, timeout=HTTP_TIMEOUT_SECONDS) as response:
            if response.getcode() != 200:
                raise HeapReadError("Status endpoint did not return HTTP 200")
            content_type = response.headers.get("Content-Type", "")
            if content_type.split(";", 1)[0].strip().lower() != "application/json":
                raise HeapReadError("Unexpected device status media type")
            length = response.headers.get("Content-Length", "")
            if length and (not length.isdecimal() or int(length) > MAX_STATUS_BYTES):
                raise HeapReadError("Status response declared excessive length")
            raw = response.read(MAX_STATUS_BYTES + 1)
            return validate_status(raw)
    except (HTTPError, URLError, TimeoutError, OSError) as exc:
        # Never display a challenge, Authorization value, private password,
        # raw HTTP response body, OS trace or URL in user-facing output.
        raise HeapReadError("Read-only status request failed") from exc


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--measure", action="store_true",
                        help="Explicitly GET one snapshot from existing private AP")
    parser.add_argument("--credentials-file", type=Path,
                        help="Matching-build ignored private credentials.txt; no CLI password")
    parser.add_argument("--phase", choices=PHASES, default="idle",
                        help="Human-set test stage; does not create load or automate anything")
    args = parser.parse_args(argv)
    if not args.measure:
        print("OFFLINE ONLY. No network, credentials, data file or device operation.")
        print("For one manual read-only status snapshot, explicitly pass "
              "--measure --credentials-file <private credentials.txt>.")
        return 0
    if args.credentials_file is None:
        parser.error("--measure requires --credentials-file")
    try:
        username, password = read_credentials(args.credentials_file)
        measurement = read_one_snapshot(make_status_opener(username, password))
    except (SenderError, HeapReadError, OSError):
        print("No trusted heap snapshot. Check private AP connection and matching "
              "credentials; no write or OTA operation was attempted.")
        return 1
    print("READ ONLY | phase="+args.phase+
          " | free_heap_bytes="+str(measurement["free_heap_bytes"])+
          " | running_application_bytes="+str(measurement["running_application_bytes"]))
    observation = measurement.get("heap_observation")
    if observation is not None:
        print("READ ONLY OBSERVED | state="+observation["state"]+
              " | samples="+str(observation["sample_count"])+
              (" | lowest_observed_free_heap_bytes="+
               str(observation["lowest_observed_free_heap_bytes"])+
               " | lowest_observed_largest_block_bytes="+
               str(observation["lowest_observed_largest_free_block_bytes"])+
               " | highest_observed_fragmentation_percent="+
               str(observation["highest_observed_fragmentation_percent"])
               if observation["sample_count"] else ""))
    print("Current heap is one instant; optional periodic extrema are OBSERVED only, "
          "not an in-flight peak, concurrency proof or authorization to flash.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
