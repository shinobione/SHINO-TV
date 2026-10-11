"""Windows OS lock + simulated HTTP; no sockets, devices or owner files.

The subprocess worker uses the real LINK engine and coordinator. Its HTTP
responses are fixtures; it does not model ESP8266/lwIP or prove device timing.
"""
from contextlib import ExitStack, contextmanager, redirect_stdout, redirect_stderr
from email.message import Message
import io
import json
from pathlib import Path
import subprocess
import sys
import tempfile
import threading
import time
import unittest
from unittest.mock import patch
from urllib.error import HTTPError, URLError
from urllib.request import Request

import shino_coordinated_qualify as qualifier
import shino_digest_coord as coord
from shino_link import LinkEngine, LinkError, coordinated_link_sender, diagnostics_writer
from push_fsless_metrics import SendStatus, make_opener
from test_push_fsless_metrics import DigestTransport, SAMPLE
import test_shino_update as updater_tests

HOST = "192.168.4.1"
PATH = "/api/v1/update/status"


@contextmanager
def no_network():
    with ExitStack() as stack:
        guards = [stack.enter_context(patch(name, side_effect=AssertionError("network forbidden")))
                  for name in ("socket.socket", "socket.create_connection", "socket.getaddrinfo",
                               "http.client.HTTPConnection.connect")]
        try:
            import serial
        except ImportError:
            pass
        else:
            guards.append(stack.enter_context(patch.object(serial, "Serial", side_effect=AssertionError("serial forbidden"))))
        yield
        for guard in guards:
            guard.assert_not_called()  # Catches attempts swallowed by LINK.


class Response(io.BytesIO):
    status = 200

    def __init__(self, body=b"{}", delay=0, event=None):
        super().__init__(body)
        self.headers = Message()
        self.delay = delay
        self.event = event

    def getcode(self):
        return self.status

    def read(self, limit=-1):
        time.sleep(self.delay)
        if self.event is not None:
            self.event["end"] = time.monotonic()
        return super().read(limit)


def worker(role, directory, delay):
    root = Path(directory)
    with no_network(), patch.object(coord, "_lock_directory", return_value=root):
        if role == "hold":
            with coord.digest_exchange(HOST):
                print("LOCKED", flush=True)
                assert sys.stdin.readline().strip() == "RELEASE"
            print("RELEASED", flush=True)
            return
        events = []

        class Opener:
            def open(self, request, timeout):
                # An actual second byte-lock must fail while POST is active.
                try:
                    with coord.digest_exchange(HOST, wait_seconds=0):
                        raise AssertionError("POST outside lock")
                except coord.CoordinationBusy:
                    pass
                assert timeout == 3.0 and request.get_method() == "POST"
                event = dict(kind="POST", start=time.monotonic())
                events.append(event)
                return Response(b'{"status":"RAM_SAMPLE_ACCEPTED","persisted":false}',
                                float(delay), event)

        diagnostics = coord.HttpDiagnostics()
        engine = LinkEngine(HOST, Opener(), lambda: SAMPLE,
                            sender=lambda *a, **k: coordinated_link_sender(*a, **k, diagnostics=diagnostics),
                            http_diagnostics=diagnostics)
        print("READY", flush=True)
        assert sys.stdin.readline().strip() == "START"
        stop = threading.Event()
        watcher = threading.Thread(target=lambda: (sys.stdin.readline(), stop.set()), daemon=True)
        watcher.start()
        engine.run(stop, lambda state: None)
        print(json.dumps(dict(events=events, diagnostics=engine.diagnostics())), flush=True)


class OfflineBase(unittest.TestCase):
    def setUp(self):
        self.enterContext(no_network())
        self.temp = self.enterContext(tempfile.TemporaryDirectory())
        self.root = Path(self.temp)
        self.enterContext(patch.object(coord, "_lock_directory", return_value=self.root))

    def child(self, role="post", delay=0.1):
        child = subprocess.Popen([sys.executable, str(Path(__file__).resolve()), "--worker",
                                  role, str(self.root), str(delay)],
                                 stdin=subprocess.PIPE, stdout=subprocess.PIPE,
                                 stderr=subprocess.PIPE, text=True)
        def cleanup():
            if child.poll() is None:
                child.kill()
            child.communicate(timeout=5)
        self.addCleanup(cleanup)
        self.assertEqual(child.stdout.readline().strip(), "LOCKED" if role == "hold" else "READY")
        return child


class OfflineTests(OfflineBase):
    def test_real_process_lock_wait_reaches_1500ms_limit_and_then_recovers(self):
        child = self.child("hold")
        timing = {}
        started = time.monotonic()
        with self.assertRaises(coord.CoordinationBusy) as caught:
            with coord.digest_exchange(HOST, timing=timing):
                self.fail("overlapping processes")
        elapsed = time.monotonic() - started
        self.assertEqual(caught.exception.code, "coordination_busy")
        self.assertGreaterEqual(elapsed, 1.5)
        self.assertLess(elapsed, 2.1)
        self.assertGreaterEqual(timing["lock_wait_ms"], 1500)
        self.assertIsNone(timing["http_under_lock_ms"])
        child.stdin.write("RELEASE\n"); child.stdin.flush()
        stdout, stderr = child.communicate(timeout=5)
        self.assertEqual(child.returncode, 0, stderr)
        self.assertIn("RELEASED", stdout)
        with coord.digest_exchange(HOST, wait_seconds=0):
            pass
        self.assertEqual(len(list(self.root.glob("*.lock"))), 1)

    def test_slow_get_body_timeout_releases_real_lock_without_retry(self):
        class Slow:
            def open(self, request, timeout):
                self.calls += 1
                self.timeout = timeout
                response = Response()
                def read(limit):
                    time.sleep(0.15)
                    raise TimeoutError("Authorization password nonce private-body")
                response.read = read
                return response
            calls = 0
        raw = Slow()
        diagnostics = coord.HttpDiagnostics()
        reader = coord.CoordinatedReader(raw, HOST, diagnostics=diagnostics)
        with self.assertRaises(TimeoutError):
            with reader.open(Request("http://" + HOST + PATH), timeout=5) as response:
                response.read(4097)
        self.assertEqual((raw.calls, raw.timeout), (1, 5))
        self.assertGreaterEqual(reader.last_exchange["http_under_lock_ms"], 125)
        self.assertEqual(diagnostics.history[-1]["outcome"], "timeout")
        with coord.digest_exchange(HOST, wait_seconds=0):
            pass

    def test_triple_get_and_concurrent_link_post_never_overlap_or_starve(self):
        child = self.child(delay=0.9)
        gets = []
        class Raw:
            def open(self, request, timeout):
                if not gets:
                    child.stdin.write("START\n"); child.stdin.flush()
                event = dict(kind="GET", start=time.monotonic())
                gets.append(event)
                return Response(delay=0.9, event=event)
        diagnostics = coord.HttpDiagnostics()
        reader = coord.CoordinatedReader(Raw(), HOST, read_gap_seconds=2.25, diagnostics=diagnostics)
        for _ in range(6):  # Two full three-GET cycles with a real competing process.
            with reader.open(Request("http://" + HOST + PATH), timeout=5) as response:
                response.read(4097)
        child.stdin.write("STOP\n"); child.stdin.flush()
        stdout, stderr = child.communicate(timeout=8)
        self.assertEqual(child.returncode, 0, stderr)
        result = json.loads(stdout)
        posts = result["events"]
        self.assertGreaterEqual(len(posts), 5)
        ordered = sorted(gets + posts, key=lambda e: e["start"])
        for left, right in zip(ordered, ordered[1:]):
            self.assertLessEqual(left["end"], right["start"])
        for first, second in zip(gets, gets[1:]):
            self.assertTrue(any(first["end"] <= post["start"] < second["start"] for post in posts))
        self.assertEqual(result["diagnostics"]["accepted"], result["diagnostics"]["attempts"])
        self.assertEqual(result["diagnostics"]["ttl_overruns"], 0)
        self.assertLess(result["diagnostics"]["max_success_interval_ms"], 6000)
        self.assertEqual(diagnostics.counts, {"http_200": 6})
        print(json.dumps(dict(fixture="WINDOWS_OS_LOCK_SIMULATED_HTTP_NO_NETWORK",
            gets=len(gets), accepted_posts=len(posts), failed_posts=0,
            max_ack_interval_ms=result["diagnostics"]["max_success_interval_ms"],
            max_post_lock_wait_ms=max(row["lock_wait_ms"] for row in result["diagnostics"]["http"]["history"]))))

    def test_coordination_failure_is_distinct_from_http_timeout(self):
        diagnostics = coord.HttpDiagnostics()
        with patch("shino_link.digest_exchange", side_effect=coord.CoordinationBusy("private", code="coordination_busy")), \
             patch("shino_link.send_sample", side_effect=AssertionError("HTTP outside lock")) as send:
            result = coordinated_link_sender(HOST, object(), SAMPLE, diagnostics=diagnostics)
        self.assertIs(result, SendStatus.CLIENT_ERROR)
        send.assert_not_called()
        self.assertEqual(diagnostics.history[-1]["outcome"], "coordination_busy")

    def test_digest_success_challenge_cache_and_terminal_errors_are_redacted(self):
        diagnostics = coord.HttpDiagnostics()
        transport = DigestTransport("SHINO-StageA")
        opener = make_opener(HOST, "shino", "fixture-password")
        opener.add_handler(transport)
        for _ in range(2):
            self.assertIs(coordinated_link_sender(HOST, opener, SAMPLE, diagnostics=diagnostics), SendStatus.ACCEPTED)
        self.assertEqual((transport.accepted, transport.challenges, transport.requests), (2, 1, 3))
        transport.unavailable_after_challenge = True
        self.assertIs(coordinated_link_sender(HOST, opener, SAMPLE, diagnostics=diagnostics), SendStatus.NO_ROUTE_TIMEOUT)
        class Refused:
            def open(self, *a, **k):
                raise HTTPError("http://secret", 401, "password nonce", Message(), io.BytesIO(b"raw-secret"))
        self.assertIs(coordinated_link_sender(HOST, Refused(), SAMPLE, diagnostics=diagnostics), SendStatus.HTTP_401)
        self.assertEqual([row["outcome"] for row in diagnostics.history],
                         ["accepted_sample", "accepted_sample", "timeout", "http_401"])
        encoded = json.dumps(diagnostics.snapshot())
        for secret in ("fixture-password", "Authorization", "nonce", "raw-secret", HOST, "SHINO-StageA"):
            self.assertNotIn(secret, encoded)

    def test_diagnostics_have_fixed_keys_bounded_history_and_no_request_text(self):
        diagnostics = coord.HttpDiagnostics()
        for _ in range(200):
            diagnostics.record("password nonce", "Authorization", dict(lock_wait_ms=1,
                http_under_lock_ms=2, private="SECRET", completed_monotonic=3), "secret")
        report = diagnostics.snapshot()
        self.assertEqual(len(report["history"]), 64)
        self.assertEqual(report["counts"], {"client_error": 200})
        self.assertNotIn("SECRET", json.dumps(report))
        self.assertEqual(report["history"][0]["operation"], "OTHER")

    def test_link_diagnostics_cannot_overwrite_receipts_backups_or_markers(self):
        for name in ("B3-readonly-receipt.json", "backup.bin", "UART-pre.attempt"):
            path = self.root / name
            path.write_bytes(b"ORIGINAL FIXTURE")
            with self.assertRaises(LinkError):
                diagnostics_writer(path)
            self.assertEqual(path.read_bytes(), b"ORIGINAL FIXTURE")

    def test_get_http401_closes_response_inside_lock(self):
        closed = []
        class Refused:
            def open(self, *a, **k):
                error = HTTPError("http://secret", 401, "nonce", Message(), io.BytesIO())
                def close():
                    with self.assert_busy():
                        pass
                    closed.append(True)
                error.close = close
                raise error
            @contextmanager
            def assert_busy(self):
                with self_test.assertRaises(coord.CoordinationBusy):
                    with coord.digest_exchange(HOST, wait_seconds=0):
                        pass
                yield
        self_test = self
        diagnostics = coord.HttpDiagnostics()
        reader = coord.CoordinatedReader(Refused(), HOST, diagnostics=diagnostics)
        with self.assertRaises(HTTPError):
            with reader.open(Request("http://" + HOST + PATH)):
                pass
        self.assertTrue(closed)
        self.assertEqual(diagnostics.history[-1]["outcome"], "http_401")


class ClockTests(unittest.TestCase):
    def setUp(self):
        self.enterContext(no_network())

    def test_backoff_recovery_and_ttl_episodes_use_completion_times(self):
        now = [0.0]
        results = iter([SendStatus.ACCEPTED, SendStatus.NO_ROUTE_TIMEOUT,
                        SendStatus.HTTP_401, SendStatus.CLIENT_ERROR, SendStatus.ACCEPTED])
        def send(*a, **k):
            now[0] += 0.1
            return next(results)
        engine = LinkEngine(HOST, object(), lambda: SAMPLE, sender=send,
                            clock=lambda: now[0], opener_factory=lambda: object())
        for delay in (2, 2, 4, 8, 2):
            engine.step()
            self.assertEqual(engine.next_due, now[0] + delay)
            engine.step()  # No immediate retry.
            now[0] = engine.next_due
        report = engine.diagnostics()
        self.assertEqual(report["accepted"], 2)
        self.assertEqual(report["ttl_overruns"], 1)
        self.assertAlmostEqual(report["history"][-1]["success_interval_ms"], 16400)
        self.assertTrue(report["history"][-1]["success_gap_exceeds_ttl"])
        self.assertEqual(engine.failures, 0)

    def test_ttl_boundary_is_strict_and_active_episode_counted_once(self):
        now = [0.0]
        engine = LinkEngine(HOST, object(), lambda: SAMPLE, sender=lambda *a, **k: True,
                            clock=lambda: now[0])
        engine.step()
        now[0] = 6
        self.assertEqual(engine.diagnostics()["ttl_overruns"], 0)
        now[0] = 6.001
        self.assertEqual(engine.diagnostics()["ttl_overruns"], 1)
        self.assertEqual(engine.diagnostics()["ttl_overruns"], 1)
        engine.step()
        self.assertEqual(engine.diagnostics()["ttl_overruns"], 1)

    def test_30_cycles_across_http_duration_envelope_have_bounded_post_gaps(self):
        # Discrete event HTTP model, actual LINK engine and pacing wrapper.
        # GET always wins immediate reacquisition; LINK runs only in the window.
        # No Windows scheduling or device guarantee is inferred from this model.
        for get_seconds, post_seconds, collection_seconds, phase in (
                (1, 1, 0, 0), (1, 1, 0, 1.999), (0.01, 1, 0, 1.9), (1, 0.01, 0, 0.5),
                (1, 1, 1.5, 0), (1, 1, 1.5, 1.999)):
            with self.subTest(get=get_seconds, post=post_seconds, collection=collection_seconds, phase=phase):
                now = [phase]
                def post(*a, **k):
                    now[0] += post_seconds
                    return SendStatus.ACCEPTED
                def sample():
                    now[0] += collection_seconds
                    return SAMPLE
                engine = LinkEngine(HOST, object(), sample, sender=post,
                                    clock=lambda: now[0])
                engine.next_due = phase
                def serve():
                    engine.step()
                def window(seconds):
                    end = now[0] + seconds
                    while engine.next_due <= end:
                        now[0] = max(now[0], engine.next_due)
                        serve()
                    now[0] = max(now[0], end)
                @contextmanager
                def locked(host, timing=None):
                    # Worst case: the GET wins when both operations are due.
                    timing.update(lock_wait_ms=0)
                    started = now[0]
                    yield
                    timing.update(http_under_lock_ms=(now[0]-started)*1000,
                                  completed_monotonic=now[0])
                class Raw:
                    def open(self, *a, **k):
                        now[0] += get_seconds
                        return Response()
                reader = coord.CoordinatedReader(Raw(), HOST, read_gap_seconds=2.25,
                                                  clock=lambda: now[0], sleep=window)
                with patch.object(coord, "digest_exchange", locked):
                    for _ in range(90):
                        with reader.open(Request("http://" + HOST + PATH)):
                            pass
                self.assertGreater(engine.accepted, 60)
                self.assertEqual(engine.attempts, engine.accepted)
                self.assertEqual(engine.ttl_overruns, 0)
                self.assertLessEqual(engine.max_success_interval_ms, 5750)


class QualifierIntegrationTests(OfflineBase):
    def setUp(self):
        super().setUp()
        updater_tests.UpdaterTests.setUp(self)  # Synthetic BIN/identity, never private owner files.

    def run_qualifier(self, *, fresh=True, fault=None, paced=True, diagnostics=True, elapsed=0):
        now = [0.0]
        calls = []
        sleeps = []
        self.enterContext(patch.object(coord.time, "monotonic", side_effect=lambda: now[0]))
        def sleep(seconds):
            sleeps.append(seconds)
            now[0] += seconds
        class Raw:
            def open(raw_self, request, timeout):
                calls.append((request.full_url, timeout))
                now[0] += elapsed
                if fault:
                    raise fault
                body = {"mode":"M9_NORMAL_STAGE_A"} if request.full_url.endswith("normal/status") else dict(self.after, metrics_fresh=fresh)
                return Response(json.dumps(body).encode())
        transport = type("IO", (), dict(base="http://"+HOST, host=HOST))()
        transport.reader = Raw()
        reader_class = coord.CoordinatedReader
        qualify_function = qualifier.shino_qualify.qualify
        receipt = self.binary.parent / "new-b3-receipt.json"
        args = ["--bin", str(self.binary), "--manifest", str(self.manifest),
                "--identity", str(self.credentials), "--receipt", str(receipt), "--authorize-read"]
        if paced:
            args.append("--b3-paced")
        if diagnostics:
            args.append("--http-diagnostics")
        with patch.object(qualifier, "Transport", return_value=transport), \
             patch.object(qualifier, "CoordinatedReader", side_effect=lambda *a, **k: reader_class(*a, **k, clock=lambda: now[0], sleep=sleep)), \
             patch.object(qualifier.shino_qualify, "qualify", side_effect=lambda *a, **k: qualify_function(*a, **k, cycles=2, sleep=sleep)), \
             redirect_stdout(io.StringIO()), redirect_stderr(io.StringIO()):
            code = qualifier.main(args)
        return code, json.loads(receipt.read_text()), calls, sleeps

    def test_b3_pacing_leaves_each_get_window_and_keeps_timeouts_and_checks(self):
        code, result, calls, sleeps = self.run_qualifier()
        self.assertEqual(code, 0)
        self.assertEqual(len(calls), 6)
        self.assertTrue(all(timeout == 5 for _, timeout in calls))
        self.assertEqual(sleeps, [2.25, 2.25, 2, 0.25, 2.25, 2.25])
        self.assertEqual(result["windows_http"]["counts"], {"http_200": 6})
        self.assertEqual(result["windows_pacing"]["maximum_get_ms"], 1000)

    def test_b2_default_retains_three_get_burst_and_cycle_sleep(self):
        code, result, calls, sleeps = self.run_qualifier(paced=False, diagnostics=False)
        self.assertEqual((code, len(calls), sleeps), (0, 6, [2]))
        self.assertNotIn("windows_http", result)
        self.assertNotIn("windows_pacing", result)

    def test_stale_metrics_still_hold_immediately_without_more_reads(self):
        code, result, calls, sleeps = self.run_qualifier(fresh=False)
        self.assertEqual(code, 2)
        self.assertEqual(result["diagnostic"]["code"], "LINK_METRICS_NOT_FRESH")
        self.assertEqual((len(calls), sleeps), (1, []))
        self.assertFalse(result["physical_acceptance"])

    def test_get_over_qualified_bound_is_hold_after_release_without_retry(self):
        code, result, calls, _ = self.run_qualifier(elapsed=1.001)
        self.assertEqual(code, 2)
        self.assertEqual(result["diagnostic"]["code"], "B3_HTTP_DURATION_OUT_OF_BOUNDS")
        self.assertEqual(len(calls), 1)
        with coord.digest_exchange(HOST, wait_seconds=0):
            pass

    def test_ambiguous_get_timeout_is_sanitized_and_not_retried(self):
        code, result, calls, _ = self.run_qualifier(fault=URLError(TimeoutError("password nonce raw")))
        self.assertEqual((code, len(calls)), (2, 1))
        self.assertEqual(result["diagnostic"]["code"], "NETWORK_TIMEOUT")
        self.assertEqual(result["diagnostic"]["windows_http"]["counts"], {"timeout": 1})
        self.assertNotIn("password", json.dumps(result))

    def test_qualifier_coordination_busy_is_explicit_and_sends_no_http(self):
        with patch.object(coord, "digest_exchange", side_effect=coord.CoordinationBusy("private", code="coordination_busy")):
            code, result, calls, _ = self.run_qualifier()
        self.assertEqual((code, len(calls)), (2, 0))
        self.assertEqual(result["diagnostic"]["code"], "COORDINATION_BUSY")
        self.assertEqual(result["diagnostic"]["windows_http"]["counts"], {"coordination_busy": 1})

    def test_terminal_get_http401_is_explicit_sanitized_and_not_retried(self):
        error = HTTPError("http://secret", 401, "nonce password", Message(), io.BytesIO(b"raw secret"))
        code, result, calls, _ = self.run_qualifier(fault=error)
        self.assertEqual((code, len(calls)), (2, 1))
        self.assertEqual(result["diagnostic"]["http_status"], 401)
        self.assertEqual(result["diagnostic"]["windows_http"]["counts"], {"http_401": 1})
        for secret in ("nonce", "password", "raw secret"):
            self.assertNotIn(secret, json.dumps(result))

    def test_existing_receipt_and_historical_case_variants_never_touched(self):
        target = self.root / "old.json"
        target.write_text("ORIGINAL")
        with patch.object(qualifier, "Transport", side_effect=AssertionError("HTTP")), \
             redirect_stdout(io.StringIO()), redirect_stderr(io.StringIO()):
            self.assertEqual(qualifier.main(["--bin","absent","--manifest","absent",
                "--receipt",str(target),"--b3-paced","--authorize-read"]), 2)
            with self.assertRaises(SystemExit):
                qualifier.main(["--bin","absent","--manifest","absent",
                    "--receipt",str(self.root/"B2-READONLY-RECEIPT.JSON"),"--b3-paced"])
        self.assertEqual(target.read_text(), "ORIGINAL")


if __name__ == "__main__":
    if len(sys.argv) > 1 and sys.argv[1] == "--worker":
        worker(*sys.argv[2:])
    else:
        unittest.main()
