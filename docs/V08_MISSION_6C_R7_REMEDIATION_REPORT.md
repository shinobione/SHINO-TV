# SHINO // TV - V0.8 Mission 6C: partial R7 remediation

30 September 2026, Europe/Paris. Exact start: `7d40df9f69bead1aa3a8c7ebd88dbfa0121968e0`. Branch: `feature/shino-tv-v08-legacy-http-hardening`.

**R7 is PARTIAL. Pre-body application authorization and compatible incremental multipart ownership are BLOCKED BY ARCHITECTURE. Stop at review.** The independent framing/authentication repairs below do not close that gate. Media remains DENY-ALL. No production firmware, device, sender, private key, OTA, installation or merge is involved.

## Source and preservation

The clean starting worktree matched the requested full SHA. Read Mission 4 R1-R10, Mission 5 socket/resource/matrix/gate, Mission 6A and 6B report/matrix/gates, the unchanged actual FirstBootBridge routes, and pinned Core 3.1.2 (`3.30102.0`) parser/auth/owner sources. Multipart source explicitly ignores its declared `len` as a termination bound and invokes upload callbacks before the final route handler. The inherited generator verifies six Core fingerprints plus five URI/handler/MIME fingerprints before compilation. Installed packages are not patched.

Live read-only GitHub inspection confirmed Draft PRs #29-35 OPEN/Draft at their retained heads: #29 `f578e11e19b4f7c7a4e78b8f6a0a7c2b4a09f702`; #30 `c5cac0ab87f0ade5bf1e2bd62934b61cedc1a4c5`; #31 `273b386070802cc6aba0a16c8cd8b5a6dc7abf00`; #32 `7cf56a6c0466a07f1d738f97c6ba3e049355ca98`; #33 `80ad35766528a3bf02b697a6ddebf70f852a9f0a`; #34 `799e69a17730c117e1c599912b0b57919d64cea2`; #35 the exact start above. None is updated or merged.

Only new Mission 6C tools/documents and CI orchestration change. All production firmware, companion/simulator, historical overlay generators, R1-R6 models/tests/evidence and prior documents remain unchanged. Candidate source is generated in temporary storage. The new runner enforces an exact allowed diff against the start; final CI additionally requires a clean checkout and exact head. GitHub delivery and pinned CI dependency retrieval are separate from laboratory TCP, which remains IPv4 loopback with ephemeral listeners and public synthetic credentials/RNG plus inert OEM dependencies.

## Bounded partial candidate

`tools/v08_m6c_overlay.py` transforms only isolated copies. It retains Mission 6A's exact first-line classifier, raw-path routing, 130-wire-byte limit, 64-byte slices, absolute 2000-ms start and corrected no-data ready/full-queue predicate at **elapsed >30 ms**. A first-line slice is not a whole-request limit.

Legacy parsing retains actual pinned route selection, arguments, authentication callers, response serialization and unchanged bridge callbacks, with these explicit input constraints:

| Input/work | Candidate limit or decision |
|---|---|
| Request line | Inherited 130 wire bytes, 64 reads/poll, origin-form/raw ASCII/version/path restrictions |
| Header line | 512 text bytes, strict complete CRLF; incomplete terminal line never dispatches |
| Aggregate headers | 2048 wire bytes including CRLF and terminal blank line; at most 32 fields |
| Duplicate critical fields | Authorization, Content-Length, Transfer-Encoding, Cookie, Host, Content-Type and Connection reject in either order, including equal lengths |
| Framing | Decimal length only, checked before conversion; no signs/junk/overflow; maximum 4096; all Transfer-Encoding rejects; nonzero body length on non-body methods rejects |
| Ordinary body | At most declared 4096 bytes; absolute deadline shared with request-line start; never read beyond declared length |
| Reader work | Shared 8192 header/body loop iterations, including waiting iterations; no reset on progress or between headers and body |
| Deadline | `uint32_t(millis() - _v08Started) >= 2000` terminates input; exact reader 1999/2000 and rollover tests |
| Multipart | Terminal close after complete headers, zero body reads/callbacks; compatible authorized uploads remain BLOCKED |
| Contention during input wait | Same strict >30-ms status-change predicate for a ready peer/full queue; terminates the current request |

The application-consumed whole-poll input bound is **64 + 2048 + 4096 = 6208 bytes** for this generated legacy path; a full request can consume its first line over multiple polls. Source bounds input and reader iterations, not native time for WiFiClient availability/read/write/flush/stop, cryptography, String allocation or handlers. The synchronous parser can still retain one application poll until a work cap/deadline/contender terminates it. Internal `yield()` does not return to FirstBootBridge repaint/OEM/watchdog work. This is not an incremental parser or a native total-poll qualification.

Waiting consumes the finite work budget, so a legitimate slow or fragmented header/body can be rejected before 2000 ms. The budget is intentionally conservative and host speed dependent. Header names are restricted to ASCII letters/digits/hyphen; header value controls/tabs and folded fields reject. These are explicit compatibility restrictions, not universal HTTP parity. Chunked requests, large ordinary bodies and every multipart upload are unavailable in this candidate. No production adoption is proposed.

## Pre-body authorization blocker

Actual source order is `_parseRequest` -> method/URI/early hook -> handler selection -> header collection -> ordinary-body buffering or multipart parsing/callbacks -> `_handleRequest` -> application `requireAuth()`.

The early `addHook` API receives method/path/client before Authorization is collected. It cannot establish the application route's authorization from completed headers. Route-handler `requireAuth()` runs after body buffering. Conditional OEM upload invokes `server.authenticate()` from its upload callback after multipart parsing has already begun. Cookies are explicitly GET-only and cannot authorize metrics/factory POST. There is no existing complete-header/pre-body application callback or resumable parser result in the pinned API.

The smallest prospective access-control seam is a complete-header authorization callback that receives the exact method/target/route and collected unambiguous headers, followed by body ownership only on success. A compatible per-poll solution additionally needs persistent request/header/body/multipart phases, byte/iteration budgets retained across polls, a NEED_MORE owner transition, request-scoped proof reuse across multiple upload callbacks, terminal cleanup and handler-specific body limits. Merely invoking the current early hook or `requireAuth()` at final dispatch does not supply these changes. This mission stops before that deeper parser/ownership and application-policy integration.

Consequently the explicit unauthorized-body test still consumes **4096 bytes before 401 in all three variants**. This is a reproduced vulnerability, labeled BLOCKED BY ARCHITECTURE, never a successful security test. Multipart's zero-body denial is a fail-closed research restriction and a lost authorized workflow, not proof of pre-body authentication.

## Authentication repairs and protocol limits

Basic requires the exact case-insensitive scheme plus space. `Basic!` is rejected; the inherited valid Basic fallback remains. No browser cookie substitutes for POST authentication. Basic is not a body-integrity mechanism, and cleartext legacy transport is not upgraded by this work.

Digest now parses a bounded, unique parameter set rather than substring searching for qop. It requires explicit qop=auth, username/realm/nonce/opaque, exact raw request target including query, eight hexadecimal nc digits with nonzero value, bounded cnonce, and real constant-time host response comparison. The candidate hashes the actual method and actual target. Duplicate parameters, unsupported algorithms and no-qop fallback reject. Omitted algorithm or explicit MD5 retains the legacy computation; this is a restricted legacy profile, not a claim of full RFC 7616 interoperability.

A fixed 32-bit watermark requires each successful proof under the current shared nonce to have a strictly greater nc. It advances only after correct proof and never wraps. Challenge rotation resets it. Switching cnonce does not revive a lower count. No unbounded replay cache is introduced. This single-watermark policy is stricter than per-client tracking: parallel clients starting nc=1 under a shared challenge may be denied; older no-qop clients, quoted escapes/extended parameter names and unsupported algorithms are incompatible. Existing shared-nonce rotation/availability and production entropy/lifetime remain unqualified. There is no persistent replay guarantee across reset/reissued nonce state. Repeated authentication of the same request would consume its proof twice; compatible multipart would need a request-scoped verified result. Multipart is blocked here.

**Digest qop=auth does not bind entity content.** A proof generated for the original metric sample and submitted first with altered CPU data still accepts in stock, previous and candidate. Counter replay denial prevents a second use, not alteration before first use. This is an ACCEPTED LEGACY LIMITATION for characterization only, and a security HOLD. RFC 7616 distinguishes qop=auth from auth-int's entity-body hash: [RFC 7616 sections 3.4.3 and 5](https://www.rfc-editor.org/rfc/rfc7616.html). No nonstandard Digest variant is introduced.

Safe protected-body integrity would require a reviewed policy change, such as an authenticated integrity-protected transport or supported auth-int with streamed hashing and post-body integrity validation. Auth-int alone cannot verify the body hash before receipt. A separately authenticated content declaration could authorize bounded receipt before final content verification, but changes the protocol/client contract. Existing POST Digest compatibility is retained only as explicitly insecure legacy characterization; neither Basic-only substitution nor fabricated Digest integrity is presented as a repair. HTTP framing decisions are informed by [RFC 9112](https://www.rfc-editor.org/rfc/rfc9112.html); stricter rejection policies are documented above.

## Differential and application evidence

`tools/v08_m6c_socket_runner.py` reuses the historical pinned-source portability generator, selecting **stock**, **previous = Mission 6A corrected overlay (unchanged in 6B)** and **corrected = partial R7**. Each executes default and conditional inert OEM variants: six actual C++/TCP compositions. The harness imports historical TCP instrumentation without editing or invoking its old vulnerable main as candidate acceptance. Source readers additionally execute directly through a subclass over real TCP at exact deadline/work boundaries. No fake dispatch map or authorization Boolean replaces the chain.

Actual dashboard, JS, metrics GET/POST, status, FS plan, OTA capabilities and factory-return GET/ordinary POST respond through unchanged route handlers. Browser session scope and expiry, valid Basic and Digest, four metric values/formatting, invalid-sample preservation, **6000 ms fresh / 6001 ms stale**, rollover, buffered/delayed pipelines, keep-alive/explicit close, complete FIN and interrupted FIN/RST bodies are checked. Multipart stock/previous callbacks still reproduce START/WRITE/END before unauthorized completion; candidate denies both authorized and unauthorized multipart with zero body callbacks. That behavior difference keeps Objective 4 HOLD for authorized OEM upload compatibility.

See the [matrix](V08_MISSION_6C_FINDINGS_MATRIX.md) for every historical R7 case and unchanged R1-R10 status. Passing stock/previous vulnerability assertions is successful reproduction only.

## Host measurements and CI

Poll instrumentation measures steady-clock elapsed time and server TCP read-counter deltas, including real parser/auth/handler/response work. Unauthorized-body measurement subtracts the exact consumed request-line/header size from the read delta. Context/descriptor counts include fixture setup/cleanup; final equal context counts and zero descriptors establish host teardown only. Peak counts are not SDK/lwIP or heap measurements. Measurements compare finite fixture sets, not equal-work throughput.

Local development runs before the CI portability correction: stock 60/62 checks, previous 66/68, candidate 84/86 (default/conditional), zero failures. Stock/previous maximum bytes/poll 4214 and slow-header polls 2.10-2.12 seconds; candidate maximum bytes/poll 6182 at the aggregate-header/body boundary and observed worst polls 33.48/33.59 ms. Unauthorized consumption remains 4096 in every variant. Ready competitor latency was 63-79 ms across development runs, with requested 1-ms cadence subject to Windows scheduling. Contexts created/destroyed matched: stock55/57, previous59/61, candidate73/75; zero live descriptors each. These are development snapshots tied to input hashes, not final-head CI evidence. Retained Node suites:47/47, zero skips; historical failures are still reproduced. Final exact-head values are generated afresh in the CI artifact and summarized in the Draft PR, including maximum bytes/poll, maximum observed duration, unauthorized body bytes, competitor latency and cleanup counts. No empirical duration is a native upper bound.

The first CI run at `8b0637d501be4fc98a9a04690e2f4cd9e6107896` exposed an invalid stock-host rollover assertion: stock subtracts host-width `unsigned long` (32-bit MSVC, 64-bit Linux), whereas the overlay explicitly subtracts `uint32_t`. It failed two stock fixture assertions on Linux; no candidate security success is inferred from that run. The corrected fixture tests stock at normal30/31 only and tests both overlays at normal and rollover30/31. This is an explicit host-width evidence restriction, not a parser change or a claim that stock fails rollover on ESP8266. Final stock assertion counts are57/59; previous66/68 and candidate84/86 remain.

Reproduce: `python tools/v08_m6c_socket_runner.py` with pinned Core, real ArduinoJson 7.4.3 and the inherited MSVC or GNU/OpenSSL host dependencies. Wrong fingerprints, compiler/socket/assertion errors are fatal; no skip/fake fallback exists. Each executable has a 45-second watchdog. Traffic is loopback only, finite bodies/caps and a 2100-ms historical header continuation. Generated files remain temporary.

CI adds one no-skip Mission 6C exact-PR-head job with clean-checkout/SHA/allowed-diff assertions and a fresh `v08-m6c-r7-evidence-<head>` artifact. Prior jobs remain. The unchanged Mission 6B evidence runner permits only its own mission diff, so its historical job explicitly reruns pinned 6B SHA and labels the artifact with that SHA; it is not represented as current-head 6C evidence. The new allowed-diff guard verifies that 6B and all other historical source/evidence remain intact at the candidate head. Final run URLs, artifact identity and conclusions are recorded in the separate Draft PR and delivery after verification.

R8/R9 remain native/runtime/accepted-media gaps; R10 remains BLOCKED. No physical browser, LCD, heap, watchdog, entropy, firmware/device or accepted media qualification is claimed. Stop at the [review gate](V08_MISSION_6C_GATE.md).
