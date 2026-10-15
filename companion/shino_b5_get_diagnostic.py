"""Bounded B5 diagnostic GETs. Default CLI is offline; no receipt or marker.

Future physical reads require separate owner approval AND --authorize-read.
Reuse reviewed Digest arithmetic and the shared Windows coordinator. Every
operation starts anonymously with fresh authentication state: one valid 401,
one authorized GET, no urllib authentication retry. The 6 s budget includes
pacing, lock acquisition, negotiation, full body validation and exchange close.
"""
from __future__ import annotations

import argparse
import http.client
import ipaddress
import json
import re
import socket
import threading
import time
from dataclasses import dataclass, field
from pathlib import Path
from urllib.error import HTTPError, URLError
from urllib.request import (
    HTTPHandler, HTTPPasswordMgrWithDefaultRealm, ProxyHandler, Request,
    build_opener, parse_http_list, parse_keqv_list,
)

from provision_home_wifi import WifiDigest
from push_fsless_metrics import NoRedirect
from shino_digest_coord import CoordinatedReader, CoordinationBusy, _safe_host
from shino_update import DEFAULT_IDENTITY, inspect, load_identity, unique

HOST = "192.168.4.1"
REALM = "SHINO-StageA"
PATHS = ("/api/v1/update/status", "/api/v1/lan/status",
         "/api/v1/m9/normal/resources")
BODY_LIMIT = 4096
PHASE_SECONDS = 3.0
OPERATION_SECONDS = 6.0
READ_GAP_SECONDS = 2.25


class DiagnosticStop(ValueError):
    """Only a fixed code leaves the transport; never an HTTP exception/body."""
    def __init__(self, code):
        super().__init__(code)
        self.code = code


@dataclass
class Exchange:
    path: str
    request_attempts: int = 0
    wire_gets_sent: int = 0
    http_401_received: int = 0
    valid_challenges_received: int = 0
    authorization_attempts: int = 0
    authorizations_sent: int = 0
    http_200_received: int = 0
    get_200_confirmed: int = 0
    final_http_status: int | None = None
    events: list = field(default_factory=list)
    guard: object = None

    def summary(self):
        return {"operation": "GET " + self.path,
                **{key: getattr(self, key) for key in (
                    "request_attempts", "wire_gets_sent", "http_401_received",
                    "valid_challenges_received", "authorization_attempts",
                    "authorizations_sent", "http_200_received",
                    "get_200_confirmed", "final_http_status")},
                "events": list(self.events)}


class Deadline:
    """One budget from get() entry through lock wait, body and close."""
    def __init__(self, clock=time.monotonic, timer_factory=threading.Timer):
        self.clock = clock
        self.until = clock() + OPERATION_SECONDS
        self.expired = threading.Event()
        self.sockets = []
        self.timer = timer_factory(OPERATION_SECONDS, self.abort)
        self.timer.daemon = True
        self.timer.start()

    def abort(self):
        self.expired.set()
        for peer in tuple(self.sockets):
            try:
                peer.shutdown(socket.SHUT_RDWR)
            except OSError:
                pass

    def check(self):
        if self.expired.is_set() or self.clock() >= self.until:
            raise DiagnosticStop("TIMEOUT")

    def register(self, peer):
        self.sockets.append(peer)
        self.check()

    def timeout(self):
        self.check()
        return min(PHASE_SECONDS, self.until - self.clock())

    def close(self):
        self.timer.cancel()


def check_request(req, base):
    if req.get_method() != "GET" or req.data is not None:
        raise DiagnosticStop("GET_ONLY")
    if req.full_url not in {base + path for path in PATHS}:
        raise DiagnosticStop("ENDPOINT_NOT_ALLOWED")


def check_challenge(headers):
    values = headers.get_all("WWW-Authenticate", [])
    if len(values) != 1:
        raise DiagnosticStop("INVALID_DIGEST_CHALLENGE")
    value = values[0]
    if not isinstance(value, str) or len(value) > 512 or not value.startswith("Digest "):
        raise DiagnosticStop("INVALID_DIGEST_CHALLENGE")
    parts = parse_http_list(value[7:])
    names = [part.split("=", 1)[0].strip() for part in parts]
    if (len(names) != len(set(names)) or any("=" not in part for part in parts)
            or set(names) - {"realm", "nonce", "opaque", "qop", "algorithm", "stale"}):
        raise DiagnosticStop("INVALID_DIGEST_CHALLENGE")
    fields = parse_keqv_list(parts)
    if (fields.get("realm") != REALM or fields.get("qop") != "auth"
            or fields.get("algorithm", "MD5") != "MD5"
            or fields.get("stale", "false") not in ("true", "false")
            or any(not re.fullmatch(r"[0-9a-f]{32}", fields.get(k, ""))
                   for k in ("nonce", "opaque"))):
        raise DiagnosticStop("INVALID_DIGEST_CHALLENGE")
    return fields


class GetDigest(WifiDigest):
    """Use existing arithmetic, without inherited cache or auth retry logic."""
    def __init__(self, manager, base, current):
        super().__init__(manager, base)
        self.current = current

    def http_request(self, req):
        check_request(req, self.root)
        self.current().guard.check()
        return req  # Never inject a previous operation's cached challenge.

    def http_error_401(self, req, fp, code, msg, headers):
        state = self.current()
        state.http_401_received += 1
        try:
            check_request(req, self.root)
            if state.http_401_received > 1:
                raise DiagnosticStop("SECOND_401")
            challenge = check_challenge(headers)
            state.valid_challenges_received += 1
            state.events.append("challenge_received")
        finally:
            fp.close()  # Close the challenge response inside the Digest lock.
        state.guard.check()
        # Only the reviewed calculation is reused. Do not enter urllib's
        # recursive retry_http_digest_auth or retain its challenge cache.
        authorization = self.get_authorization(req, challenge)
        if not authorization:
            raise DiagnosticStop("INVALID_DIGEST_CHALLENGE")
        req.add_unredirected_header(self.auth_header, "Digest " + authorization)
        return self.parent.open(req, timeout=state.guard.timeout())


class GetConnection:
    """Gate every HTTPConnection.request before it can send any bytes."""
    def __init__(self, delegate, state):
        self.delegate, self.state = delegate, state

    @property
    def sock(self):
        return self.delegate.sock

    @sock.setter
    def sock(self, value):
        self.delegate.sock = value

    def set_debuglevel(self, level):
        if level:
            raise DiagnosticStop("DEBUG_DISABLED")
        self.delegate.set_debuglevel(0)

    def request(self, method, url, body, headers, **kwargs):
        if method != "GET" or body is not None or url not in PATHS:
            raise DiagnosticStop("GET_ONLY")
        if url != self.state.path:
            raise DiagnosticStop("ENDPOINT_NOT_ALLOWED")
        if self.state.request_attempts >= 2:
            raise DiagnosticStop("REQUEST_LIMIT")
        authorized = any(name.lower() == "authorization" for name in headers)
        if authorized and self.state.authorization_attempts:
            raise DiagnosticStop("AUTHORIZATION_LIMIT")
        if (self.state.request_attempts == 0 and authorized or
                self.state.request_attempts == 1 and
                (not authorized or self.state.http_401_received != 1 or
                 self.state.valid_challenges_received != 1)):
            raise DiagnosticStop("DIGEST_SEQUENCE_HOLD")
        self.state.guard.check()
        # Reserve BEFORE connect/send: a partial write cannot permit retry.
        self.state.request_attempts += 1
        if authorized:
            self.state.authorization_attempts += 1
        self.delegate.connect()
        self.state.guard.register(self.delegate.sock)
        self.delegate.request(method, url, body, headers, **kwargs)
        self.state.wire_gets_sent += 1
        if authorized:
            self.state.authorizations_sent += 1
            self.state.events.append("authorization_sent")

    def getresponse(self):
        self.state.guard.check()
        response = self.delegate.getresponse()
        try:
            self.state.guard.check()
        except DiagnosticStop:
            response.close()
            raise
        self.state.final_http_status = response.status
        if response.status == 200:
            self.state.http_200_received += 1
        return response

    def close(self):
        self.delegate.close()


class GetHTTPHandler(HTTPHandler):
    def __init__(self, owner, connection_factory):
        super().__init__()
        self.owner, self.connection_factory = owner, connection_factory

    def http_open(self, req):
        check_request(req, self.owner.base)
        state = self.owner.current
        def connect(host, timeout):
            delegate = self.connection_factory(host, timeout=state.guard.timeout())
            return GetConnection(delegate, state)
        return self.do_open(connect, req)


class GuardedResponse:
    def __init__(self, response, guard):
        self.response, self.guard = response, guard
        self.status, self.headers = response.status, response.headers

    def read(self, n):
        self.guard.check()
        data = self.response.read(n)
        self.guard.check()
        return data

    def __enter__(self):
        return self

    def __exit__(self, *args):
        self.close()

    def close(self):
        self.response.close()  # Deadline remains active until OS lock release.


class RawReader:
    """Use the existing operation deadline after the shared lock is acquired."""
    def __init__(self, owner, opener):
        self.owner, self.opener = owner, opener

    def open(self, request, timeout):
        check_request(request, self.owner.base)
        state = self.owner.current
        state.guard.check()
        return GuardedResponse(self.opener.open(request, timeout=state.guard.timeout()),
                               state.guard)


def integers(data, fields):
    if any(type(data.get(k)) is not int or data[k] < 0 for k in fields):
        raise DiagnosticStop("INVALID_SCHEMA")


def booleans(data, fields):
    if any(type(data.get(k)) is not bool for k in fields):
        raise DiagnosticStop("INVALID_SCHEMA")


RESOURCE_INTS = (
    "checked_file_count", "checked_payload_bytes", "blocked_write_attempts",
    "setup_cont_stack_min", "fs_config_cont_stack_min", "runtime_cont_stack_min",
    "free_heap", "largest_block", "fragmentation_percent", "lowest_heap",
    "lowest_block", "highest_fragmentation_percent", "resource_sample_count",
    "rejected_sample_count", "heap_floor", "block_floor", "continuation_floor",
    "fragmentation_ceiling", "telemetry_ttl_ms",
)
RESOURCE_BOOLS = (
    "config_loaded_readonly", "private_ap_ready", "mount_attempted",
    "autoformat_disabled", "mounted", "inventory_exact", "config_seed_exact",
    "resource_measurements_valid", "design_floors_observed",
)


class B5GetDiagnostic:
    def __init__(self, identity, release, host=HOST, *,
                 connection_factory=http.client.HTTPConnection,
                 clock=time.monotonic, sleep=time.sleep, timer_factory=threading.Timer):
        self.host = _safe_host(host)
        self.base = "http://" + self.host
        if identity.get("device") != release.get("device"):
            raise DiagnosticStop("LOCAL_IDENTITY_MISMATCH")
        self.release, self.clock, self.timer_factory = release, clock, timer_factory
        self.current, self.last_boot, self.stopped = None, None, False
        self.operations = []
        self.busy = threading.Lock()
        self.digest_password = identity["digest_password"]
        self.connection_factory = connection_factory
        self.digest = None
        self.reader = CoordinatedReader(RawReader(self, self.fresh_opener()), self.host,
                                        read_gap_seconds=READ_GAP_SECONDS,
                                        clock=clock, sleep=sleep)

    def fresh_opener(self):
        """Rebuild manager, Digest handler and opener for one operation only."""
        manager = HTTPPasswordMgrWithDefaultRealm()
        manager.add_password(REALM, self.base, "shino", self.digest_password)
        self.digest = GetDigest(manager, self.base, lambda: self.current)
        return build_opener(ProxyHandler({}), NoRedirect(), self.digest,
                            GetHTTPHandler(self, self.connection_factory))

    def validate(self, path, data):
        if not isinstance(data, dict):
            raise DiagnosticStop("INVALID_SCHEMA")
        if path == PATHS[0]:
            r = self.release
            tag = f"SHINO-HTTP-OTA-1|{r['device']}|{r['build_id']}|4m2m|APP_ONLY"
            if (any(data.get(k) != r[k] for k in ("device", "sha256", "build_id", "bytes"))
                    or data.get("protocol") != r["protocol"] or data.get("descriptor") != tag):
                raise DiagnosticStop("RUNNING_IDENTITY_MISMATCH")
            for key in ("boot_id", "nonce"):
                if not isinstance(data.get(key), str) or not re.fullmatch(r"[0-9a-f]{32}", data[key]):
                    raise DiagnosticStop("INVALID_SCHEMA")
            if self.last_boot is not None and self.last_boot != data["boot_id"]:
                raise DiagnosticStop("UNEXPECTED_REBOOT")
            fields = ("bytes", "heap", "block", "stack", "frag", "fs_files", "fs_bytes",
                      "ota_heap_min", "ota_block_min", "ota_stack_min", "ota_frag_max")
            integers(data, fields)
            booleans(data, ("ota_enabled", "fs_ok", "metrics_fresh"))
            if (not data["block"] <= data["heap"] <= 81920 or data["stack"] > 4096
                    or data["frag"] > 100):
                raise DiagnosticStop("INVALID_SCHEMA")
            if not data["fs_ok"] or data["fs_files"] != 24 or data["fs_bytes"] != 181402:
                raise DiagnosticStop("LITTLEFS_HOLD")
            if (data["heap"] < 25600 or data["block"] < 16384 or data["stack"] < 2048
                    or data["frag"] > 25):
                raise DiagnosticStop("RESOURCE_FLOOR_FAILED")
            if data.get("last_update") != "NONE":
                raise DiagnosticStop("OTA_STATE_HOLD")
            self.last_boot = data["boot_id"]
            return {"identity_matches_release": True, **{k: data[k] for k in fields},
                    **{k: data[k] for k in ("ota_enabled", "fs_ok", "metrics_fresh", "last_update")}}
        if path == PATHS[1]:
            # B5: four exact fields. B5.1/B5.2: eight exact fields;
            # B5.2 retains the B5.1 handler's literal firmware="B5.1".
            fields = set(data)
            legacy = {"state", "lan_ip", "sta_online", "ota_protocol"}
            extended = legacy | {"credential_state", "connection",
                                 "provision", "firmware"}
            if fields not in (legacy, extended):
                raise DiagnosticStop("INVALID_SCHEMA")
            string_keys = ("state", "lan_ip", "ota_protocol")
            if fields == extended:
                string_keys += ("credential_state", "connection",
                                "provision", "firmware")
            if any(type(data[k]) is not str for k in string_keys):
                raise DiagnosticStop("INVALID_SCHEMA")
            booleans(data, ("sta_online",))
            states = {"NO_SAVED_WIFI", "STA_CONNECTING", "AP_RECOVERY_RETRY", "STA_ONLINE"}
            if data["state"] not in states or data["ota_protocol"] != "shino-http-ota-1":
                raise DiagnosticStop("LAN_STATE_HOLD")
            address = data["lan_ip"]
            # Core 3.1.2 renders an unset IPAddress as this exact sentinel.
            if address != "(IP unset)":
                try:
                    address = str(ipaddress.IPv4Address(address))
                except (ValueError, TypeError):
                    raise DiagnosticStop("INVALID_SCHEMA") from None
            if data["sta_online"] == (address in ("0.0.0.0", "(IP unset)")):
                raise DiagnosticStop("LAN_STATE_HOLD")
            result = {"state": data["state"], "sta_online": data["sta_online"],
                      "lan_ip": address, "wifi_storage_proven": False}
            if fields == extended:
                # All values below are emitted by the reviewed B5Lan.cpp;
                # do not accept arbitrary new enum labels/firmware IDs.
                storage = {"EMPTY", "VERIFIED", "INVALID", "UNKNOWN"}
                connection = {
                    "NOT_STARTED", "LAYOUT_HOLD", "MEMORY_HOLD",
                    "SDK_READ_FAILED", "STA_ENABLE_FAILED", "SAVED_WIFI_INVALID",
                    "SDK_CURRENT_CONFIG_FAILED", "DHCP_START_FAILED",
                    "STA_CONNECT_FAILED", "WAIT_ASSOCIATION_OR_DHCP",
                    "STA_ONLINE", "STA_AUTH_REJECTED", "STA_NO_SSID"
                }
                provision = {
                    "NOT_ATTEMPTED", "PROVISION_VERIFIED", "PROVISION_AP_STATE",
                    "PROVISION_INTENT_INVALID", "PROVISION_PAYLOAD_INVALID",
                    "PROVISION_LAYOUT_UNSAFE", "PROVISION_STA_ENABLE_FAILED",
                    "PROVISION_MEMORY_HOLD", "PROVISION_SDK_READ_FAILED",
                    "PROVISION_SDK_WRITE_FAILED_UNKNOWN",
                    "PROVISION_READBACK_FAILED_UNKNOWN",
                    "PROVISION_READBACK_MISMATCH_UNKNOWN"
                }
                if (data["credential_state"] not in storage
                        or data["connection"] not in connection
                        or data["provision"] not in provision
                        or data["firmware"] != "B5.1"):
                    raise DiagnosticStop("LAN_STATE_HOLD")
                # Do not promote SDK credential uncertainty, previous
                # provision failure or an unhealthy connection to PASS.
                if (data["credential_state"] != "VERIFIED"
                        or data["connection"] not in
                            {"STA_ONLINE", "WAIT_ASSOCIATION_OR_DHCP"}
                        or data["provision"] not in
                            {"NOT_ATTEMPTED", "PROVISION_VERIFIED"}):
                    raise DiagnosticStop("LAN_STATE_HOLD")
                result["wifi_storage_proven"] = True
                result["lan_extended_validated"] = True
                result["firmware_handler_label"] = "B5.1"
            return result
        integers(data, RESOURCE_INTS)
        booleans(data, RESOURCE_BOOLS)
        if (any(not data[k] for k in RESOURCE_BOOLS) or data["checked_file_count"] != 24
                or data["checked_payload_bytes"] != 181402 or data["blocked_write_attempts"]):
            raise DiagnosticStop("NORMAL_RESOURCES_OR_FS_HOLD")
        floors = dict(heap_floor=20480, block_floor=16384, continuation_floor=2048,
                      fragmentation_ceiling=25, telemetry_ttl_ms=6000)
        if (any(data[k] != v for k, v in floors.items()) or not data["resource_sample_count"]
                or data["rejected_sample_count"]
                or min(data[k] for k in ("setup_cont_stack_min", "fs_config_cont_stack_min",
                                         "runtime_cont_stack_min")) < 2048
                or min(data["lowest_heap"], data["free_heap"]) < 20480
                or min(data["lowest_block"], data["largest_block"]) < 16384
                or max(data["highest_fragmentation_percent"], data["fragmentation_percent"]) > 25):
            raise DiagnosticStop("RESOURCE_FLOOR_FAILED")
        return {k: data[k] for k in RESOURCE_INTS + RESOURCE_BOOLS}

    def get(self, path):
        if self.stopped:
            raise DiagnosticStop("SESSION_STOPPED")
        if path not in PATHS or len(self.operations) >= 3:
            self.stopped = True
            raise DiagnosticStop("ENDPOINT_OR_OPERATION_LIMIT")
        if not self.busy.acquire(blocking=False):
            raise DiagnosticStop("CLIENT_BUSY")
        self.current = Exchange(path)
        try:
            self.current.guard = Deadline(self.clock, self.timer_factory)
            self.reader.reader.opener = self.fresh_opener()
            request = Request(self.base + path, method="GET", headers={
                "Connection": "close", "Cache-Control": "no-store",
                "Accept": "application/json", "Content-Length": "0"})
            with self.reader.open(request, timeout=PHASE_SECONDS) as response:
                if response.status != 200:
                    raise DiagnosticStop("UNEXPECTED_HTTP_STATUS")
                if not self.current.authorizations_sent:
                    raise DiagnosticStop("UNAUTHENTICATED_200")
                if (self.current.wire_gets_sent != 2 or
                        self.current.authorizations_sent != 1 or
                        self.current.valid_challenges_received != 1):
                    raise DiagnosticStop("DIGEST_SEQUENCE_HOLD")
                lengths = response.headers.get_all("Content-Length", [])
                types = response.headers.get_all("Content-Type", [])
                if (len(lengths) != 1 or not re.fullmatch(r"[0-9]{1,4}", lengths[0])
                        or int(lengths[0]) > BODY_LIMIT or response.headers.get("Transfer-Encoding")
                        or len(types) != 1 or types[0].split(";", 1)[0].strip().lower() != "application/json"):
                    raise DiagnosticStop("INVALID_RESPONSE_FRAMING")
                raw = response.read(BODY_LIMIT + 1)
                if len(raw) != int(lengths[0]) or len(raw) > BODY_LIMIT:
                    raise DiagnosticStop("INVALID_RESPONSE_LENGTH")
                def nonfinite(value):
                    raise ValueError("Nonfinite JSON")
                try:
                    data = json.loads(raw, object_pairs_hook=unique, parse_constant=nonfinite)
                except (ValueError, UnicodeError):
                    raise DiagnosticStop("INVALID_JSON") from None
                shown = self.validate(path, data)
                self.current.guard.check()
            self.current.guard.check()  # Includes body close and lock release.
            self.current.get_200_confirmed = 1
            self.current.events.append("get_200_confirmed")
            return shown
        except DiagnosticStop as error:
            self.stopped = True
            self.record_hold(error.code)
            raise
        except Exception as error:
            self.stopped = True
            if (self.current.guard is not None and
                  (self.current.guard.expired.is_set() or
                   self.clock() >= self.current.guard.until)):
                code = "TIMEOUT"
            elif isinstance(error, CoordinationBusy):
                code = "COORDINATOR_UNAVAILABLE"
            elif (isinstance(error, TimeoutError) or isinstance(error, URLError)
                  and isinstance(error.reason, TimeoutError)):
                code = "TIMEOUT"
            elif isinstance(error, HTTPError):
                error.close()
                code = "UNEXPECTED_HTTP_STATUS"
            elif isinstance(error, (OSError, URLError, http.client.HTTPException)):
                code = "CONNECTION_OR_HTTP_ERROR"
            else:
                code = "CLIENT_ERROR"
            self.record_hold(code)
            raise DiagnosticStop(code) from None
        finally:
            if self.current.guard is not None:
                self.current.guard.close()
            # Destroy operation-scoped authentication material on success too.
            self.digest.challenge = None
            self.digest.last_nonce = None
            self.digest.nonce_count = self.digest.retried = 0
            self.operations.append(self.current.summary())
            self.current = None
            self.busy.release()

    def record_hold(self, code):
        event = {"INVALID_DIGEST_CHALLENGE": "challenge_invalid",
                 "SECOND_401": "second_401_hold", "TIMEOUT": "timeout_hold",
                 "COORDINATOR_UNAVAILABLE": "coordination_hold"}.get(
                     code, "response_invalid_hold")
        self.current.events.append(event)


def run_diagnostic(client):
    readings = {}
    result = {"status": "GET_READS_COMPLETE_NOT_QUALIFICATION", "post_requests": 0,
              "physical_acceptance": False, "native_B51_memory_qualified": False}
    try:
        for path in PATHS:
            readings[path] = client.get(path)
            if path == PATHS[1] and not readings[path]["sta_online"]:
                client.stopped = True
                raise DiagnosticStop("LAN_OFFLINE_HOLD")
    except DiagnosticStop as error:
        result.update(status="STOP", reason=error.code)
    result.update(readings=readings, exchanges=client.operations)
    return result


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--bin", type=Path, required=True)
    parser.add_argument("--manifest", type=Path, required=True)
    parser.add_argument("--identity", type=Path, default=DEFAULT_IDENTITY)
    parser.add_argument("--host", default=HOST)
    parser.add_argument("--authorize-read", action="store_true",
                        help="Requires separate owner approval for physical GETs.")
    args = parser.parse_args(argv)
    try:
        host = _safe_host(args.host)
        release, _ = inspect(args.bin, args.manifest)
        if not args.authorize_read:
            result = {"status": "PRINT_ONLY_NO_DEVICE_CONTACT", "endpoints": list(PATHS),
                      "max_logical_gets": 3, "max_wire_gets_per_operation": 2,
                      "max_authorized_gets_per_operation": 1,
                      "max_valid_challenges_per_operation": 1,
                      "phase_timeout_seconds": PHASE_SECONDS,
                      "operation_deadline_seconds": OPERATION_SECONDS,
                      "deadline_includes_lock_wait_and_close": True,
                      "post_requests": 0}
        else:
            identity = load_identity(args.identity)
            result = run_diagnostic(B5GetDiagnostic(identity, release, host))
    except DiagnosticStop as error:
        result = {"status": "STOP", "reason": error.code, "post_requests": 0}
    except Exception:
        result = {"status": "STOP", "reason": "LOCAL_INPUT_INVALID", "post_requests": 0}
    print(json.dumps(result, ensure_ascii=True, indent=2))
    return 2 if result["status"] == "STOP" else 0


if __name__ == "__main__":
    raise SystemExit(main())
