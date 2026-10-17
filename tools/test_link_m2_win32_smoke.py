"""Real Windows pystray backend M2 smoke, no device, secrets or LINK sender.

All Windows-only imports are inside skip-protected tests. CI is a genuine
Windows runner, but NOT proof of user-desktop Explorer/notification rendering.
"""
from pathlib import Path
import sys
import threading
import unittest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "companion"))


@unittest.skipUnless(sys.platform == "win32", "Win32-only tray qualification")
class Win32LinkModeTraySmoke(unittest.TestCase):
    def test_real_pystray_menu_selection_status_and_no_device_action(self):
        import pystray
        from link_mode_tray import ModeTrayController, build_preview_menu
        from link_display_modes import DisplayMode, Scene, Signals

        self.assertTrue(pystray.Icon.HAS_MENU)
        self.assertTrue(pystray.Icon.HAS_MENU_RADIO)
        controller = ModeTrayController(
            lambda: Signals(pc_connected=True, metrics_fresh=True))
        events = []
        status = {"value": "CONNECTED"}

        class InMemoryIcon:
            def __init__(self):
                self.menu_updates = 0

            def update_menu(self):
                self.menu_updates += 1

        icon = InMemoryIcon()
        menu = build_preview_menu(
            pystray, controller,
            status_supplier=lambda: status["value"],
            open_dashboard=lambda _i, _m: events.append("web"),
            quit_app=lambda _i, _m: events.append("quit"),
        )
        entries = menu.items
        self.assertEqual(entries[0].text, "LINK : CONNECTED")
        self.assertIn("aucun changement envoyé", entries[3].text)
        self.assertFalse(entries[3].enabled)
        radio = entries[1].submenu.items
        self.assertEqual([m.text for m in radio],
                         ["Automatique", "Horloge / Météo",
                          "Monitoring PC", "Musique"])
        self.assertEqual([m.checked for m in radio],
                         [True, False, False, False])
        self.assertTrue(all(m.radio for m in radio))

        # Invoke the actual pystray MenuItem callback adapter; it must
        # update only RAM state/menu, not open web or start another worker.
        radio[1](icon)
        self.assertEqual(controller.mode(), DisplayMode.CLOCK_WEATHER)
        self.assertEqual(controller.decision().proposed_scene,
                         Scene.CLOCK_WEATHER)
        radio[2](icon)
        self.assertEqual(controller.mode(), DisplayMode.MONITORING)
        radio[3](icon)
        self.assertEqual(controller.mode(), DisplayMode.MUSIC)
        self.assertIn("non vérifiée", entries[2].text)
        radio[0](icon)
        self.assertEqual(controller.mode(), DisplayMode.AUTO)
        self.assertEqual(controller.decision().proposed_scene, Scene.HYBRID)
        self.assertEqual([m.checked for m in radio],
                         [True, False, False, False])
        self.assertEqual(icon.menu_updates, 4)
        self.assertEqual(events, [])

        status["value"] = "RETRYING"
        self.assertEqual(entries[0].text, "LINK : RETRYING")
        self.assertIn("aucun changement envoyé", entries[3].text)

        # Existing actions remain callable, but only when invoked on purpose.
        entries[-2](icon)
        entries[-1](icon)
        self.assertEqual(events, ["web", "quit"])

    def test_real_win32_icon_menu_constructs_and_lifecycle_stops(self):
        import pystray
        from PIL import Image
        from link_mode_tray import ModeTrayController, build_preview_menu
        from link_display_modes import Signals

        controller = ModeTrayController(lambda: Signals())
        menu = build_preview_menu(
            pystray, controller,
            status_supplier=lambda: "WAITING",
            open_dashboard=lambda *_: None,
            quit_app=lambda *_: None,
        )
        image = Image.new("RGB", (64, 64), "#141820")
        icon = pystray.Icon(
            "SHINO_LINK_M2_CI_TEST", image, "SHINO // LINK M2 CI", menu)
        seen = threading.Event()
        errors = []

        def setup(ready_icon):
            try:
                seen.set()
                ready_icon.visible = True
            except Exception as exc:
                errors.append(type(exc).__name__)
            finally:
                ready_icon.stop()

        def run():
            try:
                icon.run(setup=setup)
            except Exception as exc:
                errors.append(type(exc).__name__)

        worker = threading.Thread(target=run, daemon=True,
                                  name="SHINO-test-Win32-tray-loop")
        worker.start()
        worker.join(timeout=12)
        if worker.is_alive():
            icon.stop()
            worker.join(timeout=3)
        self.assertFalse(worker.is_alive(), "Win32 tray event loop did not stop")
        self.assertEqual(errors, [], "Win32 tray backend raised an exception")
        self.assertTrue(seen.is_set(), "Win32 tray setup callback did not run")


if __name__ == "__main__":
    unittest.main()
