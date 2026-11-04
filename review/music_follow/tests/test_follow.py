"""Focused scheduler/session tests. No physical sockets or synthetic LCD claims."""
import asyncio
import ast, threading
from io import BytesIO
from pathlib import Path
import sys
from types import SimpleNamespace as NS
import unittest
from unittest.mock import patch
sys.dont_write_bytecode = True
BASE = Path(__file__).resolve().parent
sys.path[:0] = [str(BASE.parent / 'runtime'), str(BASE.parents[2] / 'companion')]
from media_sessions import MediaCapture, MediaSnapshot, select_session, capture
from music_service import Service, Feed

class Clock:

    def __init__(self):
        self.t = 100.0

    def __call__(self):
        return self.t

    def advance(self, n):
        self.t += n

def sample(title='first', state='PLAYING', art=None, source='browser'):
    return MediaCapture(MediaSnapshot(state, source, title, 'artist', 'album', 10, 200, art is not None), art)

class Wire:

    def __init__(self, clock):
        self.clock = clock
        self.calls = []
        self.fail = False

    def send(self, op, tx, offset, body, **kw):
        self.calls.append((op, tx, offset, body))
        self.clock.advance(0.01)
        if self.fail:
            raise TimeoutError('simulated lost ACK')

class Player:

    def __init__(self, name, state='PLAYING', bad=False):
        self.source_app_user_model_id = name
        self.state = state
        self.bad = bad

    def get_playback_info(self):
        return NS(playback_status=NS(name=self.state))

    async def try_get_media_properties_async(self):
        if self.bad:
            raise RuntimeError('temporary')
        return NS(title=self.source_app_user_model_id, artist='artist', album_title='', thumbnail=None)

    def get_timeline_properties(self):
        return None

class Events:

    def __init__(self, sessions=()):
        self.handlers = {}
        self.serial = 0
        self.sessions = sessions

    def get_sessions(self):
        return self.sessions

    def __getattr__(self, name):
        if name.startswith('add_'):

            def add(callback):
                self.serial += 1
                self.handlers[name[4:], self.serial] = callback
                return self.serial
            return add
        if name.startswith('remove_'):
            return lambda token: self.handlers.pop((name[7:], token), None)
        raise AttributeError(name)

class Follow(unittest.TestCase):

    def setUp(self):
        self.loop = asyncio.new_event_loop()
        self.addCleanup(self.loop.close)
        for name in ('socket.socket.connect', 'socket.getaddrinfo', 'socket.create_connection'):
            guard = self.enterContext(patch(name, side_effect=AssertionError('NO NETWORK')))
            self.addCleanup(guard.assert_not_called)
        self.clock = Clock()
        self.feed = Feed(clock=self.clock)
        self.wire = Wire(self.clock)
        self.s = Service(self.wire, self.feed, clock=self.clock)
        self.engine = NS(state='CONNECTED', last_success=self.clock(), next_due=self.clock() + 2, clock=self.clock)

    def tick(self):
        self.engine.last_success = self.clock()
        self.engine.next_due = self.clock() + 2
        for _ in range(50):
            if not self.s.pump(self.engine):
                break
        else:
            self.fail('pump spun beyond useful budget')

    def test_current_playing_has_priority_over_old_playing(self):
        old = Player('old')
        current = Player('new')
        self.assertIs(select_session(current, [old, current]), current)

    def test_other_playing_beats_current_paused(self):
        old = Player('old', 'PAUSED')
        new = Player('new')
        self.assertIs(select_session(old, [old, new]), new)

    def test_properties_unavailable_is_transition_not_empty_track(self):
        p = Player('new', bad=True)
        manager = NS(get_current_session=lambda: p, get_sessions=lambda: [p])
        self.assertEqual(self.loop.run_until_complete(capture(manager)).snapshot.state, 'CHANGING')

    def test_unreadable_existing_sessions_are_not_no_session(self):
        p = Player('new')

        def unreadable():
            raise RuntimeError('session is being replaced')
        p.get_playback_info = unreadable
        manager = NS(get_current_session=lambda: p, get_sessions=lambda: [p])
        self.assertEqual(self.loop.run_until_complete(capture(manager)).snapshot.state, 'UNAVAILABLE')

    def test_automatic_track_changes(self):
        for title in ['automatic-a', 'automatic-b', 'manual-youtube', 'manual-soundcloud']:
            self.feed.publish(sample(title))
            self.tick()
            self.clock.advance(2)
        self.assertEqual([op for op, *_ in self.wire.calls], [1, 1, 1, 1])

    def test_transient_no_session_does_not_quiesce(self):
        self.feed.publish(sample())
        self.tick()
        self.clock.advance(1)
        self.feed.publish(sample(state='NO_SESSION'))
        self.tick()
        self.clock.advance(1)
        self.feed.publish(sample('new'))
        self.tick()
        self.assertNotIn(5, [x[0] for x in self.wire.calls])

    def test_real_end_requires_second_spaced_observation(self):
        self.feed.publish(sample())
        self.tick()
        self.feed.publish(sample(state='NO_SESSION'))
        self.tick()
        self.clock.advance(3.01)
        self.feed.publish(sample(state='NO_SESSION'))
        self.tick()
        self.assertEqual([x[0] for x in self.wire.calls].count(5), 1)

    def test_single_collector_and_single_manager_loop(self):
        calls = []
        manager = Events()

        async def factory():
            calls.append('manager')
            return manager

        async def collect(*args, **kwargs):
            calls.append('capture')
            feed.wake.set()
            if calls.count('capture') == 3:
                feed.stop.set()
            return sample()
        feed = Feed(manager_factory=factory, capture_fn=collect)
        with patch('asyncio.events.new_event_loop', return_value=self.loop):
            feed.start()
            thread = feed.thread
            feed.start()
            thread.join(2)
        self.assertFalse(thread.is_alive())
        self.assertIs(feed.thread, thread)
        self.assertEqual(calls.count('manager'), 1)
        self.assertEqual(feed.serial, 3)
        self.assertFalse(manager.handlers)

    def test_metrics_cadence_with_real_existing_worker_and_cover(self):
        from shino_link import LinkEngine
        from push_fsless_metrics import SendStatus
        from PIL import Image
        b = BytesIO()
        Image.new('RGB', (64, 64), 'green').save(b, format='JPEG')
        self.feed.publish(sample('a', art=b.getvalue()))
        ticks = []
        data = dict(ok=True, cpu_usage=1, gpu_usage=2, memory_used_gb=3, memory_total_gb=16, gpu_vram_mb=1, gpu_temp_c=40, gpu_power=1, gpu_available=True)

        def send(*args, **kwargs):
            ticks.append(self.clock())
            return SendStatus.ACCEPTED
        engine = LinkEngine('192.168.1.200', object(), lambda: data, sender=send, clock=self.clock)
        engine.music_service = self.s
        end = self.clock() + 12
        stop = NS(is_set=lambda: self.clock() >= end, wait=lambda n: self.clock.advance(n))
        engine.run(stop, lambda state: None)
        self.assertEqual(len(ticks), 6)
        self.assertTrue(all((abs(b - a - 2) < 1e-05 for a, b in zip(ticks, ticks[1:]))))
        self.assertEqual(engine.ttl_overruns, 0)
        self.assertEqual([x[0] for x in self.wire.calls[:11]], [1] + [2] * 9 + [3])
if __name__ == '__main__':
    unittest.main(verbosity=2)
