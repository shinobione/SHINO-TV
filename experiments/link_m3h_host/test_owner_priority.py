"""M3-H: actual LINK scheduler + M1/M2 preview + M3-A in-memory control.

Never starts LINK, opens sockets, reads credentials or touches a real SmallTV.
All 4 cards are original names/fields from LINK's validated sample contract.
"""
import threading
import unittest

from control_contract import Binding, FakeDevice, LabTransport
from link_display_modes import DisplayMode, Signals
from owner_priority import OwnerPriorityLab
from shino_link import LinkEngine
from push_fsless_metrics import SendStatus

SAMPLE = {
    "ok": True, "cpu_usage": 22.5, "gpu_usage": 34.5,
    "memory_used_gb": 8.0, "memory_total_gb": 16.0,
    "gpu_vram_mb": 2048.0, "gpu_temp_c": 56.0,
    "gpu_power": 120.0, "gpu_available": True,
}
BINDING = Binding("192.168.4.1", "1234567890abcdef",
                  "1234567890abcdef1234567890abcdef")


class Clock:
    def __init__(self):
        self.now = 0.0
    def __call__(self):
        return self.now


class Harness:
    def __init__(self):
        self.clock = Clock()
        self.music = False
        self.time_valid = False
        self.weather_valid = False
        self.fail = False
        self.events = []
        self.device = FakeDevice(BINDING)
        self.transport = LabTransport(self.device)

        def send(host, opener, sample, timeout):
            assert host == BINDING.host
            assert timeout == 3.0
            assert set(sample) == set(SAMPLE)
            self.events.append(("METRICS", self.clock.now))
            return SendStatus.CONNECTION if self.fail else SendStatus.ACCEPTED

        self.engine = LinkEngine(
            BINDING.host, object(), lambda: SAMPLE.copy(),
            sender=send, clock=self.clock)
        self.owner = OwnerPriorityLab(
            self.engine, BINDING, self.transport,
            context_supplier=lambda: Signals(
                music_playing=self.music,
                time_valid=self.time_valid,
                weather_valid=self.weather_valid))
        orig_post = self.device.post

        def post(raw):
            self.events.append(("MODE_POST", self.clock.now))
            return orig_post(raw)
        self.device.post = post

    def tick(self, when):
        self.clock.now = float(when)
        return self.owner.tick(float(when))

    def click(self, mode, n):
        self.owner.click(mode, f"{n:032x}")


class OwnerPriorityIntegrationTests(unittest.TestCase):
    def test_auto_priority_music_metrics_clock_and_expiration(self):
        h = Harness()
        h.time_valid = True
        h.weather_valid = False  # B5.3 has no validated weather feed.
        self.assertEqual(h.tick(0), "METRICS_FIRST_NO_CONTROL")
        self.assertEqual(h.owner.snapshot().proposed_scene, "HYBRID")
        self.assertTrue(h.owner.snapshot().preview_metrics)
        self.assertFalse(h.owner.snapshot().preview_music)
        h.music = True
        self.assertEqual(h.owner.snapshot().proposed_scene, "MUSIC")
        self.assertFalse(h.owner.snapshot().preview_metrics)
        h.music = False
        self.assertEqual(h.owner.snapshot().proposed_scene, "HYBRID")
        h.clock.now = 6.001
        self.assertEqual(h.owner.snapshot().proposed_scene, "CLOCK_WEATHER")
        self.assertFalse(h.owner.snapshot().preview_metrics)
        self.assertFalse(h.owner.snapshot().preview_music)
        h.music = True
        self.assertEqual(h.owner.snapshot().proposed_scene, "CLOCK_WEATHER")
        self.assertEqual(h.transport.posts, 0)
        self.assertEqual(h.engine.accepted, 1)

    def test_manual_clock_monitoring_music_explicit_return_auto(self):
        h = Harness()
        h.tick(0)
        h.music = True
        h.click(DisplayMode.CLOCK_WEATHER, 1)
        self.assertEqual(h.owner.snapshot().proposed_scene, "CLOCK_WEATHER")
        self.assertEqual(h.tick(.1), "MODE_ACK_READBACK_SIMULATED_ONLY")
        self.assertTrue(h.owner.snapshot().simulated_ack_readback)
        self.assertEqual(h.device.scene.value, "OFFLINE")  # not a display proof
        h.click(DisplayMode.MONITORING, 2)
        self.assertEqual(h.owner.snapshot().proposed_scene, "MONITORING")
        self.assertEqual(h.tick(.2), "MODE_ACK_READBACK_SIMULATED_ONLY")
        h.click(DisplayMode.MUSIC, 3)
        self.assertEqual(h.tick(.3), "MODE_ACK_READBACK_SIMULATED_ONLY")
        self.assertEqual(h.owner.snapshot().proposed_scene, "MUSIC")
        h.click(DisplayMode.AUTO, 4)
        self.assertEqual(h.tick(.4), "MODE_ACK_READBACK_SIMULATED_ONLY")
        self.assertEqual(h.owner.snapshot().proposed_scene, "MUSIC")
        h.music = False
        self.assertEqual(h.owner.snapshot().proposed_scene, "HYBRID")
        self.assertEqual(h.transport.posts, 4)
        self.assertEqual(h.engine.accepted, 1)  # real 2s LINK cadence

    def test_metrics_due_wins_and_guard_does_not_starve_next_slot(self):
        h = Harness()
        h.tick(0)
        h.click(DisplayMode.MONITORING, 1)
        self.assertEqual(h.tick(1.25), "MODE_PENDING_METRICS_PRIORITY")
        self.assertEqual(h.transport.posts, 0)
        self.assertEqual(h.tick(2.0), "MODE_ACK_READBACK_SIMULATED_ONLY")
        self.assertEqual(h.events, [
            ("METRICS", 0.0), ("METRICS", 2.0), ("MODE_POST", 2.0)])
        self.assertEqual(h.engine.attempts, 2)
        self.assertEqual(h.transport.posts, 1)
        self.assertEqual(h.owner.snapshot().proposed_scene, "MONITORING")

    def test_failure_backoff_preserved_and_pending_control_waits(self):
        h = Harness()
        h.tick(0)
        h.click(DisplayMode.MONITORING, 1)
        h.fail = True
        self.assertEqual(h.tick(2), "MODE_PENDING_METRICS_PRIORITY")
        self.assertEqual(h.engine.state, "RETRYING")
        self.assertEqual(h.transport.posts, 0)
        self.assertEqual(h.engine.next_due, 4)
        self.assertTrue(h.owner.snapshot().pending_intent)
        h.fail = False
        self.assertEqual(h.tick(4), "MODE_ACK_READBACK_SIMULATED_ONLY")
        self.assertEqual(h.engine.accepted, 2)
        self.assertEqual(h.transport.posts, 1)

    def test_post_uncertainty_hold_without_second_post_or_implicit_release(self):
        h = Harness()
        h.tick(0)
        original = h.device.post
        def committed_then_lost(raw):
            result = original(raw)  # fake commits but host cannot know
            raise OSError("simulated lost ACK")
        h.device.post = committed_then_lost
        h.click(DisplayMode.CLOCK_WEATHER, 1)
        self.assertEqual(h.tick(.1), "MODE_LAB_HOLD")
        self.assertEqual(h.transport.posts, 1)
        self.assertEqual(h.device.commits, 1)
        self.assertTrue(h.owner.snapshot().control_hold)
        self.assertFalse(h.owner.snapshot().simulated_ack_readback)
        for when in (2, 4, 6, 8):
            h.tick(when)  # metrics continue, never retry mode POST
        self.assertEqual(h.transport.posts, 1)
        self.assertEqual(h.engine.accepted, 5)
        with self.assertRaises(RuntimeError):
            h.click(DisplayMode.AUTO, 2)
        snapshot = h.owner.read_only_reconcile_for_lab()
        self.assertIsInstance(snapshot, bytes)
        self.assertTrue(h.owner.snapshot().control_hold)

    def test_replay_and_fast_clicks_rejected_before_new_control(self):
        h = Harness()
        h.tick(0)
        h.click(DisplayMode.MUSIC, 1)
        with self.assertRaises(RuntimeError):
            h.click(DisplayMode.AUTO, 2)
        h.tick(.1)
        with self.assertRaises(ValueError):
            h.click(DisplayMode.MONITORING, 1)
        self.assertEqual(h.transport.posts, 1)
        self.assertEqual(h.device.commits, 1)

    def test_device_boot_changed_blocks_control_preflight_but_not_metrics(self):
        h = Harness()
        h.tick(0)
        h.device.reboot("22222222222222222222222222222222")
        h.click(DisplayMode.MONITORING, 1)
        self.assertEqual(h.tick(.1), "MODE_LAB_HOLD")
        self.assertEqual(h.transport.posts, 0)
        self.assertEqual(h.device.commits, 0)
        h.tick(2)
        self.assertEqual(h.engine.accepted, 2)
        self.assertTrue(h.owner.snapshot().control_hold)

    def test_invalid_context_transaction_type_and_timestamp(self):
        h = Harness()
        with self.assertRaises(ValueError): h.owner.tick(float("nan"))
        with self.assertRaises(TypeError): h.owner.click("MUSIC", "1" * 32)
        with self.assertRaises(ValueError): h.owner.click(DisplayMode.MUSIC, "0" * 32)
        with self.assertRaises(ValueError): h.owner.click(DisplayMode.MUSIC, "A" * 32)
        with self.assertRaises(ValueError): h.owner.click(DisplayMode.MUSIC, "1")
        self.assertEqual(h.transport.posts, 0)
        h.tick(0)
        h.owner._context = lambda: {"music_playing": True}
        with self.assertRaises(TypeError):
            h.owner.snapshot()

    def test_concurrent_clicks_one_admission_no_parallel_sender(self):
        h = Harness()
        h.tick(0)
        ready = threading.Barrier(3)
        admitted, refused = [], []
        def click(i):
            ready.wait()
            try:
                h.click(DisplayMode.MONITORING, i)
                admitted.append(i)
            except RuntimeError:
                refused.append(i)
        threads = [threading.Thread(target=click, args=(1,)),
                   threading.Thread(target=click, args=(2,))]
        for t in threads: t.start()
        ready.wait()
        for t in threads: t.join(timeout=3)
        self.assertEqual(len(admitted), 1)
        self.assertEqual(len(refused), 1)
        h.tick(.1)
        self.assertEqual(h.transport.posts, 1)


if __name__ == "__main__":
    unittest.main()
