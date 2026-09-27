# SHINO // TV — Roadmap

This roadmap deliberately separates **analysis**, **PC-side simulation**, and **hardware writes**.

## Phase 0 — Baseline and safety (current)

- [x] Identify model and reported version via the owner's read-only HTTP endpoints.
- [x] Inventory the manufacturer repository and selected community firmware projects.
- [x] Capture current configuration and observed storage behavior.
- [ ] Catalog V9.0.44-specific routes/requests from a local browser export or firmware image, distinguishing observed behavior from assumptions.
- [ ] Confirm device board revision, flash size, serial pads, and power constraints by photographs/inspection.
- [ ] Document the precise 3.3 V UART adapter and test/readback procedure.
- [ ] Obtain a complete factory flash readback, digest and an offline backup (requires owner hardware access).
- [ ] Review restoration plan and record explicit owner approval before any firmware write.

**Owner-selected path (supersedes the hardware-focused tasks above):** one existing unit, Wi-Fi-only research, no spare PCB, soldering, or UART/PCB wiring. A full owner-specific flash backup and nonbooting rescue cannot be guaranteed on this chosen path. Its residual risk is to be shown plainly, not hidden or converted into a request to purchase hardware. See [source-backed comparative flash/layout audit](COMPARATIVE_FLASH_LAYOUT_AUDIT.md).

**Immediate P0 blocker found:** the stock photo/GIF filesystem total equals Arduino `4m3m` exactly, while SHINO/Times-Z `4m2m` uses a subset at a different start. Inherited `LittleFS.begin()` defaults to **autoformat on mount failure** and is called on first SHINO boot; SecureStorage initialization can also write EEPROM. Do NOT perform a stock→SHINO first flash using this unguarded startup. Design a no-format/no-EEPROM initial diagnostics/return bridge and an explicitly owner-approved FS provisioning path. Current compiled SHINO BIN is smaller than official V9.0.44; study direct OTA before treating two-hop loader as mandatory.

**Latest safe candidate research (27 September 2026):** V2 works without LittleFS. Its source linker is now aligned to `4m3m` to model both direct stock→V2 OTA and running V2→original application return wholly below the inferred manufacturer filesystem. Two-hop transient 4m1m loader→V2 staged bytes overlap the old filesystem; do not call it a preservation fallback. [Review first-install decision packet](FIRST_INSTALL_DECISION_PACKET.md). Owner's original full-flash backup and physical first-OTA acceptance remain unavailable/unknown under Wi-Fi-only constraints. No flashing authorization.

**Gate 0:** No firmware upload or flash write until baseline, backup and recovery plan have been verified.

**Pinned OEM rollback reference available (offline only):** the exact V9.0.44 official archive has been recovered from GeekMagic's historical commit, inspected, and pinned by outer/inner SHA-256 in `recovery/factory_ota_v9_0_44.json`. Every candidate build must pass the OEM reference integrity prerequisite in CI. This does **not** complete Gate 0: no owner-unit full-flash image, custom Wi-Fi loader-to-OEM physical restore test, or reliable no-boot recovery path has been established. See [recovery/README.md](../recovery/README.md).

## Phase 1 — Static firmware and API research

- Build a manifest of official firmware packages, archive hashes, image headers, layouts, embedded web resources and printable strings.
- Analyze factory image(s) offline, including V9.0.44 only if legitimately acquired from a device readback or matching official package.
- Document each API endpoint with HTTP method, parameters, response, version, side effects and confidence level.
- Assess existing projects for board variant coverage, memory and OTA limitations, licensing and restore routes.
- Do not assume an official OTA package is a full flash backup.

**Exit:** Reproducible research notes and a documented architectural choice.

## Phase 2 — Simulator and Windows companion

- Define a minimal JSON scene protocol with capability negotiation.
- Implement desktop-only telemetry adapters: system metrics, player/track data, development-task status, release countdowns.
- Render representative 240×240 scenes to a local preview; no device flash writes.
- Prefer delta/in-memory updates and rate limits over continuous image uploads.
- Treat cloud credentials as PC-side secrets, never embed them into device firmware.

**Exit:** Working simulated widget pipeline and tests.

## Phase 3 — Firmware prototype (Times-Z upstream as proposed baseline)

- Review and preserve Times-Z GeekMagic-Open-Firmware's GPL-3.0-or-later notices and pin an audited upstream commit; do not confuse referencing it with having imported/compiled it.
- Build the unmodified upstream `esp12e` PlatformIO firmware and LittleFS assets offline first; record sizes and tests.
- Reuse upstream `DisplayManager`, `DashboardManager`, `Webserver`, `Api`, `WiFiManager`, `ConfigManager` and `RescueMode`, rather than rebuilding their existing functionality.
- Extend the existing optional metrics mode into a bounded scene/widget engine with a Windows data bridge.
- Review rescue-mode unauthenticated operations, setup AP defaults, memory/flash constraints and the stock Ultra OTA slot before any device write.
- Run any hardware deployment only after Gate 0 has passed and with owner approval.
- Establish rollback path and keep the factory backup private.

**Exit:** A source-built upstream-derived, desktop-validated firmware candidate. Physical screen and recovery tests are a separate owner-approved gate.

See [UPSTREAM_INTEGRATION.md](UPSTREAM_INTEGRATION.md) for the architectural decision and real existing metrics JSON contract.

## Phase 4 — SHINO // TV product features

- Scene/widget engine: clock, device health, PC telemetry, music, coding-agent status and SHINOBIWAN release panel.
- Web configuration with local authentication appropriate to an ESP8266 and an explicitly limited threat model.
- Graceful behavior when Wi-Fi or the PC companion disconnects.
- Safe updates with version checks, partitions and documented recovery.

## Phase 5 — Validation and release

- Soak test for memory leaks, power recovery and disconnect/reconnect.
- Assess update reliability, flash wear, input bounds, and access control.
- Document install/restore, user settings and troubleshooting.
- Release only assets for the verified model and hardware revision.

## Owner UX backlog — future V2.2 multi-scene display (NOT IMPLEMENTED)

**Captured 27 September 2026 from side-by-side photographs of the live 240×240 SmallTV and its same-origin Web dashboard.** These are requested product/design notes, not a change to the approved V2 four-card contract and not authorization to flash or open an OTA route. The Web version is the positive visual reference; a matching browser preview does **not** guarantee the native LCD has comparable contrast, typography or color. Photographic exposure can exaggerate color differences, so confirm decisions by direct physical inspection and reproducible on-device test patterns during a separately approved future visual release. Existing V2 Hotfix `review-002` remains the known working installed baseline.

### V2.2-A — Native readability and visual hierarchy (first UI priority)

- [ ] Revisit **physical LCD** background/card/text contrast: the observed cyan/light card fill washes out white text compared with the Web UI. Prefer visibly darker, quieter card surfaces; ensure strong hierarchy between background, label and large numerical value. Do not simply copy desktop CSS colors and assume RGB565/ST7789 renders identically.
- [ ] Recalibrate the dynamic gauge colors **on hardware**. Current fills appear too pale/weak; keep percentage-based mint/yellow/orange/burgundy progression and independent readings, but select RGB565-safe, distinguishable shades and sufficient contrast between track, fill and surrounding surface. Never interpret a color band as a hardware alarm threshold.
- [ ] Replace or substantially improve the **native LCD bitmap font**: user finds the current tiny/pixelated labels and numerals unpleasant/poorly legible, while Web typography is satisfactory. Compare efficient legible glyph/font sizes, consistent numeric baselines and punctuation/degree/decimal rendering within the actual 240×240 bounds. Evaluate flash/RAM/cost first; avoid clipping on longest live values and do not require runtime downloaded fonts.
- [ ] Create same-content **true 240×240 native-renderer** screenshots/test patterns and Web reference captures at several real readings, including 0%, 100%, high RAM use, missing GPU and stale data. Review from normal desk viewing distance, under both ambient and colored room lighting. Pass criterion is readable labels and values at a glance, not CSS pixel similarity alone.

### V2.2-B — Multi-scene architecture (preserve all four metrics)

- [ ] Evolve the current fixed V2 grid into a lightweight, bounded **scene/page system** without losing its exact four-value PC-health view: CPU usage, GPU usage, RAM used and GPU temperature must remain available together, with their current freshness/error behavior.
- [ ] Define switching via the protected Web control/Windows companion and consider optional configurable rotation; do not assume physical buttons or touchscreen input exist. Define clear active-scene and no-PC/fallback behavior, redraw cadence and RAM/flash bounds before implementing.
- [ ] Reserve these proposed views, each drawn for the real 240×240 surface rather than shrinking desktop cards:
  - **PC Health** — the existing four measurements and colored bars.
  - **Clock** — clear large time, optionally date/day; explicit timezone and clock-source/synchronization status. Never silently show incorrect time after boot/offline periods.
  - **Now Playing** — cover artwork of the current track, artist/title and optionally playback/progress state. Plan a PC-side metadata/artwork source (e.g. supported Windows media session or opt-in Spotify integration), bounded image conversion/transport and cached RAM-only display; do not silently write album art to the old OEM filesystem or embed account tokens on the ESP8266. Show a tasteful fallback when no track/cover is available.
  - **Local Weather** — temperature for an **owner-configurable city**, with concise location/conditions and last-update/stale status. Research provider/licensing/privacy and have the Internet-connected PC companion retrieve/cache the data where suitable; the current private-AP-only SmallTV has no guaranteed Internet access.
  - **Later extensibility** — e.g. coding-agent and SHINOBIWAN release status, only after the base scene/navigation contract is stable.
- [ ] Review data schemas, trust boundaries, refresh budgets, retained image memory and UX separately. Do not stretch the current narrow numeric metrics POST into an unchecked generic JSON/image-upload endpoint. No new device handler, image/file writer or update privilege is authorized by these notes.

### Suggested order / acceptance gates

1. Native LCD readability + font/palette trials and owner visual sign-off, preserving the existing working 4-card layout.
2. Desktop-only 240×240 page mockups and scene-switching design, with CPU/GPU/RAM/temp all preserved on their dedicated page.
3. PC-side prototypes for clock, media metadata/cover conversion and city weather; verify loss-of-connectivity and stale-data cases.
4. Only after independent size, RAM, network-auth and hardware safety review: a separately authorized device implementation/visual test. OTA/signing/recovery work has **its own** approval gate and must not be coupled to this UI backlog.

**Scope lock:** ROADMAP/DESIGN ONLY. No changes to `FirstBootBridge.cpp`, `FslessMetrics.cpp`, browser UI, display renderer, companion sender, flash layout, signing, privileged HTTP or the owner-installed firmware from this request.

## Principles

No public exposure of the device HTTP service; no scanning beyond the owner's target without permission. No unreviewed firmware writes. No proprietary manufacturer binaries or personal flash dumps committed to this repository.


## FS-less prototype — next milestone

The dedicated [native FS-less dashboard](FSLESS_NATIVE_DASHBOARD.md) extends the conservative first-boot bridge with PC CPU/GPU/RAM telemetry in volatile RAM and a same-origin HTML/JS UI compiled into application program flash. No filesystem image is built or needed in the default firmware pipeline. The separate verified full LittleFS package remains research-only and its non-atomic migration writer is still disabled. This does not prove the manufacturer V9.0.44 OTA slot accepts the binary or that Wi-Fi restore works after no-boot failure.
