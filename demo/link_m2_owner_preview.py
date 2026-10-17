"""SHINO // LINK M2 — Owner Windows visual preview, OFFLINE ONLY.

Completely separate executable. NOT the active LINK worker.
No credentials, link.json, device, HTTP, socket, filesystem preferences,
Wi-Fi, registry changes, autostart, telemetry, music probing, or OTA.
Both context switches deliberately simulate conditions on this PC only.
"""
from __future__ import annotations

import threading
import sys
from pathlib import Path

# Direct source launch works from any working directory, no installation.
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "companion"))

from PIL import Image, ImageDraw
import pystray
from link_display_modes import DisplayMode, Signals, Scene
from link_mode_tray import ModeTrayController, build_preview_menu


TITLE = "SHINO // LINK — ESSAI LOCAL (SIMULÉ)"
ICON_NAME = "SHINO_LINK_M2_OWNER_PREVIEW_NO_DEVICE"


class DemoContext:
    """Local, reset-on-relaunch simulated PC/music context."""

    def __init__(self):
        self._lock = threading.Lock()
        self._pc = True
        self._music = False

    def pc(self):
        with self._lock:
            return self._pc

    def music(self):
        with self._lock:
            return self._music

    def toggle_pc(self):
        with self._lock:
            self._pc = not self._pc

    def toggle_music(self):
        with self._lock:
            self._music = not self._music

    def signals(self):
        with self._lock:
            # No live time/weather read; all context is simulated.
            return Signals(
                pc_connected=self._pc, metrics_fresh=self._pc,
                music_playing=self._music, time_valid=False, weather_valid=False,
            )


def make_image():
    image = Image.new("RGB", (64, 64), "#141820")
    draw = ImageDraw.Draw(image)
    draw.rounded_rectangle(
        (5, 5, 58, 58), radius=12,
        fill="#242e3a", outline="#c4a779", width=3,
    )
    draw.line(
        [(15, 42), (24, 22), (32, 34), (41, 17), (49, 24)],
        fill="#80d9aa", width=5, joint="curve",
    )
    # Different from active LINK's tray icon: conspicuous demo dot.
    draw.ellipse((44, 5, 59, 20), fill="#e9b660", outline="#141820", width=2)
    return image


def build_demo_menu(context, controller):
    def noop(icon, item):
        return None

    def switch_pc(icon, item):
        context.toggle_pc()
        icon.update_menu()

    def switch_music(icon, item):
        context.toggle_music()
        icon.update_menu()

    def quit_demo(icon, item):
        icon.stop()

    # Reuse the production M2 menu and callbacks; remove the dashboard link,
    # because opening that URL would make an actual SmallTV network request.
    base = build_preview_menu(
        pystray, controller,
        status_supplier=lambda: "ESSAI SIMULÉ (aucun appareil)",
        open_dashboard=noop,
        quit_app=quit_demo,
    )
    selected = base.items

    return pystray.Menu(
        pystray.MenuItem("DÉMONSTRATION 100% LOCALE", noop, enabled=False),
        selected[1],  # Exact M2 radio submenu
        selected[2],  # Exact M2 calculated preview
        selected[3],  # Explicit no-send indicator
        pystray.MenuItem(
            "Contexte SIMULÉ (aucune détection)",
            pystray.Menu(
                pystray.MenuItem(
                    "PC connecté (simulé)", switch_pc,
                    checked=lambda item: context.pc(),
                ),
                pystray.MenuItem(
                    "Musique en lecture (simulée)", switch_music,
                    checked=lambda item: context.music(),
                ),
            ),
        ),
        pystray.Menu.SEPARATOR,
        pystray.MenuItem("Quitter cet essai", quit_demo),
    )


def self_test():
    """Bounded deterministic test for source or bundled EXE; never opens tray."""
    class IconStub:
        def __init__(self):
            self.updates = 0
            self.stopped = False
        def update_menu(self):
            self.updates += 1
        def stop(self):
            self.stopped = True

    context = DemoContext()
    controller = ModeTrayController(context.signals)
    menu = build_demo_menu(context, controller)
    items = menu.items
    icon = IconStub()
    radios = items[1].submenu.items
    assert [i.text for i in radios] == [
        "Automatique", "Horloge / Météo", "Monitoring PC", "Musique"
    ]
    assert controller.decision().proposed_scene is Scene.HYBRID
    assert "aucun changement envoyé" in items[3].text
    radios[1](icon)
    assert controller.mode() is DisplayMode.CLOCK_WEATHER
    context_menu = items[4].submenu.items
    context_menu[1](icon)  # music flag true
    assert controller.decision().proposed_scene is Scene.CLOCK_WEATHER
    radios[0](icon)  # auto resumes
    assert controller.decision().proposed_scene is Scene.MUSIC
    context_menu[0](icon)  # PC flag false, no orphan music
    assert controller.decision().proposed_scene is Scene.CLOCK_WEATHER
    radios[2](icon)  # monitoring offline
    assert controller.decision().proposed_scene is Scene.MONITORING_UNAVAILABLE
    radios[3](icon)  # manual music offline
    assert controller.decision().proposed_scene is Scene.NO_MEDIA
    assert icon.updates == 6
    items[-1](icon)
    assert icon.stopped
    return 0


def main(argv=None):
    args = list(sys.argv[1:] if argv is None else argv)
    if args == ["--self-test"]:
        return self_test()
    if args:
        return 2
    if sys.platform != "win32":
        return 3

    context = DemoContext()
    controller = ModeTrayController(context.signals)
    menu = build_demo_menu(context, controller)
    icon = pystray.Icon(ICON_NAME, make_image(), TITLE, menu)
    icon.run()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
