"""M1 HOST-only policy for the owner-approved SHINO // LINK display modes.

A proposed scene is NOT a command, acknowledged device state, renderer, or
firmware capability. This module performs no I/O, has no side effects, and
does not read the private LINK configuration. M2 can consume this decision
without altering the existing telemetry worker; M3 needs a separate,
authenticated, explicitly qualified command/status contract.
"""

from dataclasses import dataclass
from enum import Enum


class DisplayMode(str, Enum):
    AUTO = "AUTO"
    CLOCK_WEATHER = "CLOCK_WEATHER"
    MONITORING = "MONITORING"
    MUSIC = "MUSIC"


class Scene(str, Enum):
    """HOST preview only; these are NOT firmware scene IDs."""

    HYBRID = "HYBRID"  # Clock (if valid) plus four fresh PC metric cards
    CLOCK_WEATHER = "CLOCK_WEATHER"  # Clock/weather only, no metric cards
    MONITORING = "MONITORING"  # Four fresh metric cards, no music takeover
    MUSIC = "MUSIC"  # Music only, no metric cards
    MONITORING_UNAVAILABLE = "MONITORING_UNAVAILABLE"
    NO_MEDIA = "NO_MEDIA"


class Reason(str, Enum):
    AUTO_MUSIC = "AUTO_MUSIC"
    AUTO_METRICS = "AUTO_METRICS"
    AUTO_STALE_METRICS = "AUTO_STALE_METRICS"
    AUTO_PC_OFFLINE = "AUTO_PC_OFFLINE"
    MANUAL_CLOCK = "MANUAL_CLOCK"
    MANUAL_MONITORING = "MANUAL_MONITORING"
    MANUAL_METRICS_UNAVAILABLE = "MANUAL_METRICS_UNAVAILABLE"
    MANUAL_MUSIC = "MANUAL_MUSIC"
    MANUAL_MEDIA_UNAVAILABLE = "MANUAL_MEDIA_UNAVAILABLE"


@dataclass(frozen=True, slots=True)
class Signals:
    """Validated facts for one decision; unknown/unavailable == False.

    pc_connected means a fresh LINK connection, not simply Windows powered
    on. metrics_fresh is independent: a connection does not prove telemetry
    still satisfies the firmware's six-second TTL. music_playing represents
    confirmed active playback, not just an open Spotify process.

    B5.3 LEAN has no weather provider: callers must pass weather_valid=False.
    True means a future provider has *separately* validated current data.
    """

    pc_connected: bool = False
    metrics_fresh: bool = False
    music_playing: bool = False
    time_valid: bool = False
    weather_valid: bool = False

    def __post_init__(self) -> None:
        for field in ("pc_connected", "metrics_fresh", "music_playing",
                      "time_valid", "weather_valid"):
            if type(getattr(self, field)) is not bool:
                raise TypeError("Signals." + field + " must be a boolean")


@dataclass(frozen=True, slots=True)
class Decision:
    requested_mode: DisplayMode
    proposed_scene: Scene
    reason: Reason
    show_live_metrics: bool
    show_live_music: bool
    show_valid_time: bool
    show_valid_weather: bool

    # No applied/confirmed flag: M1 does not communicate with the device.
    # In particular, proposed_scene must NEVER be treated as an OTA or HTTP ACK.


def decide(requested_mode: DisplayMode, signals: Signals) -> Decision:
    """Compute one HOST preview without changing the user's manual choice.

    Automatic priority: active music on the connected PC > fresh PC metrics >
    clock/standby. Manual modes never yield control to the automatic policy.
    A manual mode's unavailable placeholder does not reset requested_mode.

    Playback PAUSED policy, persisted preference, device capability/status,
    weather retrieval and real scene switching are deliberately out of scope.
    """
    if type(requested_mode) is not DisplayMode:
        raise TypeError("requested_mode must be DisplayMode")
    if type(signals) is not Signals:
        raise TypeError("signals must be Signals")

    connected = signals.pc_connected
    metrics = connected and signals.metrics_fresh
    music = connected and signals.music_playing

    if requested_mode is DisplayMode.AUTO:
        if music:
            scene, reason = Scene.MUSIC, Reason.AUTO_MUSIC
        elif metrics:
            scene, reason = Scene.HYBRID, Reason.AUTO_METRICS
        elif connected:
            scene, reason = Scene.CLOCK_WEATHER, Reason.AUTO_STALE_METRICS
        else:
            scene, reason = Scene.CLOCK_WEATHER, Reason.AUTO_PC_OFFLINE
    elif requested_mode is DisplayMode.CLOCK_WEATHER:
        scene, reason = Scene.CLOCK_WEATHER, Reason.MANUAL_CLOCK
    elif requested_mode is DisplayMode.MONITORING:
        if metrics:
            scene, reason = Scene.MONITORING, Reason.MANUAL_MONITORING
        else:
            scene, reason = (Scene.MONITORING_UNAVAILABLE,
                             Reason.MANUAL_METRICS_UNAVAILABLE)
    else:  # DisplayMode.MUSIC, after strict enum validation
        if music:
            scene, reason = Scene.MUSIC, Reason.MANUAL_MUSIC
        else:
            scene, reason = Scene.NO_MEDIA, Reason.MANUAL_MEDIA_UNAVAILABLE

    clock_scene = scene in (Scene.CLOCK_WEATHER, Scene.HYBRID)
    return Decision(
        requested_mode=requested_mode,
        proposed_scene=scene,
        reason=reason,
        show_live_metrics=metrics and scene in (Scene.HYBRID, Scene.MONITORING),
        show_live_music=music and scene is Scene.MUSIC,
        show_valid_time=clock_scene and signals.time_valid,
        show_valid_weather=clock_scene and signals.weather_valid,
    )
