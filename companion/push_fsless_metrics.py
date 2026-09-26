"""Explicit PC -> SHINO-FirstBoot AP telemetry sender (volatile RAM only).

No device flash/filesystem/OTA routes are used. Windows must be connected to
SHINO's private AP (usually 192.168.4.1) or have a route to its actual IP.
Never send private credentials in command arguments, log or public artifacts.
"""
from __future__ import annotations

import argparse
import ipaddress
import json
from pathlib import Path
import time
from urllib.error import HTTPError, URLError
from urllib.request import (
    HTTPDigestAuthHandler, HTTPPasswordMgrWithDefaultRealm,
    HTTPRedirectHandler, ProxyHandler, Request, build_opener,
)
from metrics_server import collect_metrics, query_nvidia

ALLOWED_NETWORKS = tuple(ipaddress.ip_network(x) for x in (
    "10.0.0.0/8", "172.16.0.0/12", "192.168.0.0/16",
))
ENDPOINT = "/api/v1/bridge/metrics"
FIELDS = (
    "ok", "cpu_usage", "gpu_usage", "memory_used_gb",
    "gpu_vram_mb", "gpu_temp_c", "gpu_power", "gpu_available",
)


class SenderError(ValueError):
    pass


class NoRedirect(HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        return None


def validate_host(value: str) -> str:
    try:
        host = ipaddress.IPv4Address(value)
    except ipaddress.AddressValueError as exc:
        raise SenderError("Use an exact private LAN IPv4 literal") from exc
    if not any(host in network for network in ALLOWED_NETWORKS):
        raise SenderError("Only RFC1918 local/private IPv4 destinations are permitted")
    return str(host)


def read_credentials(path: Path) -> tuple[str, str]:
    if not path.is_file() or path.is_symlink():
        raise SenderError("Choose your private generated credentials.txt; symlinks are not accepted")
    if path.stat().st_size > 4096:
        raise SenderError("Private credentials file is unexpectedly large")
    values: dict[str, str] = {}
    for line in path.read_text(encoding="utf-8").splitlines():
        name, divider, value = line.partition(": ")
        if divider and name in ("Rescue HTTP Digest user", "Rescue HTTP Digest password"):
            if name in values:
                raise SenderError("Duplicate Digest credential entry")
            values[name] = value.strip()
    user = values.get("Rescue HTTP Digest user", "")
    password = values.get("Rescue HTTP Digest password", "")
    if user != "shino" or len(password) < 20 or len(password) > 256:
        raise SenderError("Missing or invalid generated per-build private Digest credentials")
    return user, password


def encode_sample(sample: dict) -> bytes:
    if set(FIELDS) - set(sample):
        raise SenderError("PC metrics missing required numeric or availability fields")
    if sample["ok"] is not True or type(sample["gpu_available"]) is not bool:
        raise SenderError("Metrics sampler has no valid data")
    payload = {key: sample[key] for key in FIELDS}
    for key in FIELDS:
        if key not in ("ok", "gpu_available") and (type(payload[key]) not in (float, int) or
                not -40 <= payload[key] <= 65536):
            raise SenderError("Numeric PC sample is invalid")
    body = json.dumps(payload, separators=(",", ":"), allow_nan=False).encode("utf-8")
    if not 16 <= len(body) <= 384:
        raise SenderError("PC telemetry exceeds ESP8266 bounded JSON limit")
    return body


def make_opener(host: str, user: str, password: str):
    url = "http://" + validate_host(host) + ENDPOINT
    store = HTTPPasswordMgrWithDefaultRealm()
    store.add_password("SHINO-FirstBoot", url, user, password)
    return build_opener(ProxyHandler({}), NoRedirect(), HTTPDigestAuthHandler(store))


def send_one(host: str, opener, sample: dict, timeout: float = 3.0) -> bool:
    if not 0.1 <= timeout <= 10:
        raise SenderError("Timeout out of range")
    url = "http://" + validate_host(host) + ENDPOINT
    request = Request(url, data=encode_sample(sample), method="POST", headers={
        "Content-Type": "application/json", "Accept": "application/json",
        "Cache-Control": "no-store",
        "User-Agent": "SHINO-Fsless-PC-Telemetry/1",
    })
    try:
        with opener.open(request, timeout=timeout) as response:
            if response.getcode() != 200:
                return False
            if response.headers.get("Content-Length", "").isdigit() and int(
                    response.headers["Content-Length"]) > 256:
                return False
            body = response.read(257)
            if len(body) > 256:
                return False
            data = json.loads(body)
            return data.get("status") == "RAM_SAMPLE_ACCEPTED" and data.get("persisted") is False
    except (HTTPError, URLError, TimeoutError, OSError, ValueError, json.JSONDecodeError):
        return False


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--host", default="192.168.4.1",
                        help="Current SHINO private AP IP (default 192.168.4.1), never factory IP")
    parser.add_argument("--credentials-file", type=Path,
                        help="Ignored per-build firmware/private/credentials.txt; NEVER pass secrets in CLI")
    parser.add_argument("--once", action="store_true", help="Send one RAM sample and exit")
    parser.add_argument("--dry-run", action="store_true",
                        help="Read PC metrics and report schema locally; no device or credentials accessed")
    args = parser.parse_args()
    try:
        host = validate_host(args.host)
        import psutil
        if args.dry_run:
            print("OFFLINE ONLY. Sample schema: " + ",".join(encode_sample(
                collect_metrics(psutil, query_nvidia) and
                {key: collect_metrics(psutil, query_nvidia)[key] for key in FIELDS}
            ) and FIELDS))
            return 0
        if args.credentials_file is None:
            raise SenderError("--credentials-file is required for real, manually initiated RAM telemetry")
        user, password = read_credentials(args.credentials_file)
        opener = make_opener(host, user, password)
        print("SHINO telemetry sender: RAM-only metrics to private AP; no firmware/FS writes.")
        print("Use Ctrl+C to stop. Stale PC stats expire automatically after 6 seconds.")
        while True:
            sample = collect_metrics(psutil, query_nvidia)
            accepted = send_one(host, opener, sample)
            print("RAM telemetry accepted" if accepted else "No response / rejected (no device write attempted)")
            if args.once:
                return 0 if accepted else 1
            time.sleep(2)
    except (SenderError, OSError) as exc:
        parser.exit(1, f"Telemetry sender stopped: {exc}\n")
    except KeyboardInterrupt:
        print("\nSender stopped. Device statistics will become stale.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
