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
