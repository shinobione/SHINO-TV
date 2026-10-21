"""M2 local-only SHINO // LINK tray mode selection and honest HOST preview.

No HTTP, OTA, LittleFS, device commands, background worker, persisted setting,
GSMTC subscription or credential access. The current SmallTV will NOT change
scene when these buttons are clicked; that requires a separate M3 protocol.
"""

import math
import threading

from link_display_modes import DisplayMode, Scene, Signals, decide

MODE_LABELS = {
    DisplayMode.AUTO: "Automatique",
    DisplayMode.CLOCK_WEATHER: "Horloge / Météo",
    DisplayMode.MONITORING: "Monitoring PC",
    DisplayMode.MUSIC: "Musique",
}

SCENE_LABELS = {
    Scene.HYBRID: "4 cartes + horloge si valide",
    Scene.CLOCK_WEATHER: "Horloge / Météo si disponibles",
    Scene.MONITORING: "4 cartes PC",
    Scene.MUSIC: "Musique",
    Scene.MONITORING_UNAVAILABLE: "Monitoring indisponible",
    Scene.NO_MEDIA: "Lecture musicale non vérifiée",
}

def passive_link_signals(engine, *, ttl_ms: int) -> Signals:
    """Observe the existing sender without HTTP, retries or worker mutation.

    The Windows ACK age is a local approximation, not a device scene ACK.
    Media source is deliberately unconnected in M2, and weather/time validity
    cannot be inferred from Windows wall time or the B5.3 installed clock.
    """
    if type(ttl_ms) is not int or ttl_ms <= 0:
        raise ValueError("telemetry TTL must be a positive integer in ms")
    completed = engine.last_success
    fresh = False
    if type(completed) in (int, float) and math.isfinite(completed):
        now = engine.clock()
        if type(now) in (int, float) and math.isfinite(now):
            age_ms = (now - completed) * 1000
            fresh = 0 <= age_ms <= ttl_ms
    return Signals(
        pc_connected=fresh, metrics_fresh=fresh, music_playing=False,
        time_valid=False, weather_valid=False,
    )


class ModeTrayController:
    """Thread-safe PC selection only; no persistence and no device write."""

    def __init__(self, signal_supplier):
        if not callable(signal_supplier):
            raise TypeError("signal_supplier must be callable")
        self._supplier = signal_supplier
        self._lock = threading.Lock()
        self._mode = DisplayMode.AUTO

    def mode(self) -> DisplayMode:
        with self._lock:
            return self._mode

    def choose(self, mode: DisplayMode) -> None:
        if type(mode) is not DisplayMode:
            raise TypeError("mode must be DisplayMode")
        with self._lock:
            self._mode = mode

    def decision(self):
        # Snapshot preference first; caller may race with tray callbacks.
        mode = self.mode()
        signals = self._supplier()
        if type(signals) is not Signals:
            raise TypeError("signal supplier must return Signals")
        return decide(mode, signals)

    def preview_label(self) -> str:
        # Fail closed on a broken local probe. Never claim SmallTV acceptance.
        try:
            decision = self.decision()
        except (TypeError, ValueError, OSError, ArithmeticError):
            return "Aperçu PC : données indisponibles"
        return "Aperçu PC : " + SCENE_LABELS[decision.proposed_scene]


def build_preview_menu(pystray, controller: ModeTrayController, *,
                       status_supplier, open_dashboard, quit_app, firmware_action=None):
    """Build pystray menu once, with dynamic radio checks and preview text.

    Dynamic lambdas are evaluated by pystray on menu refresh. Callbacks
    change only local state and redraw the menu. They do not call LINK's
    sender, firmware endpoints, registry or filesystem.
    """
    if type(controller) is not ModeTrayController:
        raise TypeError("controller must be ModeTrayController")

    def noop(icon_, item):
        return None

    def pick(mode):
        def selected(icon_, item):
            controller.choose(mode)
            icon_.update_menu()
        return selected

    menu_items = []
    for mode in DisplayMode:
        menu_items.append(pystray.MenuItem(
            MODE_LABELS[mode], pick(mode),
            checked=lambda item, selected=mode: controller.mode() is selected,
            radio=True,
        ))

    extra = ()
    if firmware_action is not None:
        from link_firmware_identity import LABEL
        def trigger(icon_, item):
            firmware_action.start(icon_)
        details = tuple(pystray.MenuItem(
            lambda item, field=field: firmware_action.line(field),
            noop, enabled=False,
        ) for field in (
            "version", "build", "sha", "bytes", "checked", "ota",
            "fs", "last_update",
        ))
        extra = (
            pystray.MenuItem(LABEL, trigger,
                enabled=lambda item: firmware_action.snapshot()["state"] != "READING"),
            pystray.MenuItem("Identité lue (détails)",
                pystray.Menu(*details)),
        )

    return pystray.Menu(
        pystray.MenuItem(lambda item: "LINK : " + status_supplier(),
                         noop, enabled=False),
        pystray.MenuItem("Mode d'affichage (aperçu PC)",
                         pystray.Menu(*menu_items)),
        pystray.MenuItem(lambda item: controller.preview_label(),
                         noop, enabled=False),
        pystray.MenuItem("SmallTV : aucun changement envoyé",
                         noop, enabled=False),
        *extra,
        pystray.Menu.SEPARATOR,
        pystray.MenuItem("Ouvrir SHINO // TV", open_dashboard),
        pystray.MenuItem("Quitter SHINO // LINK", quit_app),
    )
