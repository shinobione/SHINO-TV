# Architectural decision D-005 — Reuse Times-Z GeekMagic Open Firmware

**Decision date:** 2026-09-26  
**Status:** Proposed development baseline, not yet deployed to hardware.

## Why this changes our plan

The upstream source repository is not just a pinout reference or a firmware binary. Its `develop` branch contains a substantial ESP8266 firmware implementation that **explicitly reports SmallTV-Ultra compatibility** and already includes a native 240×240 metrics dashboard.

Source: https://github.com/Times-Z/GeekMagic-Open-Firmware/tree/develop

## Reusable modules (verified in upstream tree)

| Module | Reuse for SHINO // TV |
| --- | --- |
| `src/display/DisplayManager.cpp` | ST7789 LCD initialization and native drawing |
| `src/dashboard/DashboardManager.cpp` | Existing 6-tile PC monitoring, 1-second HTTP polling, changed-value redraw |
| `src/web/Api.cpp` | HTTP API registration and JSON response patterns |
| `src/web/Webserver.cpp` | Local UI and static files |
| `src/wireless/WiFiManager.cpp` | ESP8266 Wi-Fi connection and AP behavior |
| `src/config/ConfigManager.cpp` | Config storage |
| `src/boot/RescueMode.cpp` | Recovery UI and routes |
| `data/web/` | Existing browser UI and static frontend resources |
| `platformio.ini` | ESP8266 Arduino/PlatformIO target, 4MB, LittleFS |

### Existing optional metrics mode

Upstream compiles it only when `METRICS_URL` is set as a build flag. It polls once per second using HTTP GET, with an 800ms timeout. Expected JSON fields:
`ok`, `gpu_usage`, `cpu_usage`, `gpu_vram_mb`, `memory_used_gb`, `gpu_power`, `gpu_temp_c`.
No write to filesystem is needed for every metrics refresh. Values are redrawn only when changed, and `PC OFFLINE` is displayed when the service is unavailable.

This is an existing starting point, **not** a generic widget engine. No current `/api/v1/scene` endpoint is present in the inspected `src/web/Api.cpp`. Our earlier desktop simulator is a future protocol/render reference, not a claim of existing upstream functionality.

## Proposed SHINO // TV implementation

1. Keep upstream source/version pinned and auditable. Do not copy vendor proprietary binaries.
2. Run an unmodified upstream PlatformIO compilation and check image and LittleFS sizes. Then compile an Ultra-specific config, **without uploading**.
3. Integrate existing `DashboardManager` as the first firmware scene. Avoid rewriting the ST7789 driver, GIF engine, server, Wi-Fi stack, and recovery from scratch.
4. Add scene selection/render handlers for bounded `metrics`, `music`, `agent`, `release` JSON. Validate request size/types and throttle changes. Reuse the existing authentication approach for new write-capable routes. Use in-memory updates, not repeated flash filesystem writes.
5. Develop a Windows bridge serving PC and other authorized data sources. Sensitive music/cloud API keys stay on the PC; the device only receives necessary display fields.
6. Add a SHINO-specific UI and release/diagnostics pipeline **after** successful source build.

## Important caveats

- **GPL-3.0-or-later** is declared in the upstream source and license. Preserve copyright, notices and compliant licensing/source availability when copying, modifying or distributing firmware. Track upstream provenance and license before the first source import.
- The upstream readme proposes a two-step OTA install (firmware then LittleFS). Another compatible project documents the stock Ultra OTA slot as small and possible `ERROR[4]: Not Enough Space`; do not assume that a locally compiled binary is OTA-installable on V9.0.44.
- Current upstream `src/main.cpp` has a fixed default setup AP SSID/password, and `src/boot/RescueMode.cpp` explicitly registers **unauthenticated rescue endpoints** capable of setting the token and uploading firmware. Treat these as security design items, not as a network-exposed service.
- Their historical stock V9.0.40 full-flash backup does not replace an owner-unit V9.0.44 backup.
- Hardware compatibility is upstream-reported, not validated on the owner's physical board.

## Go/no-go

**Allowed now:** source review, license review, compilation, simulator and Windows companion development, test harnesses.  
**Not approved:** flashing, uploading a loader, writing LittleFS, factory erase, or exposing the device on the public internet. All physical writes require the existing complete-backup/recovery gate and explicit owner approval.

Upstream references:
- https://github.com/Times-Z/GeekMagic-Open-Firmware/blob/develop/src/dashboard/DashboardManager.cpp
- https://github.com/Times-Z/GeekMagic-Open-Firmware/blob/develop/src/main.cpp
- https://github.com/Times-Z/GeekMagic-Open-Firmware/blob/develop/src/web/Api.cpp
- https://github.com/Times-Z/GeekMagic-Open-Firmware/blob/develop/src/boot/RescueMode.cpp
- https://github.com/Times-Z/GeekMagic-Open-Firmware/blob/develop/platformio.ini
- https://github.com/Times-Z/GeekMagic-Open-Firmware/blob/develop/LICENSE
- https://github.com/giovi321/smalltv-mod/blob/main/docs/src/content/docs/getting-started/flashing.md
