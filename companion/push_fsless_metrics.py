"""Explicit PC -> SHINO-FirstBoot AP telemetry sender (volatile RAM only).

No device flash/filesystem/OTA routes are used. Windows must be connected to
SHINO's private AP (usually 192.168.4.1) or have a route to its actual IP.
Never send private credentials in command arguments, log or public artifacts.
"""
from __future__ import annotations

import argparse
from enum import Enum
import ipaddress
import json
from pathlib import Path
import time
from urllib.error import HTTPError, URLError
from urllib.request import (
    HTTPDigestAuthHandler, HTTPPasswordMgrWithDefaultRealm,
    HTTPRedirectHandler, ProxyHandler, Request, build_opener,
    parse_http_list, parse_keqv_list,
)
from metrics_server import collect_metrics, query_nvidia

ALLOWED_NETWORKS = tuple(ipaddress.ip_network(x) for x in (
    "10.0.0.0/8", "172.16.0.0/12", "192.168.0.0/16",
))
ENDPOINT = "/api/v1/bridge/metrics"
FIELDS = (
    "ok", "cpu_usage", "gpu_usage", "memory_used_gb", "memory_total_gb",
    "gpu_vram_mb", "gpu_temp_c", "gpu_power", "gpu_available",
)


class SenderError(ValueError):
    pass


class SendStatus(str, Enum):
    ACCEPTED = 'accepted_sample'
    NO_ROUTE_TIMEOUT = 'no_route_or_timeout'
    CONNECTION = 'connection_refused_or_reset'
    HTTP_401 = 'http_401'
    HTTP_403 = 'http_403'
    HTTP_ERROR = 'http_error'
    MALFORMED = 'malformed_response'
    NETWORK_ERROR = 'network_error'
    INVALID_SAMPLE = 'invalid_sample'
    CLIENT_ERROR = 'client_error'


def failure_status(exc: Exception) -> SendStatus:
    """Classify by type/code only. Never retain exception text, URLs or headers."""
    if isinstance(exc, HTTPError):
        return {401: SendStatus.HTTP_401, 403: SendStatus.HTTP_403}.get(exc.code, SendStatus.HTTP_ERROR)
    if isinstance(exc, URLError):
        return failure_status(exc.reason) if isinstance(exc.reason, Exception) else SendStatus.NETWORK_ERROR
    if isinstance(exc, (ConnectionError, BrokenPipeError)) or getattr(exc, 'errno', None) in (10054, 10061) or getattr(exc, 'winerror', None) in (10054, 10061):
        return SendStatus.CONNECTION
    if isinstance(exc, TimeoutError) or getattr(exc, 'errno', None) in (101, 113, 10051, 10060, 10065) or getattr(exc, 'winerror', None) in (10051, 10060, 10065):
        return SendStatus.NO_ROUTE_TIMEOUT
    if isinstance(exc, OSError):
        return SendStatus.NETWORK_ERROR
    return SendStatus.MALFORMED if isinstance(exc, (ValueError, UnicodeError)) else SendStatus.CLIENT_ERROR


class NoRedirect(HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        return None


class TelemetryDigestAuthHandler(HTTPDigestAuthHandler):
    """One endpoint/client's challenge cache; never shared or exposed in diagnostics."""
    def __init__(self, store, url):
        super().__init__(store)
        self.url = url
        self.challenge = None

    def http_request(self, request):
        if request.full_url == self.url and self.challenge and not request.has_header('Authorization'):
            value = self.get_authorization(request, self.challenge)
            if value:
                request.add_unredirected_header('Authorization', 'Digest ' + value)
        return request

    def http_error_401(self, req, fp, code, msg, headers):
        auth = headers.get('www-authenticate', '')
        if req.full_url == self.url and auth.lower().startswith('digest '):
            self.challenge = parse_keqv_list(parse_http_list(auth[7:]))
        try:
            return super().http_error_401(req, fp, code, msg, headers)
        finally:
            # urllib resets only after normal return; an interrupted nested auth
            # exchange must not poison future logical attempts. Its recursion cap stays intact.
            self.reset_retry_count()


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
    if payload["memory_total_gb"] <= 0 or payload["memory_used_gb"] > payload["memory_total_gb"]:
        raise SenderError("RAM total must be positive and RAM used cannot exceed total")
    body = json.dumps(payload, separators=(",", ":"), allow_nan=False).encode("utf-8")
    if not 16 <= len(body) <= 384:
        raise SenderError("PC telemetry exceeds ESP8266 bounded JSON limit")
    return body


def make_opener(host: str, user: str, password: str):
    url = "http://" + validate_host(host) + ENDPOINT
    store = HTTPPasswordMgrWithDefaultRealm()
    store.add_password("SHINO-FirstBoot", url, user, password)
    return build_opener(ProxyHandler({}), NoRedirect(), TelemetryDigestAuthHandler(store, url))


def send_sample(host: str, opener, sample: dict, timeout: float = 3.0) -> SendStatus:
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
                return {401: SendStatus.HTTP_401, 403: SendStatus.HTTP_403}.get(response.getcode(), SendStatus.HTTP_ERROR)
            if response.headers.get("Content-Length", "").isdigit() and int(
                    response.headers["Content-Length"]) > 256:
                return SendStatus.MALFORMED
            body = response.read(257)
            if len(body) > 256:
                return SendStatus.MALFORMED
            data = json.loads(body)
            return (SendStatus.ACCEPTED if isinstance(data, dict) and
                    data.get("status") == "RAM_SAMPLE_ACCEPTED" and data.get("persisted") is False
                    else SendStatus.MALFORMED)
    except (HTTPError, URLError, TimeoutError, OSError, ValueError) as exc:
        result = failure_status(exc)
        if isinstance(exc, HTTPError):
            exc.close()
        return result


def send_one(host: str, opener, sample: dict, timeout: float = 3.0) -> bool:
    # Retained bool API for existing host/loopback callers.
    return send_sample(host, opener, sample, timeout) is SendStatus.ACCEPTED


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
            sample = collect_metrics(psutil, query_nvidia)
            encoded = encode_sample(sample)
            print("OFFLINE ONLY; no device request or credentials read.")
            print("Validated bounded sample:", len(encoded), "bytes; fields:", ",".join(FIELDS))
            return 0
        if args.credentials_file is None:
            raise SenderError("--credentials-file is required for real, manually initiated RAM telemetry")
        user, password = read_credentials(args.credentials_file)
        opener = make_opener(host, user, password)
        print("SHINO telemetry sender: RAM-only metrics to private AP; no firmware/FS writes.")
        print("Use Ctrl+C to stop. Stale PC stats expire automatically after 6 seconds.")
        while True:
            sample = collect_metrics(psutil, query_nvidia)
            result = send_sample(host, opener, sample)
            accepted = result is SendStatus.ACCEPTED
            print(result.value)
            if not accepted:
                opener = make_opener(host, user, password) # Next attempt still waits below.
            if args.once:
                return 0 if accepted else 1
            time.sleep(2)
    except SenderError as exc:
        parser.exit(1, f"Telemetry sender stopped: {exc}\n")
    except OSError:
        parser.exit(1, "Telemetry sender stopped: local file unavailable\n")
    except KeyboardInterrupt:
        print("\nSender stopped. Device statistics will become stale.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
