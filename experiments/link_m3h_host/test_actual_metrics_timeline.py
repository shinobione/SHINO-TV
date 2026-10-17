"""M3-H end-to-end HOST timeline: real LinkEngine -> actual C++ FslessMetrics.

The real, unchanged FslessMetrics.cpp runs in a CHILD PROCESS using actual
ArduinoJson 7.4.3. Control is only M3-A's memory FakeDevice; no network.
"""
import json
import os
from pathlib import Path
import subprocess
import unittest

from control_contract import Binding, FakeDevice, LabTransport
from link_display_modes import DisplayMode, Signals
from owner_priority import OwnerPriorityLab
from push_fsless_metrics import SendStatus, encode_sample
from shino_link import LinkEngine

FIXTURE = {
    "ok": True, "cpu_usage": 22.5, "gpu_usage": 34.5,
    "memory_used_gb": 8.0, "memory_total_gb": 16.0,
    "gpu_vram_mb": 2048.0, "gpu_temp_c": 56.0,
    "gpu_power": 120.0, "gpu_available": True,
}
BIND = Binding("192.168.4.1", "1234567890abcdef",
               "1234567890abcdef1234567890abcdef")


class Clock:
    now = 0.0
    def __call__(self):
        return self.now


class OriginalMetricsSink:
    def __enter__(self):
        path = Path(os.environ["M3H_ORIGINAL_METRICS_PIPE_BIN"])
        if not path.is_file():
            raise AssertionError("pinned original C++ sink was not compiled")
        self.proc = subprocess.Popen(
            [str(path)], stdin=subprocess.PIPE, stdout=subprocess.PIPE,
            stderr=subprocess.PIPE, text=True, bufsize=1)
        self.history = []
        return self

    def accept(self, _host, _opener, sample, timeout):
        if timeout != 3.0:
            raise AssertionError("LINK native 3s budget unexpectedly changed")
        # Exact Windows LINK serialization and source C++ JSON decoder in
        # one synchronous HOST sender callback, no HTTP traffic.
        raw = encode_sample(sample)
        self.proc.stdin.write(raw.decode("ascii") + "\n")
        self.proc.stdin.flush()
        line = self.proc.stdout.readline()
        if not line:
            raise AssertionError("genuine FslessMetrics subprocess exited")
        result = json.loads(line)
        if result["applied_on_smalltv"] is not False or result["host_only"] is not True:
            raise AssertionError("fake success claim")
        self.history.append(result)
        return SendStatus.ACCEPTED if result["code"] == 200 else SendStatus.MALFORMED

    def __exit__(self, kind, value, tb):
        self.proc.stdin.close()
        try:
            code = self.proc.wait(timeout=3)
        except subprocess.TimeoutExpired:
            self.proc.kill()
            self.proc.wait(timeout=3)
            raise
        if code != 0 and kind is None:
            raise AssertionError("source-executing C++ sink failed")
        self.proc.stdout.close()
        self.proc.stderr.close()


class RealMetricsHostModeIntegration(unittest.TestCase):
    def setup_lab(self, sink):
        clock = Clock()
        state = {"sample": dict(FIXTURE), "music": False}
        engine = LinkEngine(BIND.host, object(), lambda: dict(state["sample"]),
                            sender=sink.accept, clock=clock)
        dev = FakeDevice(BIND)
        tx = LabTransport(dev)
        owner = OwnerPriorityLab(engine, BIND, tx, context_supplier=lambda:
                                  Signals(music_playing=state["music"]))
        return clock, state, engine, dev, tx, owner

    def test_genuine_cpp_metrics_remain_fresh_across_music_and_manual_modes(self):
        with OriginalMetricsSink() as sink:
            clock, state, engine, dev, tx, owner = self.setup_lab(sink)
            clock.now = 0
            self.assertEqual(owner.tick(0), "METRICS_FIRST_NO_CONTROL")
            self.assertEqual(sink.history[0]["code"], 200)
            self.assertEqual(sink.history[0]["cpu_usage"], 22.5)
            self.assertEqual(sink.history[0]["gpu_temp_c"], 56)
            self.assertEqual(owner.snapshot().proposed_scene, "HYBRID")

            state["music"] = True
            self.assertEqual(owner.snapshot().proposed_scene, "MUSIC")
            owner.click(DisplayMode.CLOCK_WEATHER, "1".zfill(32))
            clock.now = .1
            self.assertEqual(owner.tick(.1), "MODE_ACK_READBACK_SIMULATED_ONLY")
            self.assertEqual(owner.snapshot().proposed_scene, "CLOCK_WEATHER")
            self.assertEqual(dev.scene.value, "OFFLINE")  # no pixel proof
            self.assertEqual(tx.posts, 1)

            state["sample"]["gpu_usage"] = 81.5
            state["sample"]["gpu_temp_c"] = 66.0
            clock.now = 2
            self.assertEqual(owner.tick(2), "METRICS_FIRST_NO_CONTROL")
            self.assertEqual(sink.history[-1]["gpu_usage"], 81.5)
            self.assertEqual(sink.history[-1]["gpu_temp_c"], 66)
            self.assertEqual(engine.accepted, 2)
            self.assertEqual(tx.posts, 1)

            owner.click(DisplayMode.AUTO, "2".zfill(32))
            clock.now = 2.1
            self.assertEqual(owner.tick(2.1), "MODE_ACK_READBACK_SIMULATED_ONLY")
            self.assertEqual(owner.snapshot().proposed_scene, "MUSIC")
            self.assertFalse(owner.snapshot().preview_metrics)
            state["music"] = False
            self.assertEqual(owner.snapshot().proposed_scene, "HYBRID")
            self.assertEqual(tx.posts, 2)

    def test_invalid_sample_does_not_write_cpp_state_or_preempt_recovery(self):
        with OriginalMetricsSink() as sink:
            clock, state, engine, _dev, tx, owner = self.setup_lab(sink)
            clock.now = 0
            owner.tick(0)
            state["sample"]["cpu_usage"] = 102.0
            owner.click(DisplayMode.MONITORING, "1".zfill(32))
            clock.now = 2
            self.assertEqual(owner.tick(2), "MODE_PENDING_METRICS_PRIORITY")
            self.assertEqual(engine.state, "RETRYING")
            # LINK's serializer checks general wire types and bounds;
            # the real original receiver rejects CPU=102 after the POST.
            # It returns 422 without replacing the prior valid RAM sample.
            self.assertEqual(len(sink.history), 2)
            self.assertEqual(sink.history[-1]["code"], 422)
            self.assertEqual(sink.history[-1]["cpu_usage"], 22.5)
            self.assertEqual(tx.posts, 0)
            self.assertEqual(engine.next_due, 4.0)  # regular LINK backoff

            state["sample"]["cpu_usage"] = 33.0
            clock.now = 4
            self.assertEqual(owner.tick(4), "MODE_ACK_READBACK_SIMULATED_ONLY")
            self.assertEqual(len(sink.history), 3)
            self.assertEqual(sink.history[-1]["code"], 200)
            self.assertEqual(sink.history[-1]["cpu_usage"], 33)
            self.assertEqual(engine.accepted, 2)
            self.assertEqual(tx.posts, 1)

    def test_lost_control_ack_does_not_starve_real_original_metric_source(self):
        with OriginalMetricsSink() as sink:
            clock, state, engine, dev, tx, owner = self.setup_lab(sink)
            clock.now = 0
            owner.tick(0)
            commit = dev.post
            def lost(raw):
                commit(raw)
                raise OSError("host simulated ACK loss")
            dev.post = lost
            owner.click(DisplayMode.MUSIC, "1".zfill(32))
            clock.now = .2
            self.assertEqual(owner.tick(.2), "MODE_LAB_HOLD")
            self.assertTrue(owner.snapshot().control_hold)
            state["sample"]["cpu_usage"] = 44.0
            for t in (2,4,6):
                clock.now = t
                owner.tick(t)
            self.assertEqual(tx.posts, 1)
            self.assertEqual(engine.accepted, 4)
            self.assertEqual(sink.history[-1]["cpu_usage"], 44)
            self.assertEqual(len(sink.history), 4)


if __name__ == "__main__":
    unittest.main()
