# Mission 8 receiver qualification: HOLD with scoped receiver PASS

1 October 2026. Continued exact `fa926bedc9ea91d7fd1160b871f5d31c3a3c5626` on the existing branch and Draft PR #39.
The owner confirmed the CURRENT LCD once before body testing: correct orientation,
four updating cards and no artifacts. Same candidate boot **298452474**, companion
PID **9972**, and unchanged 446144-byte candidate/hash. No firmware write, factory
return, reboot or companion restart. The original three-minute baseline was not rerun.

| Gate / phase | Actual physical result |
|---|---|
| A: Coverless | **PASS**: five native Commits, three authenticated Aborts, invalid-transaction denial and terminal cleanup. |
| A: 32x32 | **PASS for exercised paths**: six full four-tile Commits; four consecutive replacements; corrupted-digest denial, interrupted TCP and authenticated incomplete-Commit cleanup. Image-specific Abort remains NOT RUN. |
| A: 48x48 | **HOLD - transaction deadline margin**; live memory review passed conservatively; no 48x48 body sent. |
| Native crypto/stack | 81 cumulative ECDSA calls (18 historical + 63 new); secondary maximum 2740/6200 bytes, margin 3460; maximum crypto 595838 us. No reset/canary/allocation failure. |
| B: PC telemetry | **HOLD independently**: earlier 7.266-second timeout gap remains a strict six-second continuity failure. During these two body-test windows: 85 accepted POSTs, 87 fresh readings, zero sender failures/stale readings. |
| Overall Mission 8 | **HOLD**: receiver results retained; full image Abort/CRC-negative coverage, 48x48 deadline margin and long-term telemetry continuity remain open. R3 PARTIAL; R10 BLOCKED. |

The candidate receives images into an inert RAM sink. PASS proves native body,
digest/CRC and transaction paths; it does not claim visible cover rendering.
There is no retained signature for Abort bound to an image transaction, and no
retained enrolled private signing key to create one without changing device state.
Authenticated coverless Abort passed; authenticated INCOMPLETE Commit and existing
eight-second expiry cleaned image staging. Neither is mislabeled as image Abort.
Valid CRCs passed; the corrupt-body denial is Gate2, not a separately signed
wrong-CRC negative test. Those unexercised cases remain NOT RUN.

Body-cycle minimum continuation margin was **1936 bytes**; the first preflight
still carried the earlier 1776-byte watermark. Resource watermark resets are diagnostic
counter resets, not MCU reboots. All recorded boot identities stayed unchanged.
Across this run, heap/block minima were **10472/9336 bytes**, maximum fragmentation
27%. Settled heap did not decline monotonically over repeated replacements; the
last instantaneous 18528-byte snapshot returned to 18944 after settlement and 19024
at the final snapshot. This bounded evidence does not establish long-term leak freedom.
Final heap/block: **19024/17568**, fragmentation 8%, continuation 1936,
secondary refs/challenges/body/staging zero, receiver pending=false, image=2048
(expected retained Commit allocation), cumulative commits=11. OEM recovery GET
remained enabled with the unchanged retained OEM hash; no recovery write occurred.

The initial ignored controller paused four times on **its protected GET HTTP
401s**, with every captured sender POST accepted and every device reading fresh.
Its generic `client_error` / `REPEATED_TRANSPORT_PREVENTS_PHASE_32` label was too
broad. The fifth coverless Commit completed before its observer rejection:
the retained native frame at 13:13:51.866769 UTC reports COMMITTED, commits=4,
ECDSA=32, highest=8, no pending/body/staging/image. It remains valid receiver
evidence even though that controller did not record a settled cycle PASS.
The corrected ignored reader combines required challenge controls with snapshots
and retries only explicit rejected 401s, at most four wire requests per control.
Ten bounded reader resynchronizations occurred. No media body was retried.
Cookie metrics GETs generated no independent Digest challenge. The production
sender, cadence and six-second TTL were unchanged. These reader 401s demonstrate
shared Digest observation contention; they are not sender 401s or firmware safety
failures. The historical independent network timeout remains unresolved.

The 48x48 review used actual image-bearing 32x32 replacement cycles, not the
historical 10592-byte minimum as approval. With 2560 extra retained-image bytes
and a conservative 4096-byte SDK/allocator/TCP reserve, projected preallocation
heap/block were **16104/14336**, projected peak residual heap/block **9392/7112**.
Explicit metadata overlap is 9256 bytes and separate crypto/image overlap is
10808 bytes; mutually exclusive peaks were not added together. Memory review
therefore passed conservatively; it is not an actual 48x48 allocation measurement.

Observed post-Begin 32x32 spans were 3.953-6.360 seconds in the corrected positive
cycles. Doubling the worst last-four replacement span for ten post-Begin operations
yields a conservative **12.720-second projection against the unchanged 8-second
deadline**. This includes required controls, bounded observer authentication recovery
and terminal snapshot, not just native crypto. Deadline headroom was not demonstrated
with this client; 48x48 was held rather than blindly sending an eleven-packet
transaction. This is a qualification-client timing limit, not a measured 48x48
failure, memory failure, reset or StackThunk regression.

All prior report text and evidence are preserved below as historical checkpoints;
their old BLOCKED/NOT RUN statements are superseded only by this dated scoped result.
Machine-readable measurements, cycle resources and private log hashes are in
[stack evidence](V08_MISSION_8R_STACK_EVIDENCE.json). Only these six reports changed;
firmware/companion source and private candidate/rollback bytes were reverified unchanged.
No credentials, Authorization values, raw challenges, nonce values or private paths
are published. Starting-head PR CI passed 11/11; its duplicate push run passed 10/11
with the focused link job cancelled after stalling. Final-head offline CI is tracked
separately in Draft PR #39 and cannot close physical gates. No production provisioning,
permanent sender, Mission 9 or merge.

---

Historical checkpoints retained verbatim below.

# Mission 8 continuation: BLOCKED after a separate post-window timeout

1 October 2026. Same branch, existing Draft PR #39; no firmware operation or
sender restart. **BLOCKED: an unexplained sender timeout produced a 7.266-second
accepted-sample gap, exceeding the unchanged six-second TTL.** Media escalation
stopped. Coverless, 32x32 and 48x48 body transfers remain NOT RUN. The requested
current owner LCD observation is also pending; prior LCD reports were not reused.
R3 remains PARTIAL; R10 remains BLOCKED.

The completed cookie-only baselines, bounded Test B, nine additional real ECDSA
calls, and post-crypto three-minute soak below all passed their measured windows.
The later failure is outside those windows and is preserved separately, rather
than erased by automatic recovery. It occurred more than twelve minutes after
the last observer HTTP request at 12:13:30.313321 UTC. No diagnostic HTTP polling was
running when this timeout occurred; a later evidence watcher sent zero HTTP bytes.

| Sender attempt | Sanitized result | Completion monotonic | Retry delay | Duration |
|---|---|---:|---:|---:|
| 2543 | HTTP 200 RAM_SAMPLE_ACCEPTED | 6333.921 | 2 s | 140 ms |
| 2544 | no_route_or_timeout; no HTTP status | 6338.984 | 2 s | 3047 ms |
| 2545 | HTTP 200 RAM_SAMPLE_ACCEPTED | 6341.187 | 2 s | 187 ms |

This is a complete consecutive-attempt acceptance gap, not the earlier history
with missing attempts. The device's stale flag was **not sampled during this gap**;
the acceptance interval violates the continuous six-second freshness target.
The class does not distinguish connect/route delay from a delayed HTTP response.
It is not evidence of HTTP 401, permanently poisoned Digest state, or StackThunk
regression. Its underlying cause remains unresolved.

Recovery needed no intervention: opener generation 31 to 32, same PID 9972.
The later sanitized interface inventory still showed SHINO AP association, and
a read-only port-80 connect succeeded without sending HTTP bytes. One bounded
post-timeout device check confirmed boot 298452474, cumulative ECDSA calls 18,
fresh metrics, heap 21840 bytes and largest block 20272 bytes,
no canary/allocation failure, no staged/body/image bytes, and no receiver pending.
It used one dashboard bootstrap and cookie metrics outside any measurement window.
The post-window generation 30 to 31 transition predating attempt 2544 also implies
an earlier logical failure; its attempt/status was no longer in the bounded
history and is explicitly UNKNOWN. No exact timing or Digest attribution is inferred.

All six reports, prior failures, private evidence hashes and rollback/candidate
bytes are retained. The 446144-byte candidate stays installed. No reflash,
factory return, reboot, production/source change, TTL enlargement or sender-rate
change was made. The preliminary report commit `5cb0b50cb6afd6173f2aeced8853d57d68024372`
passed both CI runs, 11/11 jobs each; final-head CI is tracked separately in PR #39.
48x48 margin/deadline review was prepared but **not executed on image-bearing
32x32 state**. Successful crypto and the historical 10592-byte block minimum
cannot qualify the 9256-byte metadata overlap or 10808-byte crypto/image overlap.

---
Earlier Digest/crypto results and checkpoints retained below.

# Mission 8 Digest isolation and crypto qualification: HOLD

1 October 2026. Continuation from exact `07a180087a578abef5bc37689ca7ba81f6f9e561`
on `feature/shino-tv-v08-stack-remediation`, existing Draft PR #39.
**HOLD: Current LCD gate pending; no media body sent.** R3 remains PARTIAL; R10 remains BLOCKED.

The exact 446144-byte StackThunk candidate remains installed, SHA-256
`8dc18cf5135b4c7da8486d4f00bcc9b944d4bb5e4956a3f9dcbad7603ce47fea`. This investigation performed **zero firmware writes,
reboots, factory returns or sender restarts**. Boot 298452474 and tray PID 9972
are unchanged. Retained V2.1/OEM rollback hashes were reverified without modifying
the kit. Firmware and production companion source are unchanged; only ignored
research observation/qualification clients changed. No TTL or sender-rate change.

| Window | Seconds | Fresh reads | Accepted POSTs | Terminal failures | Maximum accepted gap |
|---|---:|---:|---:|---|---:|
| Test A PASS | 180.031 | 84 | 83 | {} | 2.172 s |
| Test B PASS | 20.953 | 10 | 10 | {} | 2.188 s |
| Unexercised crypto attempt: telemetry only | 15.61 | 8 | 7 | {} | 2.203 s |
| Corrected reader quiet baseline telemetry PASS | 180.031 | 84 | 84 | {} | 2.172 s |
| Test C telemetry PASS | 17.688 | 8 | 8 | {} | 2.188 s |
| Post-crypto three-minute soak telemetry PASS | 180.031 | 84 | 84 | {} | 2.172 s |

Every measured device read was fresh under the unchanged six-second TTL, with
real accepted `HTTP 200 RAM_SAMPLE_ACCEPTED` sender responses. Sender histories
were captured continuously, with consecutive attempt numbering. These counts
cover logical attempts: an internally handled wire 401 is not separately exposed
by the unchanged companion diagnostics and is not claimed absent.

The exact core's `authenticate()` compares one server-wide realm/nonce/opaque
pair. `requestAuthentication()` replaces that pair on every challenge. The single
independent protected GET in Test B produced an anonymous 401 challenge and an
authenticated 200; the pair changed from the reader's cached pair (values never
logged). No terminal sender failure or stale reading followed in that bounded
window. Thus shared challenge invalidation is demonstrated by pinned source and
physical rotation, while the precise earlier consecutive-401 race remains
unresolved. A challenge storm was not recreated. The installed overlay retains
stock legacy Digest; Mission 6C's replay-count overlay is not active.

Each reader session bootstraps one authenticated dashboard cookie, then metrics
GETs carry only that cookie, no Authorization or challenge. Passive windows do
not poll protected status/factory-return. Necessary native issue controls and
resource snapshots remain authenticated. No auth boundary is removed.

The first nine-header attempt reached only Gate 1 because the ignored client
omitted `action=` in its queries: ECDSA remained 9. Its telemetry observation
passed, **its crypto qualification did not**. That record is preserved. A second
reader failed with PermissionError before measurement/media; its exact location
was not retained. A narrow four-attempt, 50 ms diagnostic-file sharing retry was
added only to the observer. The corrected run confirmed watermark-phase advance
and actual challenge issuance before sending any further headers.

The corrected subset added **nine real ECDSA calls**, three invalid signatures
and six valid proofs; cumulative calls are 18. No body/image bytes were sent in
this subset. Native minima were 14512 bytes free heap and
12048 largest block, fragmentation max 17%,
continuation margin 2080 bytes. Secondary maximum use remains
2740/6200 bytes, margin 3460.
Latest ECDSA duration was 595622 us; cumulative maximum remains
595734 us. No reset, watchdog, canary or allocation failure.
The subsequent complete three-minute cookie-only soak also passed.

Previous telemetry stale/401 failure and every historical checkpoint remain
below. No firmware-side stale-storage failure under continuous accepted POSTs
has been demonstrated; no new permanently poisoned companion is demonstrated.
Physical qualification is bounded to exercised native inputs and concurrent PC
telemetry. No production key/provisioning, permanent media sender, Mission 9,
new branch/PR or merge. Exact final-head CI is tracked in Draft PR #39 and cannot
override a physical stop. OEM address must still be rediscovered and `/v.json`
verified before any future separately authorized `/update` operation.

---
Historical checkpoints retained below; current measured result appears above.

# Mission 8 physical resume: BLOCKED on telemetry continuity during ECDSA

1 October 2026, Europe/Paris. Resume from exact clean head
`6d52243cdfa1ea8fa3c59f08f415f922537f9490` on the existing
`feature/shino-tv-v08-stack-remediation` branch and Draft PR #39.

**BLOCKED: a physical telemetry freshness regression stopped escalation during
the ECDSA phase.** The full three-minute candidate baseline passed, but a later
device GET reported `stale:true` at 11:09:03.367 UTC (13:09:03 Europe/Paris).
At that point the companion was RETRYING after consecutive HTTP 401 failures,
already using refreshed client state. No coverless/32x32/48x48 transaction was
attempted. Candidate/source remain unchanged; no reflash or sender restart was
performed after the stop. R3 remains PARTIAL; R10 remains BLOCKED.

The current candidate is retained running for diagnosis with its supported OEM
recovery route responding. This resume performed exactly two single-attempt
application writes: verified OEM return and the exact retained candidate. There
was no rollback write or blind retry. Post-stop metrics recovered automatically
and four independent device readings were fresh, with the same boot and tray PID.
The owner confirmed today's V2.1 LCD and the candidate's initial orientation,
four updating cards and absence of artifacts. The additional post-stop LCD
observation requested in this chat is pending and is not inferred from API reads.

| Physical phase | Actual result |
|---|---|
| Current V2.1 LCD; clean branch/head; rollback/candidate rehash | PASS |
| Current V2.1 identity, fresh sender/device samples, OEM-return capability | PASS |
| V2.1 to OEM | HTTP 200 staged; exact 494144-byte retained OEM image |
| OEM rediscovery | Observed MAC on domestic LAN, then live `/v.json` identity; historical IP not assumed |
| OEM to exact StackThunk candidate | HTTP 200 Update Success; 446144 bytes; retained SHA-256 unchanged |
| Candidate boot/dashboard/four metrics/recovery | PASS; running size 446144; owner LCD confirmed normal |
| Companion continuity across OEM to SHINO | Same PID 9972; automatic recovery in 28.219 seconds after AP reconnect; no restart |
| Full pre-enrollment baseline | PASS: 185.187 seconds; 35 fresh idle-baseline readings |
| Malformed headers, unknown/expired/used challenges | Exercised cheap denials with zero added ECDSA/body work |
| Controlled test public-point validation | One key check; native secondary stack exercised |
| Real ECDSA | 9 calls completed: three wrong-signature verifications and six valid proofs; phase then stopped on telemetry |
| Coverless Begin/Commit/Abort and repeated transactions | NOT RUN |
| 32x32 and 48x48 transfers/replacement cycles | NOT RUN |

The historical test PID 6100 had ended before today's resume; the existing tray
was PID 3224. One controlled PC restart before the first write loaded the same
committed files with optional diagnostics (PID 9972). No source, credentials,
configuration or autostart setting changed, and there was one sender process.
PID 9972 remained unchanged throughout installation, baseline, crypto and recovery.

| Native resource evidence, boot/baseline/authentication subset | Measured |
|---|---:|
| Stable candidate boot identifier / reset reason | 298452474 / 4 (scheduled SDK software restart) |
| Diagnostic frames / fresh metrics / stale metrics | 75 / 74 / 1 |
| Lowest observed free heap / largest free block | 13200 / 10592 bytes |
| Highest recorded fragmentation | 29% |
| Minimum continuation-stack margin | 1776 of 4096 bytes |
| Secondary stack size / measured maximum use / margin | 6200 / 2740 / 3460 bytes |
| Secondary allocations / live refs after calls | 10 / 0 |
| Key checks / ECDSA calls | 1 / 9 |
| Maximum measured crypto / media-owner poll / service interval | 595734 / 599377 / 600255 microseconds |
| Allocation / secondary-allocation / busy / canary failures | 0 / 0 / 0 / 0 |
| Media requests / commits / image bytes | 18 / 0 / 0 |
| Final pending receiver / body bytes / staged bytes / challenges | false / 0 / 0 / 0 |

These measurements establish bounded native key/verification stack behavior for
the exercised inputs, including real ROM/core calls; they do not qualify every
crypto input, full receiver body/SHA paths, transaction cleanup or image-replacement
heap trends. Successful Gate 1 headers were intentionally closed without a body:
one bounded body allocation can occur after authentication, but body reads stayed
zero and the buffer was released. Cheap denials allocated/read no body. No persistent
heap decline is inferred from transient minima; replacement-cycle trends were not run.

The stale reading is correlated with sender acceptance, rather than attributed
to StackThunk. Accepted attempt 417 completed at monotonic 1742.546. Attempts 418
and 419 returned HTTP 401 at 1744.859 and 1747.203, with 2- and 4-second backoff.
At the stale GET the sender snapshot was RETRYING, generation 26. Its earliest
next scheduled attempt was 1751.203: an accepted-sample gap of at least 8.657
seconds, exceeding the device's six-second TTL. Thus this is not continuous
HTTP 200 RAM_SAMPLE_ACCEPTED every ~2 seconds with stale device storage. Fresh
opener state was already being rebuilt, and recovery needed no manual restart;
the previously fixed permanently poisoned opener is not demonstrated here.

The pinned SDK uses one shared server Digest nonce/opaque pair and replaces both
on each challenge. The diagnostic reader also recorded HTTP 401 near the stop.
Concurrent protected-read/POST challenge interference is a source-supported
hypothesis, not a conclusively isolated root cause. Further work must isolate
that authentication coexistence/freshness failure without another candidate write.
The retained late accepted-record spacing of 17.485 seconds has missing attempts
420–423 and is not claimed as a complete acceptance gap; the 8.657-second lower
bound is supported by the known failure/backoff schedule.

Earlier local observer attempts encountered initialization/GET HTTP errors,
including one observed HTTP 401; the other failing HTTP statuses were not retained.
No enrollment or media occurred in those attempts. Their records are preserved. The local observation helper gained bounded fresh-reader retries only
after explicit HTTP 401 rejection, retaining sanitized events/cookies; no network
failure, firmware upload or media packet is retried. Successful full baseline and
the final telemetry stop belong to the same unchanged candidate boot. No firmware
or production companion source was changed to obtain these measurements.

All prior evidence/checkpoints/PRs are preserved. The candidate BIN remains
`8dc18cf5135b4c7da8486d4f00bcc9b944d4bb5e4956a3f9dcbad7603ce47fea`;
the retained V2.1/OEM/ZIP digests pass. SHINO AP is `192.168.4.1`. Any OEM address
must be rediscovered and its live `/v.json` verified before `/update`.
The starting head's 11/11 CI in both runs remains software evidence; final report
head CI is tracked in PR #39 and does not override this physical BLOCKED result.
No production key, permanent media sender, Mission 9 work, new branch/PR or merge.

---
Historical checkpoints retained below; the current result above supersedes their pending gates.

# Mission 8 continuity gate: PC recovery PASS; current LCD observation pending

1 October 2026, Europe/Paris. Same branch and Draft PR #39, continuing exact
parent `977aed52ec9f631d532f0970faaef15fb32ebc50`. Current validated code head
`0f399dd9f435a37ab3ee751dd4751ef08f7472e9`.

**HOLD before the first firmware write: current owner LCD revalidation is pending.**
The user's Part 6 explicitly requires “revalidate current V2.1/LCD/OEM-return”.
The PC continuity gate and immediate artifact/device checks pass. The requested
current physical LCD observation has not yet arrived; it is distinct from new
installation permission. Existing Mission 8 install/qualification authorization
persists. Once that observation passes, continue directly here through supported
OEM return, exact candidate reinstall, a full three-minute baseline with the same
tray process, and then the retained crypto/coverless/32/48 sequence. No new mission,
branch, PR, private key or sender is needed. No firmware write or media request has
occurred in this continuity continuation; the device is still known-good V2.1.

The PC fault mechanism is reproduced with actual Windows Python 3.12 urllib:
interrupted Digest exchanges can bypass its success-only retry-counter reset.
After `retried > 5`, a retained stock opener rejects later authentication even
after the transport returns; fresh state succeeds. Challenge rotation alone
recovers. This proves a PC failure mode consistent with the previous restart-only
recovery, but does not identify the exact uninstrumented prior incident.

The corrected engine uses an explicit opener factory, discards HTTP/Digest state
after auth/network failure before the next scheduled attempt, and keeps successful
state. An exact-endpoint Digest subclass caches successful challenges, renews
rejected/rebooted challenges and resets recursion bookkeeping in `finally`.
Steady sending avoids anonymous repeated POSTs/shared nonce rotation. Backoff remains
2/4/8/16/30 seconds after attempt completion; no immediate retry loop or duplicate
sender process. Endpoint, JSON schema, tray states/menu, config and autostart remain
unchanged. Optional atomic diagnostics retain only the latest 64 sanitized attempt
classes, counters, client generations and timings. No credentials, Authorization,
nonce value, raw exception text, URL or private path is recorded.

| Validation | Result |
|---|---|
| Deterministic actual-urllib Digest/proof/recovery/security suite | 28 tests PASS |
| Original stock poisoned state | Reproduced; failure provenance retained |
| Fresh device challenge / interrupted auth / automatic rebuild | PASS |
| Backoff / steady-state opener retention / sanitized diagnostics | PASS |
| Initial opener-refresh-only device trials | Self-healed; two freshness soaks stopped on isolated timeout/stale reading; preserved |
| Revised client, no-flash V2.1 interruption 1 | Automatic recovery; full three-minute fresh/changing metrics observation PASS |
| Revised client, no-flash V2.1 interruption 2 | Automatic recovery; full three-minute fresh/changing metrics observation PASS |
| Process lifecycle in revised test | Same PID 6100 throughout both cycles; no manual restart |
| Firmware writes / media / enrollment / ECDSA in this continuation | 0 / 0 / 0 / 0 |
| Immediate rollback artifact rehash and V2.1/OEM GET checks | PASS at 23:08:58–23:09:04 UTC |
| Current LCD revalidation | PENDING owner observation requested in this chat |
| Candidate reinstall and candidate physical receiver qualification | NOT RUN; pending that last pre-install observation |

Cycle 1 returned to accepted telemetry in 30.109 seconds after reconnect request, without restart; client generation 6. Cycle 2 returned to accepted telemetry in 30.109 seconds after reconnect request, without restart; client generation 11.

three-minute recovery soak 1: 181.063 seconds, 35 fresh device readings. three-minute recovery soak 2: 181.625 seconds, 35 fresh device readings.

All observed revised-test metrics GETs were fresh with GPU/RAM availability and
changing CPU/GPU/RAM values; GPU temperature was available even when numerically
steady. The sender records show actual HTTP 200 RAM_SAMPLE_ACCEPTED responses,
and failures during outages/recovery remain counted. This is bounded observation,
not a claim of uninterrupted acceptance at every instant. The earlier ~8-second
accepted-sample gap explains TTL staleness and self-healed; it was not stale telemetry
while HTTP 200 acceptance continued every ~2 seconds. No firmware-only cause is
established by those PC transport failures.

Both retained CI suites passed all 11 jobs at the exact revised code head:
[PR run 36788914202](https://github.com/shinobione/SHINO-TV/actions/runs/36788914202),
[push run 36788908785](https://github.com/shinobione/SHINO-TV/actions/runs/36788908785).
The guarded native scope check permits only the explicitly named companion files
and necessary contract test. Firmware/Core/native receiver are unchanged. Candidate
BIN remains exactly 446144 bytes, SHA-256
`8dc18cf5135b4c7da8486d4f00bcc9b944d4bb5e4956a3f9dcbad7603ce47fea`;
ELF `34e67a4d3da022fd5d9581628b8e8aa51c2fa0e4273d491a73e910dd1868205e`.
No crypto stack high-water or image replacement evidence is inferred from PC tests.

SHINO's current private AP is `192.168.4.1`. Any OEM domestic LAN address must be
rediscovered and verified through live `/v.json` before each `/update` write;
historical `192.168.1.70` is never a guaranteed address. Retained review-003 V2.1,
OEM and ZIP hashes are unchanged. R3 remains PARTIAL; R10 BLOCKED. No Mission 9,
production key/media sender, firmware source change or merge.

---
Historical checkpoints and prior physical attempt preserved below.

# Mission 8 continuity continuation: PC client corrected, V2.1 gate running

1 October 2026, Europe/Paris. Continue the existing branch and Draft PR #39
from `977aed52ec9f631d532f0970faaef15fb32ebc50`. No new branch or PR.

**Current gate: HOLD before further firmware writes.** The corrected PC client
is undergoing repeated no-flash V2.1 Wi-Fi interruption/recovery and three-minute
freshness observations. No candidate reinstall, media request or ECDSA has occurred
in this continuity continuation. The reviewed 446144-byte candidate remains
byte-identical (`8dc18cf5135b4c7da8486d4f00bcc9b944d4bb5e4956a3f9dcbad7603ce47fea`).

Actual Windows Python 3.12 urllib reproduction proves a PC failure mode: network
failure inside a Digest retry bypasses the stock success-only retry-counter reset.
After enough interruptions, the long-lived opener stays at `retried > 5` and
rejects all later challenges even after the transport returns; a fresh opener
succeeds. Device challenge rotation alone succeeds. This proves a mechanism, not
the uninstrumented prior incident's exact cause.

The PC-only correction retains the endpoint, JSON schema, tray states/menu and
2/4/8/16/30-second backoff measured after attempt completion. Auth/network failure
discards the opener before the next scheduled attempt; three malformed replies
also refresh it. A per-client, exact-endpoint Digest handler reuses a successful
challenge, renews rejected/rebooted challenges, and resets urllib's recursion count
in `finally` after an interrupted exchange. The original recursion bound remains.
Steady successful POSTs avoid anonymous re-posts and shared device nonce rotation.
No global state, immediate retry loop or extra sender process is introduced.

Sanitized results distinguish accepted samples, route/timeout, refused/reset,
HTTP 401/403, other HTTP, malformed response, invalid sample and client error.
Optional diagnostics contain only the latest 64 attempts, client generations,
counters and timing; no credential, Authorization, nonce value, URL, exception
text or private path is logged. Existing configuration/autostart is unchanged.

The initial opener-refresh correction recovered automatically from two deliberate
45-second disconnections in the same tray PID, with accepted telemetry returning
after the backoff. Both attempted freshness soaks later encountered isolated
sender timeouts and a stale reading, then self-healed without restart. An observed
~8-second gap between accepted samples exceeded V2.1's 6-second TTL. This was not
staleness while HTTP 200 acceptance continued every ~2 seconds. Those failed
soaks remain preserved, and do not satisfy the reinstall gate. The endpoint-bound
Digest correction is now being tested in a new single process, loaded once before
the test. No process is restarted during network recovery.

Deterministic focused suite: 28 tests PASS, including actual urllib Digest hashes,
historical poisoned state, fresh device challenge, automatic refresh, backoff,
steady-state client retention, sanitized errors and retained legacy bridge contract.
The first PC-fix commit `0a3f2ed8007f742b64915a600c0ca4cef591d80c` passed all 11 jobs
in [PR CI](https://github.com/shinobione/SHINO-TV/actions/runs/36787400691) and
[push CI](https://github.com/shinobione/SHINO-TV/actions/runs/36787395364).
The latest Digest correction must pass its own exact-head CI and physical gate.
Firmware/native receiver/Core and candidate bytes remain unchanged. The native
scope guard adds only named companion files and their necessary contract test.

Only after repeated V2.1 recovery and immediate rollback/LCD/OEM checks pass may
the already-authorized candidate reinstall proceed. Then the complete three-minute
candidate baseline must pass before enrollment/ECDSA, followed directly by the
retained crypto/coverless/32/48 sequence. R3 PARTIAL; R10 BLOCKED. No Mission 9,
production key, new media sender or merge.

---
Historical physical attempt and recovery record at 977aed52 preserved below.

# Mission 8 pinned StackThunk: installed, baseline stopped, V2.1 restored

1 October 2026, Europe/Paris (30 September UTC). Existing branch
`feature/shino-tv-v08-stack-remediation`, Draft PR #39. Installed source
`432263feb139c7af2fecc0ecaa0c348b05304914`; pre-install clean documentation head
`979d2ff3900523a8a46d4fd86677326b515867c2`.

**BLOCKED — physical telemetry continuity failed during the boot baseline.**
The exact StackThunk candidate was installed and booted, but qualification stopped
before any media request, public-point enrollment or ECDSA. Three authenticated
metrics GETs reported `stale:true`; the owner confirmed the LCD numbers had stopped
updating. This is an observed continuity failure with unresolved cause, not a
physical crypto-stack overflow finding or a renewed static ROM UNKNOWN gate.

The documented OEM → retained V2.1 rollback completed. V2.1 reports 405,712 bytes;
dashboard and exact OEM recovery capability respond. Restarting the existing
SHINO // LINK metrics tray companion, with configuration/autostart unchanged,
restored fresh changing telemetry at 22:13:52–22:13:57 UTC. The owner confirmed restored LCD orientation and all four updating cards
are normal, without artifacts. Qualification did not resume after the failure. R3 remains PARTIAL,
R10 BLOCKED; no production key, media sender, Mission 9 work or merge.

SHINO uses its private AP at `192.168.4.1`. The historical OEM LAN address
`192.168.1.70` is never a fixed assumption: after each factory return, the observed
device MAC `c4:d8:d5:10:7e:f0` was matched in LAN neighbors, and live `/v.json`
confirmed `SmallTV-Ultra` / `Ultra-V9.0.44` before `/update`. The actual firmware
form used multipart field `firmware`, POST to its current `/update` URL.

| Physical phase | Result |
|---|---|
| Immediate rollback rehash, V2.1 dashboard/metrics/OEM, owner LCD | PASS at 22:02:51–22:02:56 UTC |
| V2.1 → OEM factory return | HTTP 200 staged, 22:03:13–22:03:24 UTC |
| Live OEM model/version and update form | PASS at 22:04:01 UTC; observed MAC reachable |
| OEM → exact StackThunk candidate | HTTP 200 Update Success, 22:04:13–22:04:21 UTC |
| Candidate AP/dashboard/OEM return | PASS; actual running bytes 446,144 |
| Boot with media untouched | Unenrolled, zero crypto allocations/calls, no body/image/staging |
| Candidate LCD | Owner confirmed correct orientation/four updating cards initially |
| Real PC telemetry POST | HTTP 200 RAM_SAMPLE_ACCEPTED at 22:06:51 UTC |
| Three-minute idle baseline | NOT COMPLETED: client read auth failed after ~5 seconds of baseline |
| Later telemetry continuity | FAIL: stale at 22:08:22, 22:08:23, 22:08:25 and 22:09:40 UTC; owner confirmed frozen numbers |
| Crypto/authentication/coverless/32/48 | NOT RUN; zero media requests, key checks, ECDSA calls or allocations |
| Candidate → OEM recovery | HTTP 200 staged, 22:10:46–22:10:57 UTC |
| Recovery OEM rediscovery | First bounded GET timed out at 22:11:12; live identity/form passed at 22:11:38; no write retried |
| OEM → exact retained V2.1 | HTTP 200 Update Success, 22:11:49–22:11:57 UTC |
| Restored V2.1 telemetry | Fresh changing device readings after restarting existing metrics companion |

All four application writes were single attempts with exact locally rehashed
bytes; all succeeded. Each supported updater scheduled an intentional reboot.
The candidate boot identifier remained `3667675469` with monotonically increasing
uptime before rollback. Reset reason `4` was reported (pinned SDK software restart);
no unexpected reset, watchdog, boot loop or canary event was observed. Continuation
watermark reset actions repaint instrumentation; they do not reboot the device.

The first local client stop was HTTP 403 because it omitted authenticated GET `/`
to obtain the required browser metrics cookie. Source and independent live reads
confirmed that client precondition error, with unchanged boot/no media; the helper
was corrected and its original stop record retained. A later protected GET failed
with HTTP 401 `digest auth failed`; subsequent independent GETs succeeded but
telemetry was stale. Firmware, diagnostic-client Digest behavior and the existing
sender have not been isolated as the cause. Restoring V2.1 did not by itself
restart continuous metrics; a single real sample succeeded, and restarting the
already running metrics companion restored continuity. That recovery does not
qualify the candidate or establish a firmware-only regression.

| Candidate observation before rollback | Measured value / limit |
|---|---|
| Minimum free continuation stack after pinned phase repaint | 2,080 bytes of 4,096 |
| Minimum free heap across recorded diagnostic minima | 16,336 bytes |
| Minimum largest free block across recorded diagnostic minima | 16,240 bytes |
| Maximum recorded diagnostic fragmentation | 22% |
| Maximum observed media-owner poll / service interval | 34,886 / 65,582 microseconds |
| Secondary size / allocations / references / measured use | 6,200 / 0 / 0 / NOT EXERCISED |
| ECDSA/key checks/SHA timing | Zero calls; latency NOT MEASURED |
| Allocation/busy/canary failures | 0 / 0 / 0 reported |
| Receiver pending/body/staged/image/challenges | false / 0 / 0 / 0 / 0 |

These are bounded boot/legacy observations under diagnostic HTTP load, not a
completed idle soak, whole-firmware stack proof, heap trend across transactions
or crypto high-water proof. In particular, unallocated secondary usage `0` and
numeric margin `6200` do not constitute measured crypto margin. No image cycle
was completed, so replacement leaks/fragmentation remain unqualified.

Private candidate: BIN 446,144 bytes, SHA-256
`8dc18cf5135b4c7da8486d4f00bcc9b944d4bb5e4956a3f9dcbad7603ce47fea`;
ELF SHA-256 `34e67a4d3da022fd5d9581628b8e8aa51c2fa0e4273d491a73e910dd1868205e`.
Text/data/BSS: 439207/2840/32704. Authority/Ingress/Receiver: 2104/1432/1120.
Main stack 4096; secondary 6200. Lifecycle B frees secondary crypto before
body/JSON/image; explicit receiver peak 9256 and previous-image+crypto 10808
exclude SDK/TCP/allocator overhead and remain physically untested.

## Exact pinned Core and checked allocation

The installed package is framework-arduinoespressif8266 3.30102.0 / Core 3.1.2
under espressif8266 4.2.1. Eight exact local Core hashes, including every requested
file, are in [the manifest](../tools/v08_m8r_core_manifest.json) and are checked
before the build and linked analysis. No upstream/master substitution is used.
Pinned StackThunk.cpp explicitly describes its secondary stack as supporting
BearSSL's large stack demand. `_stackSize (6200/4)` gives 1,550 words / 6,200 bytes.

Stock `add_ref` increments ownership, chooses DRAM, mallocs 6,200, aborts on null,
sets top to pointer+1549 and save to null, then paints 0xdeadbeef. Stock `del_ref`
decrements and, at zero, frees and nulls pointer/top/save. `repaint` paints every
word; `get_max_usage` scans from the bottom and returns the used painted range,
or zero when unallocated. The exact `make_stack_thunk` saves a 16-byte continuation
frame, loads the secondary top into a1 before the native call, checks the bottom
canary through the stock fatal handler, and restores a1/registers before return.
A canary failure resets; a post-return zero counter cannot prove no prior reset.
Boot nonce, uptime and reset reason must therefore be monitored across phases.

The isolated LGPL-derived adapter changes ONLY acquisition policy: ownership is
rejected if busy; heap and largest block are checked; DRAM malloc is checked;
global fields/refcount are set only after success. Null returns false, increments
a failure counter, and executes zero ECDSA/body work. No stock add_ref call,
boot allocation, global allocator replacement, Core edit or enlarged continuation
stack is introduced. Stock layout, thunk assembly, paint/scan, fatal handler and
del_ref are retained. The precheck is not proof of malloc success: allocator
overhead is handled by the actual checked result. Allocation failure is a physical
STOP even though authentication fails closed.

Chosen provisional lifecycle B allocates/repaints immediately around each proof
or controlled test-key validation, samples usage before release, and releases
before any media body/JSON/image work. Lifecycle A would retain 6,200 through the
9,256-byte receiver peak (15,456 explicit bytes); B avoids that overlap. B can
still overlap an existing 4,608-byte committed image during proof (10,808 bytes).
These are explicit object arithmetic, excluding allocator/SDK/request overhead;
repeated target readings, not arithmetic, must decide whether B is acceptable.
No lifecycle is physically qualified yet.

## Linked boundaries and instrumentation

Parser/poll return before Proof. The noinline owner proof calls checked acquire,
thunk, and release in that order. Exact candidate disassembly proves the SP switch
before raw i15/m31 crypto and restoration before return. Both verify and point
validation wrappers are linked in the active private candidate. No parser, socket,
JSON, image or display call is put on the secondary stack. The post-proof admission
and checked body allocation block is decoded from its linked branch target;
linear Xtensa disassembly can lose alignment at inline padding. Source guards and
host denial/revocation tests establish the successful-proof condition as well as
address order. The known EC chain remains 720+272+592+304+336 = 2,224 bytes, now on
the secondary stack, plus a 32-byte native verification wrapper. ROM helper bodies
remain unavailable; they are inside the switched chain and their target high-water
is now the required evidence. Receiver/JSON/allocator whole-path maxima remain
UNKNOWN and must be paired with physical continuation measurements.

`ESP.getFreeContStack()` calls the pinned cont paint scan; reset calls cont repaint.
The latter paints only below current SP minus 64 bytes, so the qualification route
defers reset until the shallow loop returns from HTTP processing. Each phase reads
back completion. Resource samples include active crypto allocation, body, JSON
arena, image staging and owner-loop completion. A qualification-only Digest route
exports bounded counters and measurements through a fixed 2,048-byte JSON buffer.
It exposes no credentials/private key. A single controlled test public point can
be enrolled after boot; synthetic fixed epoch and volatile issue are qualification
seams, not production provisioning or an R3/R10 completion.

The one-shot fixture process discards its ephemeral private key and retains only
public point/signed packets locally. The temporary device controller remains in
ignored research-local; it is not a permanent companion sender. The DisplaySink
continues to own its committed image without LCD rendering; transfers qualify the
receiver and dashboard coexistence, not a new NowPlaying screen feature.

## Exact private install candidate and checks

Private `qualification_compile` BIN **446,144 bytes**,
SHA-256 `8dc18cf5135b4c7da8486d4f00bcc9b944d4bb5e4956a3f9dcbad7603ce47fea`; ELF SHA-256 `34e67a4d3da022fd5d9581628b8e8aa51c2fa0e4273d491a73e910dd1868205e`.
Text/data/BSS **439,207 / 2,840 / 32,704**.
Main continuation 4,096; secondary 6,200. Native fixed Authority/Ingress/Receiver
**2104 / 1432 / 1120** bytes.
Image/body/JSON explicit allocations are at most 4,608 / 552 / 4,096 bytes.
The fixed diagnostic buffer adds 2,048 BSS bytes, plus counters and the public point.
The retained matching private policy is copied only into ignored build shadow.
No BIN/ELF/private policy or credentials are committed/uploaded. Esptool confirms
DIO, 4 MiB, 40 MHz and a valid image checksum. Retained pairing and 4m3m geometry
checks pass; both modeled hops have a 106,496-byte gap and zero inferred stock-FS
staging overlap. Actual OEM updater behavior and nonbooting recovery remain unproved.

Both focused OEM configurations pass **1,065 checks, zero failures**, with all
247/247 and 249/249 owner contexts cleaned and zero live descriptors. Wire-v2
**10,207 cases** and header profile **37 cases** agree with retained host behavior.
Coverage includes public/synthetic P-256, wrong signature, unknown/used/expired
challenge, revocation between parse/proof, R1/R2/R4, allocation denial before
ECDSA/body work, Begin/Tile/Commit/Abort, Mission 6A contention, actual legacy
dashboard/four metrics and conditional OEM multipart. All three guarded public
native profiles link, and 4,096/6,144 comparison profiles pass isolation analysis.
The 6,144 sensitivity profile remains excluded from installation.

Physical installation, stop and rollback evidence is recorded above and in the other five Mission 8 documents. Native crypto high-water and image phases were not exercised.

Clean committed validation at `432263feb139c7af2fecc0ecaa0c348b05304914`: both focused configurations pass;
both PR and push CI runs pass all **11 jobs**. A clean-head rebuild produces
byte-identical private ELF/BIN; public and private isolation analyses pass.
One-shot offline checks verify all 202 signed packets and 190 receiver records
across 30 coverless/32/48 groups. This does not substitute for target measurements.
CI: [PR run](https://github.com/shinobione/SHINO-TV/actions/runs/36779971808),
[push run](https://github.com/shinobione/SHINO-TV/actions/runs/36779968038).

---
Historical records preserved below; their gates and zero-contact statements describe those earlier runs.

# Mission 8R: stack remediation and qualification gate

30 September 2026, Europe/Paris. Exact parent:
`5179eb04ea51c2a92c7f796f07ebb963e2167e00` (Mission 8 / Draft PR #38).
Branch: `feature/shino-tv-v08-stack-remediation`.

**Final engineering gate: BLOCKED before installation.** The known linked EC
chain is reduced from 4,384 to **2,224 bytes**, and parsing returns before ECDSA.
This is a verified improvement, **not a complete stack-fit PASS**. The actual
linked m31 multiplier calls ROM `__umulsidi3` at `0x4000dcf0`; its instruction
body and stack bound are absent from the retained ELF and pinned Core sources.
ROM `memcpy` and `memset` are also reachable. Full owner, JSON, allocator and
receiver bounds remain UNKNOWN. The user's explicit UNKNOWN rule prohibits
installation. No Mission 8R device contact or write occurred.

## Remediation evaluated in the requested order

**A1: separate lifetimes.** A new bounded `Proof` state stores the signature
digest and prechecked challenge slot. Header parsing finishes and returns from
the noinline poll. The existing single owner invokes noinline `verifyHeaders`
on a later service call. Neither parser nor poll remains live during ECDSA.
The verification phase has no client reference and cannot read body bytes.
Challenge precheck runs again before ECDSA; slot, serial, principal revision
and epoch must still match. Final consume uses a fresh clock after verification.
Admission and the absolute 2,000 ms deadline are rechecked before body allocation.
Splitting alone cannot repair the inherited **crypto-only 4,384-byte** excess.

**A2: bound large objects without new scratch allocations.** Signature digest
32 bytes plus slot 4 bytes move into the fixed Ingress owner; alignment makes
the native Ingress increase **40 bytes**, from 1,384 to 1,424. This state lives
for the receiver object's lifetime, is reset on begin, becomes unreachable on
terminal phase, and is overwritten before reuse. It cannot fail allocation.
It coexists with the existing bounded buffers; no additional heap scratch is
introduced. `metadata` and `receive` are noinline so the 552-byte Metadata
automatic is not merged into the poll frame. No unbounded container replaces
an automatic. The Begin parsed Metadata still lives on stack; that path's
complete nested bound remains UNKNOWN.

**A3: use an existing pinned implementation.** The precompiled Core archive
exports m15/i15, not m31/i31. The exact pinned Core package nevertheless ships
the public `br_ec_p256_m31` API and unmodified `src/ec/ec_p256_m31.c`. The new
project compiles that exact source with its pinned inner/config headers, checks
its SHA-256, and passes its EC table to the same SDK
`br_ecdsa_i15_vrfy_raw`. SHA-256, P-256 and raw 64-byte r||s are unchanged.
Point validation uses the same table. Public retained and synthetic vectors
pass. The object is named `ec_p256_m31.c.o` to use the Core's existing `*.c.o`
flash placement rule; an ordinary `.o` consumed IRAM and failed the link. No
SDK source, assembly, algorithm, partition or linker script was changed.

**A4: inspect and measure, do not select a larger constant.** `cont.h` guards
its 4,096 default with `#ifndef CONT_STACKSIZE`; project build flags can override
it consistently in Core compilation. The disabled `stack_sensitivity_compile`
comparison uses 6,144 solely to measure a +2,048-byte change, not as a selected
safe value. Both full graphs link. Actual `app_entry_redefinable` frame changes
**4,160 -> 6,208 bytes**; text/data/BSS/BIN sizes remain identical. The pinned
Core allocates `cont_t` on SYS's DRAM stack, not a heap allocation or BSS array.
Its own explanation describes reclaiming roughly 4 KiB and warns that SDK
features can use that region. A larger SYS reservation has no established
capacity proof here. Static heap figures therefore do **not** prove spare SYS
stack or a target heap margin. No target heap delta was measured or invented.
The existing Core secondary BearSSL stack instead allocates 6,200 DRAM heap
bytes and aborts on allocation failure; it was not selected. The chosen phase
split/m31 candidate retains **4,096**, with no Core or assembly patch.

## Actual linked evidence and remaining blocker

The address-keyed analyzer reads the actual ELF, `nm -S` function extents,
instruction prologues, direct calls, literal-backed indirect calls, and the
linked 28-byte EC table. It excludes trailing literal pools from function
instruction inventories. It resolves offset 24 to the actual m31 `api_muladd`
and verifies each edge below. It asserts that parse and poll no longer call
the raw verifier and that `verifyHeaders` does. Compiler `.su` files are only
supplementary resource evidence.

| Reachable EC path | Linked frame bytes |
|---|---:|
| SDK raw i15 verifier | 720 |
| m31 `api_muladd` | 272 |
| m31 `p256_mul` | 592 |
| m31 `p256_add` | 304 |
| m31 `mul_f256` | 336 |
| Accounted EC chain subtotal | **2,224** |
| `verifyHeaders` frame, preceding this chain | 128 |
| `handleClient` / FirstBoot loop / loop wrapper | 48 / 16 / 16 |
| App `loop` tail adapter / continuation wrapper | 0 / 0 |
| Accounted normal owner + EC prefix | **2,432** |

The last subtotal excludes ROM multiplier/copy/clear bodies and other branches;
**1,664 bytes is not a proven spare margin**. The m15 `mul20` assembly frame is
no longer on this selected EC chain. The replacement's multiplication helper
is now an important **ROM assembly UNKNOWN**, not an assumed zero-frame leaf.
Pinned `eagle.rom.addr.v6.ld` proves its name/address, not its implementation.
Obtaining a target ROM dump would require device contact while the gate fails,
which the mission prohibits. Adding private probes or global ROM replacements
would broaden this bounded remediation without proving the complete gate.

| Important path | Accounted evidence | Complete maximum |
|---|---|---|
| Continuation/loop/owner | Actual entry and owner frames; cont assembly switches SYS/continuation stack | UNKNOWN; callbacks and switched contexts require full bounds |
| Header/profile | poll 208, parse 736; no nested ECDSA | UNKNOWN; formatting, ROM/string calls and clock callback |
| Gate 1 | verification 128 + EC 2,224; actual EC table and multiplier calls | UNKNOWN; ROM `__umulsidi3`, memcpy/memset and admission/clock/allocation branches |
| SHA update | linked update 48 -> compression 384, known chain 432 | Full enclosing request path UNKNOWN |
| SHA final | output tail -> finalizer 128 -> compression 384, known chain 512 | UNKNOWN; reachable ROM copy/clear |
| Gate 2 | poll 208, wire and admission; actual body SHA calls | UNKNOWN; complete owner/ROM/client bounds |
| Begin | receive 640 -> metadata 400; JSON nesting explicitly capped at 2 | UNKNOWN; JSON recursion and virtual arena callbacks need context-sensitive bounds |
| Tile | same noinline receiver, bounded 512-byte copy and conflict cleanup | UNKNOWN; ROM and allocator/cleanup bounds |
| Commit | receiver, final image SHA and unique ownership move | UNKNOWN; ROM SHA/cleanup bounds |
| Abort/expiry/revocation | terminal releases staging and sink | UNKNOWN; allocator/cleanup bounds |

No unconstrained sum of all SDK branches, recursion, abort/reset paths or data
decoded as instructions is presented as a valid maximum. JSON and allocator
inventory is evidence of work remaining, not proof that those paths exceed
4,096. Increasing the stack cannot turn an unknown maximum into a proof.

## Resource accounting

| Bytes | Retained M7 local media | M8R selected 4 KiB | Delta |
|---|---:|---:|---:|
| ELF text | 427,771 | 427,907 | +136 |
| ELF data | 2,792 | 2,792 | 0 |
| ELF BSS | 30,456 | 30,488 | +32 |
| BIN | 434,656 | 434,800 | +144 |
| Authority | 2,104 | 2,104 | 0 |
| Ingress | 1,384 | 1,424 | +40 |
| Receiver | 1,120 | 1,120 | 0 |

The independently linked unchanged legacy comparison is text 394,647, data
1,672, BSS 26,960, BIN 400,416. New media deltas versus that comparison are
33,260 / 1,120 / 3,528 / 34,384. BSS delta need not equal an individual object's
size delta because linked padding/layout changes. Server remains 424 bytes in
media and 416 in legacy. Native `sizeof` comes from ELF symbols; the MSVC host
sizes differ with 64-bit pointers and are not used for target RAM budgets.

Explicit heap buffers are unchanged: body 40..552, JSON arena 4,096, one image
0/2,048/4,608 bytes. Maximum replacement overlap is old 48x48 sink image + new
Begin body + temporary arena = **9,256 bytes**, excluding allocator/TCP/SDK/
graphics and stacks. Arena dies before new staging. A checked body allocation
failure rejects and frees on terminal; checked arena allocation/overflow rejects
metadata; checked staging failure calls terminal cleanup. Tile/Commit/Abort
terminal paths release owned buffers; Commit transfers ownership without a
second image allocation. These are explicit bounds, not total target peak RAM.

Compared with retained review-003 V2.1 BIN 405,712, this guarded public BIN is
29,088 bytes larger. Policy/startup/instrumentation differ, so that comparison
does not establish an equivalent V2.1 feature cost or OEM upload acceptance.
Local selected ELF SHA-256:
`269783955c3e0b9b2de26fa47e1177f2a6fb319a9e691b1e3178df71ddbbd9a1`.
BIN SHA-256:
`dec8669d412e29c1c800e560f45cd63fd84496c5453a7147b912603c38b06abc`.
**434,800 bytes; startup disabled, epoch zero, inert public policy, not an
instrumented installation binary.** No BIN is committed or uploaded.

## Regression and physical gates

Focused tests passed before dispatching the full retained CI suite. On MSVC,
each default/OEM native composition passed **1,047 checks**, zero failures,
246/246 default and 248/248 OEM contexts, zero live descriptors. The retained legacy portions passed
224 / 227 checks. The wire differential passed 10,207 cases (one admit); profile
1.1 passed 37 cases (seven admits). Maximum socket work remained 64 bytes/poll.
The expanded tests stop at the new Proof boundary and independently revoke,
expire, rotate the same key, advance epoch or expire the ingress deadline;
all deny before ECDSA/body allocation/body reads/receiver mutation.

Inherited real public P-256 vectors, R1 revocation, R2 literal STV7, R4 cheap
challenge denial, Begin/Tile/Commit/Abort, >30 ms contention, 2,000 ms/wrap
deadline, dashboard/four metrics and authorized conditional OEM multipart pass.
The legacy parser is still exactly the Mission 6A handoff; Mission 6C multipart
denial is not substituted. Host timing is not ESP8266 ECDSA latency or LCD proof.

Local rollback files were rehashed at **19:11:50 UTC / 21:11:50 Europe/Paris**:
exact V2.1, OEM and original ZIP pins unchanged. Previous live M8 GETs and the
owner's LCD/four-card confirmation are preserved, **not refreshed device proof**.
Part D's immediate live revalidation is NOT RUN because Part B does not PASS.
Parts E/F are NOT RUN: no activated instrumented build, install, reboot,
baseline, physical invalid/valid auth, coverless, 32x32 or 48x48 escalation.
No recovery was attempted. No device success or incident resolution is inferred.

R3 remains **PARTIAL**; R10 remains **BLOCKED**. No production key/provisioning,
permanent sender, public deployment, merge or Mission 9 work was introduced.
Historical PRs #29–38 and their files are preserved. The separate Draft PR
contains a candidate improvement and a reproducible **blocked** static gate.
Green CI means regression and UNKNOWN stop evidence reproduce, not permission
to install. Qualification can resume within the existing authorization only
after complete static bounds and the exact instrumented installation gate PASS.

Reproduce with `pio run -d experiments/v08_m8r -e legacy_compile -e media_compile
-e stack_sensitivity_compile`, then `python tools/v08_m8r_runner.py` with the
pinned ArduinoJson source, and `python tools/v08_m8r_stack.py`. The sensitivity
analyzer adds `--environment stack_sensitivity_compile`. Source hashes, native
addresses, local resources and regression results are retained in
[stack evidence](V08_MISSION_8R_STACK_EVIDENCE.json). Historical M7/M8 CI jobs
remain pinned to their own exact heads; all retained jobs remain enabled.
