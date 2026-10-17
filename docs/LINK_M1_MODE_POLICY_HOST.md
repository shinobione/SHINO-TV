# SHINO // LINK — M1 pure Windows HOST mode policy

**Date:** 17 October 2026. **Status:** implemented as HOST source and
deterministic tests only. No M2 tray integration, no new firmware, no hardware
test or control route. The user approved the interactive UX model before M1;
that is UX approval, not postboot scene-switch acceptance.

## Base and scope

- Base: the reviewed UX freeze on Draft PR #52,
  planning/shino-link-display-modes-20261017 at
  f89635249896addb7a57eac452dcd1eb32ced47f.
- M1 code: companion/link_display_modes.py (Python standard library only).
- Regression matrix: companion/test_link_display_modes.py.
- Existing companion/shino_link.py, metrics sender, tray, autostart,
  configuration, private credentials, B5.2/B5.3 builders, media/GSMTC, native
  firmware, OTA, LittleFS and HTTP endpoints are **unchanged**.
- B5.3 LEAN is the owner-observed installed functional reference. It has no
  native weather HTTP provider. Do not present the weather placeholder as a
  real weather report.

## Pure selection rules

decide(DisplayMode, Signals) returns a deterministic, synchronous,
side-effect-free proposed **HOST preview**, never an ACK or verified LCD
state. Strict typed booleans prevent "false", 0 or None from silently
becoming valid observations. Flags are supplied by a future controller:

- pc_connected: currently valid LINK presence, not merely Windows running.
- metrics_fresh: independently within the existing 6-second telemetry TTL.
- music_playing: confirmed live playback, not an open Spotify process.
- time_valid: independently authorized/synchronized time, may be false.
- weather_valid: future independently validated provider, false on B5.3 LEAN.

| User mode | Context | HOST preview |
| --- | --- | --- |
| AUTO | PC present + confirmed playing | MUSIC only |
| AUTO | No playing + PC present + metrics fresh | HYBRID (clock + 4 cards) |
| AUTO | PC offline OR metrics stale | CLOCK_WEATHER, valid/unknown indicators |
| CLOCK_WEATHER | Any PC/media context | CLOCK_WEATHER only |
| MONITORING | PC + fresh metrics | MONITORING only |
| MONITORING | PC missing or metrics stale | MONITORING_UNAVAILABLE |
| MUSIC | PC + confirmed playing | MUSIC only |
| MUSIC | No confirmed playing | NO_MEDIA |

A manual fallback keeps requested_mode unchanged, so playback, reconnection
or new telemetry **cannot silently restore AUTO**. Selecting AUTO explicitly
restores context rules. No scene mixes music and metric cards. An orphaned
media event from a disconnected PC cannot activate MUSIC.

show_valid_time and show_valid_weather only become true when the respective
signal is valid **and** the scene permits that content. They cannot
manufacture time, temperatures or forecasts.

**Deferred to later gates:** Windows tray commands and preference storage (M2),
command authorization/capability/ACK/reconciliation (M3), native display
integration and PAUSED/NO ARTWORK/timeline/weather (M4), physical qualification
and packaging (M5). Do not use the M1 Scene enum as native scene IDs.

## Reproducible HOST tests

From repository root, Python 3.10+:

    python -m unittest discover -s companion -p test_link_display_modes.py -v

Tests cover owner two-checkbox simulation, manual override against all context
transitions, fallback recovery without losing intent, 128 mode/context
combinations, freshness/value-validity gates, type rejection, immutability,
repeatability and network/file-call prohibition.

**Evidence status:** record local test exit code and/or exact-head CI
conclusion separately once executed. Storing tests on GitHub is not a PASS.
The existing CI's broad companion unittest discovery includes this test file.

**Next action:** M2 may consume these typed decisions in a Windows
preview/tray menu, still without device POST. Do not automatically change
the currently running SHINO // LINK or its startup configuration.
