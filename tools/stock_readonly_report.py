#!/usr/bin/env python3
"""SmallTV-Ultra V9.0.44: strict allowlist GET-only Windows LAN evidence collector.

It never sends POST/PUT, uploads a BIN, logs full responses, scans ports/paths,
follows redirects or opens external assets. The optional /update request only
inspects form metadata: it CANNOT measure the manufacturer's real OTA slot.
"""
from __future__ import annotations

import argparse
from datetime import datetime, timezone
from html.parser import HTMLParser
import ipaddress
import json
from pathlib import Path
import re
from typing import Callable
from urllib.error import HTTPError, URLError
from urllib.parse import urlsplit
from urllib.request import HTTPRedirectHandler, Request, build_opener


MAX_BODY = 64 * 1024
KNOWN_ROUTES = ("/v.json", "/space.json", "/app.json")
UPDATE_ROUTE = "/update"
PRIVATE_NETWORKS = tuple(ipaddress.ip_network(x) for x in (
    "10.0.0.0/8", "172.16.0.0/12", "192.168.0.0/16",
))
SAFE_FIELD = re.compile(r"^[A-Za-z0-9_-]{1,48}$")
SAFE_ACTION = re.compile(r"^/[A-Za-z0-9/_-]{0,96}$")


class ProbeError(ValueError):
    """Safe-to-display problem with the observation, no raw data included."""


class NoRedirect(HTTPRedirectHandler):
    def redirect_request(self, request, response, code, message, headers, newurl):
        return None


def checked_ip(text: str) -> str:
    # Require an exact IPv4 literal; never allow localhost, DNS, credentials
    # in a URL, IPv6 literals, a scheme, or a port.
    try:
        address = ipaddress.IPv4Address(text)
    except ipaddress.AddressValueError as exc:
        raise ProbeError("Use an exact private IPv4 address, e.g. 192.168.1.70") from exc
    if not any(address in block for block in PRIVATE_NETWORKS):
        raise ProbeError("Only RFC1918 private LAN IPv4 addresses are allowed")
    return str(address)


def safe_nonnegative_int(value: object) -> int | None:
    # Avoid bool (which subclasses int) and numeric strings. Don't trust a
    # server-provided exotic number or silently cast floats.
    return value if type(value) is int and 0 <= value <= 0xFFFFFFFF else None


class UpdateFormParser(HTMLParser):
    """No HTML serialization: retain only strictly bounded structure, never values."""

    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.forms: list[dict] = []
        self.active: dict | None = None
        self.script_tag_count = 0

    @staticmethod
    def local_action(value: str) -> str:
        if not value:
            return "(default page)"
        uri = urlsplit(value)
        if uri.scheme or uri.netloc or not SAFE_ACTION.fullmatch(uri.path):
            return "(nonlocal or unrecognized)"
        return uri.path

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]):
        data = dict(attrs)
        if tag == "script":
            self.script_tag_count = min(self.script_tag_count + 1, 1000)
        if tag == "form" and len(self.forms) < 8:
            self.active = {
                "method": (data.get("method") or "GET").upper()[:8],
                "action_path": self.local_action(data.get("action") or ""),
                "enctype": (data.get("enctype") or "(default)")[:48],
                "file_field_names": [],
            }
            self.forms.append(self.active)
        elif tag == "input" and self.active is not None and (data.get("type") or "").lower() == "file":
            name = data.get("name") or ""
            if SAFE_FIELD.fullmatch(name) and len(self.active["file_field_names"]) < 16:
                self.active["file_field_names"].append(name)

    def handle_endtag(self, tag: str):
        if tag == "form":
            self.active = None


def project_json(path: str, body: bytes) -> dict:
    try:
        parsed = json.loads(body)
    except (UnicodeDecodeError, json.JSONDecodeError):
        raise ProbeError("Response was not a valid JSON object") from None
    if not isinstance(parsed, dict):
        raise ProbeError("Response was not a JSON object")
    if path == "/v.json":
        model = parsed.get("m")
        version = parsed.get("v")
        return {
            "model": model[:48] if isinstance(model, str) else None,
            "firmware": version[:48] if isinstance(version, str) else None,
            "full_response_saved": False,
        }
    if path == "/space.json":
        total = safe_nonnegative_int(parsed.get("total"))
        free = safe_nonnegative_int(parsed.get("free"))
        return {
            "storage_kind": "images_and_gifs_filesystem_NOT_OTA_slot",
            "total_bytes": total,
            "free_bytes": free,
            "free_not_larger_than_total": free <= total if total is not None and free is not None else None,
            "stock_OTA_available_bytes": "NOT_DISCLOSED_BY_THIS_ENDPOINT",
            "full_response_saved": False,
        }
    if path == "/app.json":
        theme = safe_nonnegative_int(parsed.get("theme"))
        return {"theme_id": theme, "other_settings_saved": False}
    raise ProbeError("Unexpected or unapproved route")


def project_update_page(body: bytes) -> dict:
    decoder = body.decode("utf-8", errors="replace")
    reader = UpdateFormParser()
    try:
        reader.feed(decoder)
        reader.close()
    except (ValueError, OverflowError):
        raise ProbeError("Update page HTML could not be analyzed safely") from None
    return {
        "inspection_only": True,
        "forms": reader.forms,
        "script_tag_count": reader.script_tag_count,
        "javascript_not_fetched_or_executed": True,
        "input_values_and_raw_HTML_saved": False,
        "actual_OTA_capacity_bytes": "UNKNOWN",
        "actual_file_acceptance": "NOT_TESTED",
    }


def get_one(ip: str, path: str, opener, timeout: float) -> dict:
    if path not in (*KNOWN_ROUTES, UPDATE_ROUTE):
        raise ProbeError("Route not on exact GET allowlist")
    target = f"http://{ip}{path}"
    request = Request(target, headers={
        "User-Agent": "SHINO-TV-ReadOnly-StockAudit/1",
        "Accept": "application/json" if path != UPDATE_ROUTE else "text/html",
        "Cache-Control": "no-store",
    }, method="GET")
    try:
        with opener.open(request, timeout=timeout) as response:
            status = response.getcode()
            if status != 200:
                return {"status": "http_error", "http_code": status}
            declared = response.headers.get("Content-Length", "")
            if declared.isdigit() and int(declared) > MAX_BODY:
                return {"status": "body_too_large"}
            body = response.read(MAX_BODY + 1)
            if len(body) > MAX_BODY:
                return {"status": "body_too_large"}
    except HTTPError as exc:
        # Includes denied redirect response. Never report Location or server body.
        return {"status": "http_error", "http_code": exc.code}
    except (URLError, TimeoutError, OSError, ValueError):
        return {"status": "network_error"}
    try:
        return {
            "status": "observed",
            "data": project_update_page(body) if path == UPDATE_ROUTE else project_json(path, body),
        }
    except ProbeError as exc:
        return {"status": "parse_error", "reason": str(exc)}


def collect(ip: str, *, include_update_page: bool = False,
            opener=None, timeout: float = 3.0,
            clock: Callable[[], datetime] | None = None) -> dict:
    ip = checked_ip(ip)
    if not 0.1 <= timeout <= 10:
        raise ProbeError("Timeout must be between 0.1 and 10 seconds")
    opener = opener if opener is not None else build_opener(NoRedirect())
    timestamp = (clock or (lambda: datetime.now(timezone.utc)))().astimezone(timezone.utc).isoformat()
    paths = (*KNOWN_ROUTES, UPDATE_ROUTE) if include_update_page else KNOWN_ROUTES
    result = {
        "tool": "SHINO-TV_stock_V9.0.44_readonly_audit",
        "observed_at_utc": timestamp,
        "target_ip_saved": False,
        "http_methods_sent": ["GET"],
        "routes_requested": list(paths),
        "redirects_followed": False,
        "device_write_or_firmware_upload_attempted": False,
        "response_bodies_saved": False,
        "observations": {path: get_one(ip, path, opener, timeout) for path in paths},
        "limitations": [
            "GET page/form metadata does NOT prove the stock OTA capacity, image acceptance, or restore ability.",
            "/space.json is the photo/GIF filesystem capacity, not OTA staging free space.",
            "Official V9.0.44 ZIP is application OTA, not the owner's full 4-MiB flash.",
            "No endpoint was exercised via POST or simulated upload.",
        ],
        "permission_to_flash": False,
    }
    return result


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--host", required=True, help="Owner-confirmed private LAN IPv4, e.g. 192.168.1.70")
    parser.add_argument("--include-update-page", action="store_true",
                        help="Additionally GET /update and inspect bounded form metadata, NO upload")
    parser.add_argument("--timeout", type=float, default=3)
    parser.add_argument("--out", type=Path,
                        help="Save sanitized JSON to a NEW file (never overwrite); otherwise print to terminal")
    args = parser.parse_args()
    try:
        result = collect(args.host, include_update_page=args.include_update_page, timeout=args.timeout)
        message = json.dumps(result, ensure_ascii=False, indent=2) + "\n"
        if args.out:
            # x mode: never overwrite evidence; the report does not contain the raw IP,
            # full settings/HTML, file values or captured authentication data.
            with args.out.open("x", encoding="utf-8") as output:
                output.write(message)
            print(f"Sanitized report written: {args.out}")
        else:
            print(message, end="")
    except (ProbeError, OSError) as exc:
        parser.exit(1, f"Read-only diagnostic stopped: {exc}\n")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
