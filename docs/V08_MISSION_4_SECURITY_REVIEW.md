# SHINO // TV — V0.8 Mission 4: adversarial security and architecture review

**Reviewed head: `7cf56a6c0466a07f1d738f97c6ba3e049355ca98`. Decision: GO for a bounded, offline, deny-all socket/dispatch diagnostic lab; HOLD for protocol acceptance and runtime qualification; BLOCKED for authenticated media ingress and production/device operations.**

Review date: 29 September 2026, Europe/Paris. Review branch: `codex/v08-mission-4-security-review`, created from the exact requested head. This is an adversarial source/evidence review, not implementation, formal certification, or authorization to run the next lab. Earlier GO decisions and successful CI are not production security evidence. No native media authentication bypass is claimed: the experimental native media path denies every candidate, and production firmware has no active media route.

## 1. Scope, provenance and preservation

The reviewed [Draft PR #32](https://github.com/shinobione/SHINO-TV/pull/32) is OPEN/Draft, with the requested head and base `feature/shino-tv-v08-single-owner-preparse`. Its base head is `273b386070802cc6aba0a16c8cd8b5a6dc7abf00`. Read-only GitHub inspection also confirmed:

| Preserved Draft PR | Head at review |
|---|---|
| [#29](https://github.com/shinobione/SHINO-TV/pull/29) | `f578e11e19b4f7c7a4e78b8f6a0a7c2b4a09f702` |
| [#30](https://github.com/shinobione/SHINO-TV/pull/30) | `c5cac0ab87f0ade5bf1e2bd62934b61cedc1a4c5` |
| [#31](https://github.com/shinobione/SHINO-TV/pull/31) | `273b386070802cc6aba0a16c8cd8b5a6dc7abf00` |
| [#32](https://github.com/shinobione/SHINO-TV/pull/32) | `7cf56a6c0466a07f1d738f97c6ba3e049355ca98` |

Reviewed the V0.7 wire specification, ingress/auth review, source-executed report and final gate; V0.8 carriage, crypto and resource contracts; Mission 1/2/3 gates and reports; host verifier/SF adapter, public vectors and tests; overlay transformer and generated pinned source; full-bridge shadow/build tooling, shims and resource accounting; actual bridge, metrics and conditional OEM delegation source; and exact-head CI workflow/logs.

The PR #32 diff adds research tooling/tests/docs and changes CI/ignore rules. Comparing #29's head to the reviewed head shows no changes under `firmware`, `companion` or `simulator`. The original V0.8 verifier/vectors and Mission 2 overlay are inherited, not new #32 implementations. The eight V0.5 `test_gap_*` tests in `companion/test_media_auth_transfer.py:357–451` remain historical defect characterizations; their passing status is not a repair.

Only this report is a tracked deliverable of Mission 4. Review probes ran in temporary host compiler directories or stdin, using public fixtures and existing dependencies. The overlay was regenerated only in its ignored experiment directory. No production edits, private-key generation/access, provisioning, sender, device contact, OTA, installation, merge, or remote PR mutation occurred.

Evidence references below use exact-head repository paths and one-based line numbers. `Core/...` means the installed version-checked `framework-arduinoespressif8266` package, with six source hashes verified by `tools/v07_pinned_core_probe.py:17–42`. `Overlay/...` means output of `tools/v08_native_overlay.py`, not a committed production library. These generated line numbers are tied to the hashes in section 6.

## 2. Severity and findings

High means an authorization gap or major denial-of-service exposure if used in an active ingress. Medium means a concrete contract discrepancy, compatibility/scheduling regression, or consequential missing qualification. Low means misleading source rationale or a reproducibility limit. A design blocker is not represented as a currently exploitable production defect. No Critical finding is substantiated.

| ID | Severity | Finding and evidence class | Origin |
|---|---|---|---|
| R1 | High | No principal revocation enforcement; public-vector host counterexample | Inherited V0.8 Mission 1 gate, reused by 1.1 |
| R2 | Medium | Binary magic accepts high-bit aliases; Gate 2 function-level counterexample | Inherited V0.8 Mission 1; disagrees with V0.7 |
| R3 | Medium | Challenge freshness/global boundedness depend on an unspecified issuer; model counterexamples | Inherited V0.8 Mission 1 |
| R4 | Medium | Unknown/replayed challenges reach real ECDSA verification before denial; host instrumentation | Inherited V0.8 Mission 1 |
| R5 | Medium | Ready-client grace removed; observed source scheduling regression | Mission 2 overlay relative to stock Core |
| R6 | Medium / Low rationale | Broader legacy denial than a line cap; incorrect path-decode rationale | Mission 2 overlay relative to stock Core |
| R7 | High | Legacy body-before-auth, unbounded reads and weak auth remain exposed | Pre-existing; preserved by overlay |
| R8 | Medium | Fake close/copy semantics do not establish actual lifetime or close latency | Unresolved native qualification |
| R9 | Medium | Parser/auth/handler/state labs do not compose into a qualified socket receiver | Evidence gap; Mission 3 explicitly acknowledges it |
| R10 | High design blocker | Key custody, authority enrollment, entropy and challenge delivery have no approved implementation | Inherited unresolved production architecture |

### R1 — revocation has no effect on the verifier

**Evidence:** `tools/v08_m3_profile.js:91–97,112` checks an own registry entry and P-256 key type, then delegates to `tools/v08_crypto_lab.js:177–186`. The latter checks operation membership, epoch, signature and challenge; it never checks revocation. The inherited role/revocation requirement is in `docs/V08_CRYPTO_PROFILE_REVIEW.md`, under “Principal, key and challenge lifecycle candidate”; production revocation remains explicitly blocked in `docs/V08_MISSION_3_PROTOCOL_DECISION.md:49`.

**Reproducer, executed:** with the existing public Begin vector, add `revoked: true` to the fixture's registered `media-test` principal, issue its fixture challenge, and invoke profile 1.1 Gate 1. It succeeds and consumes the challenge with zero external body reads. Appendix A contains the exact probe.

**Impact:** a registry integration that retains revoked entries and sets a flag would continue authorizing them. This is a missing host lifecycle property, not evidence of an active device bypass. Removing the entry or removing operations would deny, but neither is an implemented revocation API; key rotation, pending-transfer behavior and challenge invalidation are unspecified.

**Mitigation:** define an explicit enabled/media-role/revocation contract, reject inactive entries before crypto, invalidate all affected challenges, and define what happens to owned pending work. Do not treat the fixture's arbitrary operation Set as enrollment evidence.

**Missing tests:** revoked existing key, disabled role, revocation after issuance, rotation with outstanding challenges, cross-principal pending isolation, and state changes between proof and application admission. These are required before any active verifier integration.

### R2 — Gate 2 compares magic through a lossy ASCII decoder

**Evidence:** `tools/v08_crypto_lab.js:204–210`, specifically line 207, uses `body.toString("ascii", 0, 4) === "STV7"`. Node ASCII decoding masks the high bit; see [Node Buffer encodings](https://nodejs.org/api/buffer.html#buffers-and-character-encodings). V0.7 compares the actual four bytes at `companion/media_wire_v2_host.py:174–176`.

**Reproducer, executed:** set bit 7 in each magic byte, obtaining `d3 d4 d6 b7`, and give Gate 2 a matching digest for the changed body. It accepts. The unchanged V0.7 receiver rejects those exact header bytes with `WireError BAD_HEADER`. Appendix A supplies the function-level probe.

**Impact:** the HTTP gate accepts noncanonical binary records that the inherited wire reference rejects. This does not bypass ECDSA or SHA-256: an unauthenticated attacker cannot alter an existing signed body successfully. The probe changes the request's expected digest directly to model an authenticated malicious sender; no newly signed vector or private key was created. A later byte-exact receiver would still reject, but such dispatch is absent.

**Mitigation:** compare bytes against `Buffer.from("STV7")` or literal octets before dispatch. Preserve the digest-before-interpretation order.

**Missing tests:** each high-bit magic permutation, every incorrect magic octet, and negative differential records between Gate 2 and V0.7. Existing `tools/test_v08_vector_compat.py:24–34` checks only valid records and canonical Begin metadata.

### R3 — consumed nonce reuse, epoch reuse and total challenge storage are not prevented

**Evidence:** `tools/v08_crypto_lab.js:144–175`. `consume()` deletes a nonce; `issue()` checks only current membership/capacity. `reboot()` rejects only zero/current epoch. `rows` accepts arbitrary key IDs and retains empty maps. Profile 1.1 reexports this table at `tools/v08_m3_profile.js:114–115`.

**Reproducers, executed:** consume the public Begin challenge, issue that same string again in the same epoch, and replay the captured signed request: Gate 1 accepts. An epoch cycle A → B → A plus reissuing the old nonce also accepts the old signature. With capacity 2 per key, issuing one fixture challenge for each of 100 arbitrary key IDs creates 100 rows. These are issuer-controlled model counterexamples, not remotely demonstrated attacks; the production issuer does not exist.

**Impact:** “single-use” holds only while a nonce is not reissued. The table is bounded per key, not globally. The epoch check proves immediate inequality, not freshness across boots. V0.7 high-water may reject a previously accepted Begin in a still-live receiver, but it does not establish Gate 1 freshness and is volatile across reboot. The docs appropriately acknowledge entropy/issuance as unresolved; these executable counterexamples sharpen that boundary.

**Mitigation:** enforce a bounded enrolled-key roster and a separately reviewed issuer with fresh unpredictable challenges, collision/failure handling, key binding, monotonic expiry and boot freshness. Do not repair the model by adding an unbounded consumed-nonce history. If epochs can repeat, challenge freshness must still prevent replay; persistent supplements require separate design review.

**Missing tests:** reissue after consume and sweep, A/B/A boot epochs, roster/global capacity, empty-row lifecycle, revocation sweep, entropy failure, concurrent one-time consumption and expiry during verification. No asynchronous native atomicity or wrap-safe challenge clock is tested. Bad signatures preserving a nonce and Gate 2 failures burning it were additionally observed during this review.

### R4 — cheap challenge denial happens after expensive verification

**Evidence:** `tools/v08_crypto_lab.js:182–185` verifies first, then discovers whether the challenge exists/is expired. `tools/v08_m3_profile.js:94–97` also imports/inspects the public key before that check.

**Reproducer, executed:** instrument Node `crypto.verify`, use an empty ChallengeTable with the otherwise valid public request, and call Gate 1. It calls the real verifier once before rejecting `challenge unknown/replayed`. A captured valid request can repeatedly drive the same path after consumption.

**Impact:** bounded slots do not bound attacker-induced ECDSA work. Anyone who knows the public key ID/current epoch can submit well-shaped requests with nonexistent challenges. Native CPU/WDT impact remains a hypothesis because no native verifier or timing evidence exists; Node durations are not used as ESP measurements.

**Mitigation:** perform a read-only nonce membership/expiry precheck before crypto, then atomically recheck/consume after complete proof. Add bounded admission/rate policy and a declared work budget. Never consume a slot on a bad signature.

**Missing tests:** verify-call counts for unknown/used/expired nonces, repeated invalid signatures for a live nonce, mixed metric traffic, exact deadline during a long verification, and allocation/crypto failure without unrelated state mutation.

### R5 — the overlay removes stock ready-client scheduling policy

**Evidence:** `tools/v08_native_overlay.py:188–207,217–238` replaces the stock no-data branch with unconditional retention on `V08_LINE_PENDING`. Stock `Core/libraries/ESP8266WebServer/src/ESP8266WebServer-impl.h:369–381` drops a no-data owner after elapsed `> HTTP_MAX_DATA_AVAILABLE_WAIT` when another client has data or the pending queue is full. The value is 1,000 ms. The replacement checks only its absolute 2,000 ms first-line deadline at transformer line 40.

**Reproducer, source-executed:** queue a client containing only `GET /`, then a complete ready GET. Poll at ticks 0, 1001 and 2000. At 1001 the overlay still retains the first owner and has accepted only one client; at 2000 it releases it. The stock branch would drop at 1001 for this no-data/ready-competitor case. Appendix B includes the four added assertions; all pass as characterization.

**Impact:** a partial first line can delay a ready legacy client roughly an additional second in this scenario. Conversely, without a competitor, the new 2-second cap is stricter than stock's 5-second data wait. This is a mixed scheduling change, not an overall DoS repair. It predates Mission 3. The current tests assert retained ownership until 2 seconds, but do not compare service latency to stock.

**Mitigation:** explicitly approve the revised contention policy, or preserve a bounded ready-client/pending-queue grace alongside the absolute cap in a separately authorized change.

**Missing tests:** baseline-versus-overlay ready-client delay, full queue, stalled and trickling owners, pipelined contention, idle no-data connection, and application task latency. The clock is checked at poll entry only; deadline crossing inside a poll is an additional unmeasured timing hypothesis, not an observed physical overrun.

### R6 — legacy admission narrows beyond the documented long-line example

**Evidence:** `tools/v08_native_overlay.py:47–100` enforces the global cap, origin-form/version shape, ASCII/control rules, valid percent escapes throughout the entire request line, decoded printable bytes and substring reservation. `tools/v08_m3_parser_lab.py:27–45` already characterizes 130/131 bytes, `mediax`, encoded aliases and a query mentioning media.

**Reproducer, executed:** `GET /?x=100% HTTP/1.1\r\n` is rejected by preparse even though it is outside media and below the cap. Likewise encoded non-ASCII/control bytes in an otherwise unrelated target are rejected. Long legacy targets, unrelated paths containing the media literal, and queries containing it are deliberately over-reserved. These are concrete acceptance changes; their acceptability is a policy decision.

**Low-severity rationale defect:** transformer lines 58–59 say stock routing decodes percent escapes. The pinned parser actually copies the raw path into `_currentUri` at `Core/.../Parsing-impl.h:64–74`; `urlDecode` is used for arguments at lines 252–254. A direct source-executed parser probe retained `/api/v2/bridge/%6dedia` unchanged. Once-decoded reservation can be prudent defense in depth, but it is not parity with the actual exact-route path extraction.

**Impact:** blanket “legacy/OEM parity” is unsupported outside the exercised subset. Direct bridge URLs pass, but real clients' query serialization, maximum target lengths and timing have not been inventoried. No OEM behavior regression on an actual client was measured.

**Mitigation:** describe the conservative namespace policy accurately; approve each compatibility narrowing with explicit client cases. Any future accepted media target must still obey exact signed raw-target rules, with no silent normalization.

**Missing tests:** escaped percent, malformed/valid query escapes, `%20`, `%25`, non-ASCII encodings, method/version variants, media literal in each request-line position, nested percent encoding, and baseline comparison of actual historical browser/metrics/OEM client targets.

### R7 — pre-existing legacy resource and authentication weaknesses remain reachable

**Evidence:** stock `Core/.../Parsing-impl.h:124–168,199–219,237–241` accumulates header Strings, overwrites duplicates, converts Content-Length permissively, and reads ordinary body bytes before handlers. The overlay changes only the first-line read at `tools/v08_native_overlay.py:136–157`. `firmware/src/boot/FirstBootBridge.cpp:251–254` checks auth and handler size only after `server.arg("plain")` exists; `:469–480` runs HTTP before repaint, OEM tick, sampling and WDT feed.

Stock `Core/.../ESP8266WebServer-impl.h:99–128` accepts Basic even when the bridge advertises Digest; it accepts a `Basic!` prefix with valid credential bytes, reproduced by `tools/v08_m3_basic_probe.py:49–55`. Digest at stock lines 147–196 hashes the supplied `uri` without matching the actual URI, has no nonce-count high-water, supports the older no-qop path, and does not bind content. `requestAuthentication` at lines 224–226 replaces shared server challenge state. Duplicate Authorization last-value behavior is source-executed at `tools/v08_m3_parser_lab.py:53–58`.

**Reproducer/evidence boundary:** existing pinned parser probes characterize huge/negative/duplicate length requests and oversized headers (`tools/v07_full_parser_probe.py:112–127`); Basic executes locally and in CI. Digest URI substitution/replay/body modification are source-supported attack hypotheses in this mission, not newly executed Digest cryptographic exploits. No real credential or OEM writer was exercised.

**Impact:** arbitrary legacy traffic can still allocate or block before auth, delaying metrics, freshness repaint and application watchdog service. Cookies do not grant POST/media authority, but server.authenticate is not strict media authentication. Preserving the fallback is compatibility evidence, not security qualification. These are inherited weaknesses, not new overlay defects.

**Mitigation:** keep media terminally isolated; scope a separate legacy framing/auth hardening review. Do not silently alter frozen auth/OEM behavior in Mission 4. A future socket lab must use public fixtures and inert OEM callbacks.

**Missing tests:** real parser-to-Digest-to-handler composition, duplicate Cookie/Authorization on the wire, interrupted legacy headers/body, aggregate header limits, malformed lengths/TE conflicts, Basic fallback under Digest challenge, URI mismatch, nonce-count replay, shared challenge rotation and cookie issuance over the actual response path.

### R8 — close-once is not reference-count or TCP-close proof

**Evidence:** transformer `tools/v08_native_overlay.py:107–112` guards an explicit `stop()` call. Host shim `tools/v08_source_executed_preparse.py:159–166` represents copies by independent C++ values and stop by setting a Boolean/count. Real `Core/libraries/ESP8266WiFi/src/WiFiClient.cpp:95–127` uses shared ClientContext reference counting; actual assignment/destruction calls `unref()`. `Core/.../include/ClientContext.h:115–125` discards receive buffers/closes/deletes at final unref. These dependencies are outside the six existing fingerprint entries; their read-only hashes are recorded below.

Real `WiFiClient.h:36,88–90` and `WiFiClient.cpp:306–325` also make `stop()` flush outstanding output with a default 300-ms wait policy. `ClientContext.h:316–355` can extend its wait start when send-buffer progress changes. Thus 300 ms is not established here as a total wall-clock bound. A previously served keep-alive client followed by a denied media line may still have outstanding response output. First-request deny-all with no output is a different case.

**Hypotheses, not reproduced TCP defects:** retained aliases delaying receive-buffer reclamation; FIN/RST and buffered half-close differences; close failure taking the abort path; output-drain delay before application loop return. There is no demonstrated double-free, second acceptor or extra body read in the generated source.

**Impact:** one explicit stop assertion and one linked server symbol do not prove a unique underlying client lifetime, one FIN/RST, prompt deallocation, or a per-poll time bound. `CLIENT_IS_GIVEN` ownership transfer also needs preservation; it intentionally must not stop a handed-off connection.

**Mitigation:** retain the one acceptor/one reader design, trace aliases and terminal release, and test real close/response behavior before claiming runtime qualification. Review any change of stop/abort semantics separately.

**Missing tests:** shared aliases and last unref, handed-off clients, disconnect with buffered complete/partial lines, RST at each boundary, unacknowledged legacy response before media denial, delayed pipeline bytes, close errors and empty/full receive buffers. Measure application return time separately from internal cooperative yield.

### R9 — evidence does not compose into an end-to-end receiver

**Evidence:** `tools/v08_source_executed_preparse.py:175–184` substitutes `_handleRequest` with a counter/URI sink. `experiments/v08_full_bridge/host_shims/ESP8266WebServer.h:20–31` uses an `authorized` Boolean, map dispatch and no real socket handling. `tools/v08_m3_bridge_lab.cpp:51–55` invokes OEM completion and upload seams independently; it does not reproduce multipart callback ordering. HTTP Gate 2 returns bytes at `tools/v08_crypto_lab.js:220`; it never calls the V0.7 receiver. The docs acknowledge this at `docs/V08_MISSION_3_PROTOCOL_DECISION.md:41–43` and in the full bridge report.

**Impact:** 90 parser assertions plus 35/38 real-handler assertions cannot establish real route matching, response serialization, Digest authentication, upload ordering or state cleanup across socket failures. A valid Gate 1 + failed owned Gate 2 needs a defined authenticated cleanup boundary; a denied or unrelated request must not cancel pending work. Those combined behaviors are not exercised. Tile index/variant, canonical metadata, high-water, final image hash and no-copy Commit remain separate V0.7 model properties.

**Mitigation:** the next lab should connect the actual generated owner/parser, route dispatch and response path to unchanged handlers with explicit public/inert dependencies. Keep media deny-all. Later HTTP-to-wire integration requires its own instruction and tests; this review does not authorize it.

**Missing tests:** every relevant legacy route through the actual socket/response chain, actual cookie headers/duplicates, authenticated failures, conditional inert OEM upload ordering, response Connection behavior under contention, and combined future Gate 1/2/pending cleanup. No physical LCD/browser/OEM success may be inferred.

### R10 — key custody and trusted issuance remain production blockers

**Evidence:** `docs/V08_CRYPTO_PROFILE_REVIEW.md`, lifecycle candidate; `docs/V08_MISSION_3_PROTOCOL_DECISION.md:39,49`; fixture-only `tools/v08_crypto_lab.js:129–175`; public-key validation `tools/v08_m3_profile.js:91–97`. No native SF/base builder, P-256 verifier, media public-key store, private-key custody process, challenge delivery service or entropy-health/freshness mechanism is implemented.

**Impact/design hypothesis:** a valid signature for `tv.test` cannot establish enrollment of a real device. An authority copied from Host instead of independent configuration would remove origin binding. The cleartext profile's challenge delivery and signature capture/race risks require a defined transport policy. Signing requires protection of the PC key against theft, accidental logging/backups and unauthorized callers; neither public fixtures nor the absence of private keys in this PR proves that future custody. No live compromise is alleged.

**Mitigation:** owner-approved authority/key enrollment and media-only role mapping, durable revocation/rotation, an audited custody/threat model, issuance authorization/rate/slot policy, boot/challenge freshness with entropy failure closure, and native parser/verifier cost/side-channel review. Do not reuse OTA/browser/OEM credentials as media authority.

**Missing evidence:** approved designs, independent verification fixtures and native implementation review. Production provisioning and sender work remain BLOCKED and outside the next deny-all socket lab.

## 3. Standards assessment of profile 1.1

The accepted-input profile is defensible as a narrow application policy, subject to the defects and gaps above. It is not a general HTTP/SF implementation or a completed interoperability qualification.

| Topic | Review result and exact source |
|---|---|
| Canonical base | Six components, their actual admitted values, serialized Inner List/parameters, LF separators and no final LF are consistent with [RFC 9421 §2.5](https://www.rfc-editor.org/rfc/rfc9421.html#section-2.5). `tools/v08_crypto_lab.js:44–52`; adapter `:102–112` in `v08_m3_profile.js`. No dictionary label enters the base. Parameter order is preserved, not sorted. |
| Authority/target | Hostname lowercasing and default-port omission follow [RFC 9421 §2.2.3](https://www.rfc-editor.org/rfc/rfc9421.html#section-2.2.3). `v08_m3_profile.js:12–24,80–81` binds to independent `expectedHost`; exact origin-form target parsing is inherited at `v08_crypto_lab.js:85–93`. Scheme/proxy/IPv6 exclusions are explicit profile constraints. |
| Signature format | P-256 uses 64-byte `r || s`, not DER, as specified by [RFC 9421 §3.3.4](https://www.rfc-editor.org/rfc/rfc9421.html#section-3.3.4). `v08_crypto_lab.js:120–122,182–183`; profile checks EC/prime256v1 at `v08_m3_profile.js:94–97`. |
| Raw covered fields | Content-Digest is covered without `;sf`; retaining canonical raw spelling is necessary. Adapter `v08_m3_profile.js:103–106` rejects noncanonical raw digest instead of silently rewriting it. Restricting Content-Type/length to one spelling avoids hidden component changes. |
| Digest meaning | [RFC 9530 §2](https://www.rfc-editor.org/rfc/rfc9530.html#section-2) defines a Dictionary of algorithm Byte Sequences over actual content. The profile narrows this to SHA-256, 32 bytes. `v08_crypto_lab.js:114–116,196–206` recomputes the whole binary record before interpretation; declaration verification alone is insufficient. |
| SF versions/types | [RFC 9651 §2.4](https://www.rfc-editor.org/rfc/rfc9651.html#section-2.4) preserves field-definition type boundaries. Inherited [RFC 8941](https://www.rfc-editor.org/rfc/rfc8941.html#section-3) types remain applicable. `v08_m3_profile.js:85–100` and the reused exact grammar exclude Date, Display String, token/Boolean substitutions and component parameters. This is an intentional application subset. |
| Duplicates | RFC SF parsers ordinarily retain last duplicate keys/parameters ([RFC 9651 §4.2.2](https://www.rfc-editor.org/rfc/rfc9651.html#section-4.2.2), [§4.2.3.2](https://www.rfc-editor.org/rfc/rfc9651.html#section-4.2.3.2)). Profile rejects raw HTTP duplicates at `v08_m3_profile.js:70–79` and SF separators/repeated parameter keys before map parsing at `:26–49`. Quoted delimiters are skipped. Narrowing duplicates is security policy, not evidence that the library preserves duplicate occurrences. |
| Admission/versioning | One label, exact component/parameter order, seven fields, fixed bounds, Connection close and extension rejection deliberately exclude other standards-valid messages. Profile 1.1's authority/OWS changes are explicit at `docs/V08_MISSION_3_PROTOCOL_DECISION.md:13`. The unchanged media tag cannot negotiate 1.0 versus 1.1; peers need explicit agreement. |

No concrete accepted-input signature-base bypass was found in this review. The existing seven public requests all retain their original base hashes and verify with real P-256. That is a limited positive result; seven self-generated fixtures and one external SF library are not independent RFC conformance evidence.

Additional vector work remains necessary:

- Independent published RFC base/crypto cases and a second implementation for component extraction/serialization. Mark unsupported RFC cases as deliberately outside the profile rather than changing the historical vectors.
- Signed positive Abort, nondefault authority port, canonical IPv4, 32×32/48×48 transfers and sequence boundary cases. Current valid signed Begin is coverless; current valid Tile/Commit are record checks, not an authenticated transfer lifecycle.
- Invalid DER/short/long signatures, zero/out-of-range P-256 scalars, wrong curve/RSA/malformed keys, altered public key, and alternate valid ECDSA `s` representation. Replay must be keyed by challenge, never signature bytes.
- Duplicate/mixed-case HTTP fields and SF keys, repeated parameters with escaped quotes/backslashes/delimiters, wrong member types, empty values, invalid padding/nonzero pad bits, all cap boundaries, controls/obs-fold and exact CRLF splits. Current tests cover representative subsets, not the whole matrix.
- Noncanonical raw digest spelling signed as-is versus `;sf` interpretation; unknown algorithm/member/parameter exclusions; authority enrollment distinct from normalized Host; forbidden forwarding/scheme changes; profile 1.0/1.1 disagreement.
- R1–R4 lifecycle cases, body failures after challenge burn, and authenticated negative wire records including R2. No new private keys or sender are needed for function-level characterization; separately approved public signed fixtures would be needed for new end-to-end crypto positives.

## 4. Ownership, transformer and resource assessment

The overlay retains the existing `_server.accept()` owner and `_currentClient`; it introduces no second listener or reader. Its fixed member slot is 131 bytes, with a 130-byte wire cap and up to 64 reads per poll. A 131st byte can be consumed to detect overflow but is not stored. On a complete legacy line, CRLF is removed and the exact text is copied once into the generic parser String; subsequent bytes remain for that parser. A reserved media candidate is terminally stopped before headers/body/dispatch. These source properties are supported by the executed labs, including interrupted first lines, wrap subtraction, buffered pipelines and next-owner admission.

`tools/v08_native_overlay.py:118–121` requires exactly one anchor; `:242–261` verifies the six core hashes/version, copies into the isolated overlay, patches three files and hashes outputs. Macro-disabled parser/owner branches remain stock. The full-bridge hook at `experiments/v08_full_bridge/prepare_shadow.py:20–86` copies tracked sources, supplies inert public policy/startup, consistently rewrites WebServer includes and builds overlay MIME support. This supports ABI/link composition, not runtime lifetime. Default projects use baselines; the experiment flag is opt-in. No active media route is added.

**Low-severity reproducibility limit:** `copytree(..., dirs_exist_ok=True)` and the shadow copy do not remove obsolete destination files. Source copies are from current working-tree bytes, not `git show` of a fixed SHA. Six hashes are not a whole SDK/WiFi/dispatch dependency fingerprint. Defaults and fresh exact-head CI mitigate these risks, but arbitrary `--dest` paths and dirty/reused build directories should not be described as universally safe/hermetic. For the next lab, require clean provenance and a fresh dedicated generated destination; test anchor/hash drift, macro-disabled behavior, include resolution and stale-file contamination. No unauthorized destination was used here.

Resource claims correctly separate allocation floors from target reserve. Link evidence shows +144 bytes in the server object and +152 BSS overall, not just a 130-byte slot. The first-line decode array lives on the stack; its measured native compiler frame is 192 bytes. Per-function frames are not a call-chain maximum or runtime high-water. Legacy header/body allocation and blocking survive the handoff (R7), and actual network close can add work (R8). A first-line deadline is not a total-request timeout. TCP receive buffering can contain body bytes before application reads; zero application body reads does not imply zero TCP RAM.

## 5. CI and local validation: what the evidence actually supports

Live metadata confirmed both exact-head runs [36629248688](https://github.com/shinobione/SHINO-TV/actions/runs/36629248688) and [36629238920](https://github.com/shinobione/SHINO-TV/actions/runs/36629238920) completed successfully at the requested SHA. The six jobs in run 36629248688 all succeeded. Its logs were inspected for exact checkout SHA, actual test counts, link outputs and compiler frames. This does not substitute the earlier code-head run 36628802737 for exact-head evidence.

| Evidence | Exact-head CI observed | Mission 4 local review | Limit |
|---|---|---|---|
| Crypto/public vectors + profile 1.1 | 16/16 Node tests | 16/16, Node 24.19.0 | Real host crypto/SF, synthetic stream/table |
| Generated pinned parser/owner | 90 assertions, 0 failed; original 37 also run separately | 90/90, MSVC | Real function text; fake network/String/dispatch |
| Basic branch | 5 assertions, 0 failed | 5/5, MSVC | Digest execution false; base64/comparison seams |
| Real bridge/metrics/UI handlers | 35 default + 38 conditional OEM assertions, 0 failed | 35/35 + 38/38, real ArduinoJson 7.4.3 | Synthetic auth/dispatch, no-op graphics, inert OEM |
| Inherited wire receiver | Included in companion suite | 18/18 focused tests; 2/2 vector compatibility | Host Authority assertion, no HTTP/auth composition |
| General suites | Linux tools 281 run, 279 pass, 2 skip; companion 134 pass; Node UI 13 + 7 pass | Not broadly rerun in Mission 4 | Existing checks are preserved; no new full-local-green claim |
| Full native link pair | Baseline/overlay linked; text 393423/394251, data 1672/1672, BSS 26808/26960, BIN 399184/400016 | Existing ignored outputs inspected; no fresh native build | Compile/link only, images never run |
| Compiler frames | Loop 16, handleClient 64, preparse 192, parser 208; auth 256/Digest 368 | Existing `.su` outputs reproduce counts | Static individual frames, no runtime stack bound |
| Review counterexamples | Absent from existing CI | R1/R2/R3/R4 observed; Appendix B 41 assertions = 37 historical + 4 review characterizations | Temporary/in-memory probes only; no implementation fixes |
| Physical/TCP/target runtime | Not run | Not run | No heap/largest block, CPU, WDT, LCD, actual browser, OEM writer or device evidence |

The current CI's full-link deltas are **+828 text, +0 data, +152 BSS, +832 BIN**; server object **272 → 416 bytes**. Local pre-existing ELF hashes and Windows absolute sizes reproduce the Mission 3 report, but the script does not itself prove source-head provenance of an old build. Those files were not relabeled fresh Mission 4 builds. Exact-head CI is the stronger link provenance here.

`tools/v08_m3_resource_report.py:25–29` counts one specific anonymous bridge-server symbol, not every possible server in arbitrary firmware. No second bridge owner was found in the reviewed graph, but that assertion alone is not proof that all network services/aliases are absent. Shadow startup is deliberately unstarted; native links contain retained production code but do not test its execution. The conditional OEM handler suite does not run the writer; both native experiment policies disable restoration.

The documented broad Windows tools result (291 run, 182 pass, 11 fail, 1 error, 97 skip) was not rerun or rewritten. Its GNU compiler and symlink limitations remain historical local evidence. Exact-head Linux success does not erase those outcomes, and neither environment validates hardware.

## 6. Generated-source and dependent-source identity

All six original core fingerprints and package version `3.30102.0` passed current verification. Regenerated overlay hashes:

| Generated file | SHA-256 |
|---|---|
| `ESP8266WebServer.h` | `0bfa64d1b73a9a2558766ca1dcdd332534832ee5b3fbd2241f0d6a77c1e9bc15` |
| `Parsing-impl.h` | `ab3da42e849af911ba75172c9f5ad5e8695ed28457cc564c94b5841189fc41d4` |
| `ESP8266WebServer-impl.h` | `b830d0088562ab427dac505c64f99799f0a8e1c3af81bfef6e5c50ad16e64c16` |

Generated evidence locations: `Overlay/ESP8266WebServer.h:318–321` contains the owner fields; `Overlay/ESP8266WebServer-impl.h:285–361` contains preparse/close, `:365–529` the composed owner; `Overlay/Parsing-impl.h:45–58` the prefetched-line seam. Local output is `experiments/v08_preparse/.pio/pinned_overlay`.

Read-only additional Core dependency hashes used for R8 (not covered by the inherited six-file assertion):

| File relative to Core | SHA-256 |
|---|---|
| `libraries/ESP8266WiFi/src/WiFiClient.cpp` | `b766b52f307c8cdff24b8192fbd526520978c297eee934058af457704f45afc6` |
| `libraries/ESP8266WiFi/src/WiFiClient.h` | `e98887322abcbd5794583cbffc1c8d395aed82ac8789a9aeb28f5a5cf15af099` |
| `libraries/ESP8266WiFi/src/include/ClientContext.h` | `35eff27c222b681fa75f7084caef5dfb3fa9cd89be887e1bffa40931e45c8af5` |
| `libraries/ESP8266WiFi/src/WiFiServer.cpp` | `8c4daeb7e4468265f3df2d98562c79188acdc8e17a3e84b3d6387277b00190a9` |

## 7. Explicit next-lab gate and stop line

| Proposed next action | Decision | Required scope/evidence |
|---|---|---|
| Separately authorized offline socket/dispatch diagnostic lab | **GO** | Loopback on a PC, bounded test traffic, actual generated pinned owner/parser/response/route composition; public credentials; inert hardware/OEM; media remains deny-all. Characterize R5/R6 rather than silently “fix” acceptance. Add terminal lifetime/FIN/RST/pipeline/contention vectors from R8/R9. No network listener on a real device. |
| Claim exact legacy parity, protocol acceptance or target resource/runtime qualification | **HOLD** | Resolve R1–R6 as applicable; explicit cap/namespace/contention decisions; independent vector/implementation comparison; real response/auth/dispatch tests; then separately authorized native runtime instrumentation. PC sockets cannot establish lwIP/SDK/ESP heap/CPU/WDT/display behavior. |
| Add native Gate 1/2, accept media, provision keys or implement a live sender | **BLOCKED** | R1–R4/R10, approved key/authority/issuance design, reviewed native crypto/SF and measured reserves remain open. The next diagnostic lab does not grant this authority. |
| Device contact, OTA, installation, OEM writer, production change or automatic merge | **BLOCKED / outside scope** | No authorization supplied. Preserve PRs #29–32 and frozen firmware. |

A satisfactory socket lab must report byte consumption, response bytes/headers, dispatch/upload ordering, client aliases/terminal release, poll/application return times and ready-client delays with explicit test bounds. Test maximum valid and overlength lines; each CR/LF/percent split; media followed by legacy and legacy followed by media; partial legacy headers/body; buffered and delayed pipelines; peer close/reset before/after every boundary; invalid public authentication; cookie and metrics invariants. Do not wait for peer FIN to produce a response. Distinguish rejecting already-buffered extra bytes from proving that every later byte was observed: closing a connection does not supply that latter guarantee.

This report completes Mission 4. It grants no production security GO and performs no fixes or next-lab implementation. **Stop after the report.**

## Appendix A — executed public-fixture host counterexamples

Run this JavaScript from repository root using `node` on stdin (PowerShell here-string is suitable). Existing pinned `experiments/v08_protocol/node_modules` is required. No signer or private key is involved.

```javascript
const p = require('./tools/v08_m3_profile');
const v = require('./tools/v08_crypto_vectors.json');
const crypto = require('node:crypto');
const e = v.entries.begin, epoch = BigInt('0x' + v.epoch_hex);
const principals = {'media-test': {
  publicKey: v.public_key_pem,
  operations: new Set(['begin', 'tile', 'commit', 'abort']), revoked: true
}};
const stream = () => new p.ByteStream(Buffer.concat([
  Buffer.from(e.header), Buffer.from(e.body_hex, 'hex')
]), Buffer.byteLength(e.header));
const table = new p.ChallengeTable(epoch);
table.issue('media-test', e.nonce, 1000);
const s = stream(), req = p.gate1(s, principals, table, 100);
console.log('revoked flag: accepted, bodyReads=' + s.bodyReads);
table.issue('media-test', e.nonce, 1000);
p.gate1(stream(), principals, table, 100);
console.log('reissued nonce: captured signature accepted again');
const rebooted = new p.ChallengeTable(epoch);
rebooted.reboot(2n); rebooted.reboot(epoch);
rebooted.issue('media-test', e.nonce, 1000);
p.gate1(stream(), principals, rebooted, 100);
console.log('A -> B -> A plus reissued nonce: old signature accepted');
const body = Buffer.from(e.body_hex, 'hex');
for (let i = 0; i < 4; i++) body[i] |= 0x80;
// Function-level malicious authenticated-body model, not a forged signature.
p.gate2(new p.ByteStream(body, 0), {
  ...req, digestBytes: crypto.createHash('sha256').update(body).digest()
});
console.log('Gate2 accepted magic=' + body.subarray(0, 4).toString('hex'));
const many = new p.ChallengeTable(epoch);
for (let i = 0; i < 100; i++) many.issue('fixture-' + i, e.nonce, 1000);
console.log('per-key cap=' + many.capacityPerKey + ', rows=' + many.rows.size);
let calls = 0;
const verify = crypto.verify;
crypto.verify = (...args) => { calls++; return verify(...args); };
try { p.gate1(stream(), principals, new p.ChallengeTable(epoch), 100); }
catch (error) { console.log(error.message + ', verify calls=' + calls); }
finally { crypto.verify = verify; }
```

Observed: revoked flag accepted with `bodyReads=0`; same-nonce replay accepted after reissue; A/B/A replay accepted after reissue; Gate 2 accepts `d3d4d6b7`; per-key cap 2 permits 100 key rows; unknown challenge invokes real verification once. Independent V0.7 byte check rejected the changed magic with `BAD_HEADER`. These are characterizations at the reviewed head, not added regression tests or implementation corrections.

## Appendix B — executed temporary source characterization

Run this Python on stdin from repository root with an existing host C++ compiler/core package. `build_and_run` writes only temporary harness/compiler outputs; `harness()` regenerates the ignored overlay. The added checks are expected to pass for the current flawed/narrowed behavior.

```python
import sys, json
from pathlib import Path
sys.path.insert(0, 'tools')
from v08_source_executed_preparse import harness
from v07_cpp_lab_runner import build_and_run
source = harness()
extra = r'''
  {
    Server s; FakeClient slow, ready;
    slow.input="GET /"; ready.input="GET / HTTP/1.1\r\n\r\n";
    s._server.queue.push_back(slow); s._server.queue.push_back(ready);
    fake_ms=0; s.handleClient(); fake_ms=1001; s.handleClient();
    check(s._server.next==1 && s._currentStatus==HC_WAIT_READ,
          "ready client still waits past stock grace");
    fake_ms=2000; s.handleClient();
    check(s._currentStatus==HC_NONE,"release at 2000ms"); fake_ms=0;
  }
  {
    Server s; FakeClient c; c.input="GET /?x=100% HTTP/1.1\r\n";
    s._v08Started=fake_ms;
    check(s._v08ReadFirstLine(c)==Server::V08_LINE_REJECT,
          "outside-media literal percent rejected");
  }
  {
    Server s; FakeClient c;
    c.input="GET /api/v2/bridge/%6dedia HTTP/1.1\r\n\r\n";
    s._v08Started=fake_ms; s._v08ReadFirstLine(c);
    // Direct parser inspection bypasses classification for this probe only.
    check(s._parseRequest(c,s._v08FirstLine)==CLIENT_REQUEST_CAN_CONTINUE
          && s._currentUri.s=="/api/v2/bridge/%6dedia",
          "stock parser preserves escaped path");
  }
'''
anchor = '  std::cout << "{\\"source_executed_checks\\":"'
assert source.count(anchor) == 1
source = source.replace(anchor, extra + anchor)
print(json.dumps(build_and_run(Path('v08_m4_review_only.cpp'),
                              generated=source), indent=2))
```

Observed under MSVC: **41 assertions, 0 failures** (37 original Mission 2 assertions plus four review characterizations). Fake ticks/networks establish these source decisions, not actual TCP service latency.
