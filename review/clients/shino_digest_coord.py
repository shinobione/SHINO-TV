"""Bounded inter-process Digest HTTP exchange coordinator (PC only).

All cooperating Windows SHINO clients share one per-target OS file lock.
Keep the lock for the complete HTTP challenge + authorization + response body.
No proxy, remote service, private credentials, firmware, or OTA operations.
A local peer holding the lock longer than the bound produces a local failure;
no HTTP retry, fallback without a lock, or forced lock-file removal.
"""
from __future__ import annotations

from contextlib import contextmanager
from collections import Counter, deque
import errno
import http.client
import ipaddress
import os
from pathlib import Path
import time
from urllib.error import HTTPError, URLError


OPERATIONS = {
    "/api/v1/update/status": "GET_UPDATE_STATUS",
    "/api/v1/m9/normal/status": "GET_NORMAL_STATUS",
    "/api/v1/m9/maintenance/result": "GET_MAINTENANCE_RESULT",
}
OUTCOMES = frozenset(("http_200", "http_401", "http_403", "http_error",
                     "timeout", "network_error", "protocol_error", "json_invalid",
                     "coordination_busy", "coordination_unavailable", "client_error",
                     "accepted_sample", "malformed_response", "invalid_sample",
                     "no_route_or_timeout", "connection_refused_or_reset"))


class HttpDiagnostics:
    """64 typed exchanges plus counters; never retain a request or exception."""
    def __init__(self):
        self.history = deque(maxlen=64)
        self.counts = Counter()

    def record(self, operation, outcome, timing, http_status=None):
        operation = operation if operation in (*OPERATIONS.values(), "POST_LINK_METRICS") else "OTHER"
        outcome = outcome if outcome in OUTCOMES else "client_error"
        self.counts[outcome] += 1
        row = dict(operation=operation, outcome=outcome,
                   http_status=http_status if type(http_status) is int and 100 <= http_status <= 599 else None)
        for key in ("lock_wait_ms", "http_under_lock_ms", "yield_ms", "completed_monotonic"):
            value = timing.get(key)
            row[key] = round(value, 3) if type(value) in (int, float) and 0 <= value < float("inf") else None
        self.history.append(row)

    def snapshot(self):
        return dict(source="WINDOWS_CLIENT_TIMING", physical_cause_proven=False,
                    counts=dict(self.counts), history=list(self.history))


def exception_outcome(error):
    """Fixed classifications only, including errors raised while reading a body."""
    if isinstance(error, CoordinationBusy):
        return error.code
    if isinstance(error, HTTPError):
        return {401: "http_401", 403: "http_403"}.get(error.code, "http_error")
    if isinstance(error, URLError):
        return "timeout" if isinstance(error.reason, TimeoutError) else "network_error"
    if isinstance(error, TimeoutError):
        return "timeout"
    if isinstance(error, OSError):
        return "network_error"
    if isinstance(error, http.client.HTTPException):
        return "protocol_error"
    # shino_qualify raises sanitized failures inside the response context.
    diagnostic = getattr(error, "diagnostic", {})
    if isinstance(diagnostic, dict) and diagnostic.get("code") == "HTTP_STATUS":
        return {401: "http_401", 403: "http_403"}.get(diagnostic.get("http_status"), "http_error")
    return "json_invalid" if isinstance(error, (ValueError, UnicodeError)) else "client_error"


class CoordinationBusy(OSError):
    """Local HTTP coordinator unavailable. Message never includes paths."""
    def __init__(self, message, *, code="coordination_unavailable"):
        super().__init__(message)
        self.code = code


def _safe_host(host: str) -> str:
    if type(host) is not str:
        raise ValueError("Invalid private IPv4 target")
    try:
        address = ipaddress.IPv4Address(host)
    except ipaddress.AddressValueError as exc:
        raise ValueError("Invalid private IPv4 target") from exc
    # Exactly RFC1918 ranges, not loopback or public IPs.
    if not (address in ipaddress.ip_network("10.0.0.0/8")
            or address in ipaddress.ip_network("172.16.0.0/12")
            or address in ipaddress.ip_network("192.168.0.0/16")):
        raise ValueError("Target must be RFC1918 IPv4")
    return str(address)


def _lock_directory() -> Path:
    root = os.environ.get("LOCALAPPDATA")
    if root:
        return Path(root) / "SHINO-TV"
    return Path.home() / "AppData" / "Local" / "SHINO-TV" if os.name == "nt" else Path.home() / ".local" / "share" / "SHINO-TV"


@contextmanager
def digest_exchange(host: str, *, wait_seconds: float = 1.5,
                    directory: Path | None = None, timing=None):
    """Exclusive, finite lock on one logical HTTP operation. No network.

    directory is an offline-test injection point, not an environment override.
    On process death the OS releases the lock. The lock file remains forever
    to avoid unlink/recreate races between independent Windows processes.
    """
    host = _safe_host(host)
    if type(wait_seconds) not in (int, float) or not 0 <= wait_seconds <= 3:
        raise ValueError("Invalid bounded coordinator deadline")
    root = Path(directory) if directory is not None else _lock_directory()
    started = time.monotonic()
    acquired = None
    if timing is not None:
        timing.update(lock_wait_ms=0.0, http_under_lock_ms=None)
    try:
        if root.is_symlink():
            raise CoordinationBusy("Local coordinator path rejected")
        root.mkdir(parents=True, exist_ok=True)
        if not root.is_dir() or root.is_symlink():
            raise CoordinationBusy("Local coordinator path rejected")
        filename = root / ("digest-" + host.replace(".", "-") + ".lock")
        if filename.is_symlink():
            raise CoordinationBusy("Local coordinator path rejected")
        # Exclusive byte lock. No secrets and no unlink-on-release.
        with filename.open("a+b") as fp:
            fp.seek(0, os.SEEK_END)
            if fp.tell() == 0:
                fp.write(b"\0")
                fp.flush()
            deadline = time.monotonic() + wait_seconds
            locked = False
            while not locked:
                fp.seek(0)
                try:
                    if os.name == "nt":
                        import msvcrt
                        msvcrt.locking(fp.fileno(), msvcrt.LK_NBLCK, 1)
                    else:
                        import fcntl
                        fcntl.flock(fp.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
                    locked = True
                except OSError as exc:
                    contested = exc.errno in (errno.EACCES, errno.EAGAIN) or getattr(exc, "winerror", None) in (33, 36)
                    if not contested:
                        raise CoordinationBusy("Local coordinator unavailable") from None
                    if time.monotonic() >= deadline:
                        raise CoordinationBusy("Local coordinator busy", code="coordination_busy") from None
                    time.sleep(min(0.025, max(0, deadline - time.monotonic())))
            acquired = time.monotonic()
            if timing is not None:
                timing["lock_wait_ms"] = max(0, acquired - started) * 1000
            try:
                yield
            finally:
                fp.seek(0)
                if os.name == "nt":
                    msvcrt.locking(fp.fileno(), msvcrt.LK_UNLCK, 1)
                else:
                    fcntl.flock(fp.fileno(), fcntl.LOCK_UN)
    except CoordinationBusy:
        raise
    except OSError:
        if acquired is not None:
            raise  # An HTTP/body error is not a local lock acquisition failure.
        raise CoordinationBusy("Local coordinator unavailable") from None
    finally:
        if timing is not None:
            completed = time.monotonic()
            timing["completed_monotonic"] = completed
            if acquired is None:
                timing["lock_wait_ms"] = max(0, completed - started) * 1000
            else:
                timing["http_under_lock_ms"] = max(0, completed - acquired) * 1000


class CoordinatedReader:
    """Drop-in Transport.reader wrapper preserving urllib context semantics."""
    def __init__(self, reader, host: str, *, diagnostics=None, read_gap_seconds=0,
                 clock=time.monotonic, sleep=time.sleep):
        self.reader = reader
        self.host = _safe_host(host)
        if type(read_gap_seconds) not in (int, float) or not 0 <= read_gap_seconds <= 3:
            raise ValueError("Invalid bounded read gap")
        self.diagnostics = diagnostics
        self.read_gap_seconds = read_gap_seconds
        self.clock = clock
        self.sleep = sleep
        self.last_completed = None
        self.last_exchange = None

    @contextmanager
    def open(self, request, timeout=5):
        # Wait OUTSIDE the Digest lock. Default zero preserves historical B2.
        yield_started = self.clock()
        if self.last_completed is not None:
            remaining = self.last_completed + self.read_gap_seconds - self.clock()
            while remaining > 0:
                self.sleep(remaining)
                remaining = self.last_completed + self.read_gap_seconds - self.clock()
        timing = dict(yield_ms=max(0, self.clock() - yield_started) * 1000)
        outcome, status = "client_error", None
        try:
            with digest_exchange(self.host, timing=timing):
                try:
                    with self.reader.open(request, timeout=timeout) as response:
                        status = getattr(response, "status", None)
                        yield response
                        outcome = "http_200" if status == 200 else "http_error"
                except HTTPError as error:
                    error.close()  # Finish error cleanup before releasing the lock.
                    raise
        except Exception as error:
            outcome = exception_outcome(error)
            if isinstance(error, HTTPError):
                status = error.code
            raise
        finally:
            self.last_completed = self.clock()
            self.last_exchange = dict(timing, outcome=outcome)
            if self.diagnostics is not None:
                url = getattr(request, "full_url", "")
                operation = next((name for path, name in OPERATIONS.items()
                                  if url == "http://" + self.host + path), "OTHER")
                self.diagnostics.record(operation, outcome, timing, status)
