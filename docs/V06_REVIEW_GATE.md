# SHINO // TV V0.6 — final engineering review gate

**29 September 2026. Decision: GO for offline research; HOLD for an unconnected native experiment; BLOCKED for a real media receiver or device write.** This document consolidates the three completed V0.6 missions. It does not authorize V0.7 implementation or installation.

## 1. Baseline, provenance and change boundary

The review began on clean `feature/shino-tv-v06-native-audit` at `a42cb802706c39fd78cfd3198263cf8d8b31bf34`. Git ancestor checks passed for V0.5 PR #26 commit `3acf34418fe5308b394ff36b2cc9fe232efc3769`, Mission 1 `ff08def`, Mission 2 `2207b0bd4e4ad07c5a818d8c8b3c0fc593fac9f6`, and Mission 3 `a42cb80`. Frozen V2.1 source commit `8cef03012ae4a4864d69cbe20e02f141a36e2d54` is also an ancestor. The remote PR #26 branch was verified at `3acf344` on 29 September.

`git diff --exit-code 8cef030 HEAD -- firmware` returned no firmware changes. Relative to `3acf344`, the V0.6 changes before this document were only `.github/workflows/ci.yml`, three isolated companion test/lab files, `docs/ROADMAP.md` and the three V0.6 reports. No Windows V0.1 tray/runtime/autostart file, private artifact, credential value or firmware binary entered that changed-file set. The current branch was not on GitHub when checked; no V0.6 CI run existed at that time. Publishing and exact-commit CI are separate evidence from this local review.

The owner's private SmallTV V2.1 review-003 is reported to display four working metrics through standalone SHINO // LINK V0.1. Its historical minimum observed free heap was **28,272 B**, minimum largest block **26,216 B**, maximum fragmentation **12%**, from a finite observation window without native media (`docs/V05_MEDIA_WIRE_HOST_GATE.md:3-7`). We did not reconnect, inspect its private image or independently verify those values. `ROADMAP.md` was corrected on this independent development branch; earlier review-002 GET/return observations remain historical.

## 2. What Missions 1–3 actually established

| Mission | Verified scope | Limit |
|---|---|---|
| [1 — native source audit](V06_NATIVE_SOURCE_AUDIT.md) | `FirstBootBridge.cpp:68,399-480` is the active, single port-80 HTTP owner. `FslessMetrics.cpp:23-80` retains numeric RAM-only snapshot/strict `>6000 ms` freshness. The native four-card painter uses direct ST7789 primitives; the frozen exact-OEM return is application-only. | Source mapping and owner reports do not prove media heap, scheduling or physical rendering. The inactive legacy `Webserver`/`Api`/`SceneManager` is not an integration seam. |
| [2 — security/transfer review](V06_MEDIA_AUTH_AND_TRANSFER_REVIEW.md) | The pinned ESP8266WebServer 3.1.2 parser reads headers/body and allocates before normal handler authentication. Existing Digest shares a nonce, accepts Basic credentials, does not bind supplied Digest URI to the actual target or track nonce-count reuse. A hook exists before headers but is not registered or a complete bounded parser. | The 29 Python tests use fake HTTP and test-double authorization. Eight `test_gap_*` tests reproduce shortcomings; they certify no native protection. |
| [3 — memory/stress lab](V06_MEMORY_AND_STRESS_REPORT.md) | Existing V0.5 can retain three 8,192-byte covers simultaneously. A separate host ownership model compares copy, transfer and revoke-first strategies, injects allocation failure, and interleaves 6,000 synthetic transfers with independent four-value metrics. | The 20 new tests and CPython `tracemalloc` are neither an ESP8266 allocator nor LCD/network timing evidence. The lab's terminal-ID set is deliberately unbounded and unsuitable as a native replay design. |

The implemented V0.6 changes are **review documentation, isolated host tests/lab, and CI test registration**. `companion/media_wire_v1.py`, active firmware, numeric `/api/v1/bridge/metrics`, SHINO // LINK V0.1 and the OEM return code remain untouched.

## 3. Reproduced deficiencies and unimplemented protections

The following eight Mission 2 characterization tests (`companion/test_media_auth_transfer.py:357-461`) still assert existing V0.5 defects. Their passing status means each defect was reproduced:

1. Repeated/pending Begin can reuse a transaction and reset its eight-second start.
2. Failed or expired transaction IDs can be reused.
3. The replay set flush after 33 commits can admit an older ID again.
4. Reboot clears staged art **and** the host replay memory; no fresh production authentication epoch is defined.
5. Commit has no transaction/principal argument, so an old unbound Commit can act on newer pending work.
6. An unauthorized call directly to V0.5 `fail()` can revoke unrelated previously accepted art.
7. JSON or staging `MemoryError` can escape while retaining old/pending state.
8. Commit-copy `MemoryError` can escape while retaining old/pending state.

The Mission 3 model changes ownership behavior only inside `companion/media_memory_lab.py`; it does not modify V0.5 or repair any of these defects. It accepts a hypothetical already-authorized operation and uses a much smaller JSON check than the V0.5 canonical schema. Its bounded logical image counter omits HTTP, metadata, allocator overhead and the unbounded terminal-ID set. Its success cannot justify a media endpoint.

Native protections still absent: authenticated, route-specific Begin/tile/Commit authority; exact actual-target Digest binding; nonce freshness and replay resistance; explicit Basic-auth policy; binding of Commit and owner to the pending transaction; request-body/framing limits **before** attacker-sized allocation; bounded absolute transfer and per-poll work; native allocation cleanup; and physically verified overlay/return. Browser read-session cookies (`FirstBootBridge.cpp:81-157`) authorize selected GETs only and must never grant media writes. CRC32 and sender-provided SHA-256 provide corruption checks, not identity or body authentication.

## 4. Memory architecture decision

RGB565 payload is `edge × edge × 2`. At steady replacement, where an old cover exists, the theoretical simultaneous receiver image-storage peaks are:

| Size | Image payload | V0.5 old + staging + Commit copy | Ownership transfer, retain old | Revoke old, then transfer ownership |
|---|---:|---:|---:|---:|
| 64×64 | 8,192 B | **24,576 B** | 16,384 B | 8,192 B |
| 48×48 | 4,608 B | 13,824 B | 9,216 B | **4,608 B** |
| 32×32 | 2,048 B | 6,144 B | 4,096 B | 2,048 B |
| Text only | 0 B image | 0 B new image | 0 B new image | 0 B image after prior-art revocation |

These are payload floors, not capacities certified on a device. A candidate still requires header/body/tile buffers, authentication, metadata/JSON/UTF-8, SHA context, Strings, lwIP/Wi-Fi, stack, drawing and allocation metadata. The historical 26,216-byte largest block cannot be used as a subtraction budget. The CPython 3.12.14 sample peak of **32,821 traced bytes** measures a host process with prebuilt sender fixtures excluded; it cannot establish native headroom.

**Decision for V0.7 research:** carry **48×48 RGB565** as the *primary experimental* image size, with old-cover revocation before staging and one staging buffer transferred to display ownership after integrity verification. Its modeled image peak is 4,608 B, compared with 8,192 B at 64×64 under the same policy. Compare 32×32 and text-only fallback for legibility and resilience. Keep 64×64 as a quality/reference case, not a presumed native default. V0.5 wire format still fixes 64×64 and 16×512-byte chunks: a 48×48 variant would require a separately versioned host specification and parity review, with no implicit compatibility claim. Neither 48×48 quality nor ST7789 draw behavior has been physically verified.

Revoking old art at accepted Begin deliberately gives up image rollback. Any staging/hash/interruption failure must leave PC HEALTH/text state and all four current metric fields untouched. A rejected *unowned* request must not revoke another owner's art. The Mission 3 allocator tests show this cleanup within their model (`test_media_memory_lab.py:84-154,241-283`); they do not test native heap or real HTTP ownership.

## 5. Validation at this review gate

Local commands ran on Windows with bundled Python 3.12.14 and Node v24.19.0. PASS denotes only the stated host scope; FAIL and NOT EXECUTED remain visible.

| Check | Actual result |
|---|---|
| Full companion Python discovery | **116 run: 112 PASS, 4 SKIPPED**. The skipped tests require unavailable local C++/OpenSSL support and were NOT EXECUTED. |
| Separate V0.5 / Mission 2 / Mission 3 modules | **11/11, 29/29, 20/20 PASS**. Mission 2 includes eight passing gap characterizations. Mission 3 still contains the `500 × 3 × 4 = 6,000` transfer scenario (`test_media_memory_lab.py:231-239`). |
| Node simulator, preview and browser UI | **20/20 PASS**. Three existing JavaScript syntax checks also PASS. |
| Focused existing source tests | `test_fsless_dashboard_source.py` **5/5 PASS**; `test_shino_heap_candidate_wiring.py` **4/4 PASS**. |
| Full `tools` discovery | **269 run: 160 PASS, 11 FAIL, 1 ERROR, 97 SKIPPED**. The 11 asserted missing `g++`/preprocessor; the error is symlink privilege `WinError 1314`. These did not execute their intended native C++ checks and are not green. Other skips include missing OpenSSL/symlink capability. |
| `verify_native_arduinojson_parity.py` | **NOT EXECUTED beyond prerequisite:** local pinned ArduinoJson include tree is absent; the script stops before compiling actual `FslessMetrics.cpp`. The workflow fetches pinned source and performs this check on Ubuntu. |
| Real ESP8266 parser/auth integration, native heap and LCD, device operation | **NOT EXECUTED / no media implementation.** |

`.github/workflows/ci.yml:1-82` runs Linux host parity/tools/companion/Node and an explicit Windows companion list including all 20 Mission 3 tests. Local `gh run list` found no V0.6 branch run before publication. A CI run must be inspected at the **exact PR head SHA** after publication; until it completes, CI status is PENDING/UNVERIFIED. Even full CI PASS would not prove physical or security readiness.

## 6. Measurable gates for a later native candidate

Before any unconnected native receiver/compositor candidate can leave HOLD, require:

1. A single-owner ingress plan for the active `FirstBootBridge` server. Source-executed tests must show strict bounded request line/headers, duplicate-field/Content-Length/Transfer-Encoding rejection, and real pre-body size/auth ordering. The available pre-header `addHook()` seam (`ESP8266WebServer` 3.1.2 `Parsing-impl.h:77-82`) is a research point, not a protection by itself.
2. A reviewed standard authentication path bound to actual method, URI, principal, operation, transaction and replay lifetime; explicit decision on Basic fallback, shared nonce, `qop=auth` body-integrity gap, browser-cookie separation and reboot epoch. Denied/unowned traffic must have no staging or display side effect.
3. A fixed/stack/heap inventory for the exact native build, including HTTP/ArduinoJson/graphics/Wi-Fi and bounded replay state. Phase-specific free heap, largest contiguous block, fragmentation and stack high-water must be recorded around parse/auth, JSON, stage, every tile, SHA, ownership transfer, render and cleanup. Declare a reserve before measurement. The one-second, 1,024-sample observer misses transient peaks.
4. Allocation failure injection at every phase and a long mixed-load soak with metrics POST/GET and browser reads. Measure maximum `handleClient()` occupation, metric acceptance and stale-redraw delay, watchdog feed interval, transfer-deadline cleanup and five-second return to all four cards. Preserve current unsigned strict `>6000 ms` metric freshness and invalid-sample behavior.
5. A verified 48×48 wire revision and PC converter, 32×32/text alternatives, exact RGB565 byte order and bounded ST7789 drawing without full-frame RAM or filesystem. Measure legibility/timing separately on hardware only after explicit owner permission.

No numeric production heap PASS or universal safe threshold is assigned from Python counters or historical samples.

## 7. V0.7 sequence and installation boundary

1. Keep V0.5 frozen as a reference. Specify a separate versioned 48×48/32×32/text-only host proposal with exact tile/body bounds and a finite replay-state budget; compare PC preview quality.
2. Establish real native ingress/auth evidence on source-executed host probes, including slow/partial requests and metrics fairness, before considering a registered media route.
3. Build only an *unconnected*, compile-only native ownership/compositor candidate with explicit failure cleanup and metrics parity; obtain exact build/link/stack and phase-specific allocation evidence. Keep the OEM application return isolated and the flash/filesystem policy unchanged.
4. Review exact-head Linux/Windows CI and independent security/memory evidence. Continue with physical validation only after a new owner decision specifying the precise device operation; no Mission 4 step grants such authority.

Any future physical installation would additionally require an independently reviewed exact source/image pair and hashes, proven body bounds and route authorization, native memory reserve/fragmentation and scheduling acceptance, four-metric/LCD/overlay parity, application-only OEM-return limitations documented, power/rollback risk assessment, and explicit owner approval for that specific write. Wi-Fi remains the normal owner workflow; USB-C supplies power. No UART/PCB equipment is made a normal development dependency.

## Final decision

| Gate | Decision |
|---|---|
| Offline source analysis, isolated host tests, compile-only research, documentation and PC simulation | **GO** within frozen-source and no-device boundaries. |
| Unconnected native receiver/compositor experiments | **HOLD** pending real ingress/auth and phase-specific memory/scheduling evidence. |
| Real media endpoint, production auth activation, installation, OTA, device write or frozen V2.1 modification | **BLOCKED** without separate owner authorization and completed technical gates. |

Stop after this review. V0.7 requires a new owner instruction.
