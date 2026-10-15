"""GET-only fixtures and OS lock tests; real TCP is restricted to loopback."""
import contextlib
import hashlib
import http.client
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
import io
import json
import os
import socket
from pathlib import Path
import threading
import time
import unittest
from unittest.mock import patch
from urllib.request import Request, parse_http_list, parse_keqv_list
from email.message import Message
import tempfile

import shino_b5_get_diagnostic as target
import shino_digest_coord as coord

HOST = "192.168.4.1"
PASSWORD = "FICTITIOUS-DIGEST-TEST-PASSWORD"
RELEASE = dict(device="0123456789abcdef", bytes=65536, sha256="a" * 64,
               build_id="b" * 64, protocol="shino-http-ota-1")
IDENTITY = dict(device=RELEASE["device"], digest_password=PASSWORD)


def update_payload():
    return dict(RELEASE, descriptor="SHINO-HTTP-OTA-1|" + RELEASE["device"] + "|"
                + RELEASE["build_id"] + "|4m2m|APP_ONLY", nonce="c" * 32,
                boot_id="d" * 32, heap=30984, block=29504, stack=2128, frag=5,
                fs_ok=True, fs_files=24, fs_bytes=181402, metrics_fresh=True,
                ota_enabled=True, last_update="NONE", ota_heap_min=0,
                ota_block_min=0, ota_stack_min=0, ota_frag_max=0)


def resources_payload():
    values = {key: True for key in target.RESOURCE_BOOLS}
    values.update(checked_file_count=24, checked_payload_bytes=181402,
                  blocked_write_attempts=0, setup_cont_stack_min=2800,
                  fs_config_cont_stack_min=2400, runtime_cont_stack_min=2128,
                  free_heap=30984, largest_block=29504, fragmentation_percent=5,
                  lowest_heap=29000, lowest_block=27000, highest_fragmentation_percent=8,
                  resource_sample_count=5, rejected_sample_count=0, heap_floor=20480,
                  block_floor=16384, continuation_floor=2048, fragmentation_ceiling=25,
                  telemetry_ttl_ms=6000)
    return values


class PassiveTimer:
    def __init__(self, seconds, callback):
        self.callback, self.cancelled, self.daemon = callback, False, False
    def start(self): pass
    def cancel(self): self.cancelled = True


class FakeSocket:
    def __init__(self): self.closed, self.shutdowns = False, 0
    def close(self): self.closed = True
    def shutdown(self, how): self.shutdowns += 1


class Response(io.BytesIO):
    def __init__(self, server, status, headers, body):
        super().__init__(body)
        self.server, self.status, self.headers = server, status, headers
        self.code = status
        self.reason = "OK" if status == 200 else "Unauthorized"
        self.msg = self.reason
    def info(self): return self.headers
    def getcode(self): return self.status
    def read(self, n=-1):
        if self.server.on_read:
            self.server.on_read(self)
        return super().read(n)
    def close(self):
        if not self.closed and self.server.on_close:
            self.server.on_close(self)
        super().close()


class Server:
    """Source-equivalent Digest checks, using fixtures and only GET methods."""
    def __init__(self):
        self.generation = 0
        self.nonce, self.opaque = None, None
        self.requests = []
        self.on_read = self.on_close = None
        self.challenge_override = None
        self.always_401 = self.unauthenticated_200 = False
        self.forced_status = None
        self.body_override = self.header_override = None
        self.failure = None
        self.connections = 0
        self.fake_sockets = []
        self.payloads = {
            target.PATHS[0]: update_payload(),
            target.PATHS[1]: dict(state="NO_SAVED_WIFI", sta_online=False,
                                 lan_ip="(IP unset)", ota_protocol="shino-http-ota-1"),
            target.PATHS[2]: resources_payload(),
        }

    def challenge(self):
        self.generation += 1
        self.nonce = hashlib.md5(str(self.generation).encode()).hexdigest()
        self.opaque = hashlib.md5(("opaque-" + str(self.generation)).encode()).hexdigest()
        return (f'Digest realm="SHINO-StageA", qop="auth", nonce="{self.nonce}", '
                f'opaque="{self.opaque}"')

    def valid(self, path, headers):
        auth = headers.get("Authorization", "")
        if not auth.startswith("Digest "):
            return False
        fields = parse_keqv_list(parse_http_list(auth[7:]))
        md5 = lambda value: hashlib.md5(value.encode()).hexdigest()
        expected = md5(":".join((md5("shino:SHINO-StageA:" + PASSWORD),
                                 self.nonce or "", fields.get("nc", ""),
                                 fields.get("cnonce", ""), "auth", md5("GET:" + path))))
        return (fields.get("realm") == "SHINO-StageA" and fields.get("username") == "shino"
                and fields.get("uri") == path and fields.get("nonce") == self.nonce
                and fields.get("opaque") == self.opaque and fields.get("response") == expected)

    def response(self, path, headers):
        message = Message()
        if self.always_401 or not (self.valid(path, headers) or self.unauthenticated_200):
            status, body = 401, b""
            challenge = self.challenge()
            override = self.challenge_override
            if isinstance(override, list):
                for value in override: message["WWW-Authenticate"] = value
            else:
                message["WWW-Authenticate"] = override if override is not None else challenge
        else:
            status = self.forced_status or 200
            body = self.body_override
            if body is None: body = json.dumps(self.payloads[path]).encode()
        message["Content-Type"] = "application/json"
        message["Content-Length"] = str(len(body))
        if self.header_override: self.header_override(message)
        return Response(self, status, message, body)

    def connection(self, host, timeout):
        server = self
        assert host == HOST and 0 < timeout <= target.PHASE_SECONDS
        self.connections += 1
        number = self.connections
        def fails(phase):
            return server.failure in (phase, (phase, number))
        class Connection:
            sock = None
            response_value = None
            def set_debuglevel(self, value): assert value == 0
            def connect(self):
                if fails("connect"): raise ConnectionRefusedError(PASSWORD)
                self.sock = FakeSocket();server.fake_sockets.append(self.sock)
            def request(self, method, path, body, headers, **kwargs):
                assert method == "GET" and body is None
                if fails("send"): raise ConnectionResetError(PASSWORD)
                server.requests.append(dict(method=method, path=path,
                                            authorized="Authorization" in headers))
                self.response_value = server.response(path, headers)
            def getresponse(self):
                if fails("response"): raise TimeoutError(PASSWORD)
                return self.response_value
            def close(self):
                if self.sock: self.sock.close();self.sock = None
        return Connection()


class TestB5GetDiagnostic(unittest.TestCase):
    def setUp(self):
        # All test files stay in a new workspace-local directory, never a packet.
        workspace = Path(__file__).resolve().parents[1] / "research-local"
        self.temp = tempfile.TemporaryDirectory(prefix="b5-get-tests-", dir=workspace)
        self.directory = Path(self.temp.name).resolve()
        self.assertEqual(self.directory.parent, workspace.resolve())
        self.addCleanup(self.temp.cleanup)
        self.enterContext(patch.object(coord, "_lock_directory", return_value=self.directory))
        for name in ("socket.socket", "socket.create_connection", "socket.getaddrinfo"):
            mock = self.enterContext(patch(name, side_effect=AssertionError("NO NETWORK")))
            self.addCleanup(mock.assert_not_called)
        self.server = Server()
        self.client = self.make_client()

    def make_client(self, **kwargs):
        now = [0.0]
        kwargs.setdefault("clock", lambda: now[0])
        kwargs.setdefault("sleep", lambda delay: now.__setitem__(0, now[0] + delay))
        return target.B5GetDiagnostic(IDENTITY, RELEASE,
            connection_factory=self.server.connection,
            timer_factory=PassiveTimer, **kwargs)

    def assert_stop(self, reason, path=target.PATHS[0]):
        with self.assertRaises(target.DiagnosticStop) as caught:
            self.client.get(path)
        self.assertEqual(caught.exception.code, reason)
        self.assertTrue(self.client.stopped)
        count = len(self.server.requests)
        with self.assertRaises(target.DiagnosticStop):self.client.get(path)
        self.assertEqual(len(self.server.requests), count)
        return caught.exception

    def test_initial_challenge_then_authenticated_get(self):
        data = self.client.get(target.PATHS[0]);row = self.client.operations[-1]
        self.assertTrue(data["identity_matches_release"])
        self.assertEqual([v["authorized"] for v in self.server.requests], [False, True])
        self.assertEqual((row["valid_challenges_received"], row["authorizations_sent"],
                          row["get_200_confirmed"], row["wire_gets_sent"]), (1, 1, 1, 2))
        self.assertEqual(row["events"], ["challenge_received", "authorization_sent", "get_200_confirmed"])

    def test_old_challenge_is_never_reused_even_if_still_valid(self):
        self.client.get(target.PATHS[0]);self.client.get(target.PATHS[1])
        row = self.client.operations[-1]
        self.assertEqual((row["valid_challenges_received"], row["authorizations_sent"],
                          row["wire_gets_sent"], row["get_200_confirmed"]), (1, 1, 2, 1))
        self.assertEqual([r["authorized"] for r in self.server.requests],
                         [False, True, False, True])

    def test_renewal_between_operations_uses_only_one_authorization(self):
        self.client.get(target.PATHS[0]);self.server.challenge()
        self.client.get(target.PATHS[1]);row = self.client.operations[-1]
        self.assertEqual((row["http_401_received"], row["authorizations_sent"],
                          row["wire_gets_sent"], row["get_200_confirmed"]), (1, 1, 2, 1))
        self.assertEqual([r["authorized"] for r in self.server.requests[-2:]], [False, True])

    def test_authentication_context_is_rebuilt_and_discarded(self):
        first_handler = self.client.digest
        self.client.get(target.PATHS[0]);second_handler = self.client.digest
        self.assertIsNot(first_handler, second_handler)
        self.assertIsNone(second_handler.challenge)
        self.assertIsNone(second_handler.last_nonce)
        self.assertEqual(second_handler.nonce_count, 0)
        self.client.get(target.PATHS[1]);third_handler = self.client.digest
        self.assertIsNot(second_handler, third_handler)
        self.assertIsNot(second_handler.passwd, third_handler.passwd)
        self.assertIsNone(third_handler.last_nonce)

    def test_inherited_urllib_authentication_retry_is_never_called(self):
        with patch.object(target.WifiDigest, "http_error_401",
                          side_effect=AssertionError("implicit retry forbidden")), \
             patch.object(target.GetDigest, "retry_http_digest_auth",
                          side_effect=AssertionError("implicit retry forbidden")):
            self.client.get(target.PATHS[0])
        self.assertEqual(len(self.server.requests), 2)

    def test_an_extra_library_open_is_blocked_before_third_wire_get(self):
        original = target.GetDigest.http_error_401
        def extra_open(handler, req, *args):
            response = original(handler, req, *args)
            try:
                return handler.parent.open(req, timeout=3)
            finally:
                response.close()
        with patch.object(target.GetDigest, "http_error_401", extra_open):
            self.assert_stop("REQUEST_LIMIT")
        self.assertEqual(len(self.server.requests), 2)
        self.assertEqual(self.client.operations[-1]["wire_gets_sent"], 2)
        self.assertEqual(self.client.operations[-1]["authorizations_sent"], 1)

    def test_transport_rejects_a_second_authorization_before_connect(self):
        state = target.Exchange(target.PATHS[0], request_attempts=1,
                                http_401_received=1, valid_challenges_received=1,
                                authorization_attempts=1)
        state.guard = target.Deadline(timer_factory=PassiveTimer)
        delegate = self.server.connection(HOST, timeout=3)
        transport = target.GetConnection(delegate, state)
        with self.assertRaises(target.DiagnosticStop) as caught:
            transport.request("GET", target.PATHS[0], None,
                              {"aUtHoRiZaTiOn": "synthetic"})
        self.assertEqual(caught.exception.code, "AUTHORIZATION_LIMIT")
        self.assertEqual(self.server.requests, [])
        self.assertEqual(self.server.fake_sockets, [])
        state.guard.close()

    def test_transport_requires_anonymous_first_and_same_second_endpoint(self):
        for url, headers, reason in [
                (target.PATHS[0], {"Authorization": "synthetic"}, "DIGEST_SEQUENCE_HOLD"),
                (target.PATHS[1], {}, "ENDPOINT_NOT_ALLOWED")]:
            state = target.Exchange(target.PATHS[0])
            state.guard = target.Deadline(timer_factory=PassiveTimer)
            transport = target.GetConnection(self.server.connection(HOST, timeout=3), state)
            with self.assertRaises(target.DiagnosticStop) as caught:
                transport.request("GET", url, None, headers)
            self.assertEqual(caught.exception.code, reason)
            self.assertEqual(self.server.requests, [])
            state.guard.close()

    def test_two_clients_replace_challenges_without_overlapping(self):
        other = self.make_client()
        self.client.get(target.PATHS[0]);other.get(target.PATHS[0])
        self.client.get(target.PATHS[1])
        self.assertEqual(self.client.operations[-1]["wire_gets_sent"], 2)
        self.assertEqual(self.client.operations[-1]["get_200_confirmed"], 1)
        self.assertEqual(self.client.operations[-1]["authorizations_sent"], 1)

    def test_second_401_stops_without_a_third_get(self):
        self.server.always_401 = True;self.assert_stop("SECOND_401")
        self.assertEqual(len(self.server.requests), 2)
        row = self.client.operations[-1]
        self.assertEqual((row["http_401_received"], row["valid_challenges_received"],
                          row["authorizations_sent"], row["get_200_confirmed"]), (2, 1, 1, 0))

    def test_malformed_or_unreviewed_challenges_never_send_credentials(self):
        valid = self.server.challenge()
        variants = ["Basic realm=\"SHINO-StageA\"", valid.replace("SHINO-StageA", "UNREVIEWED"),
                    valid.replace('qop="auth"', 'qop="auth-int"'),
                    valid + ', algorithm="SHA-256"', valid + ', realm="duplicate"',
                    valid.replace(self.server.opaque, "short"), valid + ', unknown="value"',
                    "Digest " + PASSWORD, [valid, valid], [], "", "Digest", "Digest "]
        for value in variants:
            with self.subTest(kind=type(value).__name__):
                self.client = self.make_client();self.server.requests.clear()
                self.server.challenge_override = value
                self.assert_stop("INVALID_DIGEST_CHALLENGE")
                self.assertEqual(len(self.server.requests), 1)
                self.assertFalse(self.server.requests[0]["authorized"])

    def test_post_and_get_body_are_blocked_before_transport(self):
        for method, body in [("POST", None), ("PUT", None), ("PATCH", None),
                             ("DELETE", None), ("HEAD", None), ("GET", b"body")]:
            request = Request(self.client.base + target.PATHS[0], method=method, data=body)
            with self.assertRaises(target.DiagnosticStop):self.client.digest.http_request(request)
        self.assertEqual(self.server.requests, [])

    def test_intent_upload_and_foreign_hosts_are_not_allowed(self):
        for suffix in ["/api/v1/lan/intent", "/api/v1/lan/provision", "/api/v1/update",
                       "/api/v1/bridge/metrics", "/api/v1/m9/normal/status",
                       "/api/v1/m9/maintenance/result", target.PATHS[0] + "?extra=1"]:
            self.client = self.make_client()
            self.assert_stop("ENDPOINT_OR_OPERATION_LIMIT", suffix)
        request = Request("http://192.168.4.1.evil.invalid" + target.PATHS[0])
        with self.assertRaises(target.DiagnosticStop):self.client.digest.http_request(request)
        self.assertEqual(self.server.requests, [])

    def test_redirect_is_terminal_without_new_destination(self):
        self.server.forced_status = 302
        self.server.header_override = lambda h: h.__setitem__("Location", "http://foreign.invalid/secret")
        self.assert_stop("UNEXPECTED_HTTP_STATUS")
        self.assertEqual(len(self.server.requests), 2)

    def test_json_errors_are_terminal_and_redacted(self):
        for body in [b'{"nonce":"SECRET","nonce":"SECRET"}', b"NOT_JSON", b"\xff", b'{"heap":NaN}']:
            self.client = self.make_client();self.server.body_override = body
            self.assert_stop("INVALID_JSON")
            self.assertEqual(self.client.operations[-1]["http_200_received"], 1)
            self.assertEqual(self.client.operations[-1]["get_200_confirmed"], 0)

    def test_body_bound_length_and_content_type(self):
        variants = [lambda h: h.replace_header("Content-Length", "4097"),
                    lambda h: h.replace_header("Content-Length", "1"),
                    lambda h: h.__setitem__("Content-Length", h["Content-Length"]),
                    lambda h: h.replace_header("Content-Type", "text/plain"),
                    lambda h: h.__setitem__("Transfer-Encoding", "chunked")]
        for i, variant in enumerate(variants):
            self.client = self.make_client();self.server.header_override = variant
            self.assert_stop("INVALID_RESPONSE_LENGTH" if i == 1 else "INVALID_RESPONSE_FRAMING")

    def test_oversized_body_is_rejected_without_read_or_retry(self):
        self.server.body_override = b"x" * (target.BODY_LIMIT + 1)
        self.server.on_read = lambda response: self.fail("oversized body was read")
        self.assert_stop("INVALID_RESPONSE_FRAMING")
        self.assertEqual(len(self.server.requests), 2)

    def test_timeout_and_connection_loss_stop_without_resending(self):
        for phase, reason in [("connect", "CONNECTION_OR_HTTP_ERROR"),
                              ("send", "CONNECTION_OR_HTTP_ERROR"), ("response", "TIMEOUT")]:
            self.client = self.make_client();self.server.requests.clear();self.server.failure = phase
            error = self.assert_stop(reason)
            self.assertNotIn(PASSWORD, str(error))
            self.assertLessEqual(len(self.server.requests), 1)

    def test_interruption_at_either_connection_stage_never_retries(self):
        for number in (1, 2):
            for phase, reason in [("connect", "CONNECTION_OR_HTTP_ERROR"),
                                  ("send", "CONNECTION_OR_HTTP_ERROR"),
                                  ("response", "TIMEOUT")]:
                with self.subTest(connection=number, phase=phase):
                    self.server = Server();self.client = self.make_client()
                    self.server.failure = (phase, number)
                    self.assert_stop(reason)
                    row = self.client.operations[-1]
                    self.assertLessEqual(row["request_attempts"], 2)
                    self.assertLessEqual(row["wire_gets_sent"], 2)
                    self.assertLessEqual(row["authorization_attempts"], 1)
                    self.assertLessEqual(row["authorizations_sent"], 1)
                    self.assertEqual(row["get_200_confirmed"], 0)
                    with coord.digest_exchange(HOST, directory=self.directory,
                                               wait_seconds=0):pass

    def test_timeout_or_reset_while_reading_body_releases_lock(self):
        for error in [TimeoutError(PASSWORD), ConnectionResetError(PASSWORD)]:
            self.client = self.make_client()
            def fail(response): raise error
            self.server.on_read = fail
            self.assert_stop("TIMEOUT" if isinstance(error, TimeoutError) else "CONNECTION_OR_HTTP_ERROR")
            with coord.digest_exchange(HOST, directory=self.directory, wait_seconds=0):pass

    def test_absolute_deadline_includes_the_body(self):
        clock = [0.0]
        self.client = self.make_client(clock=lambda: clock[0])
        self.server.on_read = lambda response: clock.__setitem__(0, 6.1)
        self.assert_stop("TIMEOUT")

    def test_lock_wait_is_charged_to_the_same_six_second_budget(self):
        clock = [0.0];self.client = self.make_client(clock=lambda: clock[0])
        original = coord.digest_exchange
        @contextlib.contextmanager
        def delayed_lock(*args, **kwargs):
            clock[0] += 1.5
            with original(*args, **kwargs):yield
        self.server.on_read = lambda response: clock.__setitem__(0, clock[0] + 4.6)
        with patch.object(coord, "digest_exchange", delayed_lock):
            self.assert_stop("TIMEOUT")
        self.assertEqual(self.client.operations[-1]["get_200_confirmed"], 0)

    def test_expired_lock_wait_never_starts_http(self):
        clock = [0.0];self.client = self.make_client(clock=lambda: clock[0])
        original = coord.digest_exchange
        @contextlib.contextmanager
        def delayed_lock(*args, **kwargs):
            clock[0] = 6.1
            with original(*args, **kwargs):yield
        with patch.object(coord, "digest_exchange", delayed_lock):
            self.assert_stop("TIMEOUT")
        self.assertEqual(self.server.requests, [])

    def test_pacing_lock_wait_and_body_share_one_budget(self):
        clock = [0.0]
        self.client = self.make_client(clock=lambda: clock[0],
            sleep=lambda delay: clock.__setitem__(0, clock[0] + delay))
        self.client.get(target.PATHS[0])
        original = coord.digest_exchange
        @contextlib.contextmanager
        def delayed_lock(*args, **kwargs):
            clock[0] += 1.5
            with original(*args, **kwargs):yield
        self.server.on_read = lambda response: clock.__setitem__(0, clock[0] + 2.3)
        with patch.object(coord, "digest_exchange", delayed_lock):
            self.assert_stop("TIMEOUT", target.PATHS[1])
        self.assertGreater(clock[0], 6)

    def test_close_and_lock_release_precede_success_and_deadline_cancel(self):
        clock = [0.0];self.client = self.make_client(clock=lambda: clock[0])
        def close(response):
            self.assertFalse(self.client.current.guard.timer.cancelled)
            if response.status == 200:clock[0] = 6.1
        self.server.on_close = close
        self.assert_stop("TIMEOUT")
        self.assertEqual(self.client.operations[-1]["get_200_confirmed"], 0)
        with coord.digest_exchange(HOST, directory=self.directory, wait_seconds=0):pass

    def test_deadline_watchdog_interrupts_registered_sockets(self):
        guard = target.Deadline(timer_factory=PassiveTimer)
        peer = FakeSocket();guard.register(peer);guard.abort()
        with self.assertRaises(target.DiagnosticStop):guard.check()
        self.assertEqual(peer.shutdowns, 1)
        guard.close();self.assertTrue(guard.timer.cancelled)

    def test_deadline_interruption_is_timeout_even_if_read_raises_reset(self):
        def expire(response):
            self.client.current.guard.abort()
            raise ConnectionResetError(PASSWORD)
        self.server.on_read = expire
        self.assert_stop("TIMEOUT")

    def test_lock_covers_challenge_close_and_complete_body(self):
        def held(response):
            with self.assertRaises(coord.CoordinationBusy):
                with coord.digest_exchange(HOST, directory=self.directory, wait_seconds=0):pass
        self.server.on_read = self.server.on_close = held
        self.client.get(target.PATHS[0])
        with coord.digest_exchange(HOST, directory=self.directory, wait_seconds=0):pass

    def test_concurrent_clients_wait_until_body_closes(self):
        other = self.make_client();entered = threading.Event();release = threading.Event();results = []
        first = [True]
        def read(response):
            if first[0]:
                first[0] = False;entered.set()
                if not release.wait(1):raise AssertionError("test release missing")
        self.server.on_read = read
        def call(client):
            try:client.get(target.PATHS[0]);results.append("PASS")
            except Exception:results.append("FAIL")
        a = threading.Thread(target=call, args=(self.client,));b = threading.Thread(target=call, args=(other,))
        a.start();self.assertTrue(entered.wait(1));before = len(self.server.requests)
        b.start();time.sleep(0.08);self.assertEqual(len(self.server.requests), before)
        release.set();a.join(2);b.join(2)
        self.assertFalse(a.is_alive() or b.is_alive());self.assertEqual(results, ["PASS", "PASS"])

    def test_busy_coordinator_never_calls_http(self):
        with patch("shino_digest_coord.digest_exchange", side_effect=coord.CoordinationBusy("secret")):
            self.assert_stop("COORDINATOR_UNAVAILABLE")
        self.assertEqual(self.server.requests, [])
        self.assertIn("coordination_hold", self.client.operations[-1]["events"])

    def test_occupied_os_lock_is_terminal_without_any_get(self):
        with coord.digest_exchange(HOST, directory=self.directory):
            self.assert_stop("COORDINATOR_UNAVAILABLE")
        self.assertEqual(self.server.requests, [])

    def test_unavailable_lock_file_is_terminal_without_any_get(self):
        with patch.object(Path, "open", side_effect=PermissionError(PASSWORD)):
            self.assert_stop("COORDINATOR_UNAVAILABLE")
        self.assertEqual(self.server.requests, [])

    def test_unexpected_status_and_unauthenticated_success_are_terminal(self):
        self.server.unauthenticated_200 = True;self.assert_stop("UNAUTHENTICATED_200")
        self.client = self.make_client();self.server.unauthenticated_200 = False
        self.server.forced_status = 503;self.assert_stop("UNEXPECTED_HTTP_STATUS")

    def test_identity_resource_fs_and_pending_state_stop_the_session(self):
        cases = [(dict(sha256="f" * 64), "RUNNING_IDENTITY_MISMATCH"),
                 (dict(stack=2047), "RESOURCE_FLOOR_FAILED"),
                 (dict(heap=25599, block=20000), "RESOURCE_FLOOR_FAILED"),
                 (dict(fs_ok=False), "LITTLEFS_HOLD"),
                 (dict(last_update=PASSWORD), "OTA_STATE_HOLD"),
                 (dict(heap=True), "INVALID_SCHEMA")]
        for changes, reason in cases:
            self.client = self.make_client();self.server.payloads[target.PATHS[0]] = dict(update_payload(), **changes)
            self.assert_stop(reason)

    def test_full_run_uses_three_operations_and_never_displays_secrets(self):
        self.server.payloads[target.PATHS[1]].update(
            state="STA_ONLINE", sta_online=True, lan_ip="192.168.1.82")
        self.server.payloads[target.PATHS[0]]["unknown_private_field"] = PASSWORD
        report = target.run_diagnostic(self.client);encoded = json.dumps(report)
        self.assertEqual(report["status"], "GET_READS_COMPLETE_NOT_QUALIFICATION")
        self.assertEqual(len(report["exchanges"]), 3)
        self.assertFalse(report["physical_acceptance"] or report["native_B51_memory_qualified"])
        self.assertTrue(all(r["method"] == "GET" for r in self.server.requests))
        self.assertEqual(len(self.server.requests), 6)
        self.assertEqual([r["authorized"] for r in self.server.requests], [False, True] * 3)
        self.assertTrue(all(row["authorizations_sent"] == 1 and
                            row["valid_challenges_received"] == 1 and
                            row["wire_gets_sent"] == 2 for row in report["exchanges"]))
        for secret in [PASSWORD, "c" * 32, "d" * 32, self.server.nonce, self.server.opaque]:
            self.assertNotIn(secret, encoded)

    def test_failure_prevents_later_endpoints(self):
        self.server.always_401 = True
        report = target.run_diagnostic(self.client)
        self.assertEqual(report["status"], "STOP")
        self.assertEqual(report["reason"], "SECOND_401")
        self.assertEqual({r["path"] for r in self.server.requests}, {target.PATHS[0]})

    def test_operation_cap_prevents_polling(self):
        for _ in range(3):self.client.get(target.PATHS[0])
        count = len(self.server.requests);self.assert_stop("ENDPOINT_OR_OPERATION_LIMIT")
        self.assertEqual(len(self.server.requests), count)

    def test_cli_default_does_not_load_secrets_construct_transport_or_create_lock(self):
        out = io.StringIO()
        with patch.object(target, "inspect", return_value=(RELEASE, b"")), \
             patch.object(target, "load_identity", side_effect=AssertionError("credentials")), \
             patch.object(target, "B5GetDiagnostic", side_effect=AssertionError("transport")), \
             contextlib.redirect_stdout(out):
            self.assertEqual(target.main(["--bin", "fixture", "--manifest", "fixture"]), 0)
        self.assertEqual(json.loads(out.getvalue())["status"], "PRINT_ONLY_NO_DEVICE_CONTACT")
        self.assertEqual(list(self.directory.iterdir()), [])

    def test_cli_failure_outputs_only_fixed_reason(self):
        out = io.StringIO()
        with patch.object(target, "inspect", side_effect=ValueError(PASSWORD)), contextlib.redirect_stdout(out):
            self.assertEqual(target.main(["--bin", "fixture", "--manifest", "fixture"]), 2)
        self.assertNotIn(PASSWORD, out.getvalue())
        self.assertEqual(json.loads(out.getvalue())["reason"], "LOCAL_INPUT_INVALID")

    def test_second_operation_starts_anonymously_and_second_401_is_terminal(self):
        self.client.get(target.PATHS[0]);self.server.always_401 = True
        self.assert_stop("SECOND_401", target.PATHS[1])
        row = self.client.operations[-1]
        self.assertEqual((row["request_attempts"], row["authorizations_sent"],
                          row["valid_challenges_received"], row["get_200_confirmed"]), (2, 1, 1, 0))
        self.assertEqual([r["authorized"] for r in self.server.requests[-2:]], [False, True])
        self.assertIn("second_401_hold", row["events"])

    def test_raw_reader_also_blocks_post_and_other_schemes(self):
        for url, method in [(self.client.base + target.PATHS[0], "POST"),
                            ("https://" + HOST + target.PATHS[0], "GET"),
                            ("ftp://" + HOST + target.PATHS[0], "GET")]:
            request = Request(url, method=method)
            with self.assertRaises(target.DiagnosticStop):
                self.client.reader.reader.open(request, timeout=3)
        self.assertEqual(self.server.requests, [])

    def test_ip_and_resource_schemas_are_strict(self):
        self.server.payloads[target.PATHS[1]]["lan_ip"] = 0
        self.assert_stop("INVALID_SCHEMA", target.PATHS[1])
        self.client = self.make_client()
        self.server.payloads[target.PATHS[2]]["resource_sample_count"] = True
        self.assert_stop("INVALID_SCHEMA", target.PATHS[2])
        self.client = self.make_client()
        self.server.payloads[target.PATHS[2]] = dict(resources_payload(), continuation_floor=1024)
        self.assert_stop("RESOURCE_FLOOR_FAILED", target.PATHS[2])

    def test_lan_exact_b5_handler_response_is_valid(self):
        # B5 source 8de4d455 calls IPAddress(0,0,0,0).toString() offline.
        # Core 3.1.2 printTo() emits this sentinel when isSet() is false.
        self.server.payloads[target.PATHS[1]] = json.loads(
            '{"state":"NO_SAVED_WIFI","lan_ip":"(IP unset)",'
            '"sta_online":false,"ota_protocol":"shino-http-ota-1"}')
        shown = self.client.get(target.PATHS[1])
        self.assertEqual(shown, dict(state="NO_SAVED_WIFI", sta_online=False,
                                    lan_ip="(IP unset)", wifi_storage_proven=False))
        self.assertEqual(self.client.operations[-1]["get_200_confirmed"], 1)

    def test_lan_unset_requires_exact_sentinel_and_offline_sta(self):
        for address, online, reason in [
                ("(IP unset)", True, "LAN_STATE_HOLD"),
                ("(ip unset)", False, "INVALID_SCHEMA"),
                (" (IP unset)", False, "INVALID_SCHEMA"),
                ("(IP unset) ", False, "INVALID_SCHEMA"),
                ("IP unset", False, "INVALID_SCHEMA")]:
            with self.subTest(address=address, online=online):
                self.client = self.make_client()
                self.server.payloads[target.PATHS[1]].update(
                    lan_ip=address, sta_online=online)
                self.assert_stop(reason, target.PATHS[1])

    def test_valid_offline_lan_still_holds_final_diagnostic(self):
        for address in ("(IP unset)", "0.0.0.0"):
            with self.subTest(address=address):
                self.client = self.make_client()
                self.server.payloads[target.PATHS[1]]["lan_ip"] = address
                report = target.run_diagnostic(self.client)
                self.assertEqual((report["status"], report["reason"]),
                                 ("STOP", "LAN_OFFLINE_HOLD"))
                self.assertEqual(report["readings"][target.PATHS[1]]["lan_ip"], address)
                self.assertFalse(report["readings"][target.PATHS[1]]["sta_online"])
                self.assertFalse(report["physical_acceptance"])
                self.assertFalse(report["native_B51_memory_qualified"])
                self.assertEqual(len(report["exchanges"]), 2)
                self.assertEqual(report["exchanges"][1]["get_200_confirmed"], 1)
                self.assertTrue(self.client.stopped)
                self.assertNotIn(target.PATHS[2], report["readings"])
                with self.assertRaises(target.DiagnosticStop) as caught:
                    self.client.get(target.PATHS[2])
                self.assertEqual(caught.exception.code, "SESSION_STOPPED")
        self.assertNotIn(target.PATHS[2], [row["path"] for row in self.server.requests])

    def test_lan_valid_b5_states_preserve_controller_poll_transitions(self):
        # serviceRequest() precedes B5Lan::poll(): controller state can lag
        # the current Wi-Fi status. Do not invent a state/STA equivalence.
        for state, online, address in [
                ("NO_SAVED_WIFI", False, "0.0.0.0"),
                ("STA_CONNECTING", False, "0.0.0.0"),
                ("AP_RECOVERY_RETRY", False, "0.0.0.0"),
                ("STA_ONLINE", True, "192.168.1.82"),
                ("STA_CONNECTING", True, "192.168.1.82"),
                ("STA_ONLINE", False, "0.0.0.0")]:
            with self.subTest(state=state, online=online):
                self.client = self.make_client()
                self.server.payloads[target.PATHS[1]] = dict(state=state,
                    sta_online=online, lan_ip=address, ota_protocol="shino-http-ota-1")
                self.assertEqual(self.client.get(target.PATHS[1])["sta_online"], online)

    def test_lan_missing_and_extra_fields_are_schema_errors(self):
        baseline = dict(self.server.payloads[target.PATHS[1]])
        variants = []
        for name in baseline:
            payload = dict(baseline);del payload[name];variants.append(payload)
        variants.extend([dict(baseline, unexpected=True),
                         dict(baseline, firmware="B5.1")])
        for index, payload in enumerate(variants):
            with self.subTest(case=index):
                self.client = self.make_client()
                self.server.payloads[target.PATHS[1]] = payload
                self.assert_stop("INVALID_SCHEMA", target.PATHS[1])

    def test_lan_b51_b52_exact_eight_field_schema_accepts_healthy_state(self):
        # B5.2 uses the actual eight-field B5.1 LAN handler verbatim.
        self.server.payloads[target.PATHS[1]] = dict(
            state="STA_ONLINE", lan_ip="192.168.1.70", sta_online=True,
            ota_protocol="shino-http-ota-1", credential_state="VERIFIED",
            connection="STA_ONLINE", provision="NOT_ATTEMPTED", firmware="B5.1")
        shown = self.client.get(target.PATHS[1])
        self.assertEqual(shown["lan_ip"], "192.168.1.70")
        self.assertTrue(shown["sta_online"])
        self.assertFalse(shown["wifi_storage_proven"])
        self.assertTrue(shown["sdk_saved_wifi_reported_valid"])
        self.assertTrue(shown["lan_extended_validated"])
        self.assertEqual(shown["firmware_handler_label"], "B5.1")
        self.assertEqual(self.client.operations[-1]["get_200_confirmed"], 1)

    def test_lan_extended_partial_extra_or_wrong_type_stops(self):
        original = dict(state="STA_ONLINE", lan_ip="192.168.1.70",
            sta_online=True, ota_protocol="shino-http-ota-1",
            credential_state="VERIFIED", connection="STA_ONLINE",
            provision="NOT_ATTEMPTED", firmware="B5.1")
        variants = []
        for name in ("credential_state", "connection", "provision", "firmware"):
            item = dict(original)
            item.pop(name)
            variants.append(item)
            for wrong in (None, 0, True, [], {}, 2.5):
                variants.append(dict(original, **{name: wrong}))
        variants.append(dict(original, extra=True))
        for payload in variants:
            with self.subTest(payload=payload):
                self.client = self.make_client()
                self.server.payloads[target.PATHS[1]] = payload
                self.assert_stop("INVALID_SCHEMA", target.PATHS[1])

    def test_lan_extended_invalid_known_values_stop(self):
        original = dict(state="STA_ONLINE", lan_ip="192.168.1.70",
            sta_online=True, ota_protocol="shino-http-ota-1",
            credential_state="VERIFIED", connection="STA_ONLINE",
            provision="NOT_ATTEMPTED", firmware="B5.1")
        cases = [
            ("credential_state", "UNKNOWN"),
            ("credential_state", "INVALID"),
            ("credential_state", "EMPTY"),
            ("credential_state", "FABRICATED"),
            ("connection", "STA_AUTH_REJECTED"),
            ("connection", "MEMORY_HOLD"),
            ("connection", "NOT_STARTED"),
            ("connection", "FABRICATED"),
            ("provision", "PROVISION_READBACK_MISMATCH_UNKNOWN"),
            ("provision", "PROVISION_MEMORY_HOLD"),
            ("provision", "FABRICATED"),
            ("firmware", "B5.2"),
            ("firmware", "B5.3"),
            ("firmware", "FABRICATED"),
        ]
        for key,value in cases:
            with self.subTest(key=key,value=value):
                self.client = self.make_client()
                self.server.payloads[target.PATHS[1]] = dict(original,**{key:value})
                self.assert_stop("LAN_STATE_HOLD", target.PATHS[1])

    def test_lan_failure_gate_is_sanitized_and_terminal(self):
        base = dict(state="STA_ONLINE", lan_ip="192.168.1.70",
            sta_online=True, ota_protocol="shino-http-ota-1",
            credential_state="VERIFIED", connection="STA_ONLINE",
            provision="NOT_ATTEMPTED", firmware="B5.1")
        for field,value,gate in [
                ("state", "SAVED_WIFI_UNKNOWN_HOLD", "CONTROLLER_STATE"),
                ("ota_protocol", "wrong", "PROTOCOL"),
                ("sta_online", False, "STA_IP_INVARIANT"),
                ("credential_state", "NOT_REAL", "SDK_STORAGE_ENUM"),
                ("connection", "NOT_REAL", "CONNECTION_ENUM"),
                ("provision", "NOT_REAL", "PROVISION_ENUM"),
                ("firmware", "B5.2", "FIRMWARE_HANDLER"),
                ("credential_state", "UNKNOWN", "SAVED_WIFI_NOT_VERIFIED"),
                ("connection", "STA_AUTH_REJECTED", "CONNECTION_NOT_READY"),
                ("provision", "PROVISION_MEMORY_HOLD", "PROVISION_NOT_CLEAN")]:
            with self.subTest(field=field, value=value):
                self.client = self.make_client()
                self.server.requests.clear()
                self.server.payloads[target.PATHS[1]] = dict(base, **{field:value})
                result = target.run_diagnostic(self.client)
                self.assertEqual(result["status"], "STOP")
                self.assertEqual(result["reason"], "LAN_STATE_HOLD")
                self.assertEqual(result["lan_hold_gate"], gate)
                self.assertEqual(result["post_requests"], 0)
                self.assertNotIn(target.PATHS[2],
                                 [r["path"] for r in self.server.requests])
                self.assertNotIn("NOT_REAL", json.dumps(result))
                self.assertNotIn("PROVISION_MEMORY_HOLD", json.dumps(result))

    def test_unknown_lan_json_still_rejects_without_raw_values(self):
        self.server.payloads[target.PATHS[1]] = dict(
            state="STA_ONLINE", lan_ip="192.168.1.70", sta_online=True,
            ota_protocol="shino-http-ota-1", credential_state="VERIFIED",
            connection="STA_ONLINE", provision="NOT_ATTEMPTED",
            firmware="B5.1", unknown="private sample not permitted")
        result = target.run_diagnostic(self.client)
        self.assertEqual(result["reason"], "INVALID_SCHEMA")
        self.assertNotIn("lan_hold_gate", result)
        self.assertNotIn("private sample", json.dumps(result))
        self.assertEqual(len(result["exchanges"]), 2)

    def test_lan_extended_no_third_get_after_schema_failure(self):
        self.server.payloads[target.PATHS[1]] = dict(
            state="STA_ONLINE", lan_ip="192.168.1.70", sta_online=True,
            ota_protocol="shino-http-ota-1", credential_state="VERIFIED",
            connection="STA_ONLINE", provision="NOT_ATTEMPTED",
            firmware="B5.1", unexpected="no")
        result = target.run_diagnostic(self.client)
        self.assertEqual((result["status"],result["reason"]),("STOP","INVALID_SCHEMA"))
        self.assertNotIn(target.PATHS[2], [r["path"] for r in self.server.requests])

    def test_lan_extended_full_get_flow_mocked(self):
        self.server.payloads[target.PATHS[1]] = dict(
            state="STA_ONLINE", lan_ip="192.168.1.70", sta_online=True,
            ota_protocol="shino-http-ota-1", credential_state="VERIFIED",
            connection="STA_ONLINE", provision="PROVISION_VERIFIED",
            firmware="B5.1")
        result = target.run_diagnostic(self.client)
        self.assertEqual(result["status"],"GET_READS_COMPLETE_NOT_QUALIFICATION")
        self.assertEqual(len(result["exchanges"]),3)
        self.assertFalse(result["readings"][target.PATHS[1]]["wifi_storage_proven"])
        self.assertTrue(result["readings"][target.PATHS[1]]["sdk_saved_wifi_reported_valid"])
        self.assertEqual(sum(e["wire_gets_sent"] for e in result["exchanges"]),6)

    def test_b51_lan_handler_source_contract_stays_exact(self):
        # A source-level regression: no loosened JSON subset acceptance.
        source = (Path(__file__).resolve().parents[1] / "tools" /
                  "shino_b5_lan_build.py").read_text(encoding="utf-8")
        for marker in ("credential_state", "connection", "provision",
                       "firmware", "B5.1"):
            self.assertIn(marker, source)
        self.assertIn('void lanStatus()', source)


    def test_lan_field_types_are_checked_before_values(self):
        baseline = dict(self.server.payloads[target.PATHS[1]])
        for name in baseline:
            values = [None, 0, 1, 1.0, [], {}]
            values += ["false", "true"] if name == "sta_online" else [False, True]
            for value in values:
                with self.subTest(field=name, type=type(value).__name__):
                    self.client = self.make_client()
                    self.server.payloads[target.PATHS[1]] = dict(baseline, **{name:value})
                    self.assert_stop("INVALID_SCHEMA", target.PATHS[1])

    def test_lan_wrong_values_and_online_ip_invariant_remain_terminal(self):
        baseline = dict(self.server.payloads[target.PATHS[1]])
        for changes, reason in [
                (dict(state="LAN_FAULT_HOLD"), "LAN_STATE_HOLD"),
                (dict(state="SAVED_WIFI_UNKNOWN_HOLD"), "LAN_STATE_HOLD"),
                (dict(state="OTHER"), "LAN_STATE_HOLD"),
                (dict(ota_protocol="other"), "LAN_STATE_HOLD"),
                (dict(sta_online=True), "LAN_STATE_HOLD"),
                (dict(lan_ip="192.168.1.82"), "LAN_STATE_HOLD"),
                (dict(lan_ip=""), "INVALID_SCHEMA"),
                (dict(lan_ip="192.168.1.999"), "INVALID_SCHEMA"),
                (dict(lan_ip="::1"), "INVALID_SCHEMA"),
                (dict(lan_ip="192.168.1.82/24"), "INVALID_SCHEMA")]:
            with self.subTest(fields=tuple(changes)):
                self.client = self.make_client()
                self.server.payloads[target.PATHS[1]] = dict(baseline, **changes)
                self.assert_stop(reason, target.PATHS[1])

    def test_lan_corrupt_json_never_reaches_third_endpoint(self):
        for raw, reason in [(b"[]", "INVALID_SCHEMA"), (b"null", "INVALID_SCHEMA"),
                            (b'{"sta_online":false,"sta_online":true}', "INVALID_JSON"),
                            (b'{"state":', "INVALID_JSON"), (b"\xff", "INVALID_JSON")]:
            with self.subTest(reason=reason):
                self.client = self.make_client()
                self.client.get(target.PATHS[0])
                self.server.body_override = raw
                self.assert_stop(reason, target.PATHS[1])
                self.assertEqual(self.client.operations[-1]["get_200_confirmed"], 0)
                self.assertEqual(self.client.operations[-1]["wire_gets_sent"], 2)
                self.assertEqual(self.client.operations[-1]["authorizations_sent"], 1)
                self.server.body_override = None
        self.assertNotIn(target.PATHS[2], [row["path"] for row in self.server.requests])

    def test_lan_schema_failure_stops_full_session_after_http200(self):
        del self.server.payloads[target.PATHS[1]]["sta_online"]
        report = target.run_diagnostic(self.client)
        self.assertEqual((report["status"], report["reason"]), ("STOP", "INVALID_SCHEMA"))
        self.assertEqual(len(report["exchanges"]), 2)
        self.assertEqual(report["exchanges"][0]["get_200_confirmed"], 1)
        self.assertEqual(report["exchanges"][1]["final_http_status"], 200)
        self.assertEqual(report["exchanges"][1]["get_200_confirmed"], 0)
        self.assertEqual([row["path"] for row in self.server.requests],
                         [target.PATHS[0]] * 2 + [target.PATHS[1]] * 2)
        self.assertEqual([row["authorized"] for row in self.server.requests], [False, True] * 2)
        self.assertNotIn("/api/v1/lan/status", report["readings"])

    def test_unexpected_reboot_is_not_retried(self):
        self.client.get(target.PATHS[0])
        self.server.payloads[target.PATHS[0]]["boot_id"] = "e" * 32
        self.assert_stop("UNEXPECTED_REBOOT")

    def test_cli_authorized_branch_with_fake_client_reports_failure(self):
        out = io.StringIO()
        self.server.always_401 = True
        with patch.object(target, "inspect", return_value=(RELEASE, b"")), \
             patch.object(target, "load_identity", return_value=IDENTITY), \
             patch.object(target, "B5GetDiagnostic", return_value=self.client), \
             contextlib.redirect_stdout(out):
            self.assertEqual(target.main(["--bin", "fixture", "--manifest", "fixture",
                                          "--authorize-read"]), 2)
        report = json.loads(out.getvalue())
        self.assertEqual(report["reason"], "SECOND_401")
        self.assertNotIn(PASSWORD, out.getvalue())


class TestLocalTcpDeadline(unittest.TestCase):
    @contextlib.contextmanager
    def loopback_client(self, state):
        """Guard every actual connect; the nominal AP never reaches a socket."""
        class Handler(BaseHTTPRequestHandler):
            def log_message(self, *args): pass
            def do_GET(self):
                state.requests.append(dict(method="GET", path=self.path,
                                           authorized="Authorization" in self.headers))
                response = state.response(self.path, self.headers)
                self.send_response(response.status)
                for key, value in response.headers.items():self.send_header(key, value)
                self.send_header("Connection", "close");self.end_headers()
                try:self.wfile.write(response.getvalue())
                except OSError:pass
                finally:response.close()
        server = ThreadingHTTPServer(("127.0.0.1", 0), Handler)
        worker = threading.Thread(target=lambda:server.serve_forever(poll_interval=0.02),
                                  daemon=True)
        worker.start();port = server.server_address[1]
        actual_connect = socket.socket.connect;destinations = []
        def loopback_only(peer, address):
            if address[0] != "127.0.0.1":raise AssertionError("non-loopback forbidden")
            destinations.append(address[0]);return actual_connect(peer, address)
        workspace = Path(__file__).resolve().parents[1] / "research-local"
        try:
            with tempfile.TemporaryDirectory(prefix="b5-get-wire-", dir=workspace) as td:
                with patch.object(coord, "_lock_directory", return_value=Path(td)), \
                     patch.object(socket.socket, "connect", loopback_only):
                    client = target.B5GetDiagnostic(IDENTITY, RELEASE,
                        connection_factory=lambda host, timeout:http.client.HTTPConnection(
                            "127.0.0.1", port, timeout=timeout))
                    yield client, destinations
        finally:
            server.shutdown();server.server_close();worker.join(1)

    def test_real_wire_three_independent_operations_send_six_gets_three_authorizations(self):
        state = Server()
        state.payloads[target.PATHS[1]].update(
            state="STA_ONLINE", sta_online=True, lan_ip="192.168.1.82")
        with self.loopback_client(state) as (client, destinations):
            report = target.run_diagnostic(client)
            self.assertEqual(report["status"], "GET_READS_COMPLETE_NOT_QUALIFICATION")
            self.assertEqual(len(destinations), 6)
            self.assertEqual([row["authorized"] for row in state.requests], [False, True] * 3)
            self.assertEqual([row["path"] for row in state.requests],
                             [path for path in target.PATHS for _ in range(2)])
            self.assertEqual(state.generation, 3)
            self.assertTrue(all(row["wire_gets_sent"] == 2 and
                                row["authorizations_sent"] == 1 and
                                row["get_200_confirmed"] == 1 for row in client.operations))

    def test_real_wire_second_401_stops_at_two_gets_and_one_authorization(self):
        state = Server();state.always_401 = True
        with self.loopback_client(state) as (client, destinations):
            report = target.run_diagnostic(client)
            self.assertEqual(report["reason"], "SECOND_401")
            self.assertEqual(len(destinations), 2)
            self.assertEqual([row["authorized"] for row in state.requests], [False, True])
            self.assertEqual(report["exchanges"][0]["get_200_confirmed"], 0)

    def test_real_wire_blocks_an_injected_third_urllib_open(self):
        state = Server();original = target.GetDigest.http_error_401
        def extra_open(handler, req, *args):
            response = original(handler, req, *args)
            try:return handler.parent.open(req, timeout=3)
            finally:response.close()
        with self.loopback_client(state) as (client, destinations), \
             patch.object(target.GetDigest, "http_error_401", extra_open):
            report = target.run_diagnostic(client)
            self.assertEqual(report["reason"], "REQUEST_LIMIT")
            self.assertEqual(len(destinations), 2)
            self.assertEqual([row["authorized"] for row in state.requests], [False, True])

    def test_trickling_body_is_interrupted_at_absolute_deadline(self):
        self.check_trickling_deadline(lock_wait=0)

    def test_trickling_body_and_lock_wait_share_absolute_deadline(self):
        self.check_trickling_deadline(lock_wait=1.25)

    def check_trickling_deadline(self, lock_wait):
        """Two real GETs to 127.0.0.1 only; never connect to the nominal AP."""
        state = Server();stop = threading.Event();finished = threading.Event()
        class Handler(BaseHTTPRequestHandler):
            def log_message(self, *args): pass
            def do_GET(self):
                response = state.response(self.path, self.headers)
                self.send_response(response.status)
                for key, value in response.headers.items():self.send_header(key, value)
                self.send_header("Connection", "close");self.end_headers()
                try:
                    if response.status == 200:
                        for byte in response.getvalue():
                            self.wfile.write(bytes((byte,)));self.wfile.flush()
                            if stop.wait(0.03):break
                    else:self.wfile.write(response.getvalue())
                except OSError:
                    pass
                finally:
                    if response.status == 200:finished.set()
        server = ThreadingHTTPServer(("127.0.0.1", 0), Handler)
        worker = threading.Thread(target=lambda: server.serve_forever(poll_interval=0.02), daemon=True)
        worker.start();port = server.server_address[1]
        workspace = Path(__file__).resolve().parents[1] / "research-local"
        actual_connect = socket.socket.connect;destinations = []
        def loopback_only(peer, address):
            if address[0] != "127.0.0.1":raise AssertionError("non-loopback transport forbidden")
            destinations.append(address[0]);return actual_connect(peer, address)
        original_lock = coord.digest_exchange
        @contextlib.contextmanager
        def delayed_lock(*args, **kwargs):
            time.sleep(lock_wait)
            with original_lock(*args, **kwargs):yield
        try:
            with tempfile.TemporaryDirectory(prefix="b5-get-loopback-", dir=workspace) as td:
                self.assertEqual(Path(td).resolve().parent, workspace.resolve())
                with patch.object(coord, "_lock_directory", return_value=Path(td)), \
                     patch.object(coord, "digest_exchange", delayed_lock), \
                     patch.object(socket.socket, "connect", loopback_only):
                    client = target.B5GetDiagnostic(IDENTITY, RELEASE,
                        connection_factory=lambda host, timeout: http.client.HTTPConnection(
                            "127.0.0.1", port, timeout=timeout))
                    start = time.monotonic()
                    with self.assertRaises(target.DiagnosticStop) as caught:client.get(target.PATHS[0])
                    elapsed = time.monotonic() - start
                    self.assertEqual(caught.exception.code, "TIMEOUT")
                    self.assertTrue(client.stopped)
                    self.assertGreaterEqual(elapsed, 5.8);self.assertLess(elapsed, 6.5)
                    self.assertEqual(destinations, ["127.0.0.1", "127.0.0.1"])
                    self.assertEqual(client.operations[-1]["get_200_confirmed"], 0)
        finally:
            stop.set();server.shutdown();server.server_close();worker.join(1);finished.wait(1)


if __name__ == "__main__":
    unittest.main()
