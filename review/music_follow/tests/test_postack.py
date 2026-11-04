"""Fake-clock qualification of the exact post-ACK budget boundary; no network."""
import sys, json, types, unittest, tempfile, hashlib
from pathlib import Path
from types import SimpleNamespace as NS
from contextlib import contextmanager
from unittest.mock import patch
BASE = Path(__file__).resolve().parent
sys.path[:0] = [str(BASE.parent / 'runtime'), str(BASE.parents[2] / 'companion')]
import music_transport as mt
from media_music import tag, metadata
from music_service import Service, Feed
from media_sessions import MediaCapture, MediaSnapshot
from shino_b5_get_diagnostic import DiagnosticStop

class FixtureGuardFailure(ValueError):
    """HOST-only local guard fault, contains no owner evidence."""
    pass

class Clock:

    def __init__(self):
        self.t = 100.0

    def __call__(self):
        return self.t

    def advance(self, n):
        self.t += n

class PostAck(unittest.TestCase):

    def setUp(self):
        self.clock = Clock()
        self.calls = []
        self.post_delay = 0.0
        self.ack_delay = 0.1
        self.bad_guard = False
        self.lost = False
        self.bad_ack = False
        self.guard_error = FixtureGuardFailure('CONTROL_EVIDENCE_CHANGED')
        self.identity = dict(device='a' * 16, build='b' * 64, boot='c' * 32)
        owner = self

        class Deadline:

            def __init__(self, clock, timer, seconds):
                self.until = owner.clock() + seconds

            def check(self):
                if owner.clock() >= self.until:
                    raise DiagnosticStop('TIMEOUT')

            def close(self):
                pass
        self.enterContext(patch.object(mt, 'ControlDeadline', Deadline))
        self.enterContext(patch.object(mt.time, 'monotonic', self.clock))
        for name in ('socket.socket.connect', 'socket.getaddrinfo', 'socket.create_connection'):
            m = self.enterContext(patch(name, side_effect=AssertionError('NO NETWORK')))
            self.addCleanup(m.assert_not_called)

        @contextmanager
        def lease():
            yield (lambda: True)
            self.clock.advance(self.post_delay)
            if self.bad_guard:
                raise self.guard_error
        self.t = mt.Transport('192.168.1.200', 'HOST', 'INERT_HOST_PASSWORD', identity=self.identity, lease=lease, coordinator=lambda *a, **kw: __import__('contextlib').nullcontext())
        self.t.sequence = 0

        def request(method, path, headers, body, deadline):
            self.calls.append((headers['X-Shino-Nonce'], bytes(body)))
            self.clock.advance(self.ack_delay)
            if self.lost:
                raise TimeoutError('lost response')
            cmd = headers['X-Shino-Nonce']
            ack = dict(protocol=1, sequence=int(cmd[4:12], 16) + 1, accepted=True, command=cmd)
            ack['proof'] = tag('INERT_HOST_PASSWORD', self.identity, cmd, f"{ack['sequence']:08x}01")
            if self.bad_ack:
                ack['proof'] = '0' * 64
            return (200, None, json.dumps(ack).encode())
        self.t._request = request
        self.tx = b'1' * 16

    def send(self):
        return self.t.send(2, self.tx, 0, b'x' * 512, budget_seconds=0.25)

    def test_on_time_ack_normal_advances_once(self):
        self.send()
        self.assertEqual(self.t.sequence, 1)
        self.assertEqual(self.t.last_result['classification'], 'ACK_VALIDATED')

    def test_postguard_overrun_keeps_proven_ack_and_marks_budget(self):
        self.post_delay = 0.2
        self.send()
        self.assertEqual(self.t.sequence, 1)
        self.assertFalse(self.t.failed)
        self.assertTrue(self.t.budget_exhausted)
        self.assertEqual(self.t.last_result['classification'], 'ACK_VALIDATED')
        self.assertEqual(len(self.calls), 1)

    def test_ack_itself_late_stays_unknown_and_never_repeats(self):
        self.ack_delay = 0.3
        for _ in range(2):
            with self.assertRaises(mt.MediaSendError):
                self.send()
        self.assertEqual(self.t.last_result['classification'], 'SEND_OUTCOME_UNKNOWN')
        self.assertTrue(self.t.failed)
        self.assertEqual(self.t.sequence, 0)
        self.assertEqual(len(self.calls), 1)

    def test_failed_postguard_never_becomes_ack(self):
        self.bad_guard = True
        self.post_delay = 0.2
        with self.assertRaises(mt.MediaSendError):
            self.send()
        self.assertTrue(self.t.failed)
        self.assertEqual(self.t.sequence, 0)

    def test_lost_response_is_unknown_no_replay(self):
        self.lost = True
        for _ in range(2):
            with self.assertRaises(mt.MediaSendError):
                self.send()
        self.assertEqual(len(self.calls), 1)
        self.assertTrue(self.t.failed)

    def test_invalid_ack_never_qualifies(self):
        self.bad_ack = True
        with self.assertRaises(mt.MediaSendError):
            self.send()
        self.assertTrue(self.t.failed)
        self.assertEqual(self.t.sequence, 0)

    def service(self):
        self.feed = Feed(clock=self.clock)
        self.feed.publish(MediaCapture(MediaSnapshot('PLAYING', 'HOST', 'HOST', 'HOST', '', 1, 200, True), b'HOST_FAKE_JPEG'))
        self.s = Service(self.t, self.feed, clock=self.clock)
        self.e = NS(state='CONNECTED', last_success=self.clock(), next_due=self.clock() + 2, clock=self.clock)

    def tick(self):
        self.e.last_success = self.clock()
        self.e.next_due = self.clock() + 2
        self.feed.publish(MediaCapture(MediaSnapshot('PLAYING', 'HOST', 'HOST', 'HOST', '', 1, 200, True), b'HOST_FAKE_JPEG'))

    def test_budget_exhausted_stops_slot_without_resending_acked_frame(self):
        self.service()
        self.post_delay = 0.3
        self.ack_delay = 0.2
        with patch('music_service.prepare', return_value=b'x' * 4608):
            for _ in range(3):
                self.assertTrue(self.s.pump(self.e))
            self.assertFalse(self.s.pump(self.e))
        self.assertFalse(self.s.failed)
        self.assertTrue(self.s.pending)
        self.assertEqual(self.t.sequence, 4)
        self.s.pump(self.e)
        self.assertEqual(len(self.calls), 4)
        self.tick()
        self.s.pump(self.e)
        self.assertEqual(len(self.calls), 5)
        self.assertEqual(int(self.calls[4][0][4:12], 16), 4)

    def test_complete_tiles_and_commit_with_postguard_overruns_no_replay(self):
        from shino_link import LinkEngine, SendStatus
        self.service()
        self.post_delay = 0.3
        self.ack_delay = 0.2
        ticks = []
        data = dict(ok=True, cpu_usage=1, gpu_usage=2, memory_used_gb=3, memory_total_gb=16, gpu_vram_mb=1, gpu_temp_c=40, gpu_power=1, gpu_available=True)

        def sender(*a, **kw):
            ticks.append(self.clock())
            return SendStatus.ACCEPTED
        engine = LinkEngine('192.168.1.200', object(), lambda: data, sender=sender, clock=self.clock)
        engine.music_service = self.s
        stop = NS(is_set=lambda: self.clock() >= 106.0, wait=lambda n: self.clock.advance(n))
        with patch('music_service.prepare', return_value=b'x' * 4608):
            engine.run(stop, lambda _: None)
        commands = [cmd for cmd, body in self.calls]
        self.assertEqual([int(c[2:4], 16) for c in commands], [1] + [2] * 9 + [3])
        self.assertEqual([int(c[4:12], 16) for c in commands], list(range(11)))
        self.assertEqual([int(c[44:48], 16) for c in commands[1:10]], list(range(0, 4608, 512)))
        self.assertEqual(len(set(commands)), 11)
        self.assertFalse(self.s.pending)
        self.assertEqual(self.s.phase, 'ACTIVE')
        body = b''.join((body for cmd, body in self.calls[1:10]))
        self.assertEqual(len(body), 4608)
        self.assertEqual(self.calls[0][1][164:196], hashlib.sha256(body).digest())
        self.assertEqual(self.calls[-1][1], b'')
        self.assertLess(self.t.ack_validated_at - self.s.started, 7.5)
        self.assertEqual(len(ticks), 3)
        self.assertTrue(all((abs(b - a - 2.01) < 1e-05 for a, b in zip(ticks, ticks[1:]))))
        self.assertEqual(engine.ttl_overruns, 0)

    def test_expired_before_next_frame_does_not_send(self):
        self.service()
        self.post_delay = 0.2
        with patch('music_service.prepare', return_value=b'x' * 4608):
            self.s.pump(self.e)
        self.clock.advance(8.0)
        self.tick()
        self.s.pump(self.e)
        self.assertEqual(len(self.calls), 1)
        self.assertEqual(self.s.phase, 'LOCAL_EXPIRED_NOT_SENT')

    def test_ack_at_expiration_is_unknown(self):
        self.ack_delay = 0.25
        with self.assertRaises(mt.MediaSendError):
            self.send()
        self.assertTrue(self.t.failed)
        self.assertEqual(self.t.sequence, 0)

    def test_timeout_from_context_exit_is_not_swallowed(self):
        self.bad_guard = True
        self.guard_error = DiagnosticStop('TIMEOUT')
        with self.assertRaises(mt.MediaSendError):
            self.send()
        self.assertTrue(self.t.failed)
        self.assertEqual(self.t.sequence, 0)

    def test_long_guards_do_not_refresh_old_ack_or_send_expired_tile(self):
        self.service()
        self.post_delay = 8.0
        with patch('music_service.prepare', return_value=b'x' * 4608):
            self.s.pump(self.e)
        self.assertAlmostEqual(self.s.last_ack, 100.1)
        self.tick()
        self.s.pump(self.e)
        self.assertEqual(len(self.calls), 1)
        self.assertEqual(self.s.phase, 'LOCAL_EXPIRED_NOT_SENT')

    def test_exhausted_budget_is_traced_without_unknown(self):
        with tempfile.TemporaryDirectory(dir=BASE) as folder:
            path = Path(folder) / 'trace.jsonl'
            trace = mt.MusicTrace(path)
            self.t.trace = trace
            self.post_delay = 0.2
            try:
                self.send()
            finally:
                trace.close()
            rows = [json.loads(line) for line in path.read_text().splitlines()]
            self.assertEqual([r['event'] for r in rows], ['POST_ACK_BUDGET_EXHAUSTED', 'COMMAND'])
            self.assertEqual(rows[-1]['classification'], 'ACK_VALIDATED')

    def test_extreme_local_io_overrun_is_visible_and_never_sends_next_tile(self):
        from shino_link import LinkEngine, SendStatus
        self.service()
        self.post_delay = 8.0
        ticks = []
        data = dict(ok=True, cpu_usage=1, gpu_usage=2, memory_used_gb=3, memory_total_gb=16, gpu_vram_mb=1, gpu_temp_c=40, gpu_power=1, gpu_available=True)

        def sender(*a, **kw):
            ticks.append(self.clock())
            return SendStatus.ACCEPTED
        engine = LinkEngine('192.168.1.200', object(), lambda: data, sender=sender, clock=self.clock)
        engine.music_service = self.s
        stop = NS(is_set=lambda: self.clock() >= 110.0, wait=lambda n: self.clock.advance(n))
        with patch('music_service.prepare', return_value=b'x' * 4608):
            engine.run(stop, lambda _: None)
        self.assertEqual(len(ticks), 2)
        self.assertGreater(ticks[1] - ticks[0], 6.0)
        self.assertGreater(engine.ttl_overruns, 0)
        self.assertEqual(len(self.calls), 1)
        self.assertAlmostEqual(self.s.last_ack, 100.1)
        self.assertFalse(self.s.pending)
if __name__ == '__main__':
    unittest.main(verbosity=2)
