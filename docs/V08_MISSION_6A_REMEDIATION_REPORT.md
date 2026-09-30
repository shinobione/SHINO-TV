# SHINO // TV — V0.8 Mission 6A remediation report

Date: 30 September 2026, Europe/Paris. Exact start: `80ad35766528a3bf02b697a6ddebf70f852a9f0a`; separate branch `feature/shino-tv-v08-ingress-remediation`. **R5 is fixed in an isolated candidate. R6's excessive reservation and source rationale are corrected with explicitly limited compatibility. Media remains terminal DENY-ALL.** R1–R4, R7 and R10 remain open. Native runtime/security acceptance remains HOLD/BLOCKED as detailed in the [gate](V08_MISSION_6A_GATE.md) and [all-ten findings matrix](V08_MISSION_6A_FINDINGS_MATRIX.md).

## Provenance and isolation

Read the complete Mission 4 security review, Mission 5 socket/resource reports, matrix/gate, previous transformer and regenerated overlay, and pinned Core 3.1.2 (`3.30102.0`) owner/header/parser/Stream source. Six original fingerprints are checked before transformation; the socket runner additionally checks the URI/handler/MIME source hashes used by Mission 5. No installed Core file is written. Draft PRs #29–33 were confirmed OPEN/Draft with their original heads; #33 remains at the exact start above.

The corrected transformer is [v08_m6a_overlay.py](../tools/v08_m6a_overlay.py), generating ignored `experiments/v08_m6a/.pio/pinned_overlay`. The previous transformer and every Mission 4/5 report/test remain unchanged, allowing live differential execution. `experiments/v08_m6a` is a separate unstarted compile/link specimen, equivalent in all three variants. Production firmware, companion, simulator, public crypto fixtures/profiles, media-wire-v2 and historical V0.5 assertions are unchanged. Public synthetic credentials/RNG and inert hardware/OEM dependencies are inherited from Mission 5. There is no private-key or production-authentication input, active media handler, native sender, provisioning, device contact, OTA, installation or merge.

## R5: pinned scheduling policy with incremental preparse

Core's `HTTP_MAX_DATA_AVAILABLE_WAIT` is **30 ms**, strictly `elapsed > 30`, not `>=30`. Its no-data owner yields ownership if a pending peer has data **or** the queue is full. The previous overlay discarded this condition and retained incomplete owners until elapsed 2000. The corrected pending branch first drains up to 64 available bytes, then checks the stock no-data/ready/full-queue predicate using `uint32_t(millis() - _statusChange)`. It closes an interrupted owner once and lets the stock terminal release/reset run. A pending peer without data and a non-full queue does not shorten retention. Remaining buffered first-line bytes continue to use bounded incremental reads.

The independent absolute first-line clock remains `uint32_t(millis() - _v08Started) >= 2000`, never extended by trickle progress. Checks now occur at poll entry, before each byte read, before completed-line handoff and on slice exit. Keep-alive resets the first-line buffer/start for the next request while retaining the stock status-change contention clock. Both clocks pass rollover boundary tests. This bounds admission decisions at polls/slices, not the time spent in native WiFiClient operations or later legacy parsing.

Timeout, malformed/media denial, contention and interrupted first-line FIN converge on `_v08CloseOnce()`. Disconnected/no-buffer owners that skip the stock outer branch also get that terminal cleanup. No parser/handler or media state operation is called for interrupted preparse. Real-socket tests count one stop without relying on subsequent fixture cleanup for the partial-FIN and partial-ready-peer cases. `CLIENT_IS_GIVEN` still transfers ownership without a stop. Complete half-closed requests, buffered/delayed pipelines and legacy→media/media→legacy terminal behavior pass.

This restores the pinned **no-data** contention policy; stock's first-line Stream read is blocking once any bytes are present. Stock's delayed-continuation socket test still demonstrates that blocking. The corrected overlay applies the no-data policy between incremental reads without claiming stock already had partial-line fairness or a global fairness guarantee.

## R6: supported inputs and reservation policy

Source inventory: bridge registers GET `/`, `/ui.js`, `/api/v1/bridge/metrics`, `/api/v1/bridge/status`, `/api/v1/bridge/fs-plan`, `/api/v1/bridge/ota/capabilities`, `/api/v1/bridge/factory-return`; POST metrics is supported, and POST factory-return/upload is conditional. Actual UI fetches metrics without query parameters, links to the three diagnostic/OEM paths, and the PC launcher opens `/`. These concrete paths pass the retained source/bridge/socket tests, including conditional inert OEM upload. This inventory establishes checked-in clients, not every historical external browser/OEM client.

The pinned parser splits the raw target at the first literal `?`, copies the raw path to `_currentUri`, and only urlDecodes arguments. The candidate preserves the exact first-line handoff. It validates shape before examining only the path in a fixed reservation buffer. Query text no longer reserves media or requires syntactically valid percent escapes. Queries such as `/?literal=100%`, `/?bad=%GG&short=%2`, `/?x=%00%ff`, `/ui.js?cache=100%`, and `/api/v1/bridge/status?q=/api/v2/bridge/media` reach their unchanged legacy handlers; existing auth/cookie rules still apply. Those are real socket differentials against stock, not an endorsement of malformed queries as standards-conforming or new handler semantics.

Reservation is anchored to `/api/v2/bridge/media` at a path boundary (end or slash). Semicolon path-parameter and decoded-space continuations of that root are also denied as ambiguous aliases. All descendants remain denied regardless of method, query, headers or body. Valid escapes in the path are decoded once **only for reservation**, including encoded letters/slashes. Repeated slashes are collapsed in that view. The raw path is never normalized for routing. Nested escaping is rejected instead of recursively decoding; dot segments, backslash, fragment marker, decoded question mark, malformed escapes, decoded controls/non-ASCII and decoded percent are terminal rejects. Thus `/api/v2/bridge/%6dedia`, encoded-slash aliases, `%256dedia`, duplicate-slash/dot variants and malformed media-root continuations cannot reach legacy handlers.

`mediax`, `media.json` and `/other/api/v2/bridge/media` are outside this anchored namespace and now reach authenticated raw404, while media strings in query values can reach a supported route. There is no case-folding or arbitrary proxy normalization: pinned routes are case-sensitive exact raw paths; non-origin-form targets are rejected. A future accepted media design must retain its own strict raw-target contract; this reservation view is not a signed-target canonicalizer.

| Input class | Stock | Previous overlay | Corrected candidate |
|---|---|---|---|
| Query literal `%`, malformed `%GG`/`%2`, encoded control/non-ASCII query value | Legacy handler | Terminal reject | Legacy handler |
| Media literal/encoded string inside unrelated query value | Legacy handler | Terminal deny | Legacy handler |
| `mediax`, `media.json`, unrelated anchored substring | Authenticated 404 | Terminal deny | Authenticated 404 |
| Root media/descendants, encoded letters/slashes | Raw 404 (no registered media route) | Terminal deny | Terminal deny before headers/body |
| Nested encoded media `%256dedia` | Raw404 | Raw404 | Terminal reject |
| Ambiguous media paths with dot/repeated-slash/semicolon/space | Raw404 | Mixed lexical outcomes | Terminal deny/reject |
| 130/131-byte first line including CRLF | Generic parser | 130 admitted /131 rejected | Same cap retained |

Compatibility remains deliberately limited: 130 wire bytes including method, spaces, version and CRLF permit a **115-byte target for GET HTTP/1.1**, or 114 for POST. Longer otherwise legitimate queries remain rejected. CRLF, printable raw ASCII, origin-form and HTTP/1.0 or 1.1 shape remain required; the method mapping is still the legacy parser's. Literal/malformed percent in a path remains rejected even when unrelated to media. Valid `%25` in a path and dot-segment/backslash/fragment/encoded-delimiter paths are now additionally rejected under the conservative ambiguity policy; `%25` in queries is admitted. These are explicit policy restrictions, not intrinsically unavoidable HTTP requirements or unconditional legacy parity. External/OEM maximum target lengths, serializations and physical compatibility have not been qualified. R6 is therefore **partially addressed**, with the false decoding rationale fixed and tested over-reservation removed.

## Source and real socket evidence

[Source lab](../tools/v08_m6a_source_lab.py) executes generated reader/owner/parser bodies with explicit fake dependencies: stock **4/4**, previous **32/32**, corrected **47/47**. Stock source cases compare idle ready/full-queue scheduling only; fake Stream reads cannot establish stock blocking latency. Corrected checks cover inside-read deadline crossing, exact/wrapped 30/31 grace, absolute 1999/2000 deadline, namespace/query differentials and 64-byte slices/130–131 cap. Historical 37/37 and 90/90 source assertions also reran unchanged.

[Socket runner](../tools/v08_m6a_socket_runner.py) retains Mission 5's actual owner/parser/URI/FunctionRequestHandler/auth/response/unchanged bridge composition, actual PC loopback peers, real ArduinoJson 7.4.3, host MD5 and inert dependencies. Portability seams stay exactly as in Mission 5 (including multipart VLA storage and excluded unused static-file routes). It now generates stock, previous and corrected source independently, compiles four runs and saves hashes, byte histograms, response/first-write timing, lifetime and allocation-call counts. New assertions extend the original socket checks; the original runner/tests are separately retained in CI. Broad unittest discovery may skip unavailable dependencies, but dedicated CI runner commands raise on missing dependencies or failed execution and never skip.

Local Windows/MSVC snapshot values below match [LOCAL_EVIDENCE.json](V08_MISSION_6A_LOCAL_EVIDENCE.json). This is explicitly a **dirty working-tree snapshot based on the starting commit**, with input/generated hashes; it is not final-head CI. Timings vary with host load and are observations, not hard limits. Variant assertion/traffic totals differ, so this is not an equal-work throughput benchmark.

| Host observation | Stock/default | Previous/default | Corrected/default | Corrected/inert OEM |
|---|---:|---:|---:|---:|
| Socket checks, zero failures | 95 | 196 | 224 | 227 |
| Real-clock ready-peer wait, ms | 66.39 | 2040.96 | 70.29 | 71.63 |
| Injected-clock release, ms | 31 | 2000 | 31 | 31 |
| Maximum deliberately observed poll, ms | 47.11 | 2101.53 | 2110.06 | 2113.24 |
| Maximum whole-poll consumed bytes | 4214 | 4214 | 4214 | 4214 |
| First-line-only max bytes per checked poll | No preparse | 64 | 64 | 64 |
| Contexts created / destroyed | 86/86 | 176/176 | 186/186 | 188/188 |

Every teardown checks zero live host descriptors and balanced context creation/destruction. Stop totals include explicit fixture setup; per-terminal assertions measure local deltas separately. The real-clock ready fixture requests 1-ms polling sleeps; host accept/drop-next-poll, socket arrival, response transmission and Windows scheduling explain waits above 30 ms. Source grace tests use injected ticks and cannot be read as wall-time benchmarks. Partial-ready contention, full pending queue, FIN/RST, keep-alive and both pipeline directions are independently checked.

R7 persists: the corrected long-header fixture dispatches after approximately **2110 ms in one poll**, beyond the preparse deadline. Unauthorized 4096-byte metrics bodies are consumed before handler auth; maximum whole-poll reads remain 4214. Basic!/Digest URI substitution/nonce-count replay/body alteration, duplicate Cookie/Authorization ordering, incomplete terminal-header dispatch and inert multipart callbacks before completion auth still reproduce. The 21 retained Node tests, including all five R1–R4 known-failure cases, pass as characterization. Application repaint, OEM tick, sampling/freshness display and WDT feed wait for handleClient return. No finite global header/body/handler work bound is introduced or established.

## Equivalent isolated native compile/link

Fresh local PlatformIO builds used espressif8266 4.2.1, pinned Core 3.1.2, esp12e, identical linker/flash settings and the same unstarted source graph. All three linked successfully. These are compiler/static-section measurements, not native execution or runtime memory reserves. [Size script](../tools/v08_m6a_size_report.py) also records ELF hashes and the one retained `labServer` symbol.

| Native linked field, bytes | Stock | Previous | Corrected | Corrected − stock | Corrected − previous |
|---|---:|---:|---:|---:|---:|
| text | 289991 | 290779 | 291131 | +1140 | +352 |
| data | 1552 | 1552 | 1552 | 0 | 0 |
| BSS | 25944 | 26096 | 26096 | +152 | 0 |
| BIN | 295632 | 296432 | 296784 | +1152 | +352 |
| server object | 272 | 416 | 416 | +144 | 0 |

The final alias/deadline checks increase text by 352 bytes over the prior overlay; static data/BSS/object size do not increase. The 131-byte path reservation buffer is stack-local, not BSS. No heap peak/largest block, aggregate stack high-water, native CPU/WDT/LCD/OEM behavior, ClientContext/lwIP close/ACK/flush/abort/drain timing or ESP runtime evidence exists. Historical full-bridge size/frame measurements remain historical and are not replaced by these minimal specimens.

## Reproduction and final CI provenance

With existing pinned Core, host compiler, real ArduinoJson 7.4.3 and the research toolchain:

```text
python tools/v08_m6a_source_lab.py
python tools/v08_m6a_socket_runner.py
python -m unittest discover -s tools -p test_v08_m6a_remediation.py -v
pio run -d experiments/v08_m6a -e baseline_compile -e previous_compile -e corrected_compile
python tools/v08_m6a_size_report.py
python tools/v08_m5_socket_runner.py
node --test tools/test_v08_crypto_lab.js tools/test_v08_m3_profile.js tools/test_v08_m5_known_failures.js
git diff 80ad35766528a3bf02b697a6ddebf70f852a9f0a -- firmware companion simulator tools/v08_native_overlay.py docs/V08_MISSION_4_SECURITY_REVIEW.md docs/V08_MISSION_5_FINDINGS_MATRIX.md
```

Windows local Python/Node/PlatformIO executables are outside PATH and were invoked by absolute path. No new dependency installation was needed. `V07_ESP8266_CORE` and `SHINO_ARDUINOJSON_SRC` select existing dependencies. Host executables have 90-second process timeouts, loopback-only bounded traffic, at most six concurrent fixture peers, 4096-byte submitted bodies and finite split/trickle/delay vectors. No device address is used.

CI retains all previous jobs/characterizations and adds dedicated no-skip Mission 6A source/socket commands and all three native links. Evidence files are written in runner temporary storage; clean checkout checks follow source/socket and native steps. The exact checked-out SHA, source hashes, measured results and static-size JSON are uploaded as `v08-m6a-evidence-<head>`. The separate Draft PR body and final delivery record verified final-head CI run URLs/job conclusions and downloaded artifact provenance. No report self-referential commit hash or earlier-run success substitutes for that final check. Stop after the review gate.
