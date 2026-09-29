# SHINO // TV V0.7 Mission 3 — source-executed ingress laboratory

**Scope and gate:** GO for the offline research lab; HOLD for native coexistence work; BLOCKED for an active media route and production authentication. This work began at clean `feature/shino-tv-v07-host-wire-spec` HEAD `3c8588225efdaa645e055de2f38cf29aab81e40a`. It adds host tools, tests, this report and a separate CI job. It changes no production firmware, `FirstBootBridge.cpp`, V0.5 codec or gap characterizations, V0.6 memory lab, V0.7 wire-v2 host reference, metrics, browser session, OEM return, sender or device state. PR #20, PR #28, installed V2.1 review-003 and the V0.1 tray are untouched.

## 1. Source provenance and evidence classes

The local source is PlatformIO `framework-arduinoespressif8266` package `3.30102.0`, corresponding to Arduino ESP8266 Core 3.1.2 and pinned by `firmware/platformio.ini`. `tools/v07_pinned_core_probe.py` rejects any other package version or file digest before extraction. The six SHA-256 values are:

| Installed source relative to package root | SHA-256 |
|---|---|
| `libraries/ESP8266WebServer/src/Parsing-impl.h` | `f8fe756b04222f20c49813ea63f0c8a90a99034255324de84349e32755afe818` |
| `libraries/ESP8266WebServer/src/ESP8266WebServer-impl.h` | `19934c7352eea30acb6d30ab6314d1b794fa5311d88fd3cdc7edaa6cdb7bb150` |
| `libraries/ESP8266WebServer/src/ESP8266WebServer.h` | `167b098fa4f964fc92ae9b89d531a69e3984561d4ca0729ab857f8f36d52dd67` |
| `cores/esp8266/Stream.cpp` | `17e4a13566a9c0fc70ae2cbbb095d4f382a4c02dc6c07d12233aa9385b63c810` |
| `cores/esp8266/StreamSend.cpp` | `fae1fdcfffbff6deb32741ebce574c579c0518b94afdd89082368ae5a776aba6` |
| `cores/esp8266/WString.cpp` | `f1138e424d7fa31d8ac14871e9e17aa3668cdef675dcc5c714a47dcabadd3c2d` |

The evidence is intentionally separated:

1. **Exact pinned source executed under a host harness:** `tools/v07_full_parser_probe.py` copies, without editing their text, `_parseRequest`, `_collectHeader`, `readBytesWithTimeout`, `Stream::readStringUntil` and `String::toInt` from fingerprinted source into one C++ translation unit. The extracted parser body and its ordering are real pinned source. The existing two-primitive probe is also host executed now that MSVC was found.
2. **Simulated dependencies around that source:** the Arduino `String` shape, client input, `sendSize`, `S2Stream`, handler list, MIME table, argument parsing, hook and flush are host shims. In particular `sendSize` records the requested count and stores only available test bytes; it does **not** execute lwIP, target heap allocation, timeout, TCP FIN or watchdog logic. The full WebServer object and `handleClient()` are not executed.
3. **Independent candidate replacement:** `tools/v07_bounded_ingress_candidate.cpp` is new host-only C++ policy/state-machine code. Its behavior says nothing about the existing native parser unless separately integrated and measured.
4. **Python-only synthetic tests:** the unchanged Mission 2 `tools/v07_ingress_research.py` is a separate model, not native execution.
5. **Unmeasured target behavior:** ESP8266 heap/largest block, stack, LCD, metric/OEM route scheduling, Wi-Fi/TCP framing, watchdog and physical display remain unverified.

### Pinned parser observations

Eleven assertions ran through extracted `_parseRequest` and pinned helpers with simulated dependencies. `Stream::readStringUntil` accumulated a 5,000-byte request line and a 5,008-byte header line; the source has no request-line or header aggregate cap. The exact parser passed the last duplicate `Content-Length` value (`50000`) to `readBytesWithTimeout`, and `_collectHeader` overwrote an earlier collected `Authorization` with a second value. `String::toInt`/assignment accepted `-1` as a `uint32_t` body request size of `4294967295`; a declared million-byte body yielded a million-byte `sendSize` request. `Transfer-Encoding: chunked` did not change its Content-Length body read. A simulated short body returned `CLIENT_MUST_STOP`; a hook denial stopped before body read, but the hook executes after request-line allocation and before headers. These observations demonstrate parser decisions, not actual allocation of 4 GiB or network behavior. The normal application handler still runs after `_parseRequest()` and its body read, as documented in `V07_NATIVE_INGRESS_AUTH_REVIEW.md` from pinned `ESP8266WebServer-impl.h`.

## 2. Bounded candidate architecture and threat model

Assume a hostile LAN/AP peer or compromised sender can send slow or malformed lines, duplicated or conflicting fields, replayed requests, wrong principals, partial bodies and concurrent connections. Browser cookies, existing Basic/Digest fallback, `Authority` test objects, CRC32, track keys and sequence numbers confer no cryptographic media authority. The candidate uses a **single active client** and one `Pending` transaction fixture. It refuses another `start()` without replacing the active request or resetting its start time. It never listens on a socket.

The candidate accepts only a literal HTTP/1.1 `POST` request target of `/api/v2/bridge/media/{begin|tile|commit|abort}/{32 lowercase hex transaction}` with no query or path alias. The fixed research limits are a 128-byte request line, 256-byte header line, 12 header fields, 1,024 aggregate header bytes, exactly seven unique required headers, and decimal `Content-Length` of 40–552. It rejects unknown/duplicate fields, `Transfer-Encoding`, `Expect`, content encoding, malformed CRLF, leading zero/sign/overflow lengths and extra bytes **when those bytes are delivered before completion**. A real TCP EOF/pipeline policy is not implemented. `Host: unit.invalid` and placeholder Signature fields are **test fixtures**, not a deployable origin or verified proof. The research 2,000 ms request deadline and 64-byte suggested poll quantum are provisional; neither is an approved native scheduling value.

After parsing the bounded header, `Verifier::before_body(RequestView)` receives the actual method, target, raw required fields, operation, transaction and epoch. It must return a verified media principal before **any body byte** is read. The test `FakeVerifier` returns an injected Boolean and principal; this is a policy-interface test only. The gate then reads exactly 40 fixed bytes and requires version/operation/epoch/transaction/length agreement with the request target and declared length. It reads at most 512 more bytes, checks record CRC32, and calls `Verifier::after_body(RequestView, fixed span, payload span)` on the complete record without constructing a second combined body. This second gate must independently verify the signed digest before any media state transition. No actual signature, SHA-256 or media metadata parser is in this candidate. CRC32 only detects accidental corruption.

An unrelated denial, wrong principal, transaction or epoch leaves pending state and artwork intact. A verified, matching owner whose transfer is partial, timed out or corrupt terminally cleans the pending fixture; neither competing clients nor repeated Begin reset its deadline. The gate checks one externally owned high-water sequence per epoch; the media receiver must advance it on an accepted Begin and persist its bounded terminal policy. The **8,000 ms** pending deadline is absolute. The candidate does not perform accepted Begin art revocation, image allocation, Commit publication or final SHA-256; those remain in the separate V0.7 host wire implementation and would need native design review. Fault injection at header, fixed header, payload and verifier stages proves cleanup paths; these are injected faults, not measured `malloc` failures. The candidate itself has fixed inline arrays and makes no attacker-sized allocation. The injected verifier's future memory use is outside that claim.

The four-metric fixture is independent of the ingress gate. Rejected traffic cannot mutate its value or `last` timestamp. It checks freshness at exactly +6000 ms (fresh) and +6001 ms (stale), and checks the overlay comparison at five seconds. Existing simulator tests exercise the actual browser/scene overlay separately. The mixed-load test interleaves metric updates with a 512-byte tile feed on a simulated clock; it does **not** prove that a real `server.handleClient()` will return in time to run the firmware metric loop.

## 3. Production verifier boundary

A candidate standards-based profile is [RFC 9421 HTTP Message Signatures](https://www.rfc-editor.org/rfc/rfc9421.html) with an [RFC 9530 `Content-Digest`](https://www.rfc-editor.org/rfc/rfc9530.html) over the complete 40-byte header and payload. A reviewed verifier would require a unique, canonical Signature and Signature-Input and cover the **actual** `@method`, `@authority` and `@path` (or an equivalently exact RFC 9421 target representation), `Content-Type`, `Content-Length` and `Content-Digest`. The raw request target grammar must agree exactly with the signed interpretation: no query, percent-encoding, absolute-form target, alternate Host or normalization alias. Signature parameters would constrain key/principal identity, media-only role, creation/expiry or challenge lifetime, a fresh nonce and profile tag. The binary operation, transaction and epoch must exactly match the signed target. Before-body verification may authenticate a digest *declaration*; after-body verification must recompute and compare it before state mutation. A digest alone has no identity value.

This is an interface/profile proposal, **not an implemented cryptographic protocol**. No suitable native library, algorithm/key size, key provisioning path, verifier ownership, reboot-safe unpredictable epoch issuance, bounded nonce replay store, clock/challenge policy, principal revocation method or measured CPU/heap budget has been established. Existing Basic fallback, shared Digest nonce, client-supplied Digest URI and `qop=auth` body gap remain unsuitable. Production authentication stays **BLOCKED**. No secrets were accessed or generated.

## 4. Resource and timing observations

The Windows host used MSVC Build Tools 2022 compiler `cl.exe` version 14.44.35207. The dedicated Linux CI job installs PlatformIO `6.1.18`, package `platformio/framework-arduinoespressif8266@3.30102.0`, verifies all six hashes and compiles the probes with a host C++ compiler. It does not build or upload firmware. The local C++ measurements below are from one MSVC run; all time fields marked simulated are fixture clock values, **not** ESP8266 execution time.

| Observation | Local host result | Interpretation |
|---|---:|---|
| Candidate C++ assertions | 67 passed | Independent candidate policy only |
| Extracted parser C++ assertions | 11 passed | Exact pinned function bodies with simulated dependencies |
| Highest candidate header / fixed / payload use | 300 / 40 / 512 bytes | Fixed capacities 1,024 / 40 / 512 bytes |
| Maximum live payload allocations in candidate | 0 | Payload array is inline; verifier/media allocator excluded |
| `sizeof(Gate)` / `sizeof(Pending)` on MSVC x64 | 1,872 / 56 bytes | Host ABI only; not ESP8266 heap or stack requirement |
| Maximum bytes handled in one candidate request | 824 | Includes header plus 552-byte body in this fixture; hard cap is 1,576 |
| Body bytes read before injected pre-body authorization | 0 | Does not prove real cryptographic verification |
| Longest simulated request duration | 2,001 ms | Absolute timeout fixture; no CPU/WDT inference |
| One valid record host wall processing | 9 µs | Single MSVC observation; nonportable, nonrepresentative |
| Largest simulated interval between mixed-load metric updates | 100 ms | Scheduled fixture updates; no native loop measurement |
| Verified owned terminal cleanups | 3 | Partial, digest failure and timeout paths |
| Pinned parser largest `readStringUntil` accumulation | 5,008 bytes | Host shim observation with no native heap measurement |

## 5. Tests, CI and regression status

Local Windows results on 2026-09-29:

| Check | Actual result |
|---|---|
| `python -m unittest discover -s tools -p 'test_v07_source_executed_lab.py' -v` | **3 passed**; pinned hashes required; extracted parser, two primitives and candidate compiled/executed with MSVC |
| Existing `test_v07_*.py` Mission 2/probe tests | **16 passed**, including the formerly skipped host primitive execution |
| Full `tools` discovery | **288 run: 179 passed, 11 failed, 1 error, 97 skipped**. Eleven older tests explicitly require `g++`/host preprocessing absent from Windows PATH; the error is Windows symlink privilege `WinError 1314`. The new tests pass. |
| Full `companion` discovery | **134 run: 130 passed, 4 skipped**. V0.5 `test_gap_*`, V0.6 memory lab and V0.7 host wire tests remain unchanged and pass. |
| Node simulator/browser/UI tests | **20 passed**. Includes existing five-second overlay and four-card behavior. |
| Dedicated Linux CI job | **Registered, not yet observed at report authoring**. A job failure or skip must not be described as a pass; the final task report should state any observed run separately. |

The exact C++ parser probe and candidate run under a compiler-capable Windows host. The older `g++`-specific tests remain failures on this machine; MSVC availability does not change their hard-coded compiler requirement. The Linux CI job is intended to execute the new lab with the pinned package and avoid that local limitation. No CI status is inferred from local tests.

The diff contains no production firmware or companion implementation changes. Numeric metrics, browser read sessions, OEM application-only return, V0.5 frozen codec/gap tests, V0.6 memory laboratory and V0.7 wire-v2 host code have not been altered. This is regression protection by isolation plus unchanged test execution, **not** proof that a future native adapter coexists with the active port-80 owner.

## 6. Gates and next defensible step

| Gate | Decision |
|---|---|
| Pinned-source fingerprinting, extracted parser execution, bounded standalone C++ candidate and host regressions | **GO for offline research.** Evidence categories above apply. |
| A source-level single-owner handoff design inside the active WebServer/bridge, with target heap/largest-block, stack, fairness and watchdog budgets | **HOLD / UNVERIFIED.** The current lab has no socket, real handler registration or native scheduler. Requires separate instruction before native implementation. |
| Production media authentication | **BLOCKED.** Independently reviewed RFC profile/library, key provisioning, fresh epoch and bounded nonce/replay design are missing. |
| Ordinary WebServer POST media handler, second port-80 server, media route, sender, OTA, package, flash or SmallTV contact | **BLOCKED / outside Mission 3.** Current handler authorization follows generic body parsing. |

The most defensible next step is a **separately authorized design review** of a single-owner native ingress handoff and concrete standard verifier with target resource budgets, before any receiver implementation. This report does not start that work.
