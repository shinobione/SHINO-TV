"""Owner-reviewed ONE status transaction; no CLI, polling, retry or discovery.

No credentials or challenge/header/body text is retained. Tests inject fake
sockets; importing this module does not contact any host.
"""
from __future__ import annotations

import http.client
import json
import re
import socket
import threading
import time
from datetime import datetime, timezone
from pathlib import Path
from urllib.request import (HTTPDigestAuthHandler, HTTPPasswordMgrWithDefaultRealm,
                            Request, parse_http_list, parse_keqv_list)

HOST = "192.168.4.1"
PATH = "/api/v1/bridge/status"
URL = "http://" + HOST + PATH
LIMIT = 16384
TOP = ("running_application_bytes", "physical_flash_bytes_observed_at_runtime",
       "available_heap_bytes", "wifi_state", "wifi_saved", "wifi_storage_layout_safe")
OBS = ("boot", "reset_reason", "wifi_mode", "ap_clients", "min_heap", "min_block",
       "min_cont", "allocation_failures", "canary_failures", "secondary_refs",
       "secondary_used_max", "secondary_busy", "arena_denials", "arena_used_max",
       "receiver_pending", "image_bytes", "body_bytes", "staged_bytes",
       "render_max_us", "render_slices")
HEAP = ("schema", "state", "sampling_interval_ms", "sample_count", "max_samples",
        "first_free_heap_bytes", "latest_free_heap_bytes", "latest_largest_free_block_bytes",
        "latest_fragmentation_percent", "lowest_observed_free_heap_bytes",
        "lowest_observed_largest_free_block_bytes", "highest_observed_fragmentation_percent")


class DiagnosticStopped(RuntimeError):
    def __init__(self, receipt):
        super().__init__("SINGLE_STATUS_STOP_NO_RETRY")
        self.receipt = receipt


class InvalidResponse(ValueError):
    pass


def need(condition, reason):
    if not condition:
        raise InvalidResponse(reason)


def sanitize_status(raw):
    def unique(pairs):
        out = {}
        for key, value in pairs:
            need(key not in out, "DUPLICATE_JSON_KEY")
            out[key] = value
        return out
    doc = json.loads(raw, object_pairs_hook=unique)
    need(isinstance(doc, dict) and doc.get("mode") == "FIRST_BOOT_BRIDGE", "INVALID_STATUS")
    need(all(k in doc for k in TOP) and isinstance(doc.get("p1_observation"), dict), "MISSING_P1")
    obs = doc["p1_observation"]
    need(all(k in obs for k in ("boot", "reset_reason", "min_heap", "min_block", "min_cont")), "MISSING_COUNTERS")
    safe = {k: doc[k] for k in TOP}
    for k in TOP[:3]:
        need(type(safe[k]) is int and 0 <= safe[k] <= 0xffffffff, "INVALID_NUMBER")
    for k in ("wifi_saved", "wifi_storage_layout_safe"):
        need(type(safe[k]) is bool, "INVALID_BOOLEAN")
    need(safe["wifi_state"] in ("NO_SAVED_WIFI", "STA_CONNECTING", "AP_RECOVERY_RETRY",
                               "STA_ONLINE", "STORAGE_OR_AP_FAULT_HOLD"), "INVALID_WIFI_STATE")
    safe["p1_observation"] = {k: obs[k] for k in OBS if k in obs}
    for k, v in safe["p1_observation"].items():
        need(type(v) is bool if k == "receiver_pending" else type(v) is int and 0 <= v <= 0xffffffff,
             "INVALID_COUNTER")
    if "heap_observation" in doc:
        h = doc["heap_observation"]
        need(isinstance(h, dict), "INVALID_HEAP")
        clean = {k: h[k] for k in HEAP if k in h}
        need(clean.get("schema") == "OBSERVED_HEAP_V1" and
             clean.get("state") in ("NO_SAMPLES", "SAMPLING", "SATURATED"), "INVALID_HEAP_SCHEMA")
        for k, v in clean.items():
            if k not in ("schema", "state"):
                need(type(v) is int and 0 <= v <= 0xffffffff, "INVALID_HEAP_NUMBER")
        safe["heap_observation"] = clean
    return safe


def single_status(username, password, receipt_path, *, socket_factory=socket.socket,
                  phase_timeout=3.0, total_timeout=6.0):
    """Fixed AP/endpoint; at most initial GET + one fresh-challenge GET.

    A successful connect/send is only a PC socket observation, never proof that
    firmware accepted or parsed bytes. All failures stop; even another 401 ends
    the transaction. Default timeouts cannot exceed 3s/phase and 6s overall.
    """
    need(0 < phase_timeout <= 3 and 0 < total_timeout <= 6, "INVALID_TIMEOUT")
    receipt_path = Path(receipt_path)
    receipt = {"method": "GET", "path": PATH, "started_utc": datetime.now(timezone.utc).isoformat(),
               "phase_timeout_seconds": phase_timeout, "absolute_timeout_seconds": total_timeout,
               "requests": [], "events": [], "automatic_retry": False, "other_endpoints": 0,
               "device_writes": 0, "gate": "HOLD", "outcome": "RESERVED_NOT_CONNECTED"}
    with receipt_path.open("x", encoding="utf-8") as out:
        out.write(json.dumps(receipt, indent=2) + "\n")
    start = time.monotonic()
    active = {"socket": None}
    expired = threading.Event()

    def save():
        receipt_path.write_text(json.dumps(receipt, indent=2) + "\n", encoding="utf-8")

    def remaining():
        value = total_timeout - (time.monotonic() - start)
        if expired.is_set() or value <= 0:
            raise TimeoutError()
        return min(phase_timeout, value)

    def event(phase, result="START"):
        receipt["phase"] = phase
        receipt["events"].append({"request": len(receipt["requests"]), "phase": phase,
                                  "result": result, "monotonic_ns": time.monotonic_ns(),
                                  "elapsed_ms": round((time.monotonic() - start) * 1000, 3)})
        if active["socket"] is not None:
            active["socket"].settimeout(remaining())
        save()

    def abort():
        expired.set()
        s = active["socket"]
        if s is not None:
            try:
                s.shutdown(socket.SHUT_RDWR)
            except OSError:
                pass
            s.close()

    class LimitedLines:
        def __init__(self, fp):
            self.fp, self.bytes, self.lines = fp, 0, 0
        def readline(self, size=-1):
            line = self.fp.readline(min(4097, size) if size >= 0 else 4097)
            self.bytes += len(line)
            self.lines += 1
            need(len(line) <= 4096 and self.bytes <= LIMIT and self.lines <= 33, "HEADER_LIMIT")
            need(not line or line.endswith(b"\r\n"), "INVALID_HTTP_LINE")
            return line
        def __getattr__(self, key):
            return getattr(self.fp, key)

    class Response(http.client.HTTPResponse):
        def __init__(self, *args, **kwargs):
            super().__init__(*args, **kwargs)
            self.fp = LimitedLines(self.fp)
        def _read_status(self):
            event("HTTP_STATUS_WAIT")
            version, status, reason = super()._read_status()
            receipt["requests"][-1]["http_status"] = status
            event("HTTP_STATUS_WAIT", "COMPLETE")
            need(version in ("HTTP/1.0", "HTTP/1.1") and status in (200, 401), "UNEXPECTED_HTTP_STATUS")
            event("RESPONSE_HEADERS")
            return version, status, reason

    def get(authorization=None):
        remaining()
        need(len(receipt["requests"]) < 2, "REQUEST_BUDGET")
        req = {"authenticated": authorization is not None, "tcp_connected": False,
               "send_started": False, "send_completed": False, "response_complete": False}
        receipt["requests"].append(req)
        conn = http.client.HTTPConnection(HOST, 80, timeout=phase_timeout)
        conn.response_class = Response
        response = None
        s = socket_factory(socket.AF_INET, socket.SOCK_STREAM)
        active["socket"] = s
        try:
            event("TCP_CONNECT")
            s.connect((HOST, 80))
            req["tcp_connected"] = True
            event("TCP_CONNECT", "COMPLETE")
            conn.sock = s  # No implicit connect, address resolver, redirect or proxy.
            event("REQUEST_SEND")
            req["send_started"] = True
            headers = {"Host": HOST, "Connection": "close", "Cache-Control": "no-store"}
            if authorization is not None:
                headers["Authorization"] = authorization
            conn.request("GET", PATH, headers=headers)
            req["send_completed"] = True
            event("REQUEST_SEND", "COMPLETE")
            response = conn.getresponse()
            event("RESPONSE_HEADERS", "COMPLETE")
            need(response.getheader("Transfer-Encoding") is None and
                 response.getheader("Content-Encoding", "identity") == "identity", "UNSUPPORTED_FRAMING")
            lengths = response.headers.get_all("Content-Length", [])
            types = response.headers.get_all("Content-Type", [])
            need(len(lengths) == 1 and re.fullmatch(r"[0-9]{1,8}", lengths[0]) and
                 int(lengths[0]) <= LIMIT and len(types) == 1, "INVALID_HTTP_FRAMING")
            req["content_length"] = int(lengths[0])
            mime = types[0].split(";")[0].strip().lower()
            req["content_type"] = mime if mime in ("application/json", "text/html") else "OTHER"
            event("RESPONSE_BODY")
            raw = response.read(LIMIT + 1)
            req["body_bytes"] = len(raw)
            need(len(raw) == req["content_length"], "INCOMPLETE_BODY")
            req["response_complete"] = True
            event("RESPONSE_BODY", "COMPLETE")
            challenges = response.headers.get_all("WWW-Authenticate", [])
            return response.status, raw, challenges, mime
        finally:
            active["socket"] = None
            if response is not None:
                response.close()
            conn.close()
            s.close()

    timer = threading.Timer(total_timeout, abort)
    timer.daemon = True
    timer.start()
    try:
        status, raw, challenges, mime = get()
        if status == 401:
            event("DIGEST_PREPARATION")
            need(len(challenges) == 1 and challenges[0].startswith("Digest "), "INVALID_CHALLENGE")
            pairs = parse_http_list(challenges[0][7:])
            parts = parse_keqv_list(pairs)
            need(len(parts) == len(pairs) and parts.get("realm") == "SHINO-FirstBoot" and
                 parts.get("nonce") and parts.get("opaque") and
                 parts.get("algorithm", "MD5") == "MD5" and
                 "auth" in [v.strip() for v in parts.get("qop", "").split(",")], "INVALID_CHALLENGE")
            manager = HTTPPasswordMgrWithDefaultRealm()
            manager.add_password("SHINO-FirstBoot", URL, username, password)
            value = HTTPDigestAuthHandler(manager).get_authorization(Request(URL, method="GET"), parts)
            need(value and "\r" not in value and "\n" not in value, "INVALID_AUTHORIZATION")
            event("DIGEST_PREPARATION", "COMPLETE")
            status, raw, challenges, mime = get("Digest " + value)
        event("JSON_VALIDATION")
        need(status == 200 and mime == "application/json", "MISSING_STATUS_ACK")
        receipt["status"] = sanitize_status(raw)
        event("JSON_VALIDATION", "COMPLETE")
        remaining()
        receipt["outcome"] = "STATUS_CAPTURED"
        receipt["gate"] = "READ_COMPLETE__PHYSICAL_BASELINE_HOLD__STOP"
    except Exception as error:
        receipt["outcome"] = "STOP_NO_RETRY"
        receipt["error_phase"] = receipt.get("phase", "LOCAL_PREPARATION")
        receipt["error_type"] = type(error).__name__
        if isinstance(error, OSError):
            receipt["errno"] = error.errno
            receipt["winerror"] = getattr(error, "winerror", None)
        if isinstance(error, InvalidResponse):
            receipt["validation_error"] = str(error)  # Our fixed vocabulary only.
        receipt["absolute_deadline_exceeded"] = expired.is_set() or time.monotonic() - start >= total_timeout
    finally:
        timer.cancel()
        receipt["elapsed_ms"] = round((time.monotonic() - start) * 1000, 3)
        receipt["ended_utc"] = datetime.now(timezone.utc).isoformat()
        save()
    if receipt["gate"] == "HOLD":
        raise DiagnosticStopped(receipt)
    return receipt
