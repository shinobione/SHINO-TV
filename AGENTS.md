# SHINO // TV — Instructions for coding agents

This file is binding context for AI coding/review agents working in this repository. **Read `docs/PROJECT_STATE.md` (checkpoint B5.4 postboot du 19 octobre), `docs/SHINO_TV_LINK_UNIFICATION.md`, `docs/AGENT_HANDOFF.md` et le début de `docs/ROADMAP.md` AVANT tout travail.** The dated historical appendix is provenance, not current device status. Read `docs/design-reference/README.md` and its actual 240×240 square SVGs for screen requirements.

## Priority of truth
1. Explicit new owner decision in the current conversation (if available); record it in the active roadmap before implementing.
2. État physique daté / réconciliation des branches dans `docs/PROJECT_STATE.md` et `docs/SHINO_TV_LINK_UNIFICATION.md` ; contrat produit dans `docs/ROADMAP.md`, garanties dans `docs/AGENT_HANDOFF.md`.
3. Exact latest PR/commit and actual tests, separately identifying host/CI vs physical owner-unit evidence.
4. Historical docs, prior PRs and old visual mockups for provenance only. Never silently reclassify HOST PASS as DEVICE PASS.

## Immutable safety/product constraints
- One GeekMagic SmallTV-Ultra, **240×240 pixels; every individual screen 1:1**. USB-C power only; no UART/JTAG/solder/spare board as ordinary dependency. No physical flash, OEM return, credential provision, branch merge or production activation without separate explicit owner approval for exact operation and file/hash.
- **Current 19 October physical truth:** Codex reports authenticated postboot identity matching the privately installed **P0+Updater512+B5.4** (issue #81); four CPU/GPU/RAM/GPU temp cards and date/time observed by owner. Keep Digest, SHINO LINK, HMAC, 4m2m, clock, LittleFS and existing recovery safeguards. The older Mission 8/9 transport evidence remains historical and does not certify the B5.4 media path. One B5.4 OTA occurred, **the one-shot authorization is consumed**; no further OTA is authorized.
- **Modes are exclusive**: IDLE = clock/weather (when valid) + four metric cards; PLAYING / PAUSED / NO ARTWORK = music-only, NO metric cards displayed. Keep ingesting metrics in background. Source screenshot of PR #40 mixing music and metrics is an engineering proof, NOT final UX acceptance.
- Preserve dynamic percentage-bar mapping: 0–20 green, 20–50 yellow, 50–80 dark orange, 80–100 burgundy (document boundary/hysteresis); RAM and temperature must use an explicit justified normalization or honest unknown. Never fabricate unavailable measurements/weather/time.
- Square album cover, slow clipped marquee for overflowing title (and artist if needed), no text squashing, no decorative metric micro-curves. UI references in `docs/design-reference/` are **vector specifications at exactly 240×240**, not claims of native ST7789 rendering.
- Preserve the **observed home-LAN STA** link and secure AP fallback/reconnection goals, without asserting full fallback qualification. A single native OTA to private B5.4 was reported with postboot identity confirmation; **no new OTA is allowed**. Preserve staging/eboot/LittleFS/SDK boundaries, historical `STOP_UNKNOWN_NO_RETRY`, receipts and `.attempt` reservations, and audit Updater signing/MD5 before any future approved candidate.
- Prevent excessive changes/PR churn: implement a concrete bounded milestone with tests and resource numbers. Stop on reset, unsafe heap/stack, corruption or unavailable recovery. Report precisely what passed, what remains HOLD and where owner input is needed.

## Working links
- Source of record: `docs/ROADMAP.md` (active section + full original historical appendix).
- Detailed machine-actionable transfer: `docs/AGENT_HANDOFF.md`.
- Canonical scene dimensions and reference files: `docs/design-reference/README.md`.
- Offline PR #40 implementation and known non-final mixed-mode fixture: `docs/artwork-pilot/README.md`.
- Physical receiver/gates PR #39: `docs/V08_MISSION_8_GATE.md`, `docs/V08_MISSION_8R_STACK_REMEDIATION.md`.
- Native OTA research: `docs/V21_NATIVE_OTA_MANAGER_SAFETY_GATE.md`; previous return evidence: `docs/V21_WIFI_ONLY_RETURN_CHAIN_AUDIT.md`.

**Continue software convergence only on the isolated Draft PR #85 M3-R; do not merge #72/#73/#76/#82/#84 or alter Codex/private worktrees. The active device is B5.4 by issue #81 evidence, while M3-R remains HOST/Xtensa INERT and the Windows inspector is NOT installed.**

**Do not rewrite the validated past to make a new milestone look complete.** Commit focused code/docs on the correct existing branch, run matching exact-head CI, and leave Draft PRs unmerged.
