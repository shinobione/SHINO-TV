# SHINO // TV V0.8 Mission 2 — review gate

**Base:** exact reviewed Mission 1 commit `c5cac0ab87f0ade5bf1e2bd62934b61cedc1a4c5` on the separate `feature/shino-tv-v08-single-owner-preparse` branch. Draft PRs #29 and #30 are untouched. This gate covers source research, an isolated opt-in WebServer overlay, a compile/link-only sketch and offline source execution. It is not authorization to merge, activate or install a receiver.

## Scope and design verdict

The complete V0.7 and V0.8 gates, V0.8 HTTP carriage and crypto profile, V0.7 pinned parser evidence, and V0.8 resource budget were reviewed before the overlay. [Internal protocol review](V08_MISSION_2_PROTOCOL_REVIEW.md) found **no fundamental ownership contradiction** for a deny-all single-owner first-line seam. It found unresolved structured-field conformance and version choice (RFC 8941 is now obsoleted by RFC 9651), `@authority` canonicalization, signed-digest versus received-body proof, epoch/challenge issuance and production key lifecycle. No active authentication design is approved.

The [isolated candidate](../tools/v08_native_overlay.py) fingerprints the Core 3.1.2 source, modifies only a generated copy, retains one `_server.accept()` and `_currentClient`, caps a request line before any new `String`, reads at most 64 line bytes per poll, uses a wrap-safe absolute deadline, reserves once-decoded media candidates, and hands the exact first line to the stock parser at its original unread header position. All media candidates close; no route or verifier exists. Legacy request-line length acceptance is narrowed to 130 bytes. Legacy headers and body retain their original parser semantics and risks. The production `firmware/` tree, V0.5 codec and tests, numeric metrics, browser session logic, conditional OEM return and display code have no diff.

## Actual local validation

| Check | Result | Evidence boundary |
|---|---|---|
| Pinned modified source under MSVC fake client/server | **37/37 assertions PASS** | Extracted transformed `handleClient`, preparse and parser source; simulated network, not a device. |
| Baseline and opt-in candidate PlatformIO compile/link | **2/2 PASS**, Core 3.1.2, Xtensa GCC 10.3.0 | Isolated no-listener sketch. [Resource report](V08_MISSION_2_BUILD_RESOURCE_REPORT.md): +788 ELF text, +152 ELF BSS, +800 BIN bytes, +172 PlatformIO reported RAM. |
| V0.7 pinned-source C++ lab | **4/4 unittest cases PASS** | Historical source/execution and synthetic handoff retained. |
| V0.5 media-wire host emulation | **11/11 PASS** in focused file | Existing tests unchanged; not evidence of native media correction. |
| V0.5 transfer/security characterizations | **29/29 PASS**, including all **eight `test_gap_*`** defect characterizations | Historical defects remain visible and unfixed in V0.5. |
| V0.8 fixed public P-256 host vectors | **8/8 PASS** | Node host crypto, no native verifier or production key. |
| Full `tools` discovery on Windows | **291 run: 182 PASS, 11 FAIL, 1 ERROR, 97 SKIPPED.** Eleven older tests require `g++`/preprocessor absent from PATH; one symlink test errors with Windows `WinError 1314`. | These failures are environmental and pre-existing; they are not relabeled PASS. |
| Full `companion` discovery | **134 run: 130 PASS, 4 SKIPPED.** | Existing V0.5/V0.6 characterizations remain intact. |
| Physical TCP, SmallTV, heap, stack, WDT, display and OTA | **NOT RUN** | Excluded by Mission 2. |

The source-executed cases cover the normal dashboard/metrics URI path, exact unread-byte handoff, malformed and overlong lines, percent-encoded namespace reservation, partial/disconnected clients, a slow client versus a queued client, wrap-safe timeout, keep-alive pipeline and terminal deny behavior. Authentication fallback and OEM routes were characterized from unchanged `FirstBootBridge.cpp` source and prior tests; they were not driven by an ESP8266 browser or OEM upload. Four metric values and their freshness are not manipulated by the isolated candidate. Prior host metric/overlay tests remain historical evidence, not a new device result.

## Required next decisions and gates

| Gate | Decision |
|---|---|
| Isolated preparse, source execution and compile/link research | **GO for review only.** The bounded first-line ownership seam is feasible in the copied pinned template. |
| Native legacy parity and resource qualification for integration | **HOLD.** Exercise the full active bridge with real TCP partial/FIN/pipeline/keep-alive behavior; measure contiguous heap, stack high-water, per-poll CPU, watchdog intervals, browser/metrics latency, LCD/overlay timing and conditional OEM path. Decide whether the 130-byte cap is acceptable for all supported legacy clients. |
| Production media authentication and active endpoint | **BLOCKED.** Resolve RFC 8941 versus 9651/parser policy, canonical target/authority and framing, key provisioning/revocation, boot entropy, challenge issuance/rate limit, native ECDSA verification and Gate 1/2 behavior under independent security review. A copied parser and passing host vectors do not authorize this. |
| Device sender, OTA, installation or SmallTV contact | **BLOCKED.** Outside this mission and requires separate owner instruction and physical acceptance evidence. |

**Stop at this review gate.** The most defensible next step, under a separate instruction, is a security-reviewed profile decision and an instrumented unconnected integration lab for the existing bridge, followed by physical qualification before considering any active media route.
