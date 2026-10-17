"""Offline M1 tests for owner-approved four-mode SHINO // LINK behavior.

No LINK startup, network, Windows tray, private credentials or SmallTV required.
Run: python -m unittest discover -s companion -p test_link_display_modes.py -v
"""
import builtins
from dataclasses import FrozenInstanceError
from itertools import product
import socket
import unittest
from unittest.mock import patch

from link_display_modes import Decision, DisplayMode, Reason, Scene, Signals, decide


class OwnerApprovedSimulationTests(unittest.TestCase):
    def test_automatic_pc_and_music_two_checkbox_truth_table(self):
        # The exact interactive concept approved by the owner on 2026-10-17.
        expected = {
            (False, False): Scene.CLOCK_WEATHER,
            (False, True): Scene.CLOCK_WEATHER,  # orphaned media event
            (True, False): Scene.HYBRID,
            (True, True): Scene.MUSIC,
        }
        for (pc, music), scene in expected.items():
            with self.subTest(pc=pc, music=music):
                decision = decide(
                    DisplayMode.AUTO,
                    Signals(pc_connected=pc, metrics_fresh=pc,
                            music_playing=music, time_valid=True),
                )
                self.assertEqual(decision.proposed_scene, scene)
                self.assertEqual(decision.requested_mode, DisplayMode.AUTO)

    def test_manual_clock_beats_playback_and_pc(self):
        for pc, music, fresh in product((False, True), repeat=3):
            with self.subTest(pc=pc, music=music, fresh=fresh):
                result = decide(DisplayMode.CLOCK_WEATHER,
                                Signals(pc, fresh, music, True, False))
                self.assertEqual(result.proposed_scene, Scene.CLOCK_WEATHER)
                self.assertEqual(result.reason, Reason.MANUAL_CLOCK)
                self.assertFalse(result.show_live_metrics)
                self.assertFalse(result.show_live_music)
                self.assertTrue(result.show_valid_time)
                self.assertFalse(result.show_valid_weather)

    def test_manual_monitoring_never_becomes_music(self):
        for pc, fresh, music in product((False, True), repeat=3):
            with self.subTest(pc=pc, fresh=fresh, music=music):
                result = decide(DisplayMode.MONITORING,
                                Signals(pc, fresh, music))
                want = (Scene.MONITORING if pc and fresh else
                        Scene.MONITORING_UNAVAILABLE)
                self.assertEqual(result.proposed_scene, want)
                self.assertEqual(result.requested_mode, DisplayMode.MONITORING)
                self.assertEqual(result.show_live_metrics, pc and fresh)
                self.assertFalse(result.show_live_music)

    def test_manual_music_never_falls_through_to_metrics(self):
        for pc, fresh, music in product((False, True), repeat=3):
            with self.subTest(pc=pc, fresh=fresh, music=music):
                result = decide(DisplayMode.MUSIC, Signals(pc, fresh, music))
                self.assertEqual(result.proposed_scene,
                                 Scene.MUSIC if pc and music else Scene.NO_MEDIA)
                self.assertEqual(result.requested_mode, DisplayMode.MUSIC)
                self.assertFalse(result.show_live_metrics)
                self.assertEqual(result.show_live_music, pc and music)

    def test_explicit_return_to_auto_recovers_context_priority(self):
        context = Signals(pc_connected=True, metrics_fresh=True,
                          music_playing=True, time_valid=True)
        forced = decide(DisplayMode.CLOCK_WEATHER, context)
        automatic = decide(DisplayMode.AUTO, context)
        self.assertEqual(forced.proposed_scene, Scene.CLOCK_WEATHER)
        self.assertEqual(automatic.proposed_scene, Scene.MUSIC)
        self.assertEqual(forced.requested_mode, DisplayMode.CLOCK_WEATHER)
        self.assertEqual(automatic.requested_mode, DisplayMode.AUTO)

    def test_fallback_cannot_erase_manual_preference(self):
        mode = DisplayMode.MONITORING
        disappeared = decide(mode, Signals(False, True, True))
        recovered = decide(mode, Signals(True, True, True))
        self.assertEqual(disappeared.proposed_scene,
                         Scene.MONITORING_UNAVAILABLE)
        self.assertEqual(disappeared.requested_mode, mode)
        self.assertEqual(recovered.proposed_scene, Scene.MONITORING)
        self.assertEqual(recovered.requested_mode, mode)
        self.assertFalse(recovered.show_live_music)

        mode = DisplayMode.MUSIC
        paused_or_missing = decide(mode, Signals(True, True, False))
        playing = decide(mode, Signals(True, True, True))
        self.assertEqual(paused_or_missing.proposed_scene, Scene.NO_MEDIA)
        self.assertEqual(paused_or_missing.requested_mode, mode)
        self.assertEqual(playing.proposed_scene, Scene.MUSIC)

    def test_auto_stale_metrics_show_clock_placeholder_not_old_numbers(self):
        result = decide(DisplayMode.AUTO, Signals(
            pc_connected=True, metrics_fresh=False, music_playing=False,
            time_valid=False, weather_valid=False))
        self.assertEqual(result.proposed_scene, Scene.CLOCK_WEATHER)
        self.assertEqual(result.reason, Reason.AUTO_STALE_METRICS)
        self.assertFalse(result.show_live_metrics)
        self.assertFalse(result.show_valid_time)
        self.assertFalse(result.show_valid_weather)

    def test_auto_music_can_work_when_metrics_stale(self):
        result = decide(DisplayMode.AUTO, Signals(True, False, True))
        self.assertEqual(result.proposed_scene, Scene.MUSIC)
        self.assertTrue(result.show_live_music)
        self.assertFalse(result.show_live_metrics)


class PolicySafetyTests(unittest.TestCase):
    def test_exhaustive_all_128_requested_mode_and_signal_states(self):
        visited = 0
        for mode in DisplayMode:
            for pc, fresh, music, clock, weather in product((False, True), repeat=5):
                with self.subTest(mode=mode, pc=pc, fresh=fresh,
                                  music=music, clock=clock, weather=weather):
                    result = decide(mode, Signals(pc, fresh, music, clock, weather))
                    self.assertIsInstance(result, Decision)
                    self.assertEqual(result.requested_mode, mode)
                    self.assertIsInstance(result.proposed_scene, Scene)
                    if result.show_live_metrics:
                        self.assertTrue(pc and fresh)
                        self.assertIn(result.proposed_scene,
                                      (Scene.HYBRID, Scene.MONITORING))
                    if result.show_live_music:
                        self.assertTrue(pc and music)
                        self.assertEqual(result.proposed_scene, Scene.MUSIC)
                    self.assertFalse(result.show_live_metrics and result.show_live_music)
                    clock_scene = result.proposed_scene in (
                        Scene.CLOCK_WEATHER, Scene.HYBRID)
                    self.assertEqual(result.show_valid_time, clock_scene and clock)
                    self.assertEqual(result.show_valid_weather,
                                     clock_scene and weather)
                    if result.proposed_scene is Scene.NO_MEDIA:
                        self.assertEqual(mode, DisplayMode.MUSIC)
                    if result.proposed_scene is Scene.MONITORING_UNAVAILABLE:
                        self.assertEqual(mode, DisplayMode.MONITORING)
                    visited += 1
        self.assertEqual(visited, 128)

    def test_invalid_enum_and_signals_rejected_not_silently_coerced(self):
        for invalid in ("AUTO", "auto", None, 1, True):
            with self.subTest(mode=invalid), self.assertRaises(TypeError):
                decide(invalid, Signals())
        for invalid in (None, {}, True, "connected"):
            with self.subTest(signals=invalid), self.assertRaises(TypeError):
                decide(DisplayMode.AUTO, invalid)
        for name in Signals.__dataclass_fields__:
            for invalid in (0, 1, "true", None):
                with self.subTest(field=name, value=invalid):
                    with self.assertRaises(TypeError):
                        Signals(**{name: invalid})

    def test_default_state_invents_no_time_weather_metrics_or_music(self):
        state = decide(DisplayMode.AUTO, Signals())
        self.assertEqual(state.proposed_scene, Scene.CLOCK_WEATHER)
        self.assertFalse(state.show_live_metrics)
        self.assertFalse(state.show_live_music)
        self.assertFalse(state.show_valid_time)
        self.assertFalse(state.show_valid_weather)

    def test_values_immutable_and_repeatable(self):
        ctx = Signals(True, True, True, True, False)
        first = decide(DisplayMode.AUTO, ctx)
        self.assertEqual(first, decide(DisplayMode.AUTO, ctx))
        with self.assertRaises(FrozenInstanceError):
            ctx.pc_connected = False
        with self.assertRaises(FrozenInstanceError):
            first.proposed_scene = Scene.HYBRID

    def test_decision_makes_no_network_file_or_device_calls(self):
        # No socket, filesystem persistence, GUI or external action in M1.
        with patch.object(socket, "socket", side_effect=AssertionError("network")), \
             patch.object(builtins, "open", side_effect=AssertionError("file")):
            for mode in DisplayMode:
                for pc, music in product((False, True), repeat=2):
                    decide(mode, Signals(pc, pc, music, True, False))


if __name__ == "__main__":
    unittest.main()
