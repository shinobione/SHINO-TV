# SHINO // TV — Instructions for coding agents

This file is binding context for AI coding/review agents working in this repository. **Read `docs/AGENT_HANDOFF.md` and the active (1 October) section of `docs/ROADMAP.md` first.** The dated historical appendix is provenance, not current device status. Read `docs/design-reference/README.md` and its actual 240×240 square SVGs for screen requirements.

## Priority of truth
1. Explicit new owner decision in the current conversation (if available); record it in the active roadmap before implementing.
2. Active product contract in `docs/ROADMAP.md` and state/gates in `docs/AGENT_HANDOFF.md`.
3. Exact latest PR/commit and actual tests, separately identifying host/CI vs physical owner-unit evidence.
4. Historical docs, prior PRs and old visual mockups for provenance only. Never silently reclassify HOST PASS as DEVICE PASS.

## Immutable safety/product constraints
- One GeekMagic SmallTV-Ultra, **240×240 pixels; every individual screen 1:1**. USB-C power only; no UART/JTAG/solder/spare board as ordinary dependency. No physical flash, OEM return, credential provision, branch merge or production activation without separate explicit owner approval for exact operation and file/hash.
- Preserve running signed media transport (Mission 8 PR #39, 32×32 current candidate physically PASS), existing four CPU/GPU/RAM/GPU TEMP values, Digest authentication, 6-second telemetry TTL, 8-second native media transaction deadline, and OEM application-only return. R3 PARTIAL and R10 BLOCKED; native SHINO→SHINO OTA NOT active.
- **Modes are exclusive**: IDLE = clock/weather (when valid) + four metric cards; PLAYING / PAUSED / NO ARTWORK = music-only, NO metric cards displayed. Keep ingesting metrics in background. Source screenshot of PR #40 mixing music and metrics is an engineering proof, NOT final UX acceptance.
- Preserve dynamic percentage-bar mapping: 0–20 green, 20–50 yellow, 50–80 dark orange, 80–100 burgundy (document boundary/hysteresis); RAM and temperature must use an explicit justified normalization or honest unknown. Never fabricate unavailable measurements/weather/time.
- Square album cover, slow clipped marquee for overflowing title (and artist if needed), no text squashing, no decorative metric micro-curves. UI references in `docs/design-reference/` are **vector specifications at exactly 240×240**, not claims of native ST7789 rendering.
- Target normal **home-LAN STA** with secure AP fallback (not today's AP-only `192.168.4.1`). Target signed native SHINO→SHINO OTA without repeated OEM downgrade; today the OTA route is read-only/compile-only; preserve exact signed OEM escape and review Updater global signing/MD5 interaction.
- Prevent excessive changes/PR churn: implement a concrete bounded milestone with tests and resource numbers. Stop on reset, unsafe heap/stack, corruption or unavailable recovery. Report precisely what passed, what remains HOLD and where owner input is needed.

## Working links
- Source of record: `docs/ROADMAP.md` (active section + full original historical appendix).
- Detailed machine-actionable transfer: `docs/AGENT_HANDOFF.md`.
- Canonical scene dimensions and reference files: `docs/design-reference/README.md`.
- Offline PR #40 implementation and known non-final mixed-mode fixture: `docs/artwork-pilot/README.md`.
- Physical receiver/gates PR #39: `docs/V08_MISSION_8_GATE.md`, `docs/V08_MISSION_8R_STACK_REMEDIATION.md`.
- Native OTA research: `docs/V21_NATIVE_OTA_MANAGER_SAFETY_GATE.md`; previous return evidence: `docs/V21_WIFI_ONLY_RETURN_CHAIN_AUDIT.md`.

**Do not rewrite the validated past to make a new milestone look complete.** Commit focused code/docs on the correct existing branch, run matching exact-head CI, and leave Draft PRs unmerged.
