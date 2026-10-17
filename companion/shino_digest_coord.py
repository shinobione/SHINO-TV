"""Bounded inter-process Digest HTTP exchange coordinator (PC only).

All cooperating Windows SHINO clients share one per-target OS file lock.
Keep the lock for the complete HTTP challenge + authorization + response body.
No proxy, remote service, private credentials, firmware, or OTA operations.
A local peer holding the lock longer than the bound produces a local failure;
no HTTP retry, fallback without a lock, or forced lock-file removal.
"""
from __future__ import annotations

from contextlib import contextmanager
import errno
import ipaddress
import os
from pathlib import Path
import time


class CoordinationBusy(OSError):
    """Local HTTP coordinator unavailable. Message never includes paths."""


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
                    directory: Path | None = None):
    """Exclusive, finite lock on one logical HTTP operation. No network.

    directory is an offline-test injection point, not an environment override.
    On process death the OS releases the lock. The lock file remains forever
    to avoid unlink/recreate races between independent Windows processes.
    """
    host = _safe_host(host)
    if type(wait_seconds) not in (int, float) or not 0 <= wait_seconds <= 3:
        raise ValueError("Invalid bounded coordinator deadline")
    root = Path(directory) if directory is not None else _lock_directory()
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
                        raise CoordinationBusy("Local coordinator busy") from None
                    time.sleep(min(0.025, max(0, deadline - time.monotonic())))
            try:
                yield
            finally:
                fp.seek(0)
                if os.name == "nt":
                    msvcrt.locking(fp.fileno(), msvcrt.LK_UNLCK, 1)
                else:
                    fcntl.flock(fp.fileno(), fcntl.LOCK_UN)
    except (PermissionError, FileNotFoundError, IsADirectoryError) as exc:
        raise CoordinationBusy("Local coordinator unavailable") from None


class CoordinatedReader:
    """Drop-in Transport.reader wrapper preserving urllib context semantics."""
    def __init__(self, reader, host: str):
        self.reader = reader
        self.host = _safe_host(host)

    @contextmanager
    def open(self, request, timeout=5):
        with digest_exchange(self.host):
            with self.reader.open(request, timeout=timeout) as response:
                yield response
