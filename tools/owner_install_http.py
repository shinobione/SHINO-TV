"""Single-attempt owner installation transport. No CLI, discovery or auto-retry.

Callers must complete exact-image/boot/resource/owner gates before calling this.
Private bytes and Digest inputs remain in memory; receipts contain allowlisted
metadata only. This module neither obtains consent nor qualifies a device.
"""
from __future__ import annotations

import hashlib
from http.client import HTTPException
import ipaddress
import json
import re
import time
from datetime import datetime, timezone
from pathlib import Path
from urllib.error import HTTPError, URLError
from urllib.parse import urlsplit
from urllib.request import HTTPRedirectHandler, ProxyHandler, Request, build_opener

RESPONSE_LIMIT = 4096
MESSAGES = {
    "denied": "Authentication required",
    "rejected": "Original image was not fully verified; no successful OTA commit",
    "staged": "Verified OEM application image; reboot scheduled. Original filesystem restoration unproven",
    "read_only": "Experimental factory writes not compiled in this firmware",
}
ROUTES = {"/api/v1/bridge/factory-return": "factory_v9_0_44", "/update": "firmware"}


class NoRedirect(HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        return None


class UploadStopped(RuntimeError):
    def __init__(self, receipt):
        super().__init__("INSTALL_UPLOAD_HOLD_NO_RETRY")
        self.receipt = receipt


def stamp():
    return datetime.now(timezone.utc).isoformat()


def numeric_target(base, path):
    parts = urlsplit(base)
    if (parts.scheme != "http" or parts.username is not None or parts.password is not None
            or parts.path not in ("", "/") or parts.query or parts.fragment
            or path not in ROUTES):
        raise ValueError("INSTALL_TARGET_SCOPE")
    address = ipaddress.IPv4Address(parts.hostname)
    if not (address.is_loopback or any(address in ipaddress.ip_network(n) for n in
                                      ("10.0.0.0/8", "172.16.0.0/12", "192.168.0.0/16"))):
        raise ValueError("INSTALL_TARGET_SCOPE")
    port = parts.port or 80
    if not address.is_loopback and port != 80:
        raise ValueError("INSTALL_TARGET_PORT")
    return str(address) + (":" + str(port) if port != 80 else "")


def prepare_request(base, path, field, file, expected, authorization=None):
    """Preserve the existing private client's multipart construction byte-for-byte."""
    host = numeric_target(base, path)
    if field != ROUTES[path] or not re.fullmatch(r"[0-9a-f]{64}", expected):
        raise ValueError("INSTALL_IMAGE_SCOPE")
    file = Path(file)
    if file.is_symlink() or not file.is_file() or not re.fullmatch(r"[A-Za-z0-9_.-]+\.bin", file.name):
        raise ValueError("INSTALL_IMAGE_FILE")
    data = file.read_bytes()
    if not data or hashlib.sha256(data).hexdigest() != expected:
        raise ValueError("INSTALL_IMAGE_HASH")
    boundary = "SHINO_M8_" + expected[:20]
    body = (f'--{boundary}\r\nContent-Disposition: form-data; name="{field}"; filename="{file.name}"\r\n'
            'Content-Type: application/octet-stream\r\n\r\n').encode() + data + f"\r\n--{boundary}--\r\n".encode()
    # Verify there is no payload delimiter collision before entering a write.
    if b"\r\n--" + boundary.encode() in data:
        raise ValueError("INSTALL_BOUNDARY_COLLISION")
    req = Request("http://" + host + path, data=body, method="POST", headers={
        "Host": host, "Connection": "close", "Content-Length": str(len(body)),
        "Content-Type": "multipart/form-data; boundary=" + boundary})
    if path != "/update":
        if authorization is None:
            raise ValueError("INSTALL_PREEMPTIVE_DIGEST_REQUIRED")
        value = authorization(req)
        if not value or not value.startswith("Digest ") or "\r" in value or "\n" in value:
            raise ValueError("INSTALL_PREEMPTIVE_DIGEST_REQUIRED")
        req.add_unredirected_header("Authorization", value)
    metadata = {"method": "POST", "target_ipv4": host.split(":")[0], "host": host,
                "path": path, "field": field, "filename_suffix": ".bin",
                "filename_bytes": len(file.name), "image_bytes": len(data), "image_sha256": expected,
                "content_length": len(body), "boundary": boundary, "boundary_bytes": len(boundary),
                "multipart_parts": 1, "mime": "application/octet-stream",
                "preemptive_digest": req.has_header("Authorization"),
                "authorization_bytes": len(req.get_header("Authorization", "")),
                "connection": "close", "redirects_allowed": False, "retry_allowed": False}
    return req, metadata


def safe_headers(headers):
    """Do not copy arbitrary header text, cookies, Location or challenge tokens."""
    out = {}
    length = headers.get("Content-Length", "")
    if re.fullmatch(r"[0-9]{1,10}", length):
        out["content_length"] = int(length)
    content_type = headers.get("Content-Type", "").split(";")[0].strip().lower()
    if content_type in ("application/json", "text/html", "text/plain", "application/octet-stream"):
        out["content_type"] = content_type
    if headers.get("Cache-Control", "").strip().lower() == "no-store":
        out["cache_control"] = "no-store"
    if headers.get("X-Content-Type-Options", "").strip().lower() == "nosniff":
        out["x_content_type_options"] = "nosniff"
    if headers.get("Location") is not None:
        out["redirect_location_present"] = True
    challenge = headers.get("WWW-Authenticate", "")
    if challenge:
        out["auth_challenge_scheme"] = "Digest" if challenge.startswith("Digest ") else "OTHER"
    return out


def safe_body(raw, path):
    """A safe snippet is reconstructed from fixed vocabulary, never arbitrary text."""
    result = {"response_bytes_observed": len(raw), "response_status": "UNRECOGNIZED",
              "response_snippet": "[unrecognized response omitted]"}
    if len(raw) > RESPONSE_LIMIT:
        result["response_snippet"] = "[oversized response omitted]"
        return result
    try:
        doc = json.loads(raw)
    except (ValueError, UnicodeError, RecursionError):
        doc = None
    if isinstance(doc, dict) and isinstance(doc.get("status"), str) and doc["status"] in MESSAGES:
        state = doc["status"]
        snippet = {"status": state}
        if doc.get("message") == MESSAGES[state]:
            snippet["message"] = MESSAGES[state]
        result.update(response_status=state, response_snippet=json.dumps(snippet))
    elif path == "/update" and b"Update Success! Rebooting" in raw:
        result.update(response_status="OEM_UPDATE_SUCCESS", response_snippet="Update Success! Rebooting")
    return result


def upload_once(base, path, field, file, expected, *, authorization=None, receipt_path,
                timeout=90):
    """One initial POST only; every non-ack result is HOLD, including HTTPError.

    The receipt is exclusively created before I/O. Reusing its path refuses the
    operation. No auth/cookie handlers or redirect following exist on this opener.
    A timeout after sending, partial response or receipt failure never resubmits.
    """
    if not 0 < timeout <= 90:
        raise ValueError("INSTALL_TIMEOUT_SCOPE")
    req, metadata = prepare_request(base, path, field, file, expected, authorization)
    receipt_path = Path(receipt_path)
    receipt = {"started_utc": stamp(), "request": metadata, "timeout_seconds": timeout,
               "upload_attempts": 1, "automatic_retry": False, "gate": "HOLD",
               "outcome": "ATTEMPT_RESERVED_NO_ACK", "staging_sector_writes": "UNKNOWN"}
    with receipt_path.open("x", encoding="utf-8") as handle:
        handle.write(json.dumps(receipt, indent=2) + "\n")
    start = time.monotonic()
    opener = build_opener(ProxyHandler({}), NoRedirect())
    try:
        response = opener.open(req, timeout=timeout)
    except HTTPError as error:
        # HTTPError is a readable HTTP response. Capture its code FIRST, even if
        # bounded response-body reading subsequently disconnects or times out.
        response = error
    except (OSError, URLError, HTTPException) as error:
        response = None
        reason = error.reason if isinstance(error, URLError) else error
        receipt["outcome"] = "TIMEOUT" if isinstance(reason, TimeoutError) else "TRANSPORT_ERROR"
    try:
        if response is not None:
            with response:
                receipt["http_status"] = response.code
                receipt["response_headers"] = safe_headers(response.headers)
                receipt["outcome"] = "HTTP_ERROR" if response.code != 200 else "MISSING_ACK"
                raw = response.read(RESPONSE_LIMIT + 1)
                receipt.update(safe_body(raw, path))
                declared = receipt["response_headers"].get("content_length")
                complete = declared is None or declared == len(raw)
                receipt["response_framing_complete"] = complete
                wanted = "staged" if path != "/update" else "OEM_UPDATE_SUCCESS"
                if response.code == 200 and complete and receipt["response_status"] == wanted:
                    receipt["gate"] = "ACKNOWLEDGED_EXPECTED_REBOOT"
                    receipt["outcome"] = "ACKNOWLEDGED"
                elif not complete:
                    receipt["outcome"] = "INCOMPLETE_RESPONSE"
    except (OSError, ValueError, HTTPException) as error:
        receipt["outcome"] = "TIMEOUT" if isinstance(error, TimeoutError) else "RESPONSE_READ_ERROR"
    finally:
        receipt["elapsed_ms"] = round((time.monotonic() - start) * 1000, 3)
        receipt["ended_utc"] = stamp()
        receipt_path.write_text(json.dumps(receipt, indent=2) + "\n", encoding="utf-8")
    if receipt["gate"] == "HOLD":
        raise UploadStopped(receipt)
    return {"utc": receipt["ended_utc"], "bytes": metadata["image_bytes"], "sha256": expected,
            "http": receipt["http_status"], "response": receipt["response_snippet"], "receipt": receipt}
