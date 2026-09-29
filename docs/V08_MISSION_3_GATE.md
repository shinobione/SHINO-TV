# SHINO // TV V0.8 Mission 3 — review gate

**29 September 2026. GO for isolated protocol/full-link/source research. HOLD for runtime bridge qualification. BLOCKED for production media authentication, active receiver and device operations.** Began at exact clean Mission 2 head `273b386070802cc6aba0a16c8cd8b5a6dc7abf00`, on separate `feature/shino-tv-v08-full-bridge-qualification`. Draft PRs #29, #30 and #31 are preserved. A new Draft PR is stacked on Mission 2; its final SHA and exact-head CI are reported in delivery. CI passing is review evidence only.

## Decisions and deliverables

- [Protocol decision](V08_MISSION_3_PROTOCOL_DECISION.md): explicitly versioned host profile 1.1, RFC 9651 parser with RFC 8941 field types, normalized authority, duplicate preservation, HTTP/SF whitespace, fixed parameter/coverage policy and retained public-vector hashes. No native verifier or production auth.
- [Full bridge report](V08_MISSION_3_FULL_BRIDGE_REPORT.md): isolated unstarted full bridge baseline/overlay images, real handler source execution with real JSON and named seams, pinned parser execution, Basic fallback characterization and composition limitations.
- [Resource report](V08_MISSION_3_RESOURCE_REPORT.md): equivalent native links (+828 text/+152 BSS/+832 BIN), one-server symbol evidence, compiler frame accounting, phase budgets and explicit hardware exclusions.
- New host tests/tooling and CI job; original firmware, V0.5 historical evidence, tray and OEM implementation remain unchanged.

## Actual local checks

| Check | Actual result | Evidence class |
|---|---|---|
| Full bridge baseline and experiment | **2/2 native compile/link PASS** | Pinned Xtensa compiler, no image execution or installation. |
| Extended actual pinned owner/parser | **90/90 assertions PASS** | Source execution under MSVC with fake network/String/dispatch. Includes all original Mission 2's 37 checks unchanged. |
| Actual bridge/metrics/browser source, real ArduinoJson | **35/35 PASS** default; **38/38 PASS** conditional OEM delegation | Entire original source with synthetic auth/dispatch/ticks and inert hardware/OEM seams. |
| Pinned Basic auth branch | **5/5 PASS** | Source-executed fallback with host encoding/comparison seams; no Digest crypto execution. |
| New profile 1.1 crypto/SF tests | **8/8 PASS** | External pinned SF implementation, real host P-256; synthetic stream/challenges. |
| Original public crypto vectors | **8/8 PASS** | Original fixtures/verifier/tests unchanged. |
| Simulator/browser/native UI Node suites | **20/20 PASS** | Host renderer/UI; includes five-second overlay tests. |
| Full companion Python discovery | **134 run: 130 PASS, 4 SKIPPED** | Historical V0.5/V0.6 and V0.7 models unchanged. All eight V0.5 `test_gap_*` remain present. |
| Full tools Python discovery on Windows | **291 run: 182 PASS, 11 FAIL, 1 ERROR, 97 SKIPPED** | Eleven old checks require absent GNU C++ compiler/preprocessor; one source-symlink test gets Windows privilege error. No failure relabeled PASS. |
| ESP runtime TCP/heap/stack/CPU/WDT/LCD/browser/OEM writer | **NOT RUN** | Excluded by scope. Production authentication and device ingress not implemented. |

The CI workflow runs the new profile tests, actual modified parser path, Basic branch, full native link pair, actual bridge source with real ArduinoJson, and resource/symbol accounting in addition to all existing jobs. Exact-head run outcomes must be verified after the final commit; a prior code-commit run is not substituted for that evidence.

## Gates and unresolved decisions

| Gate | Decision and supporting limit |
|---|---|
| Profile 1.1 decision/public-vector retention, bounded deny-all source path, full equivalent links and handler research | **GO for review only.** Scope-specific local evidence above. |
| Independent protocol/security approval | **HOLD.** External parser use and internal review do not certify RFC interoperability/security. Require additional differential/published vectors, production authority/transport policy and reviewer approval. |
| Native legacy and resource runtime qualification | **HOLD.** Parser and handler labs are separate; real WebServer dispatch/response/TCP and heap/stack/WDT/display remain unexecuted. Accept or revise global 130-byte cap and conservative namespace over-reservation. Stock legacy headers/body are still unbounded and may block the loop. |
| Native Gate 1/2 or active media route | **BLOCKED.** No native SF/ECDSA verifier, approved key/revocation lifecycle, unpredictable epoch/challenge issuance or measured phase reserve exists. Media deny-all is the only experiment behavior. |
| Production credentials/provisioning, live sender, OTA/install, device contact | **BLOCKED / outside scope.** No authorization or implementation supplied by this mission. Default production firmware behavior, installed V2.1 and frozen PR #20 remain untouched. |

Unresolved choices include final authority and supported scheme/transport; independent profile review and native parser selection; key custody/enrollment/revocation; fresh epoch entropy/collision failure and challenge transport/rate/slot policy; strict late-byte closure semantics under TCP; supported legacy line cap and namespace over-reservation; end-to-end unchanged-handler dispatch parity; and measured target heap/contiguous block/stack/CPU/watchdog/display limits with an engineering reserve.

**Most defensible next step:** independent review of profile 1.1 and the pinned ownership seam, then a separately authorized unconnected end-to-end socket/dispatch lab. Runtime/hardware integration and route activation need separate gates and instructions. **Stop after Mission 3.**
