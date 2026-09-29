# SHINO // TV — V0.8 Mission 5: offline socket and dispatch report

Date: 29 September 2026, Europe/Paris. **GO for the completed bounded PC diagnostic composition; HOLD for legacy/security/runtime acceptance; BLOCKED for active media or device/production work.**

## Provenance and stop line

Started from verified local Mission 4 commit `ea74b8ff4ba9f6fd6d9706151f9312b79170a571`, whose subject is `docs(v08): adversarial Mission 4 security review`. Its `codex/v08-mission-4-security-review` ref resolved to that complete SHA. The working tree was clean. Read the complete `V08_MISSION_4_SECURITY_REVIEW.md`, including R1–R10, standards/resource assessment and both reproducer appendices, before implementation. The requested branch `feature/shino-tv-v08-socket-dispatch-lab` already existed at that exact SHA; reused it without recreation or history changes.

Read-only GitHub verification confirmed PRs #29–32 remain OPEN/Draft at their Mission 4 recorded heads: `f578e11e19b4f7c7a4e78b8f6a0a7c2b4a09f702`, `c5cac0ab87f0ade5bf1e2bd62934b61cedc1a4c5`, `273b386070802cc6aba0a16c8cd8b5a6dc7abf00`, `7cf56a6c0466a07f1d738f97c6ba3e049355ca98`. None is edited, merged or closed by this mission. A separate Draft PR is the delivery surface; its body records final exact-head CI metadata and links to the generated artifact.

No changes under firmware, companion or simulator relative to the start. The installed Core, historical overlay transformer, crypto profile and Mission 4 report remain unchanged. Laboratory socket creation and connect are hardcoded to IPv4 loopback and ephemeral ports. No physical SmallTV, external application socket, sender, enrollment, credential provisioning, writer, OTA, install or deployment is used. GitHub delivery/CI dependency retrieval is separate from laboratory networking.

## Executable composition

`tools/v08_m5_socket_runner.py` verifies the inherited six pinned source hashes and Core package `3.30102.0`, plus five additional URI/handler/MIME source hashes. It materializes the unchanged experimental overlay, prepares stock and overlay copies in a temporary directory, and compiles three executables: stock/default OEM, overlay/default OEM, overlay/conditional OEM. Every run includes the unchanged `FirstBootBridge.cpp`, `FslessMetrics.cpp`, `FslessWebUI.cpp` and real ArduinoJson 7.4.3.

The source chain is actual pinned `handleClient` → actual transformed preparse where enabled → actual pinned `_parseRequest` and argument/header/multipart parsing → pinned URI/FunctionRequestHandler dispatch → unchanged bridge callbacks → pinned Basic/Digest auth and response preparation/serialization → host socket writes → peer TCP receive. Pinned `Stream::readStringUntil` runs over socket-backed `timedRead`. The bridge's actual `run()` registers its routes and starts the loopback adapter; its hardware calls remain inert. The test does not invoke handlers by a substitute dispatch map or authorized Boolean.

Portability transformations are explicit and limited: GNU variadic debug macro spelling becomes standard variadic spelling; the multipart variable-length array becomes a vector-backed character buffer; unregistered filesystem `serveStatic` and static-file handler implementations are excluded. Header declarations and other function bodies remain retained. No installed package is modified. Generated file hashes, input source hashes, working-tree state and Git head accompany every result. The local tracked JSON is a **dirty working-snapshot measurement based on the Mission 4 head**, tied to its input content hashes; it is not mislabeled final exact-head execution. CI generates a separate fresh exact-head artifact.

Synthetic/host dependencies: std::string-backed Arduino String, PC Stream/socket adapters, shared_ptr client contexts, host queue/full threshold of five pending clients, injectable or steady-clock millis, deterministic public RNG, no-op graphics/Wi-Fi/watchdog/logger, public fixture policy and inert OEM functions. MD5 uses real Windows BCrypt or Linux OpenSSL through a host MD5Builder adapter, checked against the `abc` known answer. Basic base64 encoding and constant-time comparison are host implementations. Flash helpers map to host memory. These do not establish native authentication timing, RNG quality or SDK semantics. Arduino `unsigned long` storage is host-width; only explicitly cast uint32_t deadlines/freshness tests support wrap claims.

## Reproduction

With the existing pinned Core, a host C++ compiler and real ArduinoJson available:

```text
python tools/v08_m5_socket_runner.py
python -m unittest discover -s tools -p test_v08_m5_socket_lab.py -v
node --test tools/test_v08_crypto_lab.js tools/test_v08_m3_profile.js tools/test_v08_m5_known_failures.js
```

`V07_ESP8266_CORE` and `SHINO_ARDUINOJSON_SRC` can select existing dependency locations. The runner refuses a wrong Core/hash/JSON version and raises on compilation/execution failure; it has no synthetic parser or JSON fallback. Broad unittest discovery can skip absent dependencies; the dedicated CI command cannot skip. Each executable has a 90-second process timeout. Test traffic is bounded: largest submitted body 4,096 bytes, largest first-line boundary 131 bytes, finite split/trickle cases, one listener, up to six peers for queue contention. Deliberately delayed header delivery is 2,100 ms, not an unbounded stress test.

## Socket, scheduling and compatibility results

| Area | Executed characterization | Interpretation |
|---|---|---|
| Partial first line | `GET /` retained by overlay, later continuation dispatched; stock waits for a delayed continuation inside one poll | Socket-backed timedRead replaces fake immediate-EOF behavior |
| R5 exact partial contender | Partial owner at tick 0; ready competitor still waits at 1001; owner released at 2000 and competitor dispatched | Regression retained and characterized, not repaired |
| R5 stock comparison | Idle first owner with ready competitor; stock drops at tick 31, overlay retains through 1999 and releases at 2000 | Actual pinned ready grace is **30 ms**, not 1000 ms |
| Real-clock fairness | 1-ms requested poll cadence, real loopback peers, stock versus overlay wait measured | Local stock roughly 65 ms, overlay roughly 2045 ms; host scheduling overhead included |
| Full queue | Five host pending peers, no data; stock and overlay show the same retention difference at tick 31 | Host pending policy, not WiFiServer queue qualification |
| Trickled first line | One extra byte every injected 100 ms; terminal release at elapsed 2000 | Progress does not extend absolute preparse deadline |
| Trickled headers | 35-ms continuation blocks a poll; overlay 2100-ms continuation still dispatches successfully | R7 survives; preparse deadline is not total-request timeout |
| FIN/half-close | Empty/partial FIN cleanup; complete half-closed request responds without waiting for final peer close | PC TCP and adapter evidence only |
| Close/reset | Partial and buffered request RST, interrupted bodies, incomplete final headers | Cleanup observed; final incomplete header can still dispatch, a preserved framing weakness |
| Pipelining | Buffered second request remains unread after first dispatch; delayed second request works | Receive bytes retained across actual parser/owner handoff |
| Connection policy | Keep-alive response, explicit close timeout, contention disables keep-alive and serves second peer | Actual pinned response/owner policy under host dependencies |
| Terminal media | Headers and 4096-byte body remain application-unread; one denial stop; media→legacy never dispatches; legacy→media sends only first response | DENY-ALL, not proof that TCP RAM held no body bytes |
| Host aliases | Stopped context survives held alias; final alias releases; actual `CLIENT_IS_GIVEN` hook transfers without stop | Shared_ptr/OS proof, not SDK ClientContext/lwIP proof |
| Line cap | Exactly 130 bytes including CRLF accepted, 131 rejected; first-line-only polls consume at most 64 | Whole poll can consume much more after legacy handoff |
| Media namespace | Exact, encoded alias, mediax and media literal in query denied; every split position tested across two media lines | Conservative over-reservation retained |
| R6 escapes | Unrelated literal `%`, `%00`, `%ff`, truncated `%2` denied; `%20`/`%25` accepted; stock literal-percent query accepted | Legacy narrowing remains a policy HOLD |
| Nested escaping | `%256dedia` remains raw and goes to authenticated 404 | Once-decoded reservation is not recursive decoding or stock path normalization |
| Deadline wrap | Started at UINT32_MAX−1000; tick 998 pending, 999 terminal (elapsed 1999/2000) | Explicit uint32_t first-line deadline only |

Mission 4's R5 report and fake harness incorrectly specified 1,000-ms ready grace and 1,000-ms close wait. The fingerprinted Core header actually defines ready grace 30 ms and close wait 2,000 ms. Its fake stock partial-line comparison also did not model blocking Stream timedRead. Historical evidence is preserved; this mission corrects the conclusion using actual constants and sockets. The removal of ready-client policy is still substantiated, and can cause roughly two seconds of retention in this host case. No automatic fairness repair is introduced.

## Dispatch, responses and application state

Real dashboard response is 200 with SHINO page bytes, CSP and session cookie flags. Unauthenticated dashboard/diagnostics produce serialized 401 Digest challenges. Script and metrics GET accept the issued browser cookie; metrics POST with cookie alone returns 401 without changing state. A fresh-cookie control precedes duplicate-cookie tests. Duplicate session names reject; duplicate Cookie header lines overwrite in the parser, with order-dependent 200/403 results. Duplicate Authorization has order-dependent 401/200 behavior.

Actual POST accepts four numeric metrics (12 CPU, 34 GPU, 5 GB RAM, 67°C GPU) at the injected timestamp; actual formatting yields `12.0%`, `34.0%`, `5.0 GB`, `67.0`. Invalid JSON, missing fields and 385-byte samples return 422/413 and preserve the prior timestamp. Freshness stays inclusive at elapsed **6000 ms**, stale at **6001 ms**, including rollover. Status, FS plan and read-only OTA capabilities return actual JSON; session alone does not confer diagnostic authority. Actual application loop returns to inert OEM tick and watchdog feed.

Factory-return GET delegates to an inert callback. Default POST is absent and returns authenticated 404. Conditional POST and multipart upload execute actual registration/parser/dispatch: unauthorized upload callbacks occur START→WRITE→END before handler authorization rejects; authorized callbacks occur START→WRITE→END→completion. Only inert events and JSON responses result. No OEM writer code is linked into the lab.

Preserved R7 weaknesses are now executed end-to-end: Basic! prefix accepted despite Digest challenge, Digest signed URI unrelated to requested path accepted, same nonce-count proof replayed across paths, Digest POST proof reused with changed body, 4096-byte unauthorized body consumed before 401, and incomplete final header dispatch. These assertions are labeled known failures. See the [findings matrix](V08_MISSION_5_FINDINGS_MATRIX.md); passing characterization is not successful security acceptance.

## Limits

The actual source-to-PC-socket composition objective is achieved; no substitute owner/parser/handler simulation is used to claim it. R9's former composition gap is narrowed for the exercised legacy routes and responses. It does not compose native media Gate1/2 with V0.7 transfer state, because media remains denied. Browser bytes/cookies are tested through TCP peers; no interactive browser acceptance is claimed.

R8 remains open for SDK reference counts, lwIP FIN/RST/ACK behavior, output flush/abort errors, native close latency and memory reclamation. Host flush is a no-op; PC send buffers and shared_ptr do not emulate WiFiClient's flush-progress waits. No unacknowledged native response-drain bound is established. No native heap/largest-block/CPU/WDT/LCD/OEM measurements exist. The resource report supplies **host observations**, not ESP runtime bounds. Stop at the review gate.
