"""Targeted offline transport/service qualification. Never creates a device socket."""
import sys, json, unittest, tempfile
from pathlib import Path
from types import SimpleNamespace as NS
from contextlib import contextmanager, nullcontext
from email.message import Message
from unittest.mock import patch
BASE = Path(__file__).resolve().parent
sys.path[:0] = [str(BASE.parent / 'runtime'), str(BASE.parents[2] / 'companion')]
import music_transport as mt
from music_service import Service, Feed
from media_sessions import MediaCapture, MediaSnapshot
from media_music import tag
from shino_digest_coord import CoordinationBusy, digest_exchange
IDENTITY = dict(device='a' * 16, build='b' * 64, boot='c' * 32)
SECRET = 'HOST_ONLY_SECRET_DO_NOT_LOG'
TX = b'1' * 16

@contextmanager
def lease():
    yield (lambda: None)

@contextmanager
def coordinator(*args, **kwargs):
    yield

class Peer:

    def __init__(self, owner):
        self.owner = owner
        self.sock = NS(shutdown=lambda *a: None, close=lambda: None)

    def connect(self):
        if self.owner.failure == 'connect':
            raise OSError('PRIVATE_CONNECT_DETAIL')

    def request(self, method, path, body, headers):
        self.owner.requests.append((method, path, body, headers))
        if self.owner.failure in ('emit_before', 'emit_after'):
            raise OSError(SECRET)
        self.command = headers['X-Shino-Nonce']

    def getresponse(self):
        if self.owner.failure == 'response':
            raise TimeoutError(SECRET)
        cmd = self.command
        accepted = self.owner.failure != 'rejected'
        ack = dict(protocol=1, sequence=int(cmd[4:12], 16) + 1, accepted=accepted, command=cmd)
        ack['proof'] = tag(SECRET, IDENTITY, cmd, f"{ack['sequence']:08x}{int(accepted):02x}")
        if self.owner.failure == 'bad_ack':
            ack['proof'] = '0' * 64
        raw = json.dumps(ack).encode()
        headers = Message()
        headers['Content-Length'] = str(len(raw))

        def read(size):
            if self.owner.failure == 'read':
                raise TimeoutError(SECRET)
            return raw
        return NS(status=422 if not accepted else 200, headers=headers, read=read, getheader=headers.get)

    def close(self):
        pass

class Factory:

    def __init__(self, failure=None):
        self.failure = failure
        self.requests = []
        self.constructed = 0

    def __call__(self, *args, **kwargs):
        self.constructed += 1
        if self.failure == 'factory':
            raise OSError(SECRET)
        return Peer(self)

class Classification(unittest.TestCase):

    def setUp(self):
        for name in ('socket.socket.connect', 'socket.getaddrinfo', 'socket.create_connection'):
            mock = self.enterContext(patch(name, side_effect=AssertionError('NO NETWORK')))
            self.addCleanup(mock.assert_not_called)

    def transport(self, failure=None, **kwargs):
        self.factory = Factory(failure)
        t = mt.Transport('192.168.1.200', 'host-test', SECRET, identity=IDENTITY, lease=lease, coordinator=coordinator, connection_factory=self.factory, **kwargs)
        t.sequence = 7
        return t

    def failure(self, t, classification, **kwargs):
        with self.assertRaises(Exception) as caught:
            t.send(1, TX, body=b'', **kwargs)
        self.assertEqual(getattr(caught.exception, 'classification', None), classification)
        self.assertEqual(t.last_result['classification'], classification)
        return caught.exception

    def test_busy_is_proved_not_sent_and_not_permanent_failure(self):
        t = self.transport()

        @contextmanager
        def busy(*a, **k):
            raise CoordinationBusy('local busy', code='coordination_busy')
            yield
        t.coordinator = busy
        e = self.failure(t, 'NOT_SENT_PROVED')
        self.assertFalse(t.failed)
        self.assertTrue(e.retryable)
        self.assertEqual(e.phase, 'COORDINATOR')
        self.assertEqual(self.factory.constructed, 0)
        self.assertEqual(t.sequence, 7)

    def test_local_frame_validation_is_not_sent(self):
        t = self.transport()
        with self.assertRaises(Exception) as caught:
            t.send(1, TX, body=b'x' * 513)
        self.assertEqual(caught.exception.classification, 'NOT_SENT_PROVED')
        self.assertFalse(caught.exception.retryable)
        self.assertEqual(self.factory.constructed, 0)

    def test_budget_validation_is_not_sent(self):
        t = self.transport()
        self.failure(t, 'NOT_SENT_PROVED', budget_seconds=2)
        self.assertEqual(self.factory.constructed, 0)

    def test_guard_before_request_is_not_sent(self):
        t = self.transport()

        @contextmanager
        def bad():
            yield (lambda: (_ for _ in ()).throw(ValueError(SECRET)))
        t.lease = bad
        e = self.failure(t, 'NOT_SENT_PROVED')
        self.assertEqual(e.phase, 'GUARD')
        self.assertFalse(e.retryable)
        self.assertEqual(self.factory.constructed, 0)

    def test_unknown_starts_before_request_override(self):
        t = self.transport()

        def override(*args):
            raise OSError(SECRET)
        t._request = override
        self.failure(t, 'SEND_OUTCOME_UNKNOWN')
        self.assertTrue(t.failed)

    def test_factory_connect_and_emission_failures_are_conservatively_unknown(self):
        for stage in ('factory', 'connect', 'emit_before', 'emit_after'):
            with self.subTest(stage=stage):
                t = self.transport(stage)
                self.failure(t, 'SEND_OUTCOME_UNKNOWN')
                first = len(self.factory.requests)
                self.failure(t, 'SEND_OUTCOME_UNKNOWN')
                self.assertEqual(len(self.factory.requests), first)
                self.assertEqual(self.factory.constructed, 1)

    def test_response_lost_no_second_post(self):
        t = self.transport('response')
        self.failure(t, 'SEND_OUTCOME_UNKNOWN')
        self.failure(t, 'SEND_OUTCOME_UNKNOWN')
        self.assertEqual(len(self.factory.requests), 1)
        self.assertEqual(t.sequence, 7)

    def test_body_lost_records_status_but_remains_unknown(self):
        t = self.transport('read')
        self.failure(t, 'SEND_OUTCOME_UNKNOWN')
        self.assertEqual(t.last_result['http_status'], 200)

    def test_invalid_or_rejected_ack_is_unknown(self):
        for stage in ('bad_ack', 'rejected'):
            with self.subTest(stage=stage):
                t = self.transport(stage)
                self.failure(t, 'SEND_OUTCOME_UNKNOWN')
                self.assertEqual(t.sequence, 7)

    def test_ack_then_guard_failure_remains_unknown(self):
        t = self.transport()
        calls = []

        @contextmanager
        def bad():

            def guard():
                calls.append(1)
                if len(calls) == 2:
                    raise ValueError(SECRET)
            yield guard
        t.lease = bad
        self.failure(t, 'SEND_OUTCOME_UNKNOWN')
        self.assertEqual(t.last_result['phase'], 'POST_ACK_GUARD')
        self.assertEqual(t.sequence, 7)

    def test_success_ack_authenticated_and_advances_once(self):
        t = self.transport()
        ack = t.send(1, TX)
        self.assertTrue(ack['accepted'])
        self.assertEqual(t.sequence, 8)
        self.assertFalse(t.failed)
        self.assertEqual(t.last_result['classification'], 'ACK_VALIDATED')
        self.assertEqual(len(self.factory.requests), 1)

    def test_trace_disabled_by_default(self):
        t = self.transport()
        self.assertIsNone(t.trace)
        t.send(1, TX)

    def test_trace_failure_does_not_convert_ack_to_ambiguity(self):
        trace = NS(record=lambda **kw: (_ for _ in ()).throw(OSError(SECRET)))
        t = self.transport(trace=trace)
        t.send(1, TX)
        self.assertEqual(t.last_result['classification'], 'ACK_VALIDATED')
        self.assertFalse(t.failed)

    def service(self, t, cover=None):
        self.now = 100.0
        clock = lambda: self.now
        feed = Feed(clock=clock)
        feed.publish(MediaCapture(MediaSnapshot('PLAYING', 'host', 'title', 'artist', '', 1, 50, False), cover))
        service = Service(t, feed, clock=clock)
        engine = NS(state='CONNECTED', last_success=100.0, next_due=102.0, clock=clock)
        return (service, engine, feed)

    def test_busy_defers_same_unsent_frame_to_next_metrics_slot(self):
        t = self.transport()
        s, e, _ = self.service(t)
        calls = []

        @contextmanager
        def once(*a, **k):
            calls.append(1)
            if len(calls) == 1:
                raise CoordinationBusy('local busy', code='coordination_busy')
            yield
        t.coordinator = once
        self.assertFalse(s.pump(e))
        self.assertFalse(s.failed)
        self.assertEqual(s.phase, 'LOCAL_DEFERRED')
        tx = s.tx
        self.assertFalse(s.pump(e))
        self.assertEqual(len(calls), 1)
        self.now += 2
        e.last_success = self.now
        e.next_due = self.now + 2
        self.assertTrue(s.pump(e))
        self.assertEqual(s.tx, tx)
        self.assertEqual(t.sequence, 8)
        self.assertEqual(len(self.factory.requests), 1)

    def test_other_local_failure_holds_with_precise_reason(self):
        t = self.transport()
        t.sequence = None
        s, e, _ = self.service(t)
        s.pump(e)
        self.assertTrue(s.failed)
        self.assertEqual(s.phase, 'LOCAL_HOLD')
        self.assertTrue(s.error.startswith('NOT_SENT_PROVED_'))
        self.assertEqual(len(self.factory.requests), 0)

    def test_unknown_service_never_resends(self):
        t = self.transport('response')
        s, e, _ = self.service(t)
        s.pump(e)
        for n in range(4):
            self.now += 2
            e.last_success = self.now
            e.next_due = self.now + 2
            s.pump(e)
        self.assertEqual(s.phase, 'HOLD')
        self.assertTrue(s.failed)
        self.assertEqual(len(self.factory.requests), 1)

    def test_deferred_tile_after_acked_begin_keeps_offset_and_sequence(self):
        t = self.transport()
        s, e, _ = self.service(t)
        with patch('music_service.prepare', return_value=b'x' * 4608):
            self.assertTrue(s.pump(e))
        self.assertTrue(s.pending)
        self.assertEqual(t.sequence, 8)
        first = self.factory.requests[0][3]['X-Shino-Nonce']
        calls = []

        @contextmanager
        def once(*a, **k):
            calls.append(1)
            if len(calls) == 1:
                raise CoordinationBusy('busy', code='coordination_busy')
            yield
        t.coordinator = once
        self.assertFalse(s.pump(e))
        self.assertEqual(len(self.factory.requests), 1)
        self.now += 2
        e.last_success = self.now
        e.next_due = self.now + 2
        self.assertTrue(s.pump(e))
        second = self.factory.requests[-1][3]['X-Shino-Nonce']
        self.assertEqual(first[12:44], second[12:44])
        self.assertEqual(int(second[4:12], 16), 8)
        self.assertEqual(second[44:48], '0000')
        self.assertEqual(t.sequence, 9)

    def test_pending_source_expires_while_deferred_no_tile_or_commit(self):
        t = self.transport()
        s, e, _ = self.service(t)
        with patch('music_service.prepare', return_value=b'x' * 4608):
            s.pump(e)

        @contextmanager
        def busy(*a, **k):
            raise CoordinationBusy('busy', code='coordination_busy')
            yield
        t.coordinator = busy
        s.pump(e)
        self.now += 6
        e.last_success = self.now
        e.next_due = self.now + 2
        s.pump(e)
        self.assertEqual(s.phase, 'SOURCE_EXPIRED_NOT_SENT')
        self.assertFalse(s.pending)
        self.assertEqual(len(self.factory.requests), 1)
        self.assertFalse(s.failed)

    def test_deadline_before_request_is_proved_not_sent(self):
        t = self.transport()

        class Deadline:

            def __init__(self, *a):
                pass

            def check(self):
                raise TimeoutError(SECRET)

            def close(self):
                pass
        with patch.object(mt, 'ControlDeadline', Deadline):
            e = self.failure(t, 'NOT_SENT_PROVED')
        self.assertEqual(e.phase, 'GUARD')
        self.assertEqual(self.factory.constructed, 0)

    def test_coordinator_exit_failure_after_ack_is_unknown(self):
        t = self.transport()

        @contextmanager
        def bad_exit(*a, **k):
            yield
            raise CoordinationBusy('release failed', code='coordination_busy')
        t.coordinator = bad_exit
        e = self.failure(t, 'SEND_OUTCOME_UNKNOWN')
        self.assertFalse(e.retryable)
        self.assertEqual(len(self.factory.requests), 1)

    def test_unknown_during_tile_after_begin_never_resends(self):
        t = self.transport()
        s, e, _ = self.service(t)
        with patch('music_service.prepare', return_value=b'x' * 4608):
            s.pump(e)
        self.factory.failure = 'response'
        s.pump(e)
        for _ in range(4):
            self.now += 2
            e.last_success = self.now
            e.next_due = self.now + 2
            s.pump(e)
        self.assertEqual(len(self.factory.requests), 2)
        self.assertEqual(t.sequence, 8)
        self.assertTrue(s.failed)

    def test_busy_deferral_preserves_metrics_deadlines_with_real_worker(self):
        from shino_link import LinkEngine, SendStatus
        t = self.transport()
        s, _, _ = self.service(t)
        calls = []

        @contextmanager
        def once(*a, **k):
            calls.append(1)
            if len(calls) == 1:
                raise CoordinationBusy('busy', code='coordination_busy')
            yield
        t.coordinator = once
        clock = lambda: self.now
        ticks = []
        data = dict(ok=True, cpu_usage=1, gpu_usage=2, memory_used_gb=3, memory_total_gb=16, gpu_vram_mb=1, gpu_temp_c=40, gpu_power=1, gpu_available=True)

        def sender(*a, **kw):
            ticks.append(self.now)
            return SendStatus.ACCEPTED
        engine = LinkEngine('192.168.1.200', object(), lambda: data, sender=sender, clock=clock)
        engine.music_service = s
        stop = NS(is_set=lambda: self.now >= 108.0, wait=lambda n: setattr(self, 'now', self.now + n))
        engine.run(stop, lambda _: None)
        self.assertEqual(ticks, [100.0, 102.0, 104.0, 106.0])
        self.assertEqual(engine.ttl_overruns, 0)
        self.assertFalse(s.failed)
        self.assertEqual(len(self.factory.requests), 2)

    def test_real_local_coordinator_contention_then_unsent_frame_succeeds(self):
        with tempfile.TemporaryDirectory(dir=BASE) as folder:
            t = self.transport()
            t.coordinator = lambda host, **kw: digest_exchange(host, directory=Path(folder), **kw)
            with digest_exchange(t.host, directory=Path(folder), wait_seconds=0):
                e = self.failure(t, 'NOT_SENT_PROVED')
                self.assertTrue(e.retryable)
                self.assertEqual(self.factory.constructed, 0)
            t.send(1, TX)
            self.assertEqual(len(self.factory.requests), 1)
            self.assertEqual(t.sequence, 8)

    def test_failure_trace_drops_exception_text_payload_and_headers(self):
        with tempfile.TemporaryDirectory(dir=BASE) as folder:
            path = Path(folder) / 'failure.jsonl'
            trace = mt.MusicTrace(path)
            t = self.transport('response', trace=trace)
            with self.assertRaises(mt.MediaSendError):
                t.send(2, TX, body=b'PRIVATE_PAYLOAD')
            trace.close()
            raw = path.read_text()
            row = json.loads(raw)
            self.assertEqual(row['opcode'], 'TILE')
            self.assertEqual(row['phase'], 'RESPONSE')
            self.assertEqual(row['exception_class'], 'TimeoutError')
            self.assertEqual(row['classification'], 'SEND_OUTCOME_UNKNOWN')
            for forbidden in (SECRET, 'PRIVATE_PAYLOAD', 'X-Shino', TX.hex(), IDENTITY['device'], '192.168.1.200'):
                self.assertNotIn(forbidden, raw)
if __name__ == '__main__':
    unittest.main(verbosity=2)
