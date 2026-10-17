"""Offline SHINO // LINK M2 tray preview tests, without Windows/device calls."""

import builtins
from itertools import product
import socket
import threading
from types import SimpleNamespace
import unittest
from unittest.mock import patch

from link_display_modes import DisplayMode, Scene, Signals
from link_mode_tray import (
    ModeTrayController, build_preview_menu, passive_link_signals,
)
from shino_link import METRICS_TTL_MS


class FakeMenuItem:
    def __init__(self, text, action=None, *, checked=None, radio=False,
                 enabled=True, **unused):
        self.text, self.action, self.checked = text, action, checked
        self.radio, self.enabled = radio, enabled

    def label(self):
        return self.text(None) if callable(self.text) else self.text

    def is_checked(self):
        return self.checked(self) if callable(self.checked) else self.checked


class FakeMenu:
    SEPARATOR = object()

    def __init__(self, *items):
        self.items = items


class FakeIcon:
    def __init__(self):
        self.updates = 0

    def update_menu(self):
        self.updates += 1


PYSTRAY = SimpleNamespace(Menu=FakeMenu, MenuItem=FakeMenuItem)


def fake_menu(controller, on_open=None, on_quit=None, status="CONNECTED"):
    return build_preview_menu(
        PYSTRAY, controller, status_supplier=lambda: status,
        open_dashboard=on_open or (lambda icon, item: None),
        quit_app=on_quit or (lambda icon, item: None),
    )


class PassiveLinkProbeTests(unittest.TestCase):
    def test_ack_age_boundary_and_future_timestamps(self):
        for age_ms, expected in (
            (0, True), (100, True), (5999, True), (6000, True),
            (6000.01, False), (9000, False), (-1, False),
        ):
            with self.subTest(age_ms=age_ms):
                engine = SimpleNamespace(
                    last_success=20.0 - age_ms / 1000,
                    clock=lambda: 20.0,
                )
                signal = passive_link_signals(engine, ttl_ms=METRICS_TTL_MS)
                self.assertEqual(signal.pc_connected, expected)
                self.assertEqual(signal.metrics_fresh, expected)
                self.assertFalse(signal.music_playing)
                self.assertFalse(signal.time_valid)
                self.assertFalse(signal.weather_valid)
        self.assertEqual(METRICS_TTL_MS, 6000)

    def test_never_infer_device_state_before_first_ack(self):
        for prior in (None, float("nan"), float("inf"), "20", True):
            with self.subTest(last_success=repr(prior)):
                engine = SimpleNamespace(last_success=prior, clock=lambda: 20)
                result = passive_link_signals(engine, ttl_ms=METRICS_TTL_MS)
                self.assertEqual(result, Signals())

    def test_invalid_clock_does_not_claim_freshness(self):
        for now in (float("inf"), float("nan"), None, True):
            with self.subTest(now=now):
                engine = SimpleNamespace(last_success=12.0, clock=lambda: now)
                self.assertEqual(passive_link_signals(engine, ttl_ms=METRICS_TTL_MS), Signals())

    def test_passive_probe_does_not_use_engine_diagnostics_or_step(self):
        engine = SimpleNamespace(last_success=19.0, clock=lambda: 20.0,
            step=lambda: self.fail("telemetry send forbidden"),
            diagnostics=lambda: self.fail("diagnostics mutation forbidden"),
        )
        self.assertTrue(passive_link_signals(engine, ttl_ms=METRICS_TTL_MS).metrics_fresh)


class ModeMenuTests(unittest.TestCase):
    def setUp(self):
        self.context = Signals(True, True, False)
        self.controller = ModeTrayController(lambda: self.context)
        self.icon = FakeIcon()
        self.opened, self.exited = [], []
        self.menu = fake_menu(
            self.controller,
            on_open=lambda i, item: self.opened.append(True),
            on_quit=lambda i, item: self.exited.append(True),
        )
        self.radio = self.menu.items[1].action.items

    def choose(self, idx):
        self.radio[idx].action(self.icon, self.radio[idx])

    def test_default_menu_is_explicitly_not_applied(self):
        self.assertEqual(self.controller.mode(), DisplayMode.AUTO)
        self.assertEqual(self.menu.items[0].label(), "LINK : CONNECTED")
        self.assertIn("aperçu PC", self.menu.items[1].label())
        self.assertIn("aucun changement envoyé", self.menu.items[3].label())
        self.assertTrue(all(item.radio for item in self.radio))
        self.assertEqual([item.is_checked() for item in self.radio],
                         [True, False, False, False])
        self.assertIn("4 cartes", self.menu.items[2].label())

    def test_exact_four_owner_labels_and_radio_selection(self):
        self.assertEqual([item.label() for item in self.radio],
            ["Automatique", "Horloge / Météo", "Monitoring PC", "Musique"])
        for idx, mode in enumerate(DisplayMode):
            with self.subTest(mode=mode):
                self.choose(idx)
                self.assertEqual(self.controller.mode(), mode)
                self.assertEqual([item.is_checked() for item in self.radio],
                                 [i == idx for i in range(4)])
        self.assertEqual(self.icon.updates, 4)

    def test_manual_override_media_ignores_context_and_returns_to_auto(self):
        self.context = Signals(True, True, True)
        self.choose(1)  # Force clock, while Spotify context is playing.
        self.assertEqual(self.controller.decision().proposed_scene,
                         Scene.CLOCK_WEATHER)
        self.choose(2)  # Force the four cards.
        self.assertEqual(self.controller.decision().proposed_scene,
                         Scene.MONITORING)
        self.choose(3)  # Music preview only, NOT device-applied.
        self.assertEqual(self.controller.decision().proposed_scene, Scene.MUSIC)
        self.choose(0)  # Explicit return to automatic, music takes priority.
        self.assertEqual(self.controller.decision().proposed_scene, Scene.MUSIC)

    def test_menu_preview_updates_with_freshness_and_selection(self):
        self.choose(2)
        self.assertIn("4 cartes", self.menu.items[2].label())
        self.context = Signals(False, False, True)
        self.assertIn("Monitoring indisponible", self.menu.items[2].label())
        self.assertEqual(self.controller.mode(), DisplayMode.MONITORING)
        self.choose(3)
        self.assertIn("non vérifiée", self.menu.items[2].label())
        self.choose(1)
        self.assertIn("Horloge / Météo", self.menu.items[2].label())

    def test_real_web_and_exit_callbacks_still_available(self):
        self.assertEqual(self.opened, [])
        self.assertEqual(self.exited, [])
        self.menu.items[-2].action(self.icon, self.menu.items[-2])
        self.menu.items[-1].action(self.icon, self.menu.items[-1])
        self.assertEqual(self.opened, [True])
        self.assertEqual(self.exited, [True])

    def test_selection_is_memory_only_and_restarts_automatic(self):
        self.choose(3)
        fresh = ModeTrayController(lambda: self.context)
        self.assertEqual(fresh.mode(), DisplayMode.AUTO)
        self.assertEqual(self.controller.mode(), DisplayMode.MUSIC)

    def test_reject_invalid_choices_and_broken_signal_supplier(self):
        for bad in (None, "AUTO", 0, False):
            with self.subTest(mode=bad), self.assertRaises(TypeError):
                self.controller.choose(bad)
        self.assertEqual(self.controller.mode(), DisplayMode.AUTO)
        bad = ModeTrayController(lambda: "connected")
        self.assertEqual(bad.preview_label(), "Aperçu PC : données indisponibles")
        self.assertRaises(TypeError, bad.decision)
        raise_on_probe = ModeTrayController(
            lambda: (_ for _ in ()).throw(OSError("unavailable")))
        self.assertEqual(raise_on_probe.preview_label(),
                         "Aperçu PC : données indisponibles")

    def test_radio_clicks_do_not_open_network_or_files(self):
        with patch.object(socket, "socket", side_effect=AssertionError("network")), \
             patch.object(builtins, "open", side_effect=AssertionError("file")):
            for idx, _ in enumerate(DisplayMode):
                self.choose(idx)
                self.controller.decision()
                self.menu.items[2].label()
        self.assertEqual(self.opened, [])
        self.assertEqual(self.exited, [])

    def test_concurrent_local_preference_updates_never_leave_invalid_state(self):
        errors = []
        def click_worker(offset):
            try:
                for i in range(100):
                    self.controller.choose(tuple(DisplayMode)[(i + offset) % 4])
                    self.controller.decision()
            except Exception as exc:
                errors.append(type(exc).__name__)
        threads = [threading.Thread(target=click_worker, args=(i,)) for i in range(4)]
        for worker in threads:
            worker.start()
        for worker in threads:
            worker.join(timeout=5)
            self.assertFalse(worker.is_alive())
        self.assertEqual(errors, [])
        self.assertIn(self.controller.mode(), tuple(DisplayMode))

    def test_preview_every_mode_and_pc_context_is_deterministic(self):
        for mode, pc, media in product(DisplayMode, (False, True), (False, True)):
            with self.subTest(mode=mode, pc=pc, media=media):
                self.context = Signals(pc, pc, media, False, False)
                self.controller.choose(mode)
                self.assertIsInstance(self.menu.items[2].label(), str)
                self.assertEqual(self.controller.decision().requested_mode, mode)


    def test_actual_run_tray_wires_radio_menu_without_device(self):
        # Exercise real run_tray assembly, not just the isolated menu builder.
        # All Windows/PIL/worker components are fake. No UI or device.
        import sys
        from types import ModuleType
        from shino_link import run_tray

        observed = {"clicked": False, "stopped": False, "runs": 0}

        class MockEngine:
            host = "192.168.1.70"
            last_success = 99.0

            @staticmethod
            def clock():
                return 100.0

            @staticmethod
            def run(stop, report, observe, target_supplier):
                observed["runs"] += 1
                report("CONNECTED")
                stop.wait(1.0)

        class MockDraw:
            @staticmethod
            def rounded_rectangle(*args, **kwargs):
                pass

            @staticmethod
            def line(*args, **kwargs):
                pass

        class MockTrayIcon:
            def __init__(self, name, picture, title, menu):
                self.menu = menu
                self.title = title
                self.updates = 0

            def update_menu(self):
                self.updates += 1

            def run(self):
                modes = self.menu.items[1].action.items
                self.assert_mode_label(modes)
                modes[2].action(self, modes[2])  # explicit manual Monitoring
                self.ensure_selected(modes)
                observed["clicked"] = True
                self.menu.items[-1].action(self, self.menu.items[-1])

            @staticmethod
            def assert_mode_label(modes):
                assert [m.label() for m in modes] == [
                    "Automatique", "Horloge / Météo",
                    "Monitoring PC", "Musique",
                ]

            @staticmethod
            def ensure_selected(modes):
                assert [m.is_checked() for m in modes] == [
                    False, False, True, False,
                ]

            def stop(self):
                observed["stopped"] = True

        fake_pil = ModuleType("PIL")
        fake_pil.Image = SimpleNamespace(new=lambda *a, **kw: object())
        fake_pil.ImageDraw = SimpleNamespace(Draw=lambda pic: MockDraw())
        fake_pystray = SimpleNamespace(
            Menu=FakeMenu, MenuItem=FakeMenuItem, Icon=MockTrayIcon,
        )
        with patch.dict(sys.modules, {"pystray": fake_pystray, "PIL": fake_pil}), \
             patch("shino_link.make_engine", return_value=MockEngine()), \
             patch("shino_link.webbrowser.open",
                   side_effect=AssertionError("unrequested web open")), \
             patch.object(socket, "socket",
                          side_effect=AssertionError("network")):
            result = run_tray({"host": "192.168.1.70"})
        self.assertEqual(result, 0)
        self.assertTrue(observed["clicked"])
        self.assertTrue(observed["stopped"])
        self.assertEqual(observed["runs"], 1)


if __name__ == "__main__":
    unittest.main()
