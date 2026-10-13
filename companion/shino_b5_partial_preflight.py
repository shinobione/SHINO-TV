"""Owner partial OTA prequalification. CLI is local inspection by default.

Future partial POST and later evidence GET are separate, explicitly gated modes.
No firmware install(), response polling, restart, Wi-Fi or recovery operation.
The peer can write staging: this is NOT a harmless read or a successful OTA.
"""
from __future__ import annotations

import argparse
from contextlib import contextmanager
from dataclasses import dataclass, field
import http.client
import json
import os
from pathlib import Path
import re
import socket
import stat
import threading
import time

from shino_update import HOST, inspect, load_identity, signature, unique
import shino_digest_coord as coordination
from shino_digest_coord import CoordinationBusy, digest_exchange
from shino_b5_get_diagnostic import (
    B5GetDiagnostic, Deadline, DiagnosticStop, PATHS, booleans, integers,
)

BODY_CAP = 8192
CANDIDATE_BYTES = 414176
UPDATE_PATH = "/api/v1/update"
MINIMA = ("ota_heap_min", "ota_block_min", "ota_stack_min", "ota_frag_max")
IDENTITY_FIELDS = ("device", "build_id", "sha256", "bytes")
LAYOUT = {"_FS_start": 0x40400000, "_FS_end": 0x405FA000,
          "_EEPROM_start": 0x405FB000}
LAST_STATES = {"NONE", "REFUSED", "RECEIVING", "FAILED_NO_COMMIT", "STAGED"}


class Stop(ValueError):
    """Fixed codes only; never retain a server body, path or raw exception."""


def _ap_host(host):
    if type(host) is not str or host != HOST:
        raise Stop("AP_HOST_REQUIRED")
    return HOST


def bounded_json(path, limit=32768):
    path = Path(path)
    if path.is_symlink() or not path.is_file() or path.stat().st_size > limit:
        raise Stop("LOCAL_FILE_HOLD")
    return json.loads(path.read_text(encoding="utf-8"), object_pairs_hook=unique)


@dataclass(frozen=True, repr=False)
class Artifacts:
    candidate: dict
    current: dict
    prefix: bytes = field(repr=False)
    inputs: tuple = field(repr=False)

    def summary(self):
        rounded = (self.candidate["bytes"] + 4095) & ~4095
        return dict(status="LOCAL_INSPECTION_ONLY", current=self.current,
                    candidate=self.candidate, content_length=self.candidate["bytes"],
                    body_cap=BODY_CAP, staging_start=0x200000-rounded,
                    first_sector_end=0x200000-rounded+4096,
                    device_contacts=0, ota_success=False, physical_acceptance=False)


def prepare(candidate_bin, candidate_manifest, candidate_report,
            current_bin, current_manifest, current_report):
    """Real BIN SHA/CRC/segments/descriptor checks; no keys or network needed."""
    try:
        candidate, raw = inspect(candidate_bin, candidate_manifest)
        current, _ = inspect(current_bin, current_manifest)
        for manifest, report_path in ((candidate, candidate_report), (current, current_report)):
            report = bounded_json(report_path)
            if (any(report.get(k) != manifest[k] for k in (*IDENTITY_FIELDS, "layout", "protocol"))
                    or report.get("layout_symbols") != LAYOUT
                    or not re.fullmatch(r"[0-9a-f]{40}", report.get("source_commit", ""))):
                raise Stop("REPORT_IDENTITY_OR_LAYOUT_HOLD")
        if (bounded_json(candidate_report).get("firmware") != "B5.1"
                or candidate["bytes"] != CANDIDATE_BYTES
                or candidate["device"] != current["device"]
                or candidate["sha256"] == current["sha256"]
                or candidate["build_id"] == current["build_id"]):
            raise Stop("CANDIDATE_IDENTITY_OR_SIZE_HOLD")
        if 0x200000-((len(raw)+4095)&~4095) < ((current["bytes"]+4095)&~4095)+4096:
            raise Stop("STAGING_LAYOUT_HOLD")
        paths = tuple(Path(p).resolve() for p in (candidate_bin, candidate_manifest,
                      candidate_report, current_bin, current_manifest, current_report))
        return Artifacts(candidate, current, bytes(raw[:BODY_CAP]), paths)
    except Stop:
        raise
    except Exception:
        raise Stop("LOCAL_ARTIFACT_HOLD") from None


def status_payload(data):
    """Validate shape, retain unsafe measurements for a HOLD evidence record."""
    if not isinstance(data, dict):
        raise DiagnosticStop("INVALID_SCHEMA")
    for name, length in (("device", 16), ("build_id", 64), ("sha256", 64),
                         ("boot_id", 32), ("nonce", 32)):
        if not isinstance(data.get(name), str) or not re.fullmatch("[0-9a-f]{%d}" % length, data[name]):
            raise DiagnosticStop("INVALID_SCHEMA")
    if (data.get("protocol") != "shino-http-ota-1"
            or data.get("descriptor") != f"SHINO-HTTP-OTA-1|{data['device']}|{data['build_id']}|4m2m|APP_ONLY"
            or data.get("last_update") not in LAST_STATES):
        raise DiagnosticStop("INVALID_SCHEMA")
    ints = ("bytes", "heap", "block", "stack", "frag", "fs_files", "fs_bytes", *MINIMA)
    bools = ("ota_enabled", "fs_ok", "metrics_fresh")
    integers(data, ints)
    booleans(data, bools)
    if (not 64000 <= data["bytes"] <= 0xFEFF0 or data["block"] > data["heap"]
            or data["heap"] > 81920 or data["stack"] > 4096 or data["frag"] > 100
            or data["ota_block_min"] > data["ota_heap_min"]
            or data["ota_heap_min"] > 81920 or data["ota_stack_min"] > 4096
            or data["ota_frag_max"] > 100):
        raise DiagnosticStop("INVALID_SCHEMA")
    return {k: data[k] for k in (*IDENTITY_FIELDS, "protocol", "descriptor", "boot_id",
                                "nonce", "last_update", *ints, *bools)}


class ImmediateReader:
    """Keep the inherited full-body transport; refuse a contested owner immediately."""
    def __init__(self, reader, host):
        self.reader, self.host = reader, _ap_host(host)

    @contextmanager
    def open(self, request, timeout):
        host = _ap_host(self.host)
        if request.full_url != "http://"+host+PATHS[0]:
            raise Stop("AP_STATUS_ENDPOINT_REQUIRED")
        with digest_exchange(host, wait_seconds=0):
            with self.reader.open(request, timeout) as response:
                yield response


class StatusReader(B5GetDiagnostic):
    """One bounded Digest operation; same lock and transport, no last_update gate."""
    def __init__(self, identity, release, host=HOST, **kwargs):
        super().__init__(identity, release, _ap_host(host), **kwargs)
        self._secrets = tuple(identity[k] for k in ("ap_psk", "api_token", "digest_password",
                              "maintenance_password") if identity.get(k))
        self.reader = ImmediateReader(self.reader.reader, self.host)

    def validate(self, path, data):
        if path != PATHS[0]:
            raise DiagnosticStop("ENDPOINT_NOT_ALLOWED")
        shown = status_payload(data)
        if any(secret in json.dumps(shown, ensure_ascii=True) for secret in self._secrets):
            raise DiagnosticStop("SECRET_RESPONSE_HOLD")
        return shown

    def get(self, path):
        _ap_host(self.host)
        if path != PATHS[0] or self.operations:
            raise DiagnosticStop("SESSION_STOPPED")
        return super().get(path)


def public_status(data):
    return {k: v for k, v in data.items() if k != "nonce"}


def _new_output(path, protected=()):
    path = Path(path)
    if (path.is_symlink() or path.exists() or not path.parent.is_dir()
            or path.parent.is_symlink() or path.resolve() in protected):
        raise Stop("OUTPUT_EXISTS_OR_UNSAFE")
    return path


def write_new(path, data):
    """Exclusive, durable, sanitized record. Never overwrite or unlink on error."""
    with Path(path).open("x", encoding="utf-8") as out:
        json.dump(data, out, ensure_ascii=True, sort_keys=True)
        out.write("\n")
        out.flush()
        os.fsync(out.fileno())


def _attempt_directory(root):
    """Reject inaccessible, redirected or non-directory durable state."""
    try:
        for parent in (root, *root.parents):
            try:
                state = parent.lstat()
            except FileNotFoundError:
                continue
            if (not stat.S_ISDIR(state.st_mode)
                    or getattr(state, "st_file_attributes", 0) & 0x400):
                raise Stop("ATTEMPT_STATE_UNKNOWN_NO_RETRY")
    except OSError:
        raise Stop("ATTEMPT_STATE_UNKNOWN_NO_RETRY") from None


def _attempt_path(artifacts):
    # Shared per-user state, never derived from the caller's marker or BIN path.
    root = Path(coordination._lock_directory()) / "b5-partial-attempts"
    _attempt_directory(root)
    candidate = artifacts.candidate
    return root / (candidate["device"]+"-"+candidate["sha256"]+".attempt")


def _unused_attempt(path):
    try:
        path.lstat()
    except FileNotFoundError:
        return
    except OSError:
        raise Stop("ATTEMPT_STATE_UNKNOWN_NO_RETRY") from None
    # Even an empty, corrupt or incomplete reservation burns the candidate.
    raise Stop("CANDIDATE_ALREADY_ATTEMPTED_NO_RETRY")


def _reserve_attempt(path, context):
    try:
        path.parent.mkdir(parents=True, exist_ok=True)
        _attempt_directory(path.parent)
        write_new(path, context)  # Atomic exclusive create, then flush/fsync.
    except FileExistsError:
        raise Stop("CANDIDATE_ALREADY_ATTEMPTED_NO_RETRY") from None
    except OSError:
        raise Stop("ATTEMPT_STATE_UNKNOWN_NO_RETRY") from None
    # Never remove a reservation, including after fsync/marker/transport failure.


def _identity(path, artifacts):
    try:
        value = load_identity(path)
        if value["device"] != artifacts.current["device"]:
            raise Stop("OWNER_IDENTITY_HOLD")
        return value
    except Stop:
        raise
    except Exception:
        raise Stop("OWNER_IDENTITY_HOLD") from None


def _matches(data, manifest):
    return all(data[k] == manifest[k] for k in IDENTITY_FIELDS)


def _fs_ok(data):
    return data["fs_ok"] and data["fs_files"] == 24 and data["fs_bytes"] == 181402


class PartialTransport:
    """One socket/POST. Only the verified prefix ever reaches socket.send()."""
    def __init__(self, host, *, connection_factory=None, clock=time.monotonic,
                 timer_factory=threading.Timer):
        self.host = _ap_host(host)
        self.factory = connection_factory or http.client.HTTPConnection
        self.clock, self.timer_factory = clock, timer_factory
        self.used = False
        self._once = threading.Lock()
        self.sent = self.upper = self.posts = 0

    def send(self, artifacts, identity, nonce):
        _ap_host(self.host)
        if not self._once.acquire(blocking=False):
            raise Stop("SECOND_POST_FORBIDDEN")
        # Deliberately never release: a failed or concurrent call cannot rearm it.
        self.used = True  # Burn before any possibly uncertain connection/header write.
        if len(artifacts.prefix) != BODY_CAP or artifacts.candidate["bytes"] != CANDIDATE_BYTES:
            raise Stop("BODY_CAP_OR_IMAGE_SIZE_HOLD")
        headers = {"Content-Type": "application/octet-stream",
                   "Content-Length": str(artifacts.candidate["bytes"]), "Connection": "close",
                   "X-Shino-SHA256": artifacts.candidate["sha256"],
                   "X-Shino-Build": artifacts.candidate["build_id"], "X-Shino-Nonce": nonce,
                   "X-Shino-Proof": signature(identity, nonce, artifacts.candidate)}
        guard = Deadline(self.clock, self.timer_factory)
        connection = None
        try:
            # No wait/retry if another cooperating HTTP owner holds the lock.
            with digest_exchange(self.host, wait_seconds=0):
                guard.check()
                connection = self.factory(self.host, timeout=guard.timeout())
                connection.auto_open = 0
                connection.set_debuglevel(0)
                connection.connect()
                guard.register(connection.sock)
                self.posts = 1
                connection.putrequest("POST", UPDATE_PATH, skip_accept_encoding=True)
                for key, value in headers.items():
                    connection.putheader(key, value)
                connection.endheaders()  # Headers only. No body via HTTPConnection.send().
                peer = connection.sock
                prefix = memoryview(artifacts.prefix)
                while self.sent < BODY_CAP:
                    guard.check()
                    peer.settimeout(guard.timeout())
                    chunk = prefix[self.sent:min(self.sent+512, BODY_CAP)]
                    self.upper = self.sent+len(chunk)  # Bound even if send raises after a partial write.
                    count = peer.send(chunk)
                    if type(count) is not int or not 0 < count <= len(chunk):
                        raise Stop("WRITE_RESULT_UNKNOWN_NO_RETRY")
                    self.sent += count
                    self.upper = self.sent
                    guard.check()
                # Close at the cap; never read a POST reply, flush, or send the tail.
                peer.shutdown(socket.SHUT_WR)
                connection.close()
                connection = None
                guard.check()
        finally:
            try:
                if connection is not None:
                    connection.close()
            finally:
                guard.close()


def run_partial(artifacts, identity_path, host, marker, *, authorized=False,
                confirm_sha256=None, transport=None, reader_factory=StatusReader):
    """Future owner operation only: pre-read, one partial POST, NO post-read."""
    result = dict(status="STOP_UNKNOWN_NO_RETRY", reason="UNKNOWN", ota_success=False,
                  physical_acceptance=False, automatic_retries=0, post_requests=0,
                  body_bytes_sent=0, body_bytes_upper_bound=0, body_cap=BODY_CAP,
                  receiver_bytes_confirmed=None, evidence_read_performed=False)
    wire = None
    try:
        if authorized is not True or confirm_sha256 != artifacts.candidate["sha256"]:
            raise Stop("PHYSICAL_AUTHORIZATION_REQUIRED")
        host = _ap_host(host)
        if transport is not None:
            _ap_host(transport.host)
        marker = _new_output(marker, (*artifacts.inputs, Path(identity_path).resolve()))
        attempt = _attempt_path(artifacts)
        if marker.resolve() == attempt.resolve():
            raise Stop("OUTPUT_EXISTS_OR_UNSAFE")
        _unused_attempt(attempt)  # Refuse a different marker before any GET.
        identity = _identity(identity_path, artifacts)
        before = reader_factory(identity, artifacts.current, host).get(PATHS[0])
        if not _matches(before, artifacts.current) or not _fs_ok(before):
            raise Stop("RUNNING_IDENTITY_OR_FS_HOLD")
        if (before["last_update"] != "NONE" or any(before[k] for k in MINIMA)
                or not before["ota_enabled"] or not before["metrics_fresh"]
                or before["heap"] < 25600 or before["block"] < 16384
                or before["stack"] < 2048 or before["frag"] > 25):
            raise Stop("PRECONDITIONS_HOLD")
        context = dict(schema=1, operation="B5_PARTIAL_8192_NO_RETRY", host=host,
                       current=artifacts.current, candidate=artifacts.candidate,
                       before=public_status(before), body_cap=BODY_CAP)
        _reserve_attempt(attempt, context)  # Irreversible even if marker creation fails.
        write_new(marker, context)
        wire = transport or PartialTransport(host)
        wire.send(artifacts, identity, before["nonce"])
        result.update(status="PARTIAL_CLOSED_UNCONFIRMED_HOLD", reason="SEPARATE_EVIDENCE_REQUIRED")
    except (Stop, DiagnosticStop) as error:
        result["reason"] = str(error)
    except CoordinationBusy:
        result["reason"] = "COORDINATION_HOLD"
    except (TimeoutError,):
        result["reason"] = "TIMEOUT_UNKNOWN_NO_RETRY"
    except (KeyboardInterrupt, SystemExit):
        result["reason"] = "INTERRUPTED_UNKNOWN_NO_RETRY"
    except Exception:
        result["reason"] = "IO_UNKNOWN_NO_RETRY"
    if wire is not None:
        result.update(post_requests=wire.posts, body_bytes_sent=wire.sent,
                      body_bytes_upper_bound=wire.upper)
    return result


def collect_evidence(artifacts, identity_path, host, marker, *, authorized=False,
                     reader_factory=StatusReader):
    """Separately authorized single status read. Preserve unsafe data as HOLD."""
    result = dict(status="STOP_UNKNOWN_NO_RETRY", ota_success=False,
                  physical_acceptance=False, automatic_retries=0, post_requests=0)
    try:
        if authorized is not True:
            raise Stop("READ_AUTHORIZATION_REQUIRED")
        host = _ap_host(host)
        context = bounded_json(marker)
        if (context.get("schema") != 1 or context.get("operation") != "B5_PARTIAL_8192_NO_RETRY"
                or context.get("body_cap") != BODY_CAP or context.get("host") != host
                or context.get("current") != artifacts.current
                or context.get("candidate") != artifacts.candidate):
            raise Stop("ATTEMPT_CONTEXT_HOLD")
        before = context.get("before")
        if (type(context["schema"]) is not int or not isinstance(before, dict)
                or not _matches(before, artifacts.current)
                or not isinstance(before.get("boot_id"), str)
                or not re.fullmatch(r"[0-9a-f]{32}", before["boot_id"])
                or before.get("last_update") != "NONE"):
            raise Stop("ATTEMPT_CONTEXT_HOLD")
        identity = _identity(identity_path, artifacts)
        data = reader_factory(identity, artifacts.current, host).get(PATHS[0])
        result["observations"] = public_status(data)
        if not _matches(data, artifacts.current) or data["boot_id"] != before["boot_id"]:
            raise Stop("IDENTITY_OR_BOOT_CHANGED_UNKNOWN")
        if not _fs_ok(data):
            raise Stop("LITTLEFS_HOLD")
        if data["last_update"] != "FAILED_NO_COMMIT":
            raise Stop("UNEXPECTED_OTA_STATE_HOLD")
        if (data["heap"] < 20480 or data["block"] < 16384 or data["stack"] < 2048
                or data["frag"] > 25 or data["ota_heap_min"] < 20480
                or data["ota_block_min"] < 16384 or data["ota_stack_min"] < 2048
                or data["ota_frag_max"] > 25):
            raise Stop("MINIMA_UNAVAILABLE_OR_RESOURCE_HOLD")
        result.update(status="PARTIAL_OBSERVATIONS_RECORDED_HOLD", reason="NOT_OTA_QUALIFICATION",
                      receiver_bytes_confirmed=None, staging_sectors_confirmed=None,
                      native_high_water_qualified=False)
    except (Stop, DiagnosticStop) as error:
        result["reason"] = str(error)
    except (KeyboardInterrupt, SystemExit):
        result["reason"] = "INTERRUPTED_UNKNOWN_NO_RETRY"
    except Exception:
        result["reason"] = "READ_OR_CONTEXT_UNKNOWN_NO_RETRY"
    return result


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__, allow_abbrev=False)
    parser.add_argument("--mode", choices=("inspect", "partial", "evidence"), default="inspect")
    for name in ("candidate-bin", "candidate-manifest", "candidate-report",
                 "current-bin", "current-manifest", "current-report"):
        parser.add_argument("--"+name, type=Path, required=True)
    for name in ("identity", "attempt-marker", "receipt"):
        parser.add_argument("--"+name, type=Path)
    parser.add_argument("--host")
    parser.add_argument("--confirm-sha256")
    parser.add_argument("--authorize-partial", action="store_true")
    parser.add_argument("--authorize-read", action="store_true")
    args = parser.parse_args(argv)
    try:
        if args.host is not None:
            _ap_host(args.host)
        artifacts = prepare(args.candidate_bin, args.candidate_manifest, args.candidate_report,
                            args.current_bin, args.current_manifest, args.current_report)
        if args.mode == "inspect":
            result = artifacts.summary()
        else:
            if any(getattr(args, k) is None for k in ("identity", "host", "attempt_marker", "receipt")):
                raise Stop("EXPLICIT_OWNER_INPUTS_REQUIRED")
            protected = (*artifacts.inputs, args.identity.resolve(), args.attempt_marker.resolve())
            receipt = _new_output(args.receipt, protected)
            if args.mode == "partial":
                result = run_partial(artifacts, args.identity, args.host, args.attempt_marker,
                                     authorized=args.authorize_partial, confirm_sha256=args.confirm_sha256)
            else:
                result = collect_evidence(artifacts, args.identity, args.host, args.attempt_marker,
                                          authorized=args.authorize_read)
            write_new(receipt, result)
    except (Stop, DiagnosticStop) as error:
        result = dict(status="STOP_UNKNOWN_NO_RETRY", reason=str(error), ota_success=False)
    except (KeyboardInterrupt, SystemExit):
        result = dict(status="STOP_UNKNOWN_NO_RETRY", reason="INTERRUPTED", ota_success=False)
    except Exception:
        result = dict(status="STOP_UNKNOWN_NO_RETRY", reason="LOCAL_INPUT_OR_RECORD_HOLD", ota_success=False)
    print(json.dumps(result, ensure_ascii=True, indent=2))
    return 0 if args.mode == "inspect" and result["status"] == "LOCAL_INSPECTION_ONLY" else 2


if __name__ == "__main__":
    raise SystemExit(main())
