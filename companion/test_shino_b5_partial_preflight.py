"""Synthetic BINs and in-memory HTTP peers; OS networking is forbidden."""
import contextlib
import hashlib
import hmac
import io
import json
from pathlib import Path
import socket
import struct
import tempfile
import threading
import unittest
from unittest.mock import patch
from urllib.request import Request

import shino_b5_partial_preflight as target
import shino_digest_coord as coord
import shino_update as normal
from m9_first_migration import arduino_crc
from m9_signed_fixture_image import inert_image
from test_shino_b5_get_diagnostic import Server as GetServer, PassiveTimer, PASSWORD, HOST
import test_shino_b5_get_diagnostic as get_fixtures


def fixture(size, device, build):
    raw = bytearray(inert_image(size))
    tag = f"SHINO-HTTP-OTA-1|{device}|{build}|4m2m|APP_ONLY".encode()
    raw[0x2100:0x2100+len(tag)] = tag
    raw[0x1010:0x1018] = bytes(8)
    checksum = 0xef
    for value in raw[0x1010:0x1020]+raw[0x1028:-8]:
        checksum ^= value
    raw[-1] = checksum
    struct.pack_into("<II", raw, 0x1010, len(raw), arduino_crc(raw))
    return bytes(raw)


class PostServer:
    """Consume actual socket.send counts, not merely requested buffer lengths."""
    def __init__(self):
        self.body = bytearray()
        self.headers = {}
        self.connections = self.posts = self.closed = self.send_calls = 0
        self.shutdowns = []
        self.failure = None
        self.pattern = [512]
        self.on_send = None
        self.header_bytes_written = False
        self.getresponse_calls = 0

    def connection(self, host, timeout):
        assert host == HOST and 0 < timeout <= 3
        server = self
        self.connections += 1

        class Peer:
            def settimeout(self, seconds):
                assert 0 < seconds <= 3

            def send(self, data):
                server.send_calls += 1
                if server.on_send:
                    server.on_send()
                if server.failure == "send":
                    server.body.extend(bytes(data[:7]))
                    raise ConnectionResetError(PASSWORD)
                if server.failure == "timeout":
                    raise TimeoutError(PASSWORD)
                if server.failure == "interrupt":
                    raise KeyboardInterrupt(PASSWORD)
                if server.failure == "zero":
                    return 0
                count = min(len(data), server.pattern[(server.send_calls-1) % len(server.pattern)])
                server.body.extend(bytes(data[:count]))
                return count

            def shutdown(self, how):
                server.shutdowns.append(how)
                if server.failure == "shutdown":
                    raise OSError(PASSWORD)

        class Connection:
            auto_open = None
            sock = None

            def set_debuglevel(self, level):
                assert level == 0

            def connect(self):
                assert self.auto_open == 0
                if server.failure == "connect":
                    raise ConnectionRefusedError(PASSWORD)
                self.sock = Peer()

            def putrequest(self, method, path, **kwargs):
                assert (method, path) == ("POST", "/api/v1/update")
                server.posts += 1

            def putheader(self, name, value):
                server.headers[name] = value

            def endheaders(self):
                server.header_bytes_written = True
                if server.failure == "headers":
                    raise OSError(PASSWORD)

            def getresponse(self):
                server.getresponse_calls += 1
                raise AssertionError("A partial transfer must close without reading/polling its reply")

            def close(self):
                server.closed += 1
                self.sock = None

        return Connection()


class PartialPreflightTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.device = "1123456789abcdef"
        cls.current_raw = fixture(399264, cls.device, "b"*64)
        cls.candidate_raw = fixture(target.CANDIDATE_BYTES, cls.device, "c"*64)

    def setUp(self):
        workspace = Path(__file__).resolve().parents[1]/"research-local"
        self.tmp = tempfile.TemporaryDirectory(prefix="b5-partial-host-", dir=workspace)
        self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name).resolve()
        self.assertEqual(self.root.parent, workspace.resolve())
        self.enterContext(patch.object(coord, "_lock_directory", return_value=self.root))
        for name in ("socket.socket", "socket.create_connection", "socket.getaddrinfo"):
            guard = self.enterContext(patch(name, side_effect=AssertionError("NO NETWORK")))
            self.addCleanup(guard.assert_not_called)
        self.enterContext(patch.object(normal, "install", side_effect=AssertionError("NO INSTALL")))
        self.enterContext(patch.object(normal.Transport, "upload", side_effect=AssertionError("NO NORMAL UPLOAD")))
        synthetic_digest = PASSWORD+"-SYNTHETIC"
        self.enterContext(patch.object(get_fixtures, "PASSWORD", synthetic_digest))
        self.identity = dict(device=self.device, build="d"*64, ap_psk="p"*32,
                             api_token="t"*32, digest_password=synthetic_digest, maintenance_password="m"*48)
        self.identity_path = self.root/"synthetic-owner.json"
        self.identity_path.write_text(json.dumps(self.identity), encoding="utf-8")
        self.paths = []
        self.manifests = []
        for role, raw, build in (("candidate", self.candidate_raw, "c"*64),
                                  ("current", self.current_raw, "b"*64)):
            m = dict(schema=1, family="SHINO-StageA", layout="4m2m", protocol="shino-http-ota-1",
                     device=self.device, bytes=len(raw), sha256=hashlib.sha256(raw).hexdigest(), build_id=build)
            report = dict(m, layout_symbols=target.LAYOUT, source_commit="e"*40)
            if role == "candidate":
                report["firmware"] = "B5.1"
            files = tuple(self.root/(role+extension) for extension in (".bin", "-release.json", "-report.json"))
            files[0].write_bytes(raw)
            files[1].write_text(json.dumps(m), encoding="utf-8")
            files[2].write_text(json.dumps(report), encoding="utf-8")
            self.paths.extend(files)
            self.manifests.append(m)
        self.get_server = GetServer()
        m = self.manifests[1]
        self.before = dict(m, descriptor=f"SHINO-HTTP-OTA-1|{m['device']}|{m['build_id']}|4m2m|APP_ONLY",
                           boot_id="1"*32, nonce="2"*32, heap=30000, block=28000, stack=2128, frag=5,
                           fs_ok=True, fs_files=24, fs_bytes=181402, metrics_fresh=True,
                           ota_enabled=True, last_update="NONE", ota_heap_min=0,
                           ota_block_min=0, ota_stack_min=0, ota_frag_max=0)
        self.get_server.payloads[target.PATHS[0]] = self.before
        self.server = PostServer()
        self.now = 0.0
        self.marker = self.root/"unique.attempt"

    def prepare(self):
        return target.prepare(*self.paths)

    def reader(self, identity, release, host):
        return target.StatusReader(identity, release, host, connection_factory=self.get_server.connection,
                                   timer_factory=PassiveTimer, clock=lambda: self.now,
                                   sleep=lambda delta: setattr(self, "now", self.now+delta))

    def wire(self):
        return target.PartialTransport(HOST, connection_factory=self.server.connection,
                                       timer_factory=PassiveTimer, clock=lambda: self.now)

    def partial(self, *, wire=None, marker=None, authorized=True, confirm=None):
        artifacts = self.prepare()
        return target.run_partial(artifacts, self.identity_path, HOST, marker or self.marker,
                                  authorized=authorized, confirm_sha256=confirm or artifacts.candidate["sha256"],
                                  transport=wire or self.wire(), reader_factory=self.reader)

    def evidence(self):
        return target.collect_evidence(self.prepare(), self.identity_path, HOST, self.marker,
                                       authorized=True, reader_factory=self.reader)

    def after(self, **changes):
        self.get_server.payloads[target.PATHS[0]] = dict(self.before, nonce="3"*32,
            last_update="FAILED_NO_COMMIT", ota_heap_min=24000, ota_block_min=21000,
            ota_stack_min=2080, ota_frag_max=8, **changes)

    def test_full_image_length_and_exact_prefix_hmac(self):
        result = self.partial()
        self.assertEqual(result["status"], "PARTIAL_CLOSED_UNCONFIRMED_HOLD")
        self.assertEqual(self.server.body, self.candidate_raw[:8192])
        self.assertEqual(self.server.headers["Content-Length"], "414176")
        m = self.manifests[0]
        message = f"SHINO-HTTP-OTA-1\n{self.device}\n{'2'*32}\n414176\n{m['sha256']}\n{m['build_id']}".encode()
        key = hashlib.sha256(self.identity["maintenance_password"].encode()).digest()
        self.assertEqual(self.server.headers["X-Shino-Proof"], hmac.new(key, message, hashlib.sha256).hexdigest())
        self.assertEqual((self.server.posts, self.server.connections, self.server.getresponse_calls), (1, 1, 0))
        self.assertEqual(len(self.get_server.requests), 2)  # One challenge + one authenticated pre-read only.
        self.assertIn(socket.SHUT_WR, self.server.shutdowns)
        self.assertEqual(self.server.closed, 1)
        self.assertFalse(result["ota_success"])
        self.assertFalse(result["evidence_read_performed"])
        self.assertEqual(result["body_bytes_upper_bound"], 8192)

    def test_short_socket_writes_never_duplicate_or_exceed_prefix(self):
        self.server.pattern = [1, 3, 127, 511, 2, 17]
        result = self.partial()
        self.assertEqual(self.server.body, self.candidate_raw[:8192])
        self.assertGreater(self.server.send_calls, 16)
        self.assertEqual(result["body_bytes_sent"], 8192)

    def test_send_exception_after_unknown_partial_write_never_resends(self):
        self.server.failure = "send"
        result = self.partial()
        self.assertEqual((len(self.server.body), self.server.send_calls), (7, 1))
        self.assertEqual(result["body_bytes_sent"], 0)
        self.assertEqual(result["body_bytes_upper_bound"], 512)
        self.assertEqual(self.server.closed, 1)
        self.assertTrue(self.marker.exists())
        self.assertEqual(result["status"], "STOP_UNKNOWN_NO_RETRY")

    def test_single_transport_is_burned_even_after_connect_failure(self):
        self.server.failure = "connect"
        wire = self.wire()
        self.partial(wire=wire)
        with self.assertRaisesRegex(target.Stop, "SECOND_POST_FORBIDDEN"):
            wire.send(self.prepare(), self.identity, "2"*32)
        self.assertEqual(self.server.connections, 1)

    def test_two_threads_cannot_emit_two_posts_on_the_same_transport(self):
        wire = self.wire()
        artifacts = self.prepare()
        barrier = threading.Barrier(2)
        outcomes = []
        def worker():
            barrier.wait(timeout=3)
            try:
                wire.send(artifacts, self.identity, "2"*32)
                outcomes.append("CLOSED")
            except target.Stop as error:
                outcomes.append(str(error))
        workers = [threading.Thread(target=worker) for _ in range(2)]
        for worker_thread in workers:
            worker_thread.start()
        for worker_thread in workers:
            worker_thread.join(timeout=5)
            self.assertFalse(worker_thread.is_alive())
        self.assertCountEqual(outcomes, ["CLOSED", "SECOND_POST_FORBIDDEN"])
        self.assertEqual((self.server.posts, self.server.connections), (1, 1))
        self.assertEqual(self.server.body, self.candidate_raw[:8192])

    def test_existing_attempt_marker_blocks_a_second_invocation_before_any_get(self):
        self.partial()
        before = self.marker.read_bytes()
        requests = len(self.get_server.requests)
        second = self.partial()
        self.assertEqual(second["reason"], "OUTPUT_EXISTS_OR_UNSAFE")
        self.assertEqual((self.server.posts, len(self.get_server.requests)), (1, requests))
        self.assertEqual(self.marker.read_bytes(), before)

    def test_non_ap_hosts_are_rejected_by_every_network_entry_before_any_get(self):
        artifacts = self.prepare()
        hosts = ("192.168.1.1", "10.0.0.1", "172.16.1.1", "127.0.0.1",
                 "198.51.100.1", "localhost", "http://192.168.4.1",
                 "192.168.4.1:80", "192.168.004.1", " 192.168.4.1", None, 123)
        for host in hosts:
            with self.subTest(host=host):
                result = target.run_partial(artifacts, self.identity_path, host, self.marker,
                    authorized=True, confirm_sha256=artifacts.candidate["sha256"],
                    transport=self.wire(), reader_factory=self.reader)
                self.assertEqual(result["reason"], "AP_HOST_REQUIRED")
                evidence = target.collect_evidence(artifacts, self.identity_path, host, self.marker,
                    authorized=True, reader_factory=self.reader)
                self.assertEqual(evidence["reason"], "AP_HOST_REQUIRED")
                with self.assertRaisesRegex(target.Stop, "AP_HOST_REQUIRED"):
                    target.PartialTransport(host, connection_factory=self.server.connection)
                with self.assertRaisesRegex(target.Stop, "AP_HOST_REQUIRED"):
                    self.reader(self.identity, artifacts.current, host)
                with self.assertRaisesRegex(target.Stop, "AP_HOST_REQUIRED"):
                    target.ImmediateReader(None, host)
        self.assertEqual((self.server.connections, len(self.get_server.requests)), (0, 0))
        self.assertFalse(self.marker.exists())
        self.assertFalse(target._attempt_path(artifacts).exists())

    def test_all_cli_modes_reject_non_ap_host_before_artifacts_or_network(self):
        names = ("candidate-bin", "candidate-manifest", "candidate-report",
                 "current-bin", "current-manifest", "current-report")
        inputs = [value for name, path in zip(names, self.paths) for value in ("--"+name, str(path))]
        for mode in ("inspect", "partial", "evidence"):
            for host in ("192.168.1.1", "10.0.0.1", "localhost", PASSWORD):
                with self.subTest(mode=mode, host=host), \
                     patch.object(target, "prepare", side_effect=AssertionError("NO ARTIFACT READ")), \
                     contextlib.redirect_stdout(io.StringIO()) as out:
                    self.assertEqual(target.main(inputs+["--mode", mode, "--host", host]), 2)
                self.assertEqual(json.loads(out.getvalue())["reason"], "AP_HOST_REQUIRED")
                self.assertNotIn(PASSWORD, out.getvalue())
        self.assertEqual((self.server.connections, len(self.get_server.requests)), (0, 0))

    def test_host_is_rechecked_at_send_and_status_open(self):
        artifacts = self.prepare()
        wire = self.wire()
        wire.host = "192.168.1.1"
        with self.assertRaisesRegex(target.Stop, "AP_HOST_REQUIRED"):
            wire.send(artifacts, self.identity, "2"*32)
        result = target.run_partial(artifacts, self.identity_path, HOST, self.marker,
            authorized=True, confirm_sha256=artifacts.candidate["sha256"],
            transport=wire, reader_factory=self.reader)
        self.assertEqual(result["reason"], "AP_HOST_REQUIRED")
        reader = self.reader(self.identity, artifacts.current, HOST)
        reader.host = "192.168.1.1"
        with self.assertRaisesRegex(target.Stop, "AP_HOST_REQUIRED"):
            reader.get(target.PATHS[0])
        immediate = target.ImmediateReader(None, HOST)
        with self.assertRaisesRegex(target.Stop, "AP_STATUS_ENDPOINT_REQUIRED"):
            with immediate.open(Request("http://192.168.1.1"+target.PATHS[0]), 1):
                self.fail("Foreign URL must not open")
        self.assertEqual((self.server.connections, len(self.get_server.requests)), (0, 0))

    def test_new_marker_and_copied_artifacts_cannot_rearm_same_device_candidate(self):
        self.partial()
        artifacts = self.prepare()
        attempt = target._attempt_path(artifacts)
        saved_attempt, saved_marker = attempt.read_bytes(), self.marker.read_bytes()
        requests = len(self.get_server.requests)
        elsewhere = self.root/"other-directory"
        elsewhere.mkdir()
        copied = [elsewhere/path.name for path in self.paths]
        for source, destination in zip(self.paths, copied):
            destination.write_bytes(source.read_bytes())
        self.get_server.payloads[target.PATHS[0]] = dict(self.before, boot_id="9"*32)
        fresh_wire = self.wire()
        result = target.run_partial(target.prepare(*copied), self.identity_path, HOST,
            elsewhere/"changed.attempt", authorized=True,
            confirm_sha256=artifacts.candidate["sha256"], transport=fresh_wire,
            reader_factory=self.reader)
        self.assertEqual(result["reason"], "CANDIDATE_ALREADY_ATTEMPTED_NO_RETRY")
        self.assertEqual((self.server.posts, len(self.get_server.requests)), (1, requests))
        self.assertFalse(fresh_wire.used)
        self.assertFalse((elsewhere/"changed.attempt").exists())
        self.assertEqual((attempt.read_bytes(), self.marker.read_bytes()), (saved_attempt, saved_marker))

    def test_unknown_send_cannot_retry_using_another_marker(self):
        self.server.failure = "send"
        first = self.partial()
        requests = len(self.get_server.requests)
        marker = self.marker.read_bytes()
        second = self.partial(marker=self.root/"retry.attempt")
        self.assertEqual(first["status"], "STOP_UNKNOWN_NO_RETRY")
        self.assertEqual(second["reason"], "CANDIDATE_ALREADY_ATTEMPTED_NO_RETRY")
        self.assertEqual((self.server.posts, self.server.send_calls, len(self.server.body)), (1, 1, 7))
        self.assertEqual(len(self.get_server.requests), requests)
        self.assertEqual(self.marker.read_bytes(), marker)
        self.assertFalse((self.root/"retry.attempt").exists())

    def test_ambiguous_reservation_or_directory_is_preserved_and_blocks_all_http(self):
        artifacts = self.prepare()
        attempt = target._attempt_path(artifacts)
        # Independent synthetic state stores; no production marker is removed.
        for name, content in (("empty", b""), ("corrupt", b"{unfinished")):
            with self.subTest(state=name), patch.object(coord, "_lock_directory", return_value=self.root/name):
                stored = target._attempt_path(artifacts)
                stored.parent.mkdir(parents=True)
                stored.write_bytes(content)
                result = self.partial(marker=self.root/(name+".attempt"))
                self.assertEqual(result["reason"], "CANDIDATE_ALREADY_ATTEMPTED_NO_RETRY")
                self.assertEqual(stored.read_bytes(), content)
        attempt.parent.write_bytes(b"UNCLASSIFIED EXISTING STATE")
        result = self.partial()
        self.assertEqual(result["reason"], "ATTEMPT_STATE_UNKNOWN_NO_RETRY")
        self.assertEqual(attempt.parent.read_bytes(), b"UNCLASSIFIED EXISTING STATE")
        self.assertEqual((self.server.posts, len(self.get_server.requests)), (0, 0))
        self.assertFalse(self.marker.exists())

    def test_marker_fsync_failure_keeps_reservation_and_blocks_changed_path(self):
        with patch.object(target.os, "fsync", side_effect=[None, OSError(PASSWORD)]):
            first = self.partial()
        artifacts = self.prepare()
        attempt = target._attempt_path(artifacts)
        saved_attempt, saved_marker = attempt.read_bytes(), self.marker.read_bytes()
        requests = len(self.get_server.requests)
        second = self.partial(marker=self.root/"different.attempt")
        self.assertEqual(first["status"], "STOP_UNKNOWN_NO_RETRY")
        self.assertEqual(second["reason"], "CANDIDATE_ALREADY_ATTEMPTED_NO_RETRY")
        self.assertEqual((self.server.posts, len(self.get_server.requests)), (0, requests))
        self.assertEqual((attempt.read_bytes(), self.marker.read_bytes()), (saved_attempt, saved_marker))

    def test_atomic_reservation_allows_one_post_across_distinct_concurrent_instances(self):
        artifacts = self.prepare()
        barrier = threading.Barrier(2)
        before = self.before.copy()
        class ConcurrentReader:
            def __init__(self, *args):
                pass
            def get(self, path):
                barrier.wait(timeout=3)  # Both pass the initial disk check before reserving.
                return before
        outcomes = []
        markers = [self.root/(str(i)+".attempt") for i in range(2)]
        def worker(marker):
            outcomes.append(target.run_partial(artifacts, self.identity_path, HOST, marker,
                authorized=True, confirm_sha256=artifacts.candidate["sha256"],
                transport=self.wire(), reader_factory=ConcurrentReader))
        workers = [threading.Thread(target=worker, args=(marker,)) for marker in markers]
        for thread in workers:
            thread.start()
        for thread in workers:
            thread.join(timeout=5)
            self.assertFalse(thread.is_alive())
        self.assertCountEqual([row["reason"] for row in outcomes],
            ["SEPARATE_EVIDENCE_REQUIRED", "CANDIDATE_ALREADY_ATTEMPTED_NO_RETRY"])
        self.assertEqual((self.server.posts, self.server.connections), (1, 1))
        self.assertEqual(self.server.body, self.candidate_raw[:8192])
        self.assertEqual(sum(marker.exists() for marker in markers), 1)
        self.assertTrue(target._attempt_path(artifacts).is_file())

    def test_authorization_and_exact_confirm_are_required_before_any_get(self):
        for args in ({"authorized": False}, {"confirm": "f"*64}):
            result = self.partial(**args)
            self.assertEqual(result["reason"], "PHYSICAL_AUTHORIZATION_REQUIRED")
        self.assertEqual((self.server.posts, len(self.get_server.requests)), (0, 0))
        self.assertFalse(self.marker.exists())

    def test_running_identity_or_resource_failure_never_reserves_marker_or_posts(self):
        for change in ({"sha256": "a"*64}, {"stack": 2044}, {"heap": 25599},
                       {"frag": 26}, {"fs_ok": False}, {"last_update": "REFUSED"}):
            self.get_server.payloads[target.PATHS[0]] = dict(self.before, **change)
            result = self.partial()
            self.assertEqual(result["status"], "STOP_UNKNOWN_NO_RETRY")
            self.assertFalse(self.marker.exists())
        self.assertEqual(self.server.posts, 0)

    def test_second_digest_401_blocks_post_and_never_retries(self):
        self.get_server.always_401 = True
        result = self.partial()
        self.assertEqual(result["reason"], "SECOND_401")
        self.assertEqual((len(self.get_server.requests), self.server.posts), (2, 0))

    def test_malformed_digest_challenge_blocks_authorization_and_post(self):
        self.get_server.challenge_override = 'Digest realm="UNREVIEWED", nonce="bad"'
        result = self.partial()
        self.assertEqual(result["reason"], "INVALID_DIGEST_CHALLENGE")
        self.assertEqual((len(self.get_server.requests), self.server.posts), (1, 0))

    def test_wrong_owner_device_blocks_every_get_and_post(self):
        changed = dict(self.identity, device="2123456789abcdef")
        self.identity_path.write_text(json.dumps(changed), encoding="utf-8")
        result = self.partial()
        self.assertEqual(result["reason"], "OWNER_IDENTITY_HOLD")
        self.assertEqual((len(self.get_server.requests), self.server.posts), (0, 0))

    def test_corrupt_bin_sha_stops_local_inspection(self):
        self.paths[0].write_bytes(self.candidate_raw[:-1]+b"x")
        with self.assertRaises(target.Stop):
            self.prepare()
        self.assertEqual(self.server.connections, 0)

    def test_manifest_duplicate_or_wrong_size_or_wrong_build_stops_locally(self):
        for text in ('{"schema":1,"schema":1}', json.dumps(dict(self.manifests[0], bytes=8192)),
                     json.dumps(dict(self.manifests[0], build_id="f"*64))):
            self.paths[1].write_text(text, encoding="utf-8")
            with self.assertRaises(target.Stop):
                self.prepare()
        self.assertEqual(self.server.connections, 0)

    def test_candidate_role_and_layout_must_be_evidenced(self):
        original = json.loads(self.paths[2].read_text(encoding="utf-8"))
        for change in ({"firmware": "B5"}, {"layout_symbols": {}}, {"sha256": "f"*64}):
            self.paths[2].write_text(json.dumps(dict(original, **change)), encoding="utf-8")
            with self.assertRaises(target.Stop):
                self.prepare()

    def test_concurrency_holds_before_post_bytes(self):
        self.partial()  # Reuse a legitimate pre-read context, but a separate single-use wire.
        server = PostServer()
        wire = target.PartialTransport(HOST, connection_factory=server.connection,
                                       timer_factory=PassiveTimer, clock=lambda: self.now)
        with coord.digest_exchange(HOST, wait_seconds=0):
            with self.assertRaises(coord.CoordinationBusy):
                wire.send(self.prepare(), self.identity, "2"*32)
        self.assertEqual(server.connections, 0)

    def test_timeouts_interruptions_header_and_close_errors_never_send_tail(self):
        for failure in ("timeout", "interrupt", "headers", "shutdown", "zero"):
            self.server = PostServer()
            self.server.failure = failure
            # Each error scenario has an independent synthetic per-user state store.
            with patch.object(coord, "_lock_directory", return_value=self.root/(failure+"-state")):
                result = self.partial(marker=self.root/(failure+".attempt"))
            self.assertEqual(result["status"], "STOP_UNKNOWN_NO_RETRY")
            self.assertLessEqual(len(self.server.body), 8192)
            self.assertEqual(self.server.posts, 1)
            self.assertGreaterEqual(self.server.closed, 1)
            self.assertEqual(self.server.getresponse_calls, 0)

    def test_total_deadline_aborts_after_a_slow_partial_send(self):
        self.server.pattern = [16]
        self.server.on_send = lambda: setattr(self, "now", self.now+7)
        result = self.partial()
        self.assertEqual(result["reason"], "TIMEOUT")
        self.assertEqual(len(self.server.body), 16)
        self.assertEqual(self.server.send_calls, 1)

    def test_watchdog_interrupts_registered_socket_without_retry(self):
        timers = []
        class Timer(PassiveTimer):
            def __init__(self, seconds, callback):
                super().__init__(seconds, callback)
                timers.append(callback)
        self.server.pattern = [16]
        self.server.on_send = lambda: timers[-1]()
        wire = target.PartialTransport(HOST, connection_factory=self.server.connection,
                                       clock=lambda: self.now, timer_factory=Timer)
        result = self.partial(wire=wire)
        self.assertEqual(result["reason"], "TIMEOUT")
        self.assertIn(socket.SHUT_RDWR, self.server.shutdowns)
        self.assertEqual((self.server.send_calls, self.server.posts), (1, 1))
        self.assertEqual(len(self.server.body), 16)

    def test_pre_read_concurrency_is_refused_before_any_http(self):
        with coord.digest_exchange(HOST, wait_seconds=0):
            result = self.partial()
        self.assertEqual(result["status"], "STOP_UNKNOWN_NO_RETRY")
        self.assertEqual((len(self.get_server.requests), self.server.posts), (0, 0))
        self.assertFalse(self.marker.exists())

    def test_marker_creation_race_preserves_the_other_record_and_blocks_post(self):
        self.get_server.on_read = lambda response: self.marker.write_text("CONCURRENT-RECORD", encoding="utf-8")
        result = self.partial()
        self.assertEqual(result["status"], "STOP_UNKNOWN_NO_RETRY")
        self.assertEqual(self.server.posts, 0)
        self.assertEqual(self.marker.read_text(encoding="utf-8"), "CONCURRENT-RECORD")

    def test_evidence_read_is_separate_and_preserves_failed_state_and_minima(self):
        self.partial()
        self.after()
        result = self.evidence()
        self.assertEqual(result["status"], "PARTIAL_OBSERVATIONS_RECORDED_HOLD")
        self.assertEqual(result["observations"]["last_update"], "FAILED_NO_COMMIT")
        self.assertEqual([result["observations"][k] for k in target.MINIMA], [24000, 21000, 2080, 8])
        self.assertNotIn("nonce", result["observations"])
        self.assertEqual((self.server.posts, len(self.get_server.requests)), (1, 4))
        self.assertFalse(result["ota_success"])
        self.assertFalse(result["native_high_water_qualified"])
        self.assertIsNone(result["receiver_bytes_confirmed"])

    def test_unsafe_minima_or_littlefs_remain_in_hold_record(self):
        self.partial()
        for changes in ({"ota_stack_min": 2000}, {"ota_heap_min": 0, "ota_block_min": 0},
                        {"fs_ok": False}):
            after = dict(self.before, nonce="3"*32, last_update="FAILED_NO_COMMIT",
                         ota_heap_min=24000, ota_block_min=21000, ota_stack_min=2080, ota_frag_max=8)
            self.get_server.payloads[target.PATHS[0]] = dict(after, **changes)
            result = self.evidence()
            self.assertEqual(result["status"], "STOP_UNKNOWN_NO_RETRY")
            for k, v in changes.items():
                self.assertEqual(result["observations"][k], v)
        self.assertEqual(self.server.posts, 1)

    def test_reboot_or_changed_identity_is_unknown_not_ota_success(self):
        self.partial()
        for key, value in (("boot_id", "4"*32), ("sha256", "a"*64)):
            self.after()
            self.get_server.payloads[target.PATHS[0]][key] = value
            result = self.evidence()
            self.assertEqual(result["reason"], "IDENTITY_OR_BOOT_CHANGED_UNKNOWN")
            self.assertFalse(result["ota_success"])

    def test_refused_staged_or_absent_evidence_stops_without_post_or_polling(self):
        self.partial()
        for state in ("NONE", "REFUSED", "STAGED", "RECEIVING"):
            self.after()
            self.get_server.payloads[target.PATHS[0]]["last_update"] = state
            before = len(self.get_server.requests)
            result = self.evidence()
            self.assertEqual(result["reason"], "UNEXPECTED_OTA_STATE_HOLD")
            self.assertEqual(len(self.get_server.requests)-before, 2)
            self.assertFalse(result["ota_success"])
        self.assertEqual(self.server.posts, 1)

    def test_missing_evidence_response_is_not_retried(self):
        self.partial()
        self.get_server.failure = "connect"
        count = len(self.get_server.requests)
        result = self.evidence()
        self.assertEqual(result["status"], "STOP_UNKNOWN_NO_RETRY")
        self.assertEqual(len(self.get_server.requests), count)
        self.assertEqual(self.server.posts, 1)

    def test_corrupt_marker_boot_context_blocks_evidence_before_any_get(self):
        self.partial()
        context = json.loads(self.marker.read_text(encoding="utf-8"))
        context["before"]["boot_id"] = "bad"
        self.marker.write_text(json.dumps(context), encoding="utf-8")
        count = len(self.get_server.requests)
        result = self.evidence()
        self.assertEqual(result["reason"], "ATTEMPT_CONTEXT_HOLD")
        self.assertEqual(len(self.get_server.requests), count)
        self.assertEqual(self.server.posts, 1)

    def test_existing_receipt_blocks_cli_before_any_network_and_is_preserved(self):
        receipt = self.root/"preserved.json"
        receipt.write_text("OLD-RECEIPT", encoding="utf-8")
        names = ("candidate-bin", "candidate-manifest", "candidate-report",
                 "current-bin", "current-manifest", "current-report")
        args = [value for name, path in zip(names, self.paths) for value in ("--"+name, str(path))]
        args += ["--mode", "partial", "--identity", str(self.identity_path), "--host", HOST,
                 "--attempt-marker", str(self.marker), "--receipt", str(receipt),
                 "--authorize-partial", "--confirm-sha256", self.manifests[0]["sha256"]]
        with contextlib.redirect_stdout(io.StringIO()):
            self.assertEqual(target.main(args), 2)
        self.assertEqual(receipt.read_text(encoding="utf-8"), "OLD-RECEIPT")
        self.assertEqual((self.server.posts, len(self.get_server.requests)), (0, 0))

    def test_record_creation_failure_prevents_post(self):
        attempt = target._attempt_path(self.prepare())
        with patch.object(target.os, "fsync", side_effect=OSError(PASSWORD)):
            result = self.partial()
        self.assertEqual(result["status"], "STOP_UNKNOWN_NO_RETRY")
        self.assertEqual(self.server.posts, 0)
        self.assertTrue(attempt.exists())  # Failed reservations are never deleted for retry.
        requests = len(self.get_server.requests)
        self.assertEqual(self.partial(marker=self.root/"retry.attempt")["reason"],
                         "CANDIDATE_ALREADY_ATTEMPTED_NO_RETRY")
        self.assertEqual(len(self.get_server.requests), requests)

    def test_secrets_are_absent_from_results_records_and_stdout(self):
        self.get_server.payloads[target.PATHS[0]]["untrusted_field"] = PASSWORD
        self.server.failure = "send"
        output = io.StringIO()
        with contextlib.redirect_stdout(output), contextlib.redirect_stderr(output):
            result = self.partial()
        text = (output.getvalue()+json.dumps(result)+self.marker.read_text(encoding="utf-8")
                +target._attempt_path(self.prepare()).read_text(encoding="utf-8"))
        for field in ("ap_psk", "api_token", "digest_password", "maintenance_password"):
            self.assertNotIn(self.identity[field], text)
        self.assertNotIn(PASSWORD, text)
        self.assertNotIn(self.server.headers["X-Shino-Proof"], text)
        self.assertNotIn('"nonce"', text)

    def test_secret_echo_even_in_a_valid_hex_identity_field_is_not_logged(self):
        self.identity["api_token"] = "e"*64
        self.identity_path.write_text(json.dumps(self.identity), encoding="utf-8")
        self.partial()
        self.after()
        self.get_server.payloads[target.PATHS[0]]["sha256"] = self.identity["api_token"]
        result = self.evidence()
        self.assertEqual(result["reason"], "SECRET_RESPONSE_HOLD")
        self.assertNotIn(self.identity["api_token"], json.dumps(result))
        self.assertNotIn("observations", result)
        self.assertEqual(self.server.posts, 1)

    def test_default_cli_is_only_local_inspection_without_credentials_or_sockets(self):
        names = ("candidate-bin", "candidate-manifest", "candidate-report",
                 "current-bin", "current-manifest", "current-report")
        args = [value for name, path in zip(names, self.paths) for value in ("--"+name, str(path))]
        with patch.object(target, "load_identity", side_effect=AssertionError("NO PRIVATE IDENTITY")), \
             patch.object(target, "PartialTransport", side_effect=AssertionError("NO TRANSPORT")), \
             contextlib.redirect_stdout(io.StringIO()) as out:
            self.assertEqual(target.main(args), 0)
        self.assertEqual(json.loads(out.getvalue())["status"], "LOCAL_INSPECTION_ONLY")
        self.assertFalse(self.marker.exists())

    def test_evidence_requires_independent_authorization(self):
        result = target.collect_evidence(self.prepare(), self.identity_path, HOST, self.marker,
                                         reader_factory=self.reader)
        self.assertEqual(result["reason"], "READ_AUTHORIZATION_REQUIRED")
        self.assertEqual(len(self.get_server.requests), 0)

    def test_one_status_reader_cannot_poll_or_use_other_endpoints(self):
        reader = self.reader(self.identity, self.manifests[1], HOST)
        reader.get(target.PATHS[0])
        for path in (target.PATHS[0], target.PATHS[1]):
            with self.assertRaises(target.DiagnosticStop):
                reader.get(path)
        self.assertEqual(len(self.get_server.requests), 2)


if __name__ == "__main__":
    unittest.main()
