"""Real LINK, Digest, HMAC and 1s deadline against one loopback-only fake receiver.

No owner config, identity or secret is read. The socket seam maps the public
logical fixture to 127.0.0.1 and forbids every other connection and DNS lookup.
The simulated receiver is not the native ESP8266 and provides no device proof.
"""
from contextlib import contextmanager, ExitStack
import hashlib
import hmac
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
import json
from pathlib import Path
import socket
import struct
import sys
import tempfile
import threading
import time
import unittest
from unittest.mock import patch
from urllib.request import parse_http_list, parse_keqv_list

import clock_sync
import shino_digest_coord as coord
import shino_link as link
from push_fsless_metrics import make_opener, FIELDS
from test_shino_link import SAMPLE

HOST = '192.168.4.1'  # Logical fixture ONLY; never a real socket destination.
USER, PASSWORD, REALM = 'shino', 'PUBLIC-INERT-LINK-CLOCK-FIXTURE', 'SHINO-StageA'
METRICS = '/api/v1/bridge/metrics'
STATUS, SYNC = '/api/v1/clock/status', '/api/v1/clock/sync'
MEASUREMENTS = []


class Receiver(ThreadingHTTPServer):
    daemon_threads = True
    def __init__(self, phase, locks):
        self.phase, self.locks = phase, locks
        self.guard = threading.Lock()
        self.nonce = ''
        self.sequence = 0
        self.boot = bytes.fromhex('11' * 16)
        self.pending = None
        self.utc = None
        self.events, self.metrics_at, self.metric_values = [], [], []
        self.clock_at, self.frames, self.errors = [], [], []
        super().__init__(('127.0.0.1', 0), Handler)


class Handler(BaseHTTPRequestHandler):
    protocol_version = 'HTTP/1.1'
    def log_message(self, *args): pass
    def response(self, packet, code=200, *, slow=False, headers=None):
        raw = json.dumps(packet, separators=(',', ':')).encode()
        self.send_response(code)
        self.send_header('Content-Length', str(len(raw)))
        self.send_header('Connection', 'close')
        for name, value in (headers or {}).items(): self.send_header(name, value)
        self.end_headers()
        if slow:
            for ch in raw:
                self.wfile.write(bytes((ch,)))
                self.wfile.flush()
                time.sleep(.05)
        else: self.wfile.write(raw)
        self.close_connection = True
    def authenticated(self):
        auth = self.headers.get('Authorization', '')
        if not auth.startswith('Digest '): return False
        fields = parse_keqv_list(parse_http_list(auth[7:]))
        if (fields.get('username') != USER or fields.get('realm') != REALM
                or fields.get('nonce') != self.server.nonce or fields.get('uri') != self.path
                or fields.get('qop') != 'auth'):
            return False
        md5 = lambda value: hashlib.md5(value.encode()).hexdigest()
        ha1, ha2 = md5(f'{USER}:{REALM}:{PASSWORD}'), md5(f'{self.command}:{self.path}')
        expected = md5(':'.join((ha1, self.server.nonce, fields.get('nc', ''),
                                 fields.get('cnonce', ''), 'auth', ha2)))
        return hmac.compare_digest(fields.get('response', ''), expected)
    def handle_request(self):
        self.connection.settimeout(2)
        count = int(self.headers.get('Content-Length', '0'))
        if not 0 <= count <= 384: raise AssertionError('public fixture body bound')
        raw = self.rfile.read(count)
        server = self.server
        with server.guard:
            # Both metrics and clock must hold the actual OS Digest lock.
            try:
                with coord.digest_exchange(HOST, wait_seconds=0, directory=server.locks):
                    raise AssertionError('HTTP outside coordinator')
            except coord.CoordinationBusy: pass
            valid = self.authenticated()
            server.events.append((self.command, self.path, valid))
            if not valid:
                server.sequence += 1
                server.nonce = f'public-nonce-{server.sequence}'
                challenge = f'Digest realm="{REALM}", nonce="{server.nonce}", opaque="public", algorithm=MD5, qop="auth"'
                self.response({}, 401, headers={'WWW-Authenticate': challenge})
                return
            if self.command == 'POST' and self.path == METRICS:
                packet = json.loads(raw)
                if set(packet) != set(FIELDS): raise AssertionError('metrics shape changed')
                server.metrics_at.append(time.monotonic())
                server.metric_values.append(tuple(packet[name] for name in
                    ('cpu_usage', 'gpu_usage', 'memory_used_gb', 'gpu_temp_c')))
                self.response(dict(status='RAM_SAMPLE_ACCEPTED', persisted=False))
            elif self.command == 'GET' and self.path == STATUS:
                if server.phase == 'absent':
                    self.response({}, 404)
                    return
                server.pending = bytes.fromhex(f'{server.sequence + len(server.clock_at) + 32:032x}')
                packet = dict(protocol=clock_sync.PROTOCOL, clock_enabled=True,
                              boot=server.boot.hex(), challenge=server.pending.hex(), challenge_ms=2000)
                if server.phase == 'incompatible': packet['protocol'] = 'unsupported'
                if server.phase == 'slow_get_headers': time.sleep(1.15)
                self.response(packet, slow=server.phase == 'slow_get_body')
            elif self.command == 'POST' and self.path == SYNC:
                server.frames.append(raw)
                if len(raw) != 64 or raw[:8] != b'SHINOCL2' or raw[16:32] != server.pending:
                    raise AssertionError('clock frame/challenge invalid')
                server.pending = None
                key = hmac.new(PASSWORD.encode(), b'SHINO-PC-CLOCK-KEY-2\n', hashlib.sha256).digest()
                tag = hmac.new(key, b'SHINO-PC-CLOCK-SYNC-2\n' + server.boot + raw[:32], hashlib.sha256).digest()
                if not hmac.compare_digest(tag, raw[32:]): raise AssertionError('clock proof invalid')
                utc, offset, lease = struct.unpack('<IhH', raw[8:16])
                if not 1577836800 <= utc <= 4102444799 or not -720 <= offset <= 840 or not 1 <= lease <= 120:
                    raise AssertionError('clock field invalid')
                server.utc = utc
                server.clock_at.append(time.monotonic())
                if server.phase == 'post_401':
                    self.response({}, 401, headers={'WWW-Authenticate':
                        f'Digest realm="{REALM}", nonce="replacement", qop="auth"'})
                elif server.phase == 'unknown': self.response(dict(status='UNKNOWN'))
                else:
                    self.response(dict(status='CLOCK_SAMPLE_ACCEPTED', persisted=False),
                                  slow=server.phase == 'slow_post_body')
            else: raise AssertionError('unexpected route')
    def do_GET(self): self.dispatch()
    def do_POST(self): self.dispatch()
    def dispatch(self):
        try: self.handle_request()
        except (ConnectionError, TimeoutError): pass  # Deadline closes the fake peer.
        except Exception as exc:
            self.server.errors.append(type(exc).__name__)
            self.close_connection = True


@contextmanager
def loopback(phase):
    with tempfile.TemporaryDirectory(prefix='shino-link-clock-host-') as folder:
        locks = Path(folder) / 'digest'
        with Receiver(phase, locks) as server:
            real_connect, real_resolve = socket.create_connection, socket.getaddrinfo
            real_raw_connect = socket.socket.connect
            violations = []
            def connect(address, *args, **kwargs):
                if address != (HOST, 80):
                    violations.append('unexpected_logical_destination')
                    raise AssertionError('NO DEVICE CONTACT')
                return real_connect(server.server_address, *args, **kwargs)
            def resolve(host, port, *args, **kwargs):
                if (host, port) != server.server_address:
                    violations.append('non_loopback_resolution')
                    raise AssertionError('NO EXTERNAL DNS')
                return real_resolve(host, port, *args, **kwargs)
            def raw_connect(sock, address):
                if address != server.server_address:
                    violations.append('non_loopback_socket')
                    raise AssertionError('NO DEVICE SOCKET')
                return real_raw_connect(sock, address)
            worker = threading.Thread(target=server.serve_forever,
                                      kwargs={'poll_interval': .02}, daemon=True)
            worker.start()
            try:
                with ExitStack() as stack:
                    stack.enter_context(patch.object(socket, 'create_connection', connect))
                    stack.enter_context(patch.object(socket, 'getaddrinfo', resolve))
                    stack.enter_context(patch.object(socket.socket, 'connect', raw_connect))
                    stack.enter_context(patch.object(coord, '_lock_directory', return_value=locks))
                    yield server
            finally:
                server.shutdown()
                worker.join(1)
                if violations: raise AssertionError(violations)
                if server.errors: raise AssertionError(server.errors)


def make_test_engine(server):
    # Test-only socket redirection above keeps the production private-host gate.
    publisher = link.LinkClockPublisher(HOST, lambda host: clock_sync.ClockTransport(host, USER, PASSWORD))
    number = [0]
    def sample():
        number[0] += 1
        return dict(SAMPLE, cpu_usage=20 + number[0] % 20,
                    gpu_usage=40 + number[0] % 20, memory_used_gb=7 + number[0] / 1000,
                    gpu_temp_c=45 + number[0] % 10)
    engine = link.LinkEngine(HOST, make_opener(HOST, USER, PASSWORD), sample,
        sender=link.coordinated_link_sender,
        opener_factory=lambda: make_opener(HOST, USER, PASSWORD), clock_publisher=publisher)
    return engine


class LoopbackTests(unittest.TestCase):
    def exercise(self, phase, samples=2):
        with loopback(phase) as server:
            engine = make_test_engine(server)
            stop = threading.Event()
            release, locked = threading.Event(), threading.Event()
            holder = None
            if phase == 'busy':
                # A cooperating other client acquires the OS lock after telemetry.
                # No second sender and no HTTP from that client.
                original = engine.sender
                def sender(*args, **kwargs):
                    result = original(*args, **kwargs)
                    if engine.attempts == 0:
                        def hold():
                            with coord.digest_exchange(HOST, wait_seconds=0, directory=server.locks):
                                locked.set()
                                release.wait(3)
                        nonlocal holder
                        holder = threading.Thread(target=hold)
                        holder.start()
                        if not locked.wait(1): raise AssertionError('holder failed')
                    return result
                engine.sender = sender
            def observe(data):
                release.set()
                if data['accepted'] >= samples: stop.set()
            started = time.monotonic()
            watchdog = threading.Timer(samples * 3 + 5, stop.set)
            watchdog.daemon = True
            watchdog.start()
            try:
                engine.run(stop, lambda state: None, observe)
            finally:
                watchdog.cancel()
                release.set()
                if holder is not None: holder.join(1)
            elapsed = time.monotonic() - started
            self.assertEqual(engine.accepted, samples)
            self.assertEqual(engine.failures, 0)
            self.assertEqual(engine.ttl_overruns, 0)
            self.assertEqual(len(server.metrics_at), samples)
            self.assertEqual(len(set(server.metric_values)), samples, 'all four measurements remain live')
            self.assertLess(engine.max_success_interval_ms, 6000)
            self.assertTrue(all(route in (METRICS, STATUS, SYNC) for _, route, _ in server.events))
            self.assertTrue(all(valid for method, route, valid in server.events if route == SYNC),
                            'POST must carry Digest on its first and only request')
            self.assertTrue(all(row['duration_ms'] < 1400 for row in engine.clock_publisher.history),
                            '1s deadline with explicit HOST scheduling tolerance, not a physical bound')
            row = dict(phase=phase, duration_ms=round(elapsed * 1000, 3), metrics_accepted=engine.accepted,
                       max_ack_interval_ms=round(engine.max_success_interval_ms, 3),
                       ttl_overruns=engine.ttl_overruns,
                       clock=engine.clock_publisher.snapshot(),
                       clock_gets=sum(method == 'GET' and route == STATUS for method, route, _ in server.events),
                       clock_posts=len(server.frames), metrics_http_requests=sum(route == METRICS for _, route, _ in server.events))
            MEASUREMENTS.append(row)
            return row

    def test_real_sixty_second_cadence_with_metrics_active(self):
        row = self.exercise('nominal', samples=32)
        self.assertEqual(row['clock']['accepted'], 2)
        self.assertEqual(row['clock_posts'], 2)
        self.assertEqual(row['clock_gets'], 4, 'fresh Digest challenge for each periodic operation')

    def test_busy_lock_does_not_issue_clock_get_and_metrics_continue(self):
        row = self.exercise('busy')
        self.assertEqual(row['clock']['last_result'], 'CLOCK_COORDINATION_HOLD')
        self.assertEqual((row['clock_gets'], row['clock_posts']), (0, 0))

    def test_slow_get_headers_and_body_timeout_without_post(self):
        for phase in ('slow_get_headers', 'slow_get_body'):
            with self.subTest(phase=phase):
                row = self.exercise(phase)
                self.assertEqual(row['clock']['last_result'], 'CLOCK_SOURCE_HOLD')
                self.assertEqual(row['clock_posts'], 0)

    def test_slow_post_unknown_and_401_suspend_without_replay(self):
        for phase in ('slow_post_body', 'unknown', 'post_401'):
            with self.subTest(phase=phase):
                row = self.exercise(phase)
                self.assertEqual(row['clock']['state'], 'CLOCK_UNKNOWN_NO_RETRY')
                self.assertEqual(row['clock_posts'], 1)

    def test_absent_and_incompatible_receiver_stop_before_post(self):
        for phase in ('absent', 'incompatible'):
            with self.subTest(phase=phase):
                row = self.exercise(phase)
                self.assertEqual(row['clock']['state'], 'CLOCK_COMPATIBILITY_HOLD')
                self.assertEqual(row['clock_posts'], 0)

    def test_new_boot_fresh_transport_and_secret_not_in_diagnostics(self):
        with loopback('nominal') as server:
            engine = make_test_engine(server)
            engine.step()
            server.boot = bytes.fromhex('33' * 16)
            server.utc = None
            engine.clock_publisher.disconnected()
            engine.next_due = 0  # Only this protocol regression accelerates metrics.
            engine.step()
            self.assertEqual(engine.clock_publisher.accepted, 2)
            self.assertNotEqual(server.frames[0], server.frames[1])
            # A restarted companion has no prior packet/nonce to replay.
            fresh = make_test_engine(server)
            fresh.step()
            self.assertEqual(fresh.clock_publisher.accepted, 1)
            self.assertEqual(len(set(server.frames)), 3)
            encoded = json.dumps(fresh.diagnostics())
            for forbidden in (PASSWORD, USER, REALM, 'nonce', 'Authorization', 'challenge', HOST):
                self.assertNotIn(forbidden, encoded)

    def test_concurrent_lock_load_with_clock_enabled_preserves_metric_ttl(self):
        with loopback('nominal') as server:
            engine = make_test_engine(server)
            stop, peer_stop = threading.Event(), threading.Event()
            peer_holds, peer_errors = [], []
            def peer():
                while not peer_stop.is_set():
                    try:
                        with coord.digest_exchange(HOST, wait_seconds=0, directory=server.locks):
                            peer_holds.append(time.monotonic())
                            peer_stop.wait(.12)
                    except coord.CoordinationBusy: pass
                    except Exception as exc: peer_errors.append(type(exc).__name__)
                    peer_stop.wait(.03)
            contender = threading.Thread(target=peer)
            def observe(data):
                if data['accepted'] == 1: contender.start()
                # Stress only: make every following fresh ACK eligible instead
                # of waiting60s. The real1s deadline and2s metrics stay unchanged.
                engine.clock_publisher.next_due = 0
                if data['accepted'] >= 6: stop.set()
            started = time.monotonic()
            watchdog = threading.Timer(20, stop.set)
            watchdog.daemon = True
            watchdog.start()
            try:
                engine.run(stop, lambda state: None, observe)
            finally:
                watchdog.cancel()
                peer_stop.set()
                if contender.ident is not None: contender.join(1)
            self.assertEqual(peer_errors, [])
            self.assertGreater(len(peer_holds), 10)
            self.assertEqual(engine.accepted, 6)
            self.assertEqual(engine.ttl_overruns, 0)
            self.assertLess(engine.max_success_interval_ms, 6000)
            self.assertEqual(len(set(server.metric_values)), 6)
            self.assertGreaterEqual(engine.clock_publisher.accepted, 1)
            self.assertEqual(len(server.frames), engine.clock_publisher.accepted)
            self.assertEqual(len(set(server.frames)), len(server.frames), 'no POST replay')
            MEASUREMENTS.append(dict(phase='concurrent_lock_load',
                duration_ms=round((time.monotonic() - started) * 1000, 3),
                metrics_accepted=engine.accepted,
                max_ack_interval_ms=round(engine.max_success_interval_ms, 3),
                ttl_overruns=engine.ttl_overruns, peer_lock_holds=len(peer_holds),
                clock=engine.clock_publisher.snapshot(), clock_posts=len(server.frames),
                cadence='ACCELERATED_DUE_FOR_STRESS_ONLY'))


if __name__ == '__main__':
    program = unittest.main(exit=False)
    print('HOST_LOOPBACK_MEASUREMENTS=' + json.dumps(MEASUREMENTS, sort_keys=True))
    raise SystemExit(0 if program.result.wasSuccessful() else 1)
