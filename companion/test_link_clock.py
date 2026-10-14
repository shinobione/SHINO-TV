"""Single LINK worker/clock policy regressions; all network calls forbidden."""
import contextlib
import io
import json
import struct
import subprocess
import sys
import tempfile
import threading
import unittest
from types import SimpleNamespace
from datetime import datetime, timezone, timedelta
from pathlib import Path
from unittest.mock import patch

import clock_sync
import shino_link as link
from push_fsless_metrics import SendStatus
from test_push_fsless_metrics import OfflineNetworkTestCase
from test_shino_link import SAMPLE

HOST = '192.168.4.1'  # Public logical fixture; sockets are forbidden.
UTC = 1791980760


class Monotonic:
    def __init__(self): self.value = 0.0
    def __call__(self): return self.value
    def advance(self, seconds): self.value += seconds


class Transport:
    """Fresh per-operation receiver, records only synthetic public packets."""
    def __init__(self, rig):
        self.rig = rig
        self.clock_key = clock_sync.derive_key('PUBLIC-INERT-LINK-CLOCK-FIXTURE')
        number = len(rig.transports) + 2
        self.status = dict(protocol=clock_sync.PROTOCOL, clock_enabled=True,
                           boot=rig.boot, challenge=f'{number:032x}', challenge_ms=2000)
        self.frames = []
    def prepare(self):
        self.rig.events.append('GET_CLOCK')
        if self.rig.on_prepare: self.rig.on_prepare()
        return self.status
    def post(self, raw):
        self.rig.events.append('POST_CLOCK')
        self.frames.append(raw)
        if self.rig.post_error: raise self.rig.post_error
        return self.rig.reply


class Rig:
    def __init__(self, test, enabled=True):
        self.time = Monotonic()
        self.events, self.transports = [], []
        self.boot = '11' * 16
        self.on_prepare = None
        self.post_error = None
        self.reply = dict(status='CLOCK_SAMPLE_ACCEPTED', persisted=False)
        self.metric_result = SendStatus.ACCEPTED
        self.stop = threading.Event()
        test.assertTrue(hasattr(link, 'LinkClockPublisher'), 'LINK clock scheduler not integrated')
        publisher = link.LinkClockPublisher(HOST, self.factory, clock=self.time) if enabled else None
        self.engine = link.LinkEngine(HOST, object(), lambda: SAMPLE.copy(),
                                      sender=self.send, clock=self.time,
                                      opener_factory=lambda: object(), clock_publisher=publisher)
        self.publisher = publisher
    def factory(self, host):
        if host != HOST: raise AssertionError('clock must remain pinned to reviewed target')
        transport = Transport(self)
        self.transports.append(transport)
        return transport
    def send(self, host, opener, sample, timeout):
        self.events.append('METRICS')
        if set(sample) != set(SAMPLE): raise AssertionError('four-metric payload changed')
        return self.metric_result
    def step(self, at):
        self.time.value = at
        return self.engine.step(stop=self.stop)


class LinkClockTests(OfflineNetworkTestCase):
    def setUp(self):
        super().setUp()
        self.enterContext(patch.object(clock_sync, 'digest_exchange',
                                       lambda *a, **k: contextlib.nullcontext()))
        self.enterContext(patch.object(clock_sync, 'capture_pc_clock', return_value={
            'schema': 1, 'utc_s': UTC, 'offset_min': 120, 'lease_s': 120}))

    def test_default_disabled_metrics_only(self):
        rig = Rig(self, enabled=False)
        for at in (0, 2, 4, 60, 120): rig.step(at)
        self.assertEqual(rig.events, ['METRICS'] * 5)
        self.assertEqual(rig.engine.diagnostics()['clock']['state'], 'CLOCK_DISABLED')

    def test_metrics_first_nominal_cadence_and_fresh_packets(self):
        rig = Rig(self)
        for at in range(0, 123, 2): rig.step(at)
        self.assertEqual(rig.events[:3], ['METRICS', 'GET_CLOCK', 'POST_CLOCK'])
        self.assertEqual(rig.engine.accepted, 62)
        self.assertEqual(len(rig.transports), 3)
        frames = [t.frames[0] for t in rig.transports]
        self.assertEqual([len(f) for f in frames], [64] * 3)
        self.assertEqual(len(set(frames)), 3, 'never repeat a frame/challenge')
        self.assertEqual(rig.engine.max_success_interval_ms, 2000)
        self.assertEqual(rig.engine.ttl_overruns, 0)

    def test_busy_digest_skips_clock_no_get_no_immediate_retry(self):
        rig = Rig(self)
        with patch.object(clock_sync, 'digest_exchange', side_effect=clock_sync.CoordinationBusy('busy')):
            for at in (0, 2, 4): rig.step(at)
        self.assertEqual(rig.events, ['METRICS'] * 3)
        self.assertEqual(rig.publisher.snapshot()['last_result'], 'CLOCK_COORDINATION_HOLD')
        rig.step(60)
        self.assertEqual(rig.events[-3:], ['METRICS', 'GET_CLOCK', 'POST_CLOCK'])

    def test_no_clock_without_fresh_metric_ack_and_reconnect_resets_cadence(self):
        rig = Rig(self)
        rig.metric_result = SendStatus.CONNECTION
        rig.step(0)
        self.assertEqual(rig.transports, [])
        rig.metric_result = SendStatus.ACCEPTED
        rig.step(2)
        rig.metric_result = SendStatus.CONNECTION
        rig.step(4)
        rig.metric_result = SendStatus.ACCEPTED
        rig.boot = '33' * 16
        rig.step(6)
        self.assertEqual(len(rig.transports), 2)
        self.assertNotEqual(rig.transports[0].frames[0], rig.transports[1].frames[0])
        self.assertEqual(rig.transports[-1].status['boot'], '33' * 16)

    def test_retarget_suspends_clock_until_explicit_reverification(self):
        rig = Rig(self)
        rig.step(0)
        rig.engine.retarget('192.168.4.2')
        rig.step(2)
        rig.engine.retarget(HOST)
        rig.step(60)
        self.assertEqual(len(rig.transports), 1)
        self.assertEqual(rig.engine.accepted, 3)
        self.assertEqual(rig.publisher.snapshot()['state'], 'CLOCK_TARGET_REVERIFY_HOLD')

    def test_unknown_post_suspends_even_across_disconnect(self):
        for failure in (TimeoutError('synthetic-secret'), ConnectionResetError('synthetic-secret'), None):
            with self.subTest(failure=type(failure).__name__):
                rig = Rig(self)
                rig.post_error = failure
                rig.reply = {'status': 'UNKNOWN'}
                rig.step(0)
                rig.metric_result = SendStatus.CONNECTION
                rig.step(2)
                rig.metric_result = SendStatus.ACCEPTED
                for at in (4, 60, 120, 240): rig.step(at)
                self.assertEqual(len(rig.transports), 1)
                self.assertEqual(len(rig.transports[0].frames), 1)
                self.assertEqual(rig.publisher.snapshot()['state'], 'CLOCK_UNKNOWN_NO_RETRY')

    def test_absent_or_incompatible_route_stops_clock_metrics_continue(self):
        from urllib.error import HTTPError
        for absent in (False, True):
            rig = Rig(self)
            def prepare():
                if absent: raise HTTPError('http://public-fixture', 404, 'absent', {}, None)
                rig.transports[-1].status['protocol'] = 'unsupported'
            rig.on_prepare = prepare
            for at in (0, 2, 60, 120): rig.step(at)
            self.assertEqual(rig.events.count('POST_CLOCK'), 0)
            self.assertEqual(len(rig.transports), 1)
            self.assertEqual(rig.engine.accepted, 4)
            self.assertEqual(rig.publisher.snapshot()['state'], 'CLOCK_COMPATIBILITY_HOLD')

    def test_stop_after_challenge_never_posts_and_worker_restart_uses_new_challenge(self):
        rig = Rig(self)
        rig.on_prepare = rig.stop.set
        rig.step(0)
        self.assertEqual(rig.events, ['METRICS', 'GET_CLOCK'])
        new = Rig(self)
        new.boot = '44' * 16
        new.step(0)
        self.assertEqual(new.events, ['METRICS', 'GET_CLOCK', 'POST_CLOCK'])
        self.assertEqual(new.transports[0].status['boot'], '44' * 16)

    def test_stop_before_iteration_never_calls_sender(self):
        rig = Rig(self)
        rig.stop.set()
        rig.engine.run(rig.stop, lambda state: None)
        self.assertEqual(rig.events, [])

    def test_transport_construction_consuming_slack_defers_clock(self):
        rig = Rig(self)
        factory = rig.publisher.transport_factory
        def slow_factory(host):
            value = factory(host)
            rig.time.advance(1)
            return value
        rig.publisher.transport_factory = slow_factory
        rig.step(0)
        self.assertEqual(rig.events, ['METRICS'])
        self.assertEqual(rig.engine.next_due, 2)

    def test_bad_pc_clock_does_not_block_telemetry_or_post(self):
        rig = Rig(self)
        with patch.object(clock_sync, 'capture_pc_clock', side_effect=clock_sync.ClockHold('CLOCK_UNAVAILABLE')):
            for at in (0, 2, 4): rig.step(at)
        self.assertEqual(rig.events.count('POST_CLOCK'), 0)
        self.assertEqual(rig.engine.accepted, 3)
        self.assertEqual(rig.publisher.snapshot()['last_result'], 'CLOCK_SOURCE_HOLD')

    def test_real_invalid_pc_dates_rejected_and_plausible_wrong_date_is_not_provable(self):
        for value in (float('nan'), 0, 4102444800):
            rig = Rig(self)
            with patch.object(clock_sync, 'capture_pc_clock', side_effect=lambda:
                    self.real_capture(wall=lambda: value,
                                      local=lambda n: datetime.fromtimestamp(n, timezone.utc))):
                for at in (0, 2, 4): rig.step(at)
            self.assertEqual(rig.events.count('POST_CLOCK'), 0)
            self.assertEqual(rig.engine.accepted, 3)
        # A freshly signed plausible 2020 date is not distinguishable from true
        # UTC at an unanchored cold boot. This is a demonstrated trust LIMIT.
        rig = Rig(self)
        with patch.object(clock_sync, 'capture_pc_clock', side_effect=lambda:
                self.real_capture(wall=lambda: 1577836800,
                                  local=lambda n: datetime.fromtimestamp(n, timezone.utc))):
            rig.step(0)
        self.assertEqual(struct.unpack('<I', rig.transports[0].frames[0][8:12])[0], 1577836800)
        self.assertEqual(rig.publisher.accepted, 1)  # Fake receipt, not proof of actual UTC.

    def test_clock_unexpected_exception_cannot_kill_metrics_or_log_secret(self):
        rig = Rig(self)
        def broken(host): raise RuntimeError('sensitive-fixture-exception')
        rig.publisher.transport_factory = broken
        for at in (0, 2, 4, 60): rig.step(at)
        self.assertEqual(rig.engine.accepted, 4)
        self.assertEqual(rig.transports, [])
        self.assertEqual(rig.publisher.snapshot()['state'], 'CLOCK_UNKNOWN_NO_RETRY')
        self.assertNotIn('sensitive-fixture-exception', json.dumps(rig.engine.diagnostics()))

    def test_both_dst_directions_short_lease_then_new_offset(self):
        for before, after in ((60, 120), (120, 60)):
            rig = Rig(self)
            def local(epoch):
                minutes = before if epoch < UTC + 50 else after
                return datetime.fromtimestamp(epoch, timezone(timedelta(minutes=minutes)))
            # The source function is real; the simulated OS alone supplies DST.
            with patch.object(clock_sync, 'capture_pc_clock',
                              side_effect=lambda: self.real_capture(wall=lambda: UTC, local=local)):
                rig.step(0)
            self.assertEqual(struct.unpack('<IhH', rig.transports[0].frames[0][8:16]), (UTC, before, 42))
            with patch.object(clock_sync, 'capture_pc_clock',
                              side_effect=lambda: self.real_capture(wall=lambda: UTC + 60, local=local)):
                rig.step(60)
            self.assertEqual(struct.unpack('<IhH', rig.transports[1].frames[0][8:16]), (UTC + 60, after, 120))

    real_capture = staticmethod(clock_sync.capture_pc_clock)

    def test_diagnostics_no_credentials_headers_challenges_or_target(self):
        rig = Rig(self)
        rig.post_error = ValueError('PUBLIC-INERT-LINK-CLOCK-FIXTURE Authorization secret')
        output = io.StringIO()
        with contextlib.redirect_stdout(output), contextlib.redirect_stderr(output): rig.step(0)
        encoded = json.dumps(rig.engine.diagnostics()) + output.getvalue()
        for forbidden in ('PUBLIC-INERT', 'Authorization', 'secret', 'challenge', HOST, rig.boot):
            self.assertNotIn(forbidden, encoded)


class LinkActivationTests(OfflineNetworkTestCase):
    def test_real_engine_default_off_and_explicit_target_check_before_credentials(self):
        config = {'host': HOST, 'credentials_file': 'PUBLIC-FIXTURE-NOT-READ'}
        psutil = SimpleNamespace(cpu_percent=lambda **k: None)
        with patch.object(link, 'read_credentials', return_value=('shino', 'PUBLIC-INERT-LINK-CLOCK-FIXTURE')), \
                patch.dict(sys.modules, {'psutil': psutil}):
            disabled = link.make_engine(config)
            enabled = link.make_engine(config, clock_b52_host=HOST)
        self.assertIsNone(disabled.clock_publisher)
        self.assertEqual(enabled.clock_publisher.verified_host, HOST)
        with patch.object(link, 'read_credentials') as read, self.assertRaises(link.LinkError):
            link.make_engine(config, clock_b52_host='192.168.4.2')
        read.assert_not_called()

    def test_main_passes_explicit_opt_in_without_writing_config_or_autostart(self):
        config = {'host': HOST, 'credentials_file': 'PUBLIC-FIXTURE-NOT-READ'}
        seen = []
        engine = SimpleNamespace(run=lambda *a, **k: None)
        def factory(value, **kwargs):
            seen.append((value.copy(), kwargs))
            return engine
        with patch.object(link, 'load_config', return_value=config), \
                patch.object(link, 'link_instance', lambda: contextlib.nullcontext()), \
                patch.object(link, 'make_engine', side_effect=factory), \
                patch.object(link, 'save_config') as save, patch.object(link, 'autostart') as auto, \
                contextlib.redirect_stdout(io.StringIO()):
            self.assertEqual(link.main(['--run', '--clock-b52-host', HOST]), 0)
            self.assertEqual(link.main(['--run']), 0)
        self.assertEqual([v[1]['clock_b52_host'] for v in seen], [HOST, None])
        save.assert_not_called()
        auto.assert_not_called()

    def test_worker_cannot_be_started_twice_while_first_is_active(self):
        entered, release, stop = threading.Event(), threading.Event(), threading.Event()
        def sampler():
            entered.set()
            if not release.wait(2): raise AssertionError('test release missing')
            return SAMPLE.copy()
        sent = []
        engine = link.LinkEngine(HOST, object(), sampler,
            sender=lambda *a, **k: sent.append(1) or stop.set() or True)
        worker = threading.Thread(target=engine.run, args=(stop, lambda state: None))
        worker.start()
        try:
            self.assertTrue(entered.wait(1))
            with self.assertRaises(link.LinkError): engine.run(stop, lambda state: None)
        finally:
            release.set()
            worker.join(2)
        self.assertFalse(worker.is_alive())
        self.assertEqual(sent, [1])

    def test_clock_opt_in_rejected_for_config_dry_run_once_and_autostart_before_io(self):
        for args in (['--dry-run'], ['--configure'], ['--once'], ['--autostart', 'enable']):
            with self.subTest(args=args), patch.object(link, 'config_path') as config, \
                    contextlib.redirect_stderr(io.StringIO()), self.assertRaises(SystemExit):
                link.main(args + ['--clock-b52-host', HOST])
            config.assert_not_called()

    def test_single_instance_is_global_across_targets_and_preserves_lock_file(self):
        self.assertTrue(hasattr(link, 'link_instance'), 'single sender guard missing')
        with tempfile.TemporaryDirectory() as folder:
            directory = Path(folder) / 'worker'
            with link.link_instance(directory=directory):
                with self.assertRaises(link.LinkError):
                    with link.link_instance(directory=directory): self.fail('second sender entered')
            files = list(directory.iterdir())
            self.assertTrue(files)
            with link.link_instance(directory=directory): pass
            self.assertEqual(files, list(directory.iterdir()))

    def test_single_instance_cross_process_and_restart(self):
        self.assertTrue(hasattr(link, 'link_instance'), 'single sender guard missing')
        # A separate Python process exercises the OS lock; it never constructs a sender.
        script = '''import sys
from pathlib import Path
from shino_link import link_instance, LinkError
try:
    with link_instance(directory=Path(sys.argv[1])): print('ENTERED')
except LinkError: print('BUSY')
'''
        with tempfile.TemporaryDirectory() as folder:
            command = [sys.executable, '-B', '-c', script, folder]
            with link.link_instance(directory=Path(folder)):
                busy = subprocess.run(command, cwd=Path(__file__).parent, capture_output=True, text=True, timeout=5)
            ready = subprocess.run(command, cwd=Path(__file__).parent, capture_output=True, text=True, timeout=5)
            self.assertEqual((busy.returncode, busy.stdout.strip()), (0, 'BUSY'))
            self.assertEqual((ready.returncode, ready.stdout.strip()), (0, 'ENTERED'))


if __name__ == '__main__': unittest.main()
