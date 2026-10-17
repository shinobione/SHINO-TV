"""PC-only SHINO // LINK tests; no psutil, tray, Windows registry or device needed."""
import json
import io
import tempfile
import threading
import unittest
from pathlib import Path
from unittest.mock import patch

from shino_link import (
    LinkEngine, LinkError, autostart, exact_keys, load_config, save_config, diagnostics_writer,
)
from push_fsless_metrics import ENDPOINT, encode_sample, send_one, make_opener, SendStatus
from test_push_fsless_metrics import DigestTransport, OfflineNetworkTestCase

SAMPLE = {
    "ok": True, "cpu_usage": 22.5, "gpu_usage": 60.0,
    "memory_used_gb": 7.25, "memory_total_gb": 16.0,
    "gpu_vram_mb": 2700.0, "gpu_temp_c": 49.0,
    "gpu_power": 85.0, "gpu_available": True,
}


class LinkConfigTests(OfflineNetworkTestCase):
    def test_config_contains_private_file_path_only_not_secret_and_no_network(self):
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            creds = root / "credentials.txt"
            secret = "private-generated-password-is-never-copied"
            creds.write_text(
                "Rescue HTTP Digest user: shino\n"
                "Rescue HTTP Digest password: " + secret + "\n", encoding="utf-8",
            )
            cfg = root / "AppData" / "SHINO-TV" / "link.json"
            save_config(cfg, "192.168.4.1", creds)
            self.assertEqual(load_config(cfg)["credentials_file"], str(creds))
            self.assertEqual(load_config(cfg)["host"], "192.168.4.1")
            self.assertNotIn(secret, cfg.read_text(encoding="utf-8"))
            self.assertNotIn("Rescue HTTP Digest password", cfg.read_text(encoding="utf-8"))
            self.assertEqual(json.loads(cfg.read_text(encoding="utf-8"))["schema"], 1)

    def test_config_bad_host_and_credentials_rejected_before_write(self):
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            creds = root / "credentials.txt"
            creds.write_text("Rescue HTTP Digest user: shino\n"
                             "Rescue HTTP Digest password: long-but-valid-private-secret\n",
                             encoding="utf-8")
            cfg = root / "link.json"
            for bad in ("8.8.8.8", "127.0.0.1", "example.com",
                        "http://192.168.4.1", "192.168.4.1/ota"):
                with self.subTest(host=bad), self.assertRaises(ValueError):
                    save_config(cfg, bad, creds)
            self.assertFalse(cfg.exists())
            creds.write_text("Rescue HTTP Digest user: shino\n", encoding="utf-8")
            with self.assertRaises(ValueError):
                save_config(cfg, "192.168.4.1", creds)
            self.assertFalse(cfg.exists())

    def test_invalid_duplicate_and_symlink_config_rejected(self):
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            cfg = root / "link.json"
            cfg.write_text('{"schema":1,"schema":1,"host":"192.168.4.1","credentials_file":"C:/x"}')
            with self.assertRaises(LinkError):
                load_config(cfg)
            cfg.write_text('{"schema":1,"host":"8.8.8.8","credentials_file":"C:/x"}')
            with self.assertRaises(ValueError):
                load_config(cfg)
            try:
                alias = root / "alias.json"
                alias.symlink_to(cfg)
            except (OSError, NotImplementedError):
                pass
            else:
                with self.assertRaises(LinkError):
                    load_config(alias)

    def test_root_launcher_is_explicit_tray_only_no_update(self):
        launcher = (Path(__file__).resolve().parent.parent /
                    "start-shino-link.cmd").read_text(encoding="utf-8")
        self.assertIn('start "" pyw -3 "%~dp0companion\\shino_link.py" --tray', launcher)
        self.assertIn('if not exist "%LOCALAPPDATA%\\SHINO-TV\\link.json"', launcher)
        self.assertNotIn(" --send-oem-once", launcher)
        self.assertNotIn(" --flash", launcher)
        self.assertNotIn(" /update", launcher)

    def test_config_cannot_supply_a_digest_realm(self):
        with tempfile.TemporaryDirectory() as folder:
            cfg = Path(folder) / 'link.json'
            cfg.write_text(json.dumps({'schema': 1, 'host': '192.168.4.1',
                           'credentials_file': 'C:/fixture/credentials.txt',
                           'realm': 'SHINO-Unlisted'}), encoding='utf-8')
            with self.assertRaises(LinkError):
                load_config(cfg)

    def test_no_registry_side_effect_on_non_windows(self):
        # Covers the default Linux CI path without monkeypatching OS globals.
        import os
        if os.name != "nt":
            with self.assertRaises(LinkError):
                autostart("enable", Path("no-config"))
            with self.assertRaises(LinkError):
                autostart("status", Path("no-config"))


class LinkEngineTests(OfflineNetworkTestCase):
    def test_success_every_two_seconds_without_any_other_endpoint(self):
        calls = []
        def send(host, opener, sample, timeout):
            calls.append((host, sample.copy(), timeout))
            return True
        engine = LinkEngine("192.168.4.1", object(), lambda: SAMPLE.copy(), sender=send)
        self.assertEqual(engine.step(100), "CONNECTED")
        self.assertEqual(engine.next_due, 102)
        self.assertEqual(engine.step(101), "CONNECTED")
        self.assertEqual(engine.step(102), "CONNECTED")
        self.assertEqual(len(calls), 2)
        self.assertEqual(calls[0][0], "192.168.4.1")
        self.assertEqual(calls[0][2], 3.0)
        self.assertEqual(set(calls[0][1]), set(SAMPLE))
        self.assertEqual(ENDPOINT, "/api/v1/bridge/metrics")

    def test_backoff_bounded_and_resets_only_on_accepted_sample(self):
        results = iter([False, False, False, False, False, False, True])
        engine = LinkEngine("192.168.4.1", object(), lambda: SAMPLE,
                            sender=lambda *args, **kwargs: next(results))
        elapsed = 0
        for delay in (2, 4, 8, 16, 30, 30):
            self.assertEqual(engine.step(elapsed), "RETRYING")
            self.assertEqual(engine.next_due, elapsed + delay)
            self.assertEqual(engine.step(elapsed + delay / 2), "RETRYING")
            elapsed += delay
        self.assertEqual(engine.step(elapsed), "CONNECTED")
        self.assertEqual(engine.failures, 0)
        self.assertEqual(engine.next_due, elapsed + 2)

    def test_retry_wait_starts_after_slow_network_timeout(self):
        timepoint = [100.0]
        def slow_failure(*args, **kwargs):
            timepoint[0] += 4.5
            return False
        engine = LinkEngine("192.168.4.1", object(), lambda: SAMPLE,
                            sender=slow_failure, clock=lambda: timepoint[0])
        self.assertEqual(engine.step(), "RETRYING")
        self.assertEqual(timepoint[0], 104.5)
        self.assertEqual(engine.next_due, 106.5)
        self.assertEqual(engine.step(), "RETRYING")
        # No new HTTP request is permitted until two seconds AFTER timeout.
        self.assertEqual(timepoint[0], 104.5)

    def test_invalid_sample_never_passed_to_sender_and_recovers(self):
        called = []
        values = iter([dict(SAMPLE, cpu_usage="bad"), SAMPLE.copy()])
        engine = LinkEngine("192.168.4.1", object(), lambda: next(values),
                            sender=lambda *args, **kwargs: called.append(1) or True)
        self.assertEqual(engine.step(10), "RETRYING")
        self.assertEqual(called, [])
        self.assertEqual(engine.step(12), "CONNECTED")
        self.assertEqual(called, [1])

    def test_exceptions_do_not_print_secrets_or_trigger_immediate_retry(self):
        def broken():
            raise ValueError("sensitive-secret-never-shown")
        engine = LinkEngine("192.168.4.1", object(), broken)
        self.assertEqual(engine.step(1), "RETRYING")
        self.assertEqual(engine.next_due, 3)
        self.assertEqual(engine.step(2), "RETRYING")

    def test_stop_event_breaks_long_wait_no_background_timer(self):
        # Fake monotonic clock keeps first post-attempt delay positive.
        stop = threading.Event()
        states = []
        engine = LinkEngine("192.168.4.1", object(), lambda: SAMPLE,
                            sender=lambda *args, **kwargs: stop.set() or True,
                            clock=lambda: 100.0)
        engine.run(stop, states.append)
        self.assertEqual(states, ["CONNECTED"])


class LinkContinuityTests(OfflineNetworkTestCase):
    realm = 'SHINO-FirstBoot'

    def engine(self):
        transport = DigestTransport(self.realm)
        created = []
        def factory():
            opener = make_opener('192.168.4.1', 'shino', 'fixture-password')
            opener.add_handler(transport)
            created.append(opener)
            return opener
        engine = LinkEngine('192.168.4.1', factory(), lambda: SAMPLE.copy(), opener_factory=factory)
        return engine, transport, created

    def test_success_network_disappears_returns_success_without_restart(self):
        engine, transport, created = self.engine()
        self.assertEqual(engine.step(0), 'CONNECTED')
        transport.unavailable_before_challenge = True
        self.assertEqual(engine.step(2), 'RETRYING')
        self.assertIs(engine.last_result, SendStatus.CONNECTION)
        transport.unavailable_before_challenge = False
        self.assertEqual(engine.step(3), 'RETRYING')
        self.assertEqual(len(created), 1)
        self.assertEqual(engine.step(4), 'CONNECTED')
        self.assertEqual(len(created), 2)

    def test_success_fresh_device_challenge_success_same_opener(self):
        engine, transport, created = self.engine()
        for now in (0, 2, 4):
            transport.generation += 1
            self.assertEqual(engine.step(now), 'CONNECTED')
        self.assertEqual(len(created), 1)

    def test_poisoned_digest_state_is_rebuilt_before_next_bounded_attempt(self):
        engine, transport, created = self.engine()
        self.assertEqual(engine.step(0), 'CONNECTED')
        digest = next(h for h in engine.opener.handlers if type(h).__name__ == 'TelemetryDigestAuthHandler')
        digest.retried = 6 # Exact real urllib poisoned-state reproducer is retained separately.
        transport.generation += 1 # A recreated device must reject the cached challenge.
        self.assertEqual(engine.step(2), 'RETRYING')
        self.assertIs(engine.last_result, SendStatus.HTTP_401)
        self.assertEqual(engine.step(3), 'RETRYING')
        self.assertEqual(len(created), 1)
        self.assertEqual(engine.step(4), 'CONNECTED')
        self.assertEqual(len(created), 2)

    def test_repeated_interrupted_handshakes_backoff_and_automatic_return(self):
        engine, transport, created = self.engine()
        self.assertEqual(engine.step(0), 'CONNECTED')
        transport.unavailable_after_challenge = True
        now = 2
        for delay in (2, 4, 8, 16, 30, 30, 30):
            self.assertEqual(engine.step(now), 'RETRYING')
            self.assertIs(engine.last_result, SendStatus.NO_ROUTE_TIMEOUT)
            self.assertEqual(engine.next_due, now + delay)
            count = len(created)
            engine.step(now + delay / 2)
            self.assertEqual(len(created), count)
            now += delay
        transport.unavailable_after_challenge = False
        transport.generation += 1
        self.assertEqual(engine.step(now), 'CONNECTED')
        self.assertEqual(engine.next_due, now + 2)
        self.assertEqual(engine.failures, 0)

    def test_success_keeps_opener_and_diagnostics_are_bounded(self):
        engine, transport, created = self.engine()
        for now in range(0, 200, 2):
            self.assertEqual(engine.step(now), 'CONNECTED')
            self.assertIs(engine.last_result, SendStatus.ACCEPTED)
            self.assertEqual(engine.next_due, now + 2)
            self.assertEqual(engine.step(now + 1), 'CONNECTED')
        self.assertEqual(len(created), 1)
        self.assertEqual(engine.accepted, 100)
        self.assertEqual(transport.accepted, 100)
        self.assertEqual(transport.requests, 101)
        self.assertEqual(transport.challenges, 1)
        self.assertEqual(len(engine.diagnostics()['history']), 64)

    def test_diagnostics_never_include_exception_credentials_headers_or_paths(self):
        secret = 'password Authorization nonce C:/private/credentials.txt'
        def broken(*args, **kwargs): raise ValueError(secret)
        engine = LinkEngine('192.168.4.1', object(), lambda: SAMPLE, sender=broken,
                            opener_factory=lambda: object())
        stdout = io.StringIO()
        with patch('sys.stdout', stdout), patch('sys.stderr', stdout):
            engine.step(0)
            with tempfile.TemporaryDirectory() as folder:
                path = Path(folder) / 'diagnostics.json'
                diagnostics_writer(path)(engine.diagnostics())
                encoded = path.read_text(encoding='utf-8')
        self.assertNotIn(secret, encoded + stdout.getvalue())
        self.assertNotIn('Authorization', encoded)
        self.assertNotIn('nonce', encoded)
        self.assertNotIn('private', encoded)
        self.assertEqual(json.loads(encoded)['history'][0]['result'], 'client_error')

    def test_real_digest_success_and_timeout_diagnostics_are_sanitized(self):
        engine, transport, created = self.engine()
        output = io.StringIO()
        with patch('sys.stdout', output), patch('sys.stderr', output):
            self.assertEqual(engine.step(0), 'CONNECTED')
            transport.unavailable_after_challenge = True
            self.assertEqual(engine.step(2), 'RETRYING')
            transport.unavailable_after_challenge = False
            self.assertEqual(engine.step(4), 'CONNECTED')
            with tempfile.TemporaryDirectory() as folder:
                path = Path(folder) / 'private-diagnostics.json'
                diagnostics_writer(path)(engine.diagnostics())
                encoded = path.read_text(encoding='utf-8')
        for forbidden in ('fixture-password', 'Authorization', 'nonce', 'private',
                          'credentials', 'fixture-1', '192.168.4.1', self.realm):
            self.assertNotIn(forbidden, encoded + output.getvalue())
        self.assertEqual([entry['result'] for entry in json.loads(encoded)['history']],
                         ['accepted_sample', 'no_route_or_timeout', 'accepted_sample'])
        self.assertEqual(len(created), 2)

    def test_invalid_samples_do_not_rebuild_and_factory_errors_remain_bounded(self):
        created = []
        def factory():
            created.append(1)
            raise OSError('private credential file')
        values = iter([dict(SAMPLE, cpu_usage='bad'), SAMPLE, SAMPLE])
        engine = LinkEngine('192.168.4.1', None, lambda: next(values), opener_factory=factory)
        self.assertEqual(engine.step(0), 'RETRYING')
        self.assertEqual(created, [])
        self.assertEqual(engine.step(2), 'RETRYING')
        self.assertEqual(engine.next_due, 6)
        self.assertEqual(engine.step(5), 'RETRYING')
        self.assertEqual(len(created), 1)
        self.assertEqual(engine.step(6), 'RETRYING')
        self.assertEqual(engine.next_due, 14)


class StageALinkContinuityTests(LinkContinuityTests):
    realm = 'SHINO-StageA'


if __name__ == "__main__":
    unittest.main()
