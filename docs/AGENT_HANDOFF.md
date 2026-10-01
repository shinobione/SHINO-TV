# SHINO // TV — Agent handoff / operational source of truth
Last product contract update: **2026-10-01**. This document is primarily for ChatGPT, Codex and successor coding agents, not a short end-user marketing summary. It deliberately points to historical records instead of deleting them. Always check live branch HEAD and exact CI again at execution time.

**2 October owner preparation gate:** existing PR #41 continues from accepted
`ce718f0`. Actual private active P0+P1 candidate is 464544 B, SHA-256
`31e3f225744bd806df3302dbf3355770a313f8b71f65b33fd6e2f431449b0be5`;
matching retained credentials/media identity and OEM/V2.1/M8 rollback are locally
verified outside Git. New owner profile adds read-only numeric runtime/LCD counters
to existing authenticated status, without exposing qualification write controls
on LAN. [Exact image, lifetime review, abort limits and physical sequence](home-lan/OWNER_INSTALL_GATE.md).
Fresh GET-only current-M8 preflight: 446944 B, boot 2962927510, actual 4 MiB,
exact OEM capability enabled, native OTA absent. No upload/reboot/network switch or
persistent credential write. **STOP at new exact-image/chain owner approval.**
Installation consent must name both M8→OEM and OEM→exact P1 hops; first credential
write needs a later separate confirmation after boot/display/AP/telemetry checks.
P1 physical qualification remains NOT RUN, R3 PARTIAL/R10 BLOCKED unchanged.

**P1 offline implementation update:** owner requires persistent Wi-Fi, configured
once locally and retained across normal failures/boots. Follow-on branch
`codex/shino-tv-p1-home-lan` starts from verified PR #40 `a3d9fdb`; older Home
Wi-Fi "unimplemented" rows below are prior-state provenance. Opt-in active
FirstBoot P1 now loads reviewed SDK parameters (`0x3FD000–0x400000`), writes only
on Digest/AP/one-use-intent protected Change/Forget with readback, reconnects and
retains secure AP fallback. LINK supports live local IP retargeting. Three native
guarded graphs compile; P1 versus P0 adds 11,136 BIN / 1,180 static DRAM bytes.
183 shared assertions, 34 target-handler loopback checks and 33 real signed
receiver/scene cases at each AP/LAN authority pass locally. See
[P1 contract, exact local password procedure, resource evidence and HOLD gates](home-lan/README.md).
**P1 device/release remains HOLD:** persistence under real power loss, native
heap/block/stack, radio/DHCP and OEM return after saved-config writes NOT RUN.
No owner-device contact/install/provision/migration; current M8 remains installed.
Recheck final branch SHA and exact-head CI; host SDK/radio models are not DEVICE PASS.

**V2.2 implementation update (offline only):** PR #40 now has exclusive scenes,
160px integer artwork (128px alternative also built/tested), clipped title/artist
marquees, explicit provider leases and a disabled-by-default paused timeout seam.
33 actual native-receiver host cases pass at both sizes; the final linked delta
versus the previous PR #40 graph is +1,080 static DRAM / +5,456 BIN bytes.
See [current implementation and eight 240×240 previews](artwork-pilot/README.md)
and active roadmap P0. The older mixed-screen row below is retained prior-proof
provenance, superseded for current UI implementation. Physical UI NOT RUN;
installed M8 candidate and PR #39 remain unchanged. Recheck exact-head CI.

## Latest engineering update (supersedes older PR #40 pilot snapshot below)

> **LATEST VERIFIED P0 STATUS — 1 October 2026, PR #40 `332eaa48580de60eba06faaa6dbb67c301b2b1be`: OFFLINE GO / PHYSICAL LCD HOLD.** The mutually exclusive `IDLE`, `PLAYING`, `PAUSED`, `NO ARTWORK`, `OFFLINE` C++ scene engine, 160×160 5× cover upscale and bounded title/artist scrolling are implemented. Actual eight independently produced 240×240 renderer previews. 33 host scenarios pass for both 128 and 160px artwork, ASan/UBSan pass, exact-head push and PR CI each 12/12. Public paired build delta against preceding PR #40 pilot: **+5,456 padded BIN bytes, +1,080 static DRAM bytes, 448-byte row buffer, zero observed renderer dynamic heap; Receiver Begin compiler frame +64 B.** No live native LCD timing/heap/stack has been measured, providers for clock and weather do not exist yet, and no device flash/reboot has occurred. The IDLE concept-city background is not a requirement to store or render large native art without resource proof. `GPU TEMP` bar remains neutral until a documented scale is approved. The next implementation priority is **P1 secure normal-home-LAN STA with protected private-AP fallback**, followed by P2 integrated signed SHINO→SHINO OTA. Do not conflate OFFLINE GO with physical approval.

## A. Quick state — differentiate firmware, experiments and future goals

| Axis | Verified current engineering evidence | Gap / prohibition |
| --- | --- | --- |
| Single physical Ultra | Owner-approved Mission 8 private candidate **446,944 B**, SHA-256 `269fcf2be7e61b4f581f892f36c519cca5ebf1ef41759d9923d9df90aad682fa` installed through verified OEM round-trip; private AP `192.168.4.1`; four PC metrics update via SHINO // LINK Windows tray. | Not yet home-router STA. No hardware recovery if no application boots. Do not expose private material. |
| Mission 8 / PR #39 | Frozen validated `9fce7137f9fadd83678887442bf91cf60ea86b2e`, Draft. Actual current candidate 32×32 RGB565LE Commit in 3.672 s post-Begin and replacement in 4.016 s; image Abort and signed wrong-CRC Gate2 rejection PASS; actual ArduinoJson temporary peak **1,984/2,048 B**; persistent image **2,048 B**. Actual crypto StackThunk secondary max **2,708/6,200 B**; no observed reset/canary/allocation failure in reported windows. | Receiver owns **inert RAM**; those tests do not show physical LCD artwork. Overall M8 HOLD for optional 48 and separately 6-second strict long-term telemetry (historical recovered 7.266 s gap). R3 PARTIAL; R10 BLOCKED. |
| Optional 48×48 | Old candidate managed one nine-tile transfer; optimized current candidate has not executed it. Current conservative projection **10.142 s against unchanged 8 s**; replacement not proven on a retained 4,608 B image state. | Do not make 48 mandatory for first music product; no blind 48 hardware attempt or deadline weakening. |
| Artwork LCD / PR #40 | `codex/shino-tv-32-artwork-display-pilot`, based on PR #39. Offline actual native ST7789/receiver renderer passes 16 host scenarios including signed receiver and cancellation; scanline **192 B**; cover enlarged **32→96 px**; **+520 B static DRAM** and **+96 B Receiver Begin frame**; no added renderer heap/full-screen framebuffer. New renderer runs cooperatively after HTTP owner with `networkReady` guard. Latest report says exact-head 12/12 in both CI runs; recheck latest SHA because subsequent docs commits may have occurred. | PR #40's current **music + all 4 cards in one scene** is a functional proof, explicitly REJECTED as target UX. The pilot binaries are guarded/offline and not installable owner builds. Physical LCD cover/latency/high-water **NOT RUN**. |
| Native OTA | `GET /api/v1/bridge/ota/capabilities` is READ-ONLY; reports `native_ota_writer_compiled=false`, `native_ota_upload_route_registered=false`. Signed-SHINO / signed+exact-OEM contracts, payload geometry, one-use intent, precommit gates and Core 3.1.2 review exist as host/compile-only research. | Current field sequence is SHINO→pinned OEM V9.0.44→SHINO. Native SHINO→SHINO update is NOT shipped; no native uploader route and no independent brick recovery. Do not claim otherwise. |
| Home Wi-Fi | Active FS-less FirstBoot bridge uses private SHINO AP, while OEM can use household STA. | Home-STA onboarding/secure credential storage/recovery/AP fallback and authenticated LAN API are a high-priority **unimplemented** deliverable. |
| Music PC side | SHINO // LINK V0.1 live telemetry; V0.2 GSMTC monitor and V0.3–V0.4 preview experimental PC-side. | Permanent authenticated production cover sender not yet connected to actual display/scene engine. |
| Time and weather | Product visual reference shows clock, date, city/weather. | Actual wall-clock synchronization, freshness/timezone/DST, provider/city/caching and offline fallback require implementation. Concept data are illustrative, never live measurements. |

## B. Requirement keywords: MUST / MUST NOT / OPEN

**MUST:** all individual LCD views exactly `240×240` (1:1); square cover without stretch; IDLE screen uses prominent time (only when genuinely synced), optional fresh/cached weather and FOUR metric cards simultaneously in a 2×2 layout; adaptive bar colours; received media retained securely in RAM, no partial tiles painted; PLAYING screen only art/title/artist/progress/status (no metric cards); PAUSED/music-without-cover likewise never shows metric cards. Keep accepting metric POSTs invisibly during music. Long title scrolling must be slow, bounded, horizontally clipped with an initial pause, endpoint dwell/loop and reset on track change. Use bounded font glyph / UTF-8 fallback; do not shrink titles to fit.

**MUST NOT:** reuse PR #40 mixed screen as product approval; display clock if not synced, stale telemetry as fresh, fake weather, empty GPU temp as 0; add mini-graphs above metrics; enlarge 6 s telemetry TTL or 8 s signed-media transaction deadline merely to pass; share production credentials/signing keys; merge/flash by inference; promise that OEM app BIN is full-flash backup or can rescue no-boot failure; interpret source/CI builds as device tests.

**OPEN decisions, present to owner only when needed:** precise PAUSED→IDLE timeout or immediate transition; weather provider/city (Lezignan displayed as *concept example*, not approved hardcoded setting), normalization of GPU temperature and RAM bars, exact marquee speed/dwell and Unicode fallback, brightness/night mode, clock sync PC vs NTP once STA exists, home STA vs AP fallback timeout, any manual scene override.

## C. State machine and visibility (product intent)

| Event or state | Visible scene | 4 metrics painted? | Receiver/clock consideration |
| --- | --- | --- | --- |
| Boot before valid time and PC contact | explicit SHINO waiting/offline | Unknown cards only if meaningful | No made-up clock; AP or STA recovery accessible |
| NO_SESSION / STOPPED with validated time | IDLE | YES, all four as valid/stale/unknown | Grace/debounce owner choice |
| PLAYING + committed 32px cover | PLAYING | NO | Square cover and clipped title, progress if reliable |
| PLAYING without artwork, or incoming valid Begin before Commit | NO ARTWORK / music fallback | NO | Existing receiver intentionally drops prior cover at accepted Begin; invalid metadata leaves existing image unchanged. Never show partially staged cover. |
| PAUSED | PAUSED artwork/placeholder | NO | Position freezes; exact timeout to IDLE is OPEN |
| Playback ended / source lost after bounded grace | IDLE / offline | YES if known, otherwise unknown | Keep time freshness independent |
| Music while telemetry POST continues | stays music | NO | Still accept/age all numeric values, no false firmware network change |
| No PC / router / Internet | clock if genuinely synchronized, else offline | Only actual safe last-valid state with explicit age | Weather cache age shown or hidden if unknown |

## D. Layout/source asset contract

`docs/design-reference/` contains **four canonical vector references** with root `width="240" height="240" viewBox="0 0 240 240"` plus a clipped marquee state. Those are mood/position **targets**, not production binary pixel evidence. Render with an SVG rasterizer at EXACT 240×240 to create reference PNGs and assert dimensions; then produce independent actual C++ software-LCD previews from the pinned 6×8 GFX font and ST7789 driver. Compare readability and geometry. No rectangular 16:9 panels with "240×240" labels. Source high-level original ChatGPT illustrations were 1254×1254 concepts, not proof of native 240px legibility.

Preferred layout baseline, to be reviewed with physical readability:
- IDLE top city/clock/weather region `x=4..235, y=4..117`. Clock large; date/weather read only if valid. Four cards: `(8,124,110,50), (122,124,110,50), (8,181,110,50), (122,181,110,50)`. No top-line curves. CPU 37.5% must display **yellow** according to the owner's 20–50 threshold; older imagery using green at 37% is illustrative and wrong.
- PLAYING/PAUSED/NO ARTWORK: album/placeholder **square** `(41,10,158,158)`; mode/title/artist/status and optional elapsed/total in remaining `y=170..236`. Minimum rendered metadata must be verified with real GFX font, clipped title line and bounded slow marquee. Small 32×32 RGB565 cover may enlarge by nearest-neighbour without new 240×240 frame allocation. No 4 cards anywhere in music scene.
- Proposed bar palette is GREEN [0,20), YELLOW [20,50), DARK_ORANGE [50,80), BURGUNDY [80,100]; exact inclusive boundaries and hysteresis must be consistent between native and PC preview. RAM percent = used/valid total; GPU temp requires an *explicit reviewed reference scale* before applying 0–100 colour thresholds; until agreed label and treat as informational rather than invented percent.

## E. Current native contracts that future edits must preserve

- Pinned ESP8266 Arduino Core 3.1.2 and exact private OEM application hash; network ingress bounds before body, ECDSA P256 on isolated 6,200 B StackThunk, transaction replay/ownership, signature and Content-Digest/Gate2 CRC/SHA validation. No new generic FS/updater surface.
- M8 RAM receiver `DisplaySink` moves a complete staging image only after signed Commit. Legacy source intentionally releases previous committed image on valid Begin; ensure mode fallback matches that contract or separately review an ownership/memory-safe redesign. Renderer borrows image during one cooperative main-loop slice only; cannot hold pointer across owner mutation; no LCD draw inside ingress callback. Pilot 192 B line buffer, 2,048 B temporary metadata arena, zero renderer dynamic heap.
- Preserve numeric schema and normal LINK sender cadence (~2 s), **six-second freshness TTL**; current qualified 32 transfer/replace and OEM recovery. Distinguish historical PC Digest observer failures from native server failures; one 7.266 s self-recovered sender gap remains strict-continuity HOLD.
- Four metrics always exist in state/backend, but paint them ONLY in IDLE. Source `firmware/include/display/ArtworkPilot.h`, `experiments/artwork_pilot/native/ArtworkAdapter.inc`, `firmware/src/boot/FirstBootBridge.cpp`, `firmware/src/boot/FslessMetrics.cpp`, actual display manager and `companion/shino_link.py` must be inspected before edits.
- Source docs: `docs/artwork-pilot/README.md` for as-built offline mixed pilot (not final UX), `docs/V08_MISSION_8_GATE.md` for owner physical proof, `docs/V21_NATIVE_OTA_MANAGER_SAFETY_GATE.md` for OTA barriers, `docs/V21_WIFI_ONLY_RETURN_CHAIN_AUDIT.md` for application-only OEM return.

## F. Delivery dependencies and tests (the roadmap order)

1. **P0 UI:** restructure PR #40's tested renderer into mutually exclusive scenes; marquee; square scene reference proof; deterministic host tests for new track, pause, unavailable cover, Abort/expiry, metadata rejection, stale LINK, missing clock/weather, long UTF-8 names, no mixed card painting. Before physical installation independently measure linked BIN/DRAM/stack and rendering slices. Keep PR #39 untouched.
2. **P1 normal LAN:** audit active AP-only FirstBoot, explicit secure STA onboarding (no stock FS autoformat/unsafe EEPROM shortcut), AP fallback and no-lockout transitions, DHCP/address discovery, PC target updates, Digest/origin/host/auth review on both interfaces, tests for router loss and reconnection. Avoid assumptions that `192.168.4.1` can be globally replaced. No routine device write without approved exact owner build.
3. **P2 genuine signed native OTA:** integrate reviewed bound/one-use privileged request before unbounded POST body, stream signed SHINO to staging, pinned trusted owner public key, precise image/layout/transport length, safe Updater semantics and error/power interruption analysis; preserve separate **signed AND pinned raw OEM** return. Core's global signature mode can skip legacy OEM MD5 check, so do not simply enable `installSignature` alongside old OEM route. No claimed resume/atomic guarantee absent evidence. An OEM-assisted one-time bootstrap of self-updater might still be needed.
4. **P3 physical platform gate:** agree scope, verify exact local candidate hashes/boot/recovery and owner LCD, obtain fresh approval for any firmware change, test STA+AP recovery and safe native OTA with actually measured heap/block/stack. Single device with NO UART rescue: stop on regressions.
5. **P4 music end-to-end:** GSMTC input opt-in, metadata bounded, cover change only, PC-crop to 32×32 RGB565LE, signed private media sender separate from numeric telemetry; verify actual LCD art and marquee plus playback transitions. Unsupported players and no cover get deterministic fallback, never promises Spotify direct without review.
6. **P5 clock/weather:** authenticated PC time first or reviewed NTP on STA, timezone/DST/age, configurable weather city/provider freshness cache, independent-power caveat (USB PC off may remove power), privacy/brightness/night controls.
7. **P6 optional:** 48×48 if demonstrated timing and same-state 4,608 B retained image memory; longer strict telemetry reliability; R3 freshness persistence and R10 production trust provisioning as release gates; future widgets.

## G. Agent execution protocol / evidence ledger

- Before coding, retrieve exact PR #40 current HEAD and compare to PR #39 baseline. Never overwrite a newer concurrent Codex commit; fast-forward or stop and reconcile. This documentation commit may have moved the head beyond the last functional CI. Re-run CI on the actual final head.
- Choose one bounded milestone and output real changed files, tests, resource delta and visual preview. Do not restart multi-day Missions 1–8 or propose yet another audit as a deliverable when code can be implemented offline.
- Label each result one of: SOURCE-INSPECTED, HOST-PASS, CI-PASS (with SHA), DEVICE-PASS (with boot/PID/evidence), EXPERIMENTAL, HOLD, BLOCKED, NOT-RUN. Do not promote across categories.
- An offline design or simulator never authorizes field OTA. Preserve all owner-private keys/binaries outside Git, exact hashed factory return, no automatic merge, no production sender/OTA activation, no unsafe debugging endpoints.
- A complete handoff states: exact head/branch and CI, what changed, what is installed (if physically known), image dimensions, measured FLASH/DRAM/heap/stack if relevant, tests, known deficiencies, next bounded action, explicit owner decisions still needed.

## H. Canonical pointers / historical record integrity

- `docs/ROADMAP.md`: current product contract + complete unabridged 28 September historical roadmap.
- `docs/design-reference/README.md`: mockup files and coordinates.
- PR #20 (`feature/v21-native-ota-gated`): OTA safety exploration only, no signed writer.
- PR #21–26: Windows companion, media experiments and initial scene plans.
- PR #27–39: security, bounded HTTP, physically proven M8 32 receiver.
- PR #40: offline LCD artwork pilot (as-built mixed screen, to be refactored).
- `docs/artwork-pilot/README.md`: exact current renderer, 16 scenarios/33,737 host checks, 192 B scanline, +520 B static RAM.
- `docs/V08_MISSION_8_GATE.md` and `docs/V08_MISSION_8R_STACK_REMEDIATION.md`: M8 physical measurements and conditional blockers.
- `docs/V21_NATIVE_OTA_MANAGER_SAFETY_GATE.md`: read-only status, signer/Updater conflict and unshipped writer.
- `docs/ONE_DEVICE_WIFI_PATH.md` and `docs/V21_WIFI_ONLY_RETURN_CHAIN_AUDIT.md`: historically observed OEM path, not full-flash backup.

If requirements collide, preserve the highest-authority newer owner instruction, explicitly document the conflict, and ask only for the essential missing owner choice.
