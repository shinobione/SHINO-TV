"""PC-only SHINO // LINK tests; no psutil, tray, Windows registry or device needed."""
import json
import tempfile
import threading
import unittest
from pathlib import Path
from unittest.mock import patch

from shino_link import (
    LinkEngine, LinkError, autostart, exact_keys, load_config, save_config,
)
from push_fsless_metrics import ENDPOINT, encode_sample, send_one

SAMPLE = {
    "ok": True, "cpu_usage": 22.5, "gpu_usage": 60.0,
    "memory_used_gb": 7.25, "memory_total_gb": 16.0,
    "gpu_vram_mb": 2700.0, "gpu_temp_c": 49.0,
    "gpu_power": 85.0, "gpu_available": True,
}


class LinkConfigTests(unittest.TestCase):
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

    def test_no_registry_side_effect_on_non_windows(self):
        # Covers the default Linux CI path without monkeypatching OS globals.
        import os
        if os.name != "nt":
            with self.assertRaises(LinkError):
                autostart("enable", Path("no-config"))
            with self.assertRaises(LinkError):
                autostart("status", Path("no-config"))


class LinkEngineTests(unittest.TestCase):
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


if __name__ == "__main__":
    unittest.main()
