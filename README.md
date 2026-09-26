# SHINO // TV

An independent, experimental firmware and PC-companion project for the **GeekMagic SmallTV-Ultra (ESP8266)**.

> **Status:** Phase 0 — research and recovery planning. No firmware has been flashed, extracted from the device, or validated on the owner's hardware.

## Target device

| Field | Observed value |
|---|---|
| Web-reported model | `SmallTV-Ultra` |
| Web-reported firmware | `Ultra-V9.0.44` |
| Current LAN address (development only) | `192.168.1.70` |
| Display | 240 × 240, ST7789 (reported by third-party reverse engineering; verify board revision) |
| MCU | ESP8266 / ESP-12F (reported by third-party reverse engineering; verify board revision) |
| Flash | Reported 4 MB, to verify on actual hardware |

The address above is an example of the owner's local device, not a hardcoded firmware setting or internet endpoint.

## Goal

Replace the factory application's limitations with an extensible, documented system:

- Native drawing on the LCD, without continuously writing JPEGs to flash.
- Local HTTP control and structured JSON status updates.
- A Windows companion for GPU/CPU/RAM monitoring, music, coding-agent status, and SHINOBIWAN release information.
- A configurable 240 × 240 scene/widget system.
- Recoverable firmware updates, careful flash/RAM usage, and local-only by default.

## Safety gate

**DO NOT FLASH** until all the following have been completed and reviewed:

1. Identify the physical board/MCU, boot pins, power requirements, and flash size.
2. Document a suitable **3.3 V UART** connection and the recovery process.
3. Read back the full existing flash from the owner's unit, when hardware access is available.
4. Verify the backup size and cryptographic digest; preserve an off-device copy.
5. Establish and rehearse a non-destructive recovery plan with an explicit go/no-go decision.
6. Build/test a candidate image and check partition/OTA constraints before any write.

Never feed 5 V TTL signals into an ESP8266 GPIO. The existing manufacturer's `/v.json`, `/app.json`, and `/space.json` endpoints have already responded to read-only requests, but that does not establish any undocumented API's semantics.

## Research starting points

- [GeekMagic manufacturer firmware repository](https://github.com/GeekMagicClock/smalltv-ultra) — factory packages, manual, update history.
- [Times-Z / GeekMagic-Open-Firmware](https://github.com/Times-Z/GeekMagic-Open-Firmware) — SmallTV-Ultra compatible source, LCD pinout and flash-backup procedure (GPL-3.0).
- [giovi321 / smalltv-mod](https://github.com/giovi321/smalltv-mod) — alternative firmware, Ultra-specific installation caveat and PC-driven features (see its license).
- [aydarik / geekmagic-tv-esp8266](https://github.com/aydarik/geekmagic-tv-esp8266) — ESP8266 firmware and compatibility endpoints (MIT).

Upstream software will be evaluated **before** code reuse, with attribution and license obligations documented.

## Working method

Start with read-only investigation and a PC-side simulator. Keep original firmware binaries, local credentials, backups, and personal data out of Git. Firmware and any update mechanism are out of scope until the safety gate is passed.

See [ROADMAP](docs/ROADMAP.md) and [device baseline](docs/DEVICE_BASELINE.md) on the planning branch.

## Try the offline simulator

Requires Python 3 and a modern browser. This serves **only local demo files** and never reaches the SmallTV:

```bash
python -m http.server 8080 --directory simulator
```

Open http://localhost:8080, select PC HEALTH / MUSIC / CODEX / RELEASE, edit the JSON, apply, or export a 240 × 240 PNG. Values are explicitly **demo placeholders**; real PC telemetry is not implemented yet.

## Offline firmware research tooling

Download the desired official ZIP package yourself from the manufacturer repository and inspect it offline:

```bash
python tools/inspect_factory.py "path/to/FW-Smalltv-Ultra-V9.0.46.zip" --json
```

This outputs archive/firmware SHA-256 hashes, conservative ESP8266 header fields and a limited sample of printable route strings; no hardware access, uploading, flashing or automatic web requests. Candidate route strings are not proof of a callable route on stock V9.0.44.

## Local tests

```bash
python -m unittest discover -s tools -p 'test_*.py' -v
node --test simulator/scene.test.mjs
```

See also [firmware audit](docs/FIRMWARE_AUDIT_01.md) and [scene protocol](docs/SCENE_PROTOCOL.md).

## Imported firmware baseline and Windows bridge

- [Firmware source](firmware/UPSTREAM.md): pinned Times-Z ESP8266 baseline; GPL-3.0-or-later, with full imported source in `firmware/`.
- [Firmware build guide](docs/FIRMWARE_BUILD.md): offline PlatformIO + LittleFS compile and explicitly closed hardware-flash gate.
- [Windows telemetry bridge](companion/README.md): opt-in, read-only local HTTP JSON metrics for the upstream six-tile dashboard. Runs locally by default; LAN exposure requires a specific address and firewall restriction.

The device still has its stock Ultra-V9.0.44 firmware. No hardware deployment or V9.0.44 full-flash backup has occurred.

## Native scene engine — PR #3

The proposed ESP8266 firmware now contains a RAM-only scene renderer supporting `music`, `agent`, `release`, and Times-Z's existing optional `metrics` screen. A Bearer-protected `/api/v1/shino/scene` endpoint accepts bounded JSON, and custom scenes display `DATA STALE` after 60 seconds without fresh input.

See [native scene protocol and examples](docs/NATIVE_SCENES.md). The independent [PC scene client](companion/scene_client.py) **previews only by default**. The device is still on factory Ultra-V9.0.44; these routes do not exist there until a separately approved firmware installation.

## Before any physical access: verified recovery gate

- [Full-flash readback protocol](docs/RECOVERY_PROTOCOL.md): requires owner PCB/pad/voltage identification, two independent read-only esptool acquisitions and an offline/private backup.
- [Static security audit](docs/SECURITY_AUDIT_01.md): identifies fixed setup/rescue AP credentials, unauthenticated rescue actions, fallback updater and configuration exposure as deployment blockers.
- [Offline verifier](tools/verify_flash_backup.py): validates two readback files, their expected byte counts, exact equality and SHA-256 without connecting to a device.

**Hardware state unchanged.** No owner-unit dump or restoration test has taken place. A compiled build is not authorization to flash.

## Protected Wi-Fi recovery loader prototype — no flash approved

The separate `recovery_loader/` PlatformIO project compiles two **offline-only** variants: read-only by default, and an explicitly enabled experimental upload handler that accepts only per-build pinned SHINO and official V9.0.44 application images. It generates private WPA2/Digest credentials locally, does not publish binaries and does not contact the owner's device. See [loader safety and setup notes](recovery_loader/README.md) and the [pinned original OTA reference](recovery/README.md).

**The intermediate loader is overwritten by the final firmware**, so it is not a persistent rescue partition. A no-solder Wi-Fi install still has residual brick risk and remains subject to a separate end-to-end test and owner approval.

## Owner-only stock V9.0.44 diagnostic — no flash

A no-install/no-flash Windows report tool is available on the stacked `research/stock-v9044-readonly-report` branch: double-click `run-stock-readonly.cmd`, enter your SmallTV's current private LAN IPv4, and optionally enable **GET-only** `/update` page inspection. It writes a sanitized, gitignored `research-local/stock-report.json`. It never POSTs, uploads firmware, collects Wi-Fi credentials or claims to measure the stock OTA slot. See [read-only diagnostic guide](docs/STOCK_READONLY_WIFI_REPORT.md).


## Verified LittleFS package: source-only

The [LittleFS migration safety report](docs/VERIFIED_FS_PROVISIONING.md) explains why a full 2,072,576-byte image of our 4m2m FS is **not an atomic OTA operation** on this ESP8266. The new offline tooling verifies and pins the exact FS image and safely reports the old-data overlap; the bridge has only an authenticated GET impact page. Automatic formatting, filesystem writer and on-device upload remain disabled. The original V9.0.44 application ZIP does not restore stock filesystem data.


## Native UI V2 — exact 240×240 / four live metrics

The [approved V2 240×240 specification](docs/NATIVE_UI_V2_240_SPEC.md) is implemented in stacked branch `feature/native-ui-v2-four-cards`: four always-visible CPU/GPU/RAM/temperature cards, dynamic four-band colored bar fills, real PC memory total for RAM normalization, 30–90 °C *visual-only* thermal scale and per-card ±2pp hysteresis. `start-fsless-preview.cmd` serves the **exact embedded Web assets locally** for inspection without device access. The code is compiled/tested offline only, not a device-ready upload.

## FS-less native display and Web UI — source-only

The latest stacked [FS-less dashboard work](docs/FSLESS_NATIVE_DASHBOARD.md) removes the runtime need for LittleFS: native 240×240 CPU/GPU/RAM gauges, a flash-embedded same-origin Web page and an opt-in Windows-to-device RAM-only telemetry sender. Firmware CI now builds **no LittleFS image or config seed** for this first-boot profile; automatic format and storage migration remain forbidden. Original manufacturer flash layout, first OTA acceptance and no-boot rescue remain unproven, so **do not upload a custom BIN to the owner TV** without a separate explicit go/no-go process.
