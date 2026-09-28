# V0.6 — media authentication and transfer safety review

**28 September 2026 — AUTHENTICATION READINESS: BLOCKED. Native media receiver: BLOCKED.**

This review starts at clean commit `ff08defa01cb39504ae4c516192de8418e34cf42` on `feature/shino-tv-v06-native-audit`. The complete [Mission 1 audit](V06_NATIVE_SOURCE_AUDIT.md) was read first. Its critical R1 (HTTP allocation before validation), critical R2 (authentication/authorization) and high R3 (heap/contiguous allocation) remain unresolved implementation gates. Findings below strengthen R1/R2; host tests do not close them. `git diff 8cef030 HEAD -- firmware` was empty at the start. Frozen V2.1, its private image, V0.1 tray and external worktrees are outside this change.

Only this review, an isolated Python test module and its Windows CI invocation change. No native media route, firmware modification/build, device connection, private artifact access or cryptographic implementation is introduced.

## 1. Source provenance and trust boundaries

Firmware references below refer to the inherited source at `ff08def`; the V0.5 Python codec remains unchanged. The active boot profile calls `FirstBootBridge::run/loop` (`firmware/src/main.cpp:116-126,232-236`). The normal web/scene/Wi-Fi modules are outside that profile. A future media operation cannot inherit authority merely because its module or route name appears elsewhere in the repository.

The actual installed dependency source was read at `C:/Users/jerry/.platformio/packages/framework-arduinoespressif8266/`; `package.json` identifies **3.30102.0**, matching `firmware/platformio.ini:18-21` (Arduino core 3.1.2). `WS` below means its `libraries/ESP8266WebServer/src/`. Line numbers refer to this local package, whose inspected files have these SHA-256 values:

| File | SHA-256 |
|---|---|
| `WS/ESP8266WebServer-impl.h` | `19934c7352eea30acb6d30ab6314d1b794fa5311d88fd3cdc7edaa6cdb7bb150` |
| `WS/Parsing-impl.h` | `f8fe756b04222f20c49813ea63f0c8a90a99034255324de84349e32755afe818` |
| `WS/ESP8266WebServer.h` | `167b098fa4f964fc92ae9b89d531a69e3984561d4ca0729ab857f8f36d52dd67` |

Official upstream references are the [3.1.2 WebServer implementation](https://github.com/esp8266/Arduino/blob/3.1.2/libraries/ESP8266WebServer/src/ESP8266WebServer-impl.h) and [3.1.2 parser](https://github.com/esp8266/Arduino/blob/3.1.2/libraries/ESP8266WebServer/src/Parsing-impl.h). These were also consulted; this audit does not claim a reproducible build or byte identity between an owner-private image and this dependency installation.

Threats considered: an untrusted client able to reach the private AP, an authenticated but faulty/compromised PC, malformed or oversized input, captured/repeated requests, concurrent browser/metrics requests, transport loss, memory exhaustion and reboot. The private WPA2 AP limits access but is not request authorization. An authorized malicious sender can still lie about music; resource bounds and isolation must hold even for that sender.

Trust boundaries are: PC media provider → bounded PC metadata/codec → untrusted HTTP bytes → independently verified request identity and operation → RAM transaction staging → atomic media publication → LCD composition. The independent four-metric state and the optional exact-OEM writer are separate boundaries. A read cookie, CRC, SHA digest, transaction ID or Python boolean must never cross an authentication boundary as proof of identity. No threat is exercised against the real device here.

## 2. Existing authentication: observed source behavior

`FirstBootBridge.cpp:159-163` calls `server.authenticate(user, password)` and issues `requestAuthentication(DIGEST_AUTH, "SHINO-FirstBoot")` on failure. **Digest is the configured challenge; it is not an exclusive accepted scheme.** `WS/ESP8266WebServer-impl.h:99-131` also accepts a correctly encoded Basic credential. This refines Mission 1's shorthand “Digest-protected”; no installed behavior is changed.

`authenticateDigest()` (`WS/ESP8266WebServer-impl.h:135-202`) checks the supplied username and stored realm/nonce/opaque, computes MD5 HA1 and HA2 using the current method and the **client-supplied `uri`**, then compares the response hash. Its `qop=auth` calculation includes supplied `nc` and `cnonce`. If qop is absent it supports the older calculation. These are real library checks, not the V0.5 boolean; they do **not** establish the following missing protections:

- No comparison of the Digest `uri` with `_currentUri`. An otherwise valid proof for another path of the same method is not rejected by this comparison, because that comparison does not exist.
- No used-nonce or monotonic nonce-count tracking, nonce age limit, or peer binding in this verifier. Reusing a valid response while the shared challenge remains current is not excluded by its state.
- No strict Digest parameter uniqueness/algorithm/qop policy. `_extractParam()` (`:91-95`) selects substrings; it is not a strict duplicate-rejecting parser. Challenge qop is `auth`, not body integrity protection. CRC32 and sender-supplied SHA-256 cannot authenticate a changed body.
- `requestAuthentication()` (`:215-229`) replaces one server-wide nonce/opaque using `_getRandomHexString()` (`:205-211`, four hardware RNG register reads). There is no per-media-operation challenge lifecycle. A new challenge can invalidate another client's outstanding request. Entropy quality and on-device interoperability were not measured here.

There is no production media authorization mechanism to demonstrate. Reusing `requireAuth()` alone is **BLOCKED**. Any future choice must use an independently reviewed standard authentication implementation, exact request-target/method binding, bounded challenge lifetime, replay control, explicit operation/principal binding and a justified body-integrity/channel threat model. Do not invent cryptography or treat changing the Digest hash alone as a solution.

The disconnected `firmware/include/boot/NativeOtaStrictDigestGate.h:3-14,35-125` already describes a SHA-256 Digest review contract with exact OTA routes and one-shot proof. It is not included by the active bridge, has no media operations, and depends on external randomness/credentials/challenge issuance. It is not permission to reuse OTA authority for music. Its host tests and independent client probes do not qualify an active media endpoint.

### Actual authorization map

All references in this table are to `firmware/src/boot/FirstBootBridge.cpp`.

| Operation | Active requirement |
|---|---|
| GET `/` (`399-408`) | Existing valid browser session, otherwise `requireAuth()` then issue read session. |
| GET `/ui.js` (`409-414`), GET `/api/v1/bridge/ota/capabilities` (`421-439`) | Read session or `requireAuth()`; capability endpoint is read-only. |
| GET `/api/v1/bridge/metrics` (`242-249`) | Read cookie only; missing/expired session yields 403 without a new Digest challenge (`169-176`). |
| POST `/api/v1/bridge/metrics` (`251-272`) | `requireAuth()` before application JSON parse/apply; cookie cannot authorize it. |
| GET status, fs-plan, factory-return (`178-240,440-443`) | `requireAuth()`; no read-cookie bypass. |
| POST factory-return (`444-454`) | Only when `SHINO_ENABLE_FACTORY_RESTORE`; upload callbacks call `server.authenticate`, completion uses `requireAuth()`. Separate OEM checks precede `Update.begin` (`FactoryRollback.cpp:85-143`). |
| Unknown routes (`455-458`) | `requireAuth()` before 404; this is not a pre-parser firewall. |
| Native media or generic native OTA writes | No active route. Native signed OTA/FS migration remain compile-disabled (`35-64`). |

Browser read sessions (`FirstBootBridge.cpp:81-157`) are two volatile token slots with IP binding, 2-hour expiry, bounded cookie extraction and duplicate-name rejection. They mitigate background challenge churn, not write authorization. Active POST processing has no dedicated media Origin/Host/CSRF or per-operation authorization policy. The installed metrics/OEM behavior stays frozen.

## 3. Body allocation, framing and interruption

The dependency resolves Mission 1's uncertainty about **ordering**, while confirming the blocker:

1. `handleClient()` invokes `_parseRequest()` before `_handleRequest()` (`WS/ESP8266WebServer-impl.h:338-360`). Therefore application `requireAuth()` runs after the generic parser for ordinary POSTs.
2. `_parseRequest()` reads request/header lines into `String`, converts `Content-Length` using `toInt()` and overwrites the length on repetition (`WS/Parsing-impl.h:45-74,114-158`). There is no 384/512-byte route-specific cap here, strict decimal check, duplicate-length rejection or explicit request Transfer-Encoding rejection.
3. Non-multipart bodies are read into `String plainBuf` via `readBytesWithTimeout()`/`S2Stream`, before argument parsing and `arg.value = plainBuf` (`:38-41,160-188`). `cores/esp8266/StreamString.h:102-105` appends to the destination String. The firmware's 16..384 bound at `FirstBootBridge.cpp:254-260` comes later. Authentication is **not complete before body-dependent allocation or parsing**.
4. Incomplete declared body reads return `CLIENT_MUST_STOP` (`Parsing-impl.h:161-168`), and `handleClient()` stops that connection. This avoids dispatching that incomplete non-multipart body, but does not undo peak allocation or time already consumed. Duplicate headers overwrite collected values (`Parsing-impl.h:237-246`). Extra bytes and persistent connections are not an exact-one-request fail-closed media policy; malformed headers can terminate the header loop rather than produce a uniform strict rejection.
5. `HTTP_MAX_POST_WAIT` is 5000 ms (`WS/ESP8266WebServer.h:61-65`), but stream send timeouts reset on progress (`cores/esp8266/StreamSend.cpp:62-129,156-209,235-296`). `readStringUntil()` also repeatedly uses per-character `timedRead()` (`Stream.cpp:29-41,255-263`). These are not an absolute eight-second transaction deadline or total header budget. Yielding services the SDK; it does not run the bridge's pending metric paint while still inside the handler/parser call.
6. Multipart parsing allocates argument and upload structures before invoking upload callbacks (`Parsing-impl.h:348-430`). OEM authentication-before-`Update.begin()` is therefore not authentication-before-HTTP-allocation. Media must not borrow the multipart OEM return path. Its abort/complete/restart behavior belongs exclusively to the frozen OEM implementation (`FactoryRollback.cpp:142-175`).

No network attack or native peak-allocation measurement was performed. Exact effects of resource exhaustion, malicious framing and sustained partial traffic on real Wi-Fi/metrics remain **BLOCKED/HOLD as in Mission 1**, not newly proven safe.

## 4. Required future bounds (review constraints, not an activated API)

- Validate a bounded request line and header section before body-dependent storage. Reject unknown method/target, duplicate critical fields, absent/invalid/overflowing `Content-Length`, all Transfer-Encoding, conflicting framing, unsupported MIME/content encoding and unsupported Expect behavior. Never drain arbitrarily large rejected input. “Before allocation” means before attacker-sized body/JSON/art staging allocation; a bounded header workspace and network stack still need their own memory budget.
- Begin metadata stays <=512 canonical UTF-8 bytes with exact known fields/types. A cover is exactly 8192 bytes, 16 indexed 512-byte tiles, CRC32 per tile and final SHA-256. Reject invalid metadata before **cover** allocation. No JPEG decode, URLs, filenames, scripts or filesystem data on the device.
- The V0.5 `Packet` dataclass does not define HTTP serialization for transaction ID/index/CRC, and `commit()` has no transaction argument. The tests use <=512-byte Begin, exactly 512-byte raw chunk and zero-byte Commit bodies under **test-only paths**. A real envelope must define where bounded operation/transaction fields live and count them in its wire/header budgets. These fixture sizes do not silently approve an unspecified transport.
- Authenticate and authorize each operation independently before consuming its body. Bind it to the actual method/target, authenticated principal/session and exact pending transaction. A read cookie cannot authorize Begin, tile or Commit. A valid proof for metrics/OTA cannot authorize media. Reject replay before staging. Treat body integrity separately: `qop=auth` does not sign the payload; a sender-provided digest is not a MAC.
- At most one pending transaction; concurrent/repeated Begin must not silently replace it or extend its original deadline. Select an explicit reject/busy policy. An identical tile retry may be idempotent without incrementing progress or renewing lifetime; a conflicting retry is terminal. Commit must name and consume exactly its intended transaction. A repeated/delayed Commit must never commit a newer one.
- Keep the absolute transfer deadline at eight seconds, measured from the accepted Begin and never renewed by progress/retries. Current Python accepts exactly 8.0 seconds and rejects greater elapsed time; any native tick-resolution/boundary choice needs explicit parity tests. Separate bounded header/read-idle/work-per-poll limits must fit inside this absolute deadline. Timeout cleanup must run even with no further request.
- Replay protection must cover pending, failed, expired and consumed operations for the relevant authentication lifetime. Do not clear replay history wholesale when a small cache fills. On reboot all staged/displayed media is lost; old authentication challenges must become unusable. This requires an independently validated volatile session/boot freshness design, not media persistence or credentials supplied by this audit.
- Handle every allocation failure, parse error and transport cancellation explicitly. Release staging and revoke untrusted/obsolete media before publication; do not substitute zeros for any metric. The current four-metric snapshot and last-good timestamp remain owned by `FslessMetrics` (`FslessMetrics.cpp:25-69`). Invalid metrics preserve previous state; stale means no received sample or unsigned elapsed **>6000 ms**. Media cannot renew that TTL.

The fake header ceilings in `ReviewOnlyHttpGate` are 2048 total bytes, 12 fields and 768 bytes per line. They exercise ordering only and are **not an ESP8266 allocation budget**. Its “complete” input is a finite synthetic message, not real TCP framing, FIN semantics, a slowloris scheduler or an implementation of Digest.

## 5. Failure-handling matrix

“Revoke” means discard committed artwork/media eligibility and return to PC HEALTH, including previously accepted art. “Owned” means a request already associated by verified authorization with the accepted transaction; an arbitrary request must not gain permission to cancel another client's transaction. Every row preserves four-metric values/timestamp and permits normal stale handling.

| Failure / case | Required rejection point and pending action | Previously accepted/displayed art | V0.5 evidence or gap |
|---|---|---|---|
| Unauthenticated request / read cookie used for writes | Before body read, JSON or staging; do not dispatch to receiver or mutate an unrelated transaction. | Preserve on unrelated denied request; prevents unauthenticated artwork-clearing DoS. An owned transfer that loses authorization is cancelled/revoked. | Boolean gate precedes parse, but direct `fail("UNAUTHORIZED")` clears all art (`media_wire_v1.py:197-210`). Outer ownership policy is absent. |
| Oversized declared body / forged length syntax | Reject header before body allocation; close boundedly. No new pending state. | Preserve unrelated valid state; revoke if terminal failure of the owned transaction. | No HTTP layer in V0.5; only metadata byte length <=512 is checked. Frozen core buffers before handler auth. |
| Chunked transfer, TE+CL, duplicate CL/Authorization, unsupported encoding | Reject at bounded header boundary; no body/cover allocation. | Same ownership rule as above. | Fake framing test only. No native media framing policy. |
| Short read, TCP disconnect, forged actual length or trailing body | Reject incomplete/extra message before protocol dispatch; discard affected pending state. Do not infer success from socket close alone. | Revoke after an owned incomplete transfer. | V0.5 has no disconnect callback; test explicitly models `fail` on owned disconnect. |
| Repeated pending Begin / competing Begin | No new cover allocation; reject/busy, without replacing pending or renewing its deadline. | No new publication; retain only according to chosen ownership/busy policy. | **GAP:** `begin()` replaces pending and resets `started` (`207-225`). |
| Repeated completed/failed/expired transaction ID | Reject before cover allocation; consume/retain appropriate replay evidence. | An owned replay rejection must not expose stale art or act as a new commit. | Completed IDs rejected while cached. **GAP:** failed/expired IDs reusable; cache clears older entries after 33 commits (`273-277`). |
| Exact duplicate chunk | Accept only verified same owner/tx/index/bytes; no progress or deadline change. | No partial/new display. | Implemented in host (`247-253`). |
| Conflicting duplicate / wrong ID / wrong order / wrong index or length | Validate before copying tile; discard affected pending transfer. | Revoke. | Host rejects (`227-254`). |
| CRC32 mismatch | Reject before tile copy; discard pending. | Revoke. | Host rejects; CRC is not authentication. |
| Missing tile or final SHA-256 mismatch | Reject Commit; discard pending; never publish partially verified cover. | Revoke. | Host rejects (`256-270`); currently copies full buffer before completion/hash checks. |
| Wrong metadata types, fields, duplicate JSON keys, malformed UTF-8/canonical bytes | Bounded body only; reject before cover allocation; cancel owned transfer. | Revoke for owned invalid update. | Host canonical reserialization/type checks reject (`81-115,207-220`). New tests cover UTF-8/surrogate/duplicate-key cases. |
| Expiration / backward test clock | Cancel at timer tick or next operation; deadline not extended. | Revoke. | Host rejects elapsed >8 or backward time (`233-234,262-263,290-302`); repeated Begin can currently defeat original deadline. |
| Repeated Commit / delayed Commit for previous transfer | Require exact tx and consumed-operation proof; reject without publishing a newer transaction. | Current V0.5 repeated Commit with no pending clears art; do not let an unbound old Commit publish new art. | **GAP:** `commit()` accepts only a boolean and clock; new test demonstrates an old unbound Commit committing a newer pending transfer. |
| Reboot while staged | Drop pending and committed media; new boot authentication epoch; no resume from partial pixels. | Gone; PC HEALTH with metrics initially unavailable until fresh telemetry. | Host recreation clears state but also replay set. It supplies no fresh production auth epoch. |
| Missing artwork / metadata-only update | Valid cover_len=0, null hash, zero chunks; still authorize Begin/Commit and enforce metadata bounds. | Remove prior cover; no fake image. New PLAYING identity may trigger 5 s overlay; paused/no-session must not fabricate new play. | Host supports coverless commit; new tests cover removal and five-second return. |
| Bad/expired transfer after good cover | Terminal owned failure must discard pending and previous accepted artwork. | Revoke, never restore old cover as a fallback. | Protocol errors/timeout do this (`197-205,290-302`); existing tests plus new cases confirm. |
| Allocation failure at HTTP body, JSON, cover staging or Commit copy | No partial publication; terminate affected transaction and release/revoke owned media state. Metrics continue. | Revoke for failed owned transfer. | Fake HTTP body allocator rejects. **GAP:** Python `MemoryError` at JSON/staging/Commit copy escapes and leaves old pending/committed state. No firmware correction is made. |

The pre-authentication preservation rule is a **proposed outer authorization boundary**, not a silent change to V0.5's global `fail()`. Determining authenticated transaction ownership from real requests is still blocked. Aggressive cleanup of every anonymous request would itself allow media denial of service.

## 6. New host evidence and its limits

`companion/test_media_auth_transfer.py` adds **29 tests** in six groups. All use in-memory synthetic bytes; no socket or live URL is opened. The test module is not imported by the tray, firmware or runtime codec. Eight tests named `test_gap_*` deliberately assert the existing deficient behavior. Their success means the gap was reproduced; it is not a passed security requirement. No existing assertion is weakened, no expected-failure marker hides a new regression, and production code is not edited to make these tests pass.

| Group / exact source reference | Tests | Evidence |
|---|---:|---|
| `ProtocolValidationTests` (`test_media_auth_transfer.py:159`) | 4 | Invalid UTF-8/JSON/types/duplicate fields; allocation-before-validation spy; tile order/identity/CRC and final SHA rejection. Executes unchanged V0.5 code. |
| `AuthorizationGateOrderingTests` (`:219`) | 4 | Explicit synthetic decision precedes body allocation/read; cookie cannot grant that decision; direct V0.5 boolean ordering. **No cryptographic verification.** |
| `RequestFramingAndBodyLimitTests` (`:259`) | 6 | Fake headers, length ambiguity/oversize, TE/encoding, partial/extra fragments, disconnect/timeout, synthetic body allocation failure. Exercises only `ReviewOnlyHttpGate`, not the ESP parser. |
| `TransactionConsistencyAndReplayTests` (`:333`) | 7 | Duplicate/replay/Commit behavior plus five reproduced gaps: Begin deadline reset, failed/expired reuse, cache flush, reboot replay loss and unbound Commit. |
| `InterruptedTransferRecoveryTests` (`:405`) | 5 | Expiry boundaries, explicit owned-disconnect callback, recovery, and three gap tests for anonymous revocation and allocation failures. |
| `MediaFailureMetricsIsolationTests` (`:477`) | 3 | Interleaved four-value updates retain last-good timestamp, 6000/6001 ms boundary and unsigned wrap; coverless/five-second behavior. Clock is a **test model**, not execution of native `FslessMetrics.cpp`. |

The original emulator's fixed metrics tuple is insufficient proof of real scheduling independence. The added mutable four-value/clock fixture makes host state isolation more explicit, but cannot establish native HTTP fairness, C++ allocation failure handling, true free heap, SPI duration or LCD freshness during a blocked parser. Those Mission 1 gaps remain.

### Local results and reproducibility

Runtime: bundled Python **3.12.14**, Node **v24.19.0**. In this workspace `$taskPython` can be set to `C:/Users/jerry/.cache/codex-runtimes/codex-primary-runtime/dependencies/python/python.exe`; standard Python on another host can run the same modules. No dependency installation or private configuration is required for the new test file.

```powershell
$taskPython = 'C:/Users/jerry/.cache/codex-runtimes/codex-primary-runtime/dependencies/python/python.exe'
& $taskPython -m unittest discover -s companion -p 'test_media_auth_transfer.py' -v
& $taskPython -m unittest discover -s companion -p 'test_*.py'
& $taskPython -m unittest discover -s tools -p 'test_*.py'
node --test simulator/scene.test.mjs simulator/now_playing.test.mjs tools/test_native_ui_v2.cjs
```

| Check | This mission's result |
|---|---|
| New isolated review tests | **29/29 pass**, including 8 explicit gap characterizations; no security-readiness PASS. |
| Full companion discovery | **96 run, 92 pass, 4 skipped** (Mission 1: 67 run, 4 skipped). The 4 compiler/OpenSSL-dependent host tests remain **NOT EXECUTED**. |
| Node scene/native-browser UI | **20/20 pass**, same scope as Mission 1. |
| Existing tools discovery, unchanged tests | **269 run: 160 pass, 11 failures, 1 error, 97 skipped**, matching Mission 1. Failures are mandatory C++ compiler/preprocessor preconditions; the error is symlink `WinError 1314`. Skips also include unavailable OpenSSL and symlink support. **Full suite is not green.** |
| Original native HTTP/Digest runtime or native media integration | **NOT EXECUTED / media implementation absent.** Source inspection and Python test doubles cannot supply this evidence. |
| ESP8266 heap/stress/LCD/device checks | **NOT EXECUTED**, no device contact/build/installation authorized. |

Local environmental blockers are absent `g++`/OpenSSL in PATH and Windows symlink privilege restrictions. The 11 tools failures are in `test_native_ota_{intent_gate,legacy_compatibility,legacy_response_preview,manual_consent,network_pump,port80_plan,raw_header,request_policy,single_ingress_shadow,streaming_review,updater_isolation}`; the error is `test_verify_fs_provisioning.test_source_symlink_refused`. These are not new functional regressions and are not reclassified as passes. The protocol/auth deficiencies above are separate functional findings, reproduced or source-confirmed even though characterization tests pass.

`.github/workflows/ci.yml` already runs all companion/tool tests on Ubuntu with pinned ArduinoJson source and host C++/OpenSSL fixtures. Its Windows explicit test list now also includes the new module. On a later authorized push/PR, GitHub Actions can execute the existing strict-Digest, external-client, interruption and original-FslessMetrics/ArduinoJson host probes that cannot execute here, with a compiler/OpenSSL-capable runner and Linux symlinks. Inspect exact-commit results, including skips. No new CI run is claimed in this local-only mission. Even successful host C++/Digest fixtures would leave native media auth/heap/physical acceptance blocked.

## 7. Gates and recommendation for Mission 3

| Gate | Decision |
|---|---|
| Source/security review and isolated test evidence | **GO — completed within this mission.** |
| Mission 1 R1, critical: pre-body bounds | **BLOCKED.** Actual core source confirms body processing before application auth/cap, permissive framing and progress-reset timeouts. Fake preallocation tests do not repair it. |
| Mission 1 R2, critical: actual authentication/authorization | **BLOCKED / NOT READY.** Existing verifier lacks exact-target and replay lifecycle guarantees; Basic fallback and body-integrity/ownership questions remain. No native media auth demonstrated. |
| Mission 1 R3/R7: free heap, contiguous block and observation limits | **HOLD as findings; BLOCKING prerequisites for native media.** No measurements added. |
| Mission 1 R4/R5: scheduling, metrics freshness, overlay restoration | **HOLD.** Host isolation is evidence for state behavior only; native mixed-load/display scheduling unproven. |
| Mission 1 R6/R8: firmware/OEM boundary and physical LCD qualification | **BLOCKED for writes/policy change; HOLD for physical visual claims.** Unchanged. |
| Native media receiver activation, production-auth change or device access | **BLOCKED.** No permission is supplied by this review or test result. |

Mission 3 should be **host-only memory and stress analysis**, after separate instruction: inventory each live allocation and its lifetime, force failures at every boundary, exercise mixed metric updates/media retries/partial traffic with independent virtual clocks, and report resource/latency ceilings without adding a route. In particular, V0.5 can hold an old 8192-byte committed cover, a new 8192-byte staging buffer, and a new 8192-byte `bytes()` Commit copy concurrently (`media_wire_v1.py:221-223,265-272`) — **24,576 payload bytes before objects, metadata, HTTP or metrics**, not an ESP8266 measurement. Repeated Begin can also temporarily overlap old/new staging. Measure and redesign ownership in an isolated future model before assuming a single 8192-byte buffer is enough.

Use the historical 28,272-byte free / 26,216-byte largest-block samples only as observations from the owner's existing firmware, not a safe subtraction budget. Mission 3 must preserve both authentication/framing blockers, quantify gaps honestly, and keep firmware sources, installation paths, private artifacts and the working four-metric system frozen.
