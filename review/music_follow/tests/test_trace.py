import sys,json,tempfile,unittest,asyncio
from pathlib import Path
from types import SimpleNamespace as NS
from unittest.mock import patch
BASE=Path(__file__).resolve().parent
sys.path[:0]=[str(BASE.parent/'runtime'),str(BASE.parents[2]/'companion')]
import test_network as support
import test_follow as follow
from music_transport import MusicTrace
from music_service import Service,Feed
from media_sessions import MediaCapture,MediaSnapshot
class Trace(unittest.TestCase):

    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory(dir=BASE)
        self.addCleanup(self.tmp.cleanup)
        self.path = Path(self.tmp.name) / 'trace.jsonl'
        self.trace = MusicTrace(self.path)
        self.addCleanup(self.trace.close)

    def rows(self):
        return [json.loads(line) for line in self.path.read_text().splitlines()]

    def capture(self, title='PRIVATE_TITLE', state='PLAYING', source='PRIVATE_SOURCE'):
        return MediaCapture(MediaSnapshot(state, source, title, 'PRIVATE_ARTIST', 'PRIVATE_ALBUM', 1, 60, False))

    def test_gsmtc_acquire_track_change_temporary_loss_restore(self):
        feed = Feed(trace=self.trace)
        for value in (self.capture(), self.capture('PRIVATE_OTHER'), self.capture(state='UNAVAILABLE'), self.capture('PRIVATE_OTHER'), self.capture(state='NO_SESSION')):
            feed.publish(value)
        events = [r['event'] for r in self.rows()]
        self.assertIn('SESSION_ACQUIRED', events)
        self.assertIn('TRACK_CHANGED', events)
        self.assertIn('SESSION_UNAVAILABLE', events)
        self.assertIn('SESSION_RESTORED', events)
        self.assertIn('SESSION_LOST', events)
        raw = self.path.read_text()
        for forbidden in ('PRIVATE_TITLE', 'PRIVATE_OTHER', 'PRIVATE_SOURCE', 'PRIVATE_ARTIST', 'PRIVATE_ALBUM'):
            self.assertNotIn(forbidden, raw)

    def test_latest_64_events_keep_late_failure(self):
        for _ in range(70):
            self.trace.event('SESSION_ACQUIRED', phase='CAPTURE')
        self.trace.event('SERVICE_EXCEPTION', phase='PUMP', error=TimeoutError('PRIVATE_SECRET'))
        rows = self.rows()
        self.assertEqual(len(rows), 64)
        self.assertEqual(rows[-1]['event'], 'SERVICE_EXCEPTION')
        self.assertEqual(rows[-1]['exception_class'], 'TimeoutError')
        self.assertNotIn('PRIVATE_SECRET', self.path.read_text())

    def test_service_start_state_stop_and_dashboard_decision(self):
        now = [100.0]
        clock = lambda: now[0]
        feed = Feed(clock=clock, trace=self.trace)
        wire = NS(trace=self.trace, send=lambda *a, **kw: None)
        service = Service(wire, feed, clock=clock)
        engine = NS(state='CONNECTED', last_success=100.0, next_due=102.0, clock=clock)
        feed.publish(self.capture())
        service.pump(engine)
        feed.publish(self.capture(state='NO_SESSION'))
        service.pump(engine)
        now[0] += 3
        engine.last_success = now[0]
        engine.next_due = now[0] + 2
        feed.publish(self.capture(state='NO_SESSION'))
        service.pump(engine)
        service.close()
        events = [r['event'] for r in self.rows()]
        self.assertIn('SERVICE_START', events)
        self.assertIn('MUSIC_STATE', events)
        self.assertIn('DASHBOARD_DECISION', events)
        self.assertIn('SERVICE_STOP', events)

    def test_trace_absent_has_no_io(self):
        with patch('builtins.open', side_effect=AssertionError('NO IO')):
            feed = Feed()
            feed.publish(self.capture())
            feed.close()

    def test_collector_callback_kind_is_recorded_without_session_identifier(self):
        feed = Feed(trace=self.trace)
        feed._event('sessions_changed')
        feed._event('current_session_changed')
        self.assertEqual([r['event'] for r in self.rows()], ['SESSIONS_CHANGED', 'CURRENT_SESSION_CHANGED'])
        self.assertEqual(feed.serial, 0)
        self.assertTrue(feed.wake.is_set())

    def test_network_unknown_has_operation_and_dashboard_reason(self):
        factory = support.Factory('response')
        from music_transport import Transport
        t = Transport('192.168.1.200', 'HOST', support.SECRET, identity=support.IDENTITY, lease=support.lease, coordinator=support.coordinator, connection_factory=factory, trace=self.trace)
        t.sequence = 7
        clock = lambda: 100.0
        feed = Feed(clock=clock, trace=self.trace)
        feed.publish(self.capture())
        s = Service(t, feed, clock=clock)
        e = NS(state='CONNECTED', last_success=100.0, next_due=102.0, clock=clock)
        s.pump(e)
        s.pump(e)
        self.assertTrue(s.failed)
        self.assertEqual(len(factory.requests), 1)
        command = next((r for r in self.rows() if r['event'] == 'COMMAND'))
        self.assertEqual(command['opcode'], 'BEGIN')
        self.assertEqual(command['phase'], 'RESPONSE')
        self.assertEqual(command['classification'], 'SEND_OUTCOME_UNKNOWN')
        self.assertTrue(any((r['decision'] == 'NO_RETRY_WAIT_NATIVE_LEASE' for r in self.rows())))
        self.assertNotIn(support.SECRET, self.path.read_text())

    def test_collector_exception_records_exact_phase_and_actual_stop(self):
        loop = asyncio.new_event_loop()
        self.addCleanup(loop.close)
        calls = []

        async def manager():
            return follow.Events()

        async def capture(*a, **kw):
            calls.append(1)
            feed.stop.set()
            raise TimeoutError('PRIVATE_CAPTURE_DETAIL')
        feed = Feed(manager_factory=manager, capture_fn=capture, trace=self.trace)
        with patch('asyncio.events.new_event_loop', return_value=loop), patch('socket.socket.connect', side_effect=AssertionError('NO NETWORK')):
            feed.start()
            thread = feed.thread
            feed.start()
            thread.join(2)
        self.assertFalse(thread.is_alive())
        self.assertIs(feed.thread, thread)
        self.assertEqual(len(calls), 1)
        rows = self.rows()
        failure = next((r for r in rows if r['event'] == 'COLLECTOR_EXCEPTION'))
        self.assertEqual(failure['phase'], 'CAPTURE')
        self.assertEqual(failure['exception_class'], 'TimeoutError')
        self.assertEqual(rows[-1]['event'], 'COLLECTOR_STOP')
        self.assertNotIn('PRIVATE_CAPTURE_DETAIL', self.path.read_text())

    def test_trace_rejects_arbitrary_labels_and_existing_file(self):
        self.trace.event('PRIVATE_EVENT', phase='PRIVATE_PHASE', from_state='PRIVATE_STATE', decision='PRIVATE_REASON')
        self.assertNotIn('PRIVATE_', self.path.read_text())
        with self.assertRaises(FileExistsError):
            MusicTrace(self.path)
