# SHINO // TV — Roadmap

> **Current live owner state, updated 28 September 2026:** owner's 240 × 240 SmallTV Ultra is running private **V2 Hotfix review-002**, with four real PC metrics, browser mirror and private WPA2 AP; its **authenticated read-only current-device GET** confirms `write_enabled=true` for the pinned, exact **OEM V9.0.44 return**, 494,144 bytes and SHA-256 `a6421f5bfee7860d97bed26620c346b8008f503e513702d4bfdf6e01010a7718`. The **owner-private review-003 V2.1** (diagnostic heap + retained exact-OEM receiver) has been locally prepared from frozen source commit `8cef03012ae4a4864d69cbe20e02f141a36e2d54`; owner-reported file is 405,712 bytes, SHA-256 `3252ba5cd1f85683945d4d9a87ce49118568c0977605debc089267f54d7f3b0e`. Its uploaded sanitized manifest passes the pair/layout checks and explicitly says `owner_ready_to_flash=false`. These owner reports are **not independent hashes of the local BIN** and no new device flash is authorized by roadmap edits.

> **Binding constraint:** development/install via **Wi-Fi only**, USB-C for power. **No proposed adapter, UART, pogo pins, solder, PCB access, extra device or purchase as a normal dependency.** Hardware recovery is a break-glass discussion **only after an actual brick and only at the owner's request**. Older hardware-gate research retained below is superseded for this owner. The manufacturer OTA application image is **not** a 4 MiB full-chip backup. No guarantee of Wi-Fi rescue if the application fails to boot.

> **Source freeze:** all product-roadmap additions live on independent branch `planning/v22-shino-link-scene-roadmap`, based on `8cef030...`. Do **not merge or cherry-pick this branch into PR #20** until the exact `review-003` source/image freeze is no longer needed. Documentation is not device installation approval.

## 28 September 2026 — SHINO // LINK & V2.2 integrated product roadmap

### Current delivered functionality vs future design

| Capability | Installed review-002 | Private V2.1 review-003 | V2.2 planned |
| --- | --- | --- | --- |
| 240x240 four live metrics CPU/GPU/RAM/GPU TEMP, variable-color bars | Owner observed, working | Retained by source | **Always preserved together** |
| Windows PC metrics push to `/api/v1/bridge/metrics` every ~2s | Working, manual sender | Retained | Managed SHINO // LINK background companion |
| Invalid/absent samples expire in ~6s, no invented zeros | Present in V2 code | Retained | Scene transition based on explicit PC connectivity |
| Same-origin Chrome dashboard | Working | Retained | Configurable scenes and preview |
| Observed heap/free block/fragmentation 1Hz summary | No | **Opt-in, compiled/private, not installed yet** | Optional diagnostics |
| Exact pinned OEM return via authenticated Wi-Fi | **Live GET confirms enabled; earlier return worked** | Compiled and privately paired | Preserve a reviewed return path; no automatic flash |
| Media session / cover / clock / weather / auto-start | Not in installed bridge | **Not part of review-003** | Product backlog below |

### Roadmap milestone A — SHINO // LINK Windows companion (PC only, zero TV firmware changes)

- [ ] Unify existing `companion/metrics_server.py` collector and `companion/push_fsless_metrics.py` sender into a small resident **SHINO // LINK** process, without altering today's bounded Digest telemetry contract. System tray, clear status (Connected/Retrying/PC offline), config outside repo, start on Windows user logon, delayed start and graceful exit; **no administrator rights or auto-install required by default**. Preserve manual CLI fallback and keep private owner credentials only on PC.
- [ ] Continue CPU usage, GPU usage, RAM actual used/total and GPU real temperature, update roughly **every two seconds**, GPU unavailable explicitly marked rather than fake 0°C; collector errors never replace last valid readings. Automatic reconnect with capped backoff, no busy-loop or repeated credential prompts; LAN-private target allowlist and no redirection.
- [ ] Use a **separate bounded music data provider** so music errors never interrupt PC metrics. Preferred initial provider is Windows **Global System Media Transport Controls (GSMTC)** when source applications expose artist/title, duration/position, playback state and optional thumbnail; confirm support per actual source/app. **Alternative selectable options:** Spotify API with owner opt-in and tokens confined to the PC, a compatible local-player adapter, or **media disabled**. Avoid claiming every browser/streaming app exposes a session or artwork.
- [ ] Local PC-only preview for both 240x240 native-screen concept and companion behavior: playing/paused/no title, missing cover, source switch, empty metadata, reconnect and silent/privacy mode.
- [ ] Capture owner choices: **launch on sign-in** [on/off], **media provider** [Windows session(default proposal)/optional Spotify/local/disabled], **media display** [brief track-change overlay (proposal)/permanent music scene/manual only/disabled], **show progress** [yes/no], **notifications** [none/tray only].
- **Acceptance:** default metrics behavior and refresh remain uninterrupted by media, tray or PC power-state simulation; tests are PC-only and use synthetic media/session fixtures. No need to upload a new device image while this milestone develops.

### Roadmap milestone B — 240x240 display scene system (software preview before flashing)

- [ ] Preserve exact **four simultaneously visible measurements** (CPU, GPU, RAM used and real GPU temp), their 90x6 bars, percentage-driven mint/yellow/dark orange/burgundy with hysteresis, correctly unknown/stale state. Never substitute album art for one metric in the permanent monitoring grid.
- [ ] Introduce small **bounded scene state machine** rather than general remote HTML/image/filesystem writer. Screen choices: **PC Health (existing/default)**, **NOW PLAYING** (cover, title, artist, optionally elapsed/total), **CLOCK / OFFLINE** (time only when trustworthy and show sync/age), **WEATHER** (later opt-in city/provider), and extensibility later for code-agent / SHINOBIWAN releases.
- [ ] Design selectable scene policy: **A: four-card always except short 3-8s track-change overlay (initial proposal)**; **B: permanent music scene while playing**; **C: manual scene via authenticated browser/Windows tray**; **D: configurable timer rotation**; **E: music off**. No physical touchscreen/buttons assumed. Source/app playback `pause` must not be confused with PC disconnected.
- [ ] Define explicit **PC-state transitions**: live sample → freshness timeout ~6s → stale/waiting/PC offline; then independent screen policy may switch to clock/offline after a configurable grace period. On reconnect return to PC Health or owner's last selected scene without flashing old CPU/GPU samples. A powered-off PC sends no data: SHINO device is still on only if USB-C has **independent power** or the PC USB port remains powered while off.
- [ ] Clock synchronization: initial time comes from a **valid PC time message only when paired**; running ESP8266 uptime is not a battery-backed real-time clock. After power-loss/offline with no valid sync, show unsynchronized waiting state, **never an invented wall clock**. Alternatives requiring explicit design: periodic PC time push (first choice), local NTP only if SHINO has Internet via home network, or no clock until valid sync; timezone/DST owner-selected and source/last-sync age visible. No embedding an unsupported RTC claim.
- [ ] Native readability: preserve prior V2.2-A owner notes for darker cards and stronger text contrast, compact uppercase `CPU`, `GPU`, `RAM`, `GPU TEMP`; compare native RGB565 fonts and browser render within the **real 240x240** coordinate system. All four cards/bar/color thresholds must survive visual changes.
- **Acceptance:** simulated exact-pixel screenshots for worst-case numerical widths, missing GPU/media/cover, stale data and offline; bounded heap/CPU use, one existing HTTP server, no extra FS writes.

### Roadmap milestone C — artwork and music transport, incremental not raw frame spam

- [ ] PC acquires artwork **only upon source/track/cover change**, detects hash/size, resizes/crops to display target (max real 240x240), converts/compresses **on the PC**. No direct Internet download or Spotify secrets on SmallTV. User selectable **cover mode**: artwork when available / generated tasteful placeholder / text-only (privacy and memory).
- [ ] Avoid naive whole RGB565 frame allocation: **240x240x2 = 115,200 bytes**, beyond observed free device heap (~32k in owner samples). Research bounded transport in segments with strict total bytes, MIME/signature, 1 image in flight, authentication, no generic file writer, no concurrent image flashes, no optional second HTTP server, fixed memory/time caps, CRC/complete-frame switching and interruption handling. Do not silently reuse `/api/v1/bridge/metrics` for image uploads; it accepts bounded numeric telemetry only.
- [ ] Compare **options with actual bench evidence**: PC-preconverted tiled RGB565 with tiny fixed buffers; small compressed JPEG with streaming decoder if memory/flash fit; small palette/quantized image with tiled decoding; **text-only if none meets headroom**. Never make an untested decoder part of review-003 or call an arbitrary 240px uploaded JPG safe.
- [ ] Track progress can be interpolated from session timestamp but never run after source pauses/stops/stales. Bound owner-chosen metadata lengths, support accents only after font proof, clear prior cover on unavailable/privacy source, avoid persistent artwork writes.

### Roadmap milestone D — connectivity and autonomous fallback

- [ ] **Current/working:** SHINO private WPA2 AP (`SHINO-FirstBoot-<chipid>`), ordinary `192.168.4.1`, Windows must join it to send Digest RAM-only metrics. The owner's home Internet may disappear if Windows has only one Wi-Fi radio; do not treat domestic LAN / Internet as existing in review-003.
- [ ] **User-selectable future network mode:** A: keep isolated private AP (simple, existing, no router dependency); B: explicit home-Wi-Fi client STA (same LAN PC+TV, less Internet interruption), with audited credential storage/handling and private LAN access control; C: switchable hybrid AP/STA only after heap/radio/downtime validation. Never copy home Wi-Fi credentials into a public build or auto-enable mode B.
- [ ] PC absent: display no stale metrics as live; show clock only if synchronized, otherwise SHINO offline/standby identity, and optionally dim after user-configurable delay. Product options: always-on status / screen saver / reduced brightness / blank display (while USB powered). Device powered from PC USB may turn off with PC; **no internal battery is assumed**. No wake-on-LAN remote shutdown/start feature promised.
- [ ] Weather is **future optional**, sourced/cached on PC where Internet exists, for user-selected city/provider and visible observation age; the current AP-only ESP has no guaranteed Internet.

### Roadmap milestone E — shipping/verification boundaries, do NOT couple release cycles

- **review-003 V2.1** is strictly the frozen diagnostics candidate. Owner reported 405,712 B, exact owner SHA `3252ba5cd1f85683945d4d9a87ce49118568c0977605debc089267f54d7f3b0e`, pinned source SHA `8cef03012ae4a4864d69cbe20e02f141a36e2d54`. It **does not implement NOW PLAYING, artwork transfer, clock, home-Wi-Fi STA or scene engine**. The owner-private kit stays retained without build-source mutations from this roadmap.
- The **current review-002** post-install authenticated `GET /api/v1/bridge/factory-return` showed `write_enabled:true`, correct OEM image bytes and SHA, `full_flash_backup:false`, `filesystem_layout_verified:false`. Its prior Wi-Fi-only OEM return and stock→V2 Hotfix were owner-observed, but do not prove future two-step success.
- The **possible**, individually consented future Wi-Fi sequence is current V2 → **exact original OEM V9.0.44 app** → verify manufacturer clock/actual `GET /v.json`, stock `GET /update` availability → **new separate decision** for OEM→exact owner-private review-003. No automatic second upload, retries, arbitrary POST to diagnostic routes, or using disposable CI BIN. Before each operation, confirm local file path/exact size/hash, auth pair, power continuity, residual brick risk, and stop on ambiguous staging/boot response. `review-003`'s sanitized manifest specifically says `permission_to_flash=false` and independent checksum evidence before an actual write. The *owner* controls the private local Windows restore helper; roadmap changes do not invoke it.
- Never merge a V2.2 roadmap/product-code branch onto the frozen V2.1 PR head **before the current private image source lock is released**, or pretend a documentation SHA change is the same private BIN. No device contact, OTA, flash, restart, factory-reset, credential display or PR merge is authorized by a roadmap entry.

### Choice register — decisions we will make with owner before V2.2 implementation

| Decision | Alternatives | Current proposed default; not yet approved |
| --- | --- | --- |
| PC collector | single Windows tray service / manual console | Tray with manual CLI fallback |
| Windows start | automatic at login / manual | Automatic, disableable |
| Media source | Windows GSMTC / Spotify PC API / local adapter / none | Windows GSMTC first; verify app compatibility |
| Music scene | brief track-change overlay / persistent while playing / manual / never | Brief overlay, leave four-card scene intact |
| Album art | streaming compressed/tiled / text-only / placeholder | Implement only after measured memory/security gate |
| No-PC screen | clock if synchronized / logo offline / dim/blank | Synced clock else SHINO offline; owner brightness option |
| Wi-Fi topology | existing private AP / home STA / tested hybrid | Keep current AP until separate review; STA as optional evolution |
| Clock source | authenticated PC time / NTP with reviewed STA / no clock | PC time, explicit unsynchronized fallback |
| Weather | off / opt-in city and PC provider | Off initially |
| Visual polish | native font and contrast trials / current fixed V2 look | Preview-first, owner visual sign-off |

---
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
- [ ] Shorten the four metric card labels consistently in **native LCD and Web UI**: `CPU usage` → **CPU**, `GPU usage` → **GPU**, `RAM in use` → **RAM**, `GPU temperature` → **GPU TEMP**. Preserve the four measurements, engineering values, freshness, and bar normalization; uppercase compact labels are the owner-approved display wording. Free the previously wrapped temperature header for value legibility. Do not implement as part of current OTA PR safety work.
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
