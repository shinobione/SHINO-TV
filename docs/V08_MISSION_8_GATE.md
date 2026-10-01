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

The two evidence windows are 13:13:02.952129-13:14:54.538500 UTC (111.578 s,
51 accepted POSTs / 52 fresh readings) and 13:25:02.302362-13:26:19.668988 UTC
(77.359 s, 34 accepted POSTs / 35 fresh readings). Maximum accepted interval was
2.797 seconds in each. Captured rolling history also contains pre-window samples;
it is not counted as extra measured duration. Continuity between the windows is
not claimed. CPU, GPU and RAM values changed; GPU TEMP remained fresh at 43 C.
No temperature change is invented. The earlier timeout gap and all historical
failures below remain intact; successful independent receiver phases survive them.

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

# Mission 8 engineering gate: BLOCKED on telemetry continuity

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

Retained local rollback artifacts are unchanged:

| Image | Bytes | SHA-256 |
|---|---:|---|
| V2.1 review-003 | 405712 | `3252ba5cd1f85683945d4d9a87ce49118568c0977605debc089267f54d7f3b0e` |
| OEM V9.0.44 application | 494144 | `a6421f5bfee7860d97bed26620c346b8008f503e513702d4bfdf6e01010a7718` |
| Manufacturer ZIP | 349377 | `cfbef50754ec552f9791878931c5f3643734de15f3c81cebdecf7ce05b28230f` |

Kit: `C:\Users\jerry\SHINO-PRIVATE\review-003`. The recovery was exercised
successfully for this responsive application. This is application-only rollback;
no full owner flash/filesystem restoration, power-cut safety or nonbooting rescue
is established. Private images, credentials, policy, one-shot packets and device
controllers remain ignored/local. No additional firmware writes followed recovery.

Source/host/linked gates remain PASS: both focused OEM configurations pass
1065 checks with zero failures, 10207 wire cases and 37 profile cases agree;
202 signed packets / 190 receiver records were checked offline. Clean source
head `432263feb139c7af2fecc0ecaa0c348b05304914` rebuilds the same private bytes.
Pre-install head `979d2ff3900523a8a46d4fd86677326b515867c2` passes all 11 jobs in
[PR CI](https://github.com/shinobione/SHINO-TV/actions/runs/36781108025) and
[push CI](https://github.com/shinobione/SHINO-TV/actions/runs/36781102151).
CI proves retained software checks; physical qualification remains BLOCKED.

---
Historical records preserved below; their gates and zero-contact statements describe those earlier runs.

# Current Mission 8 / 8R engineering gate

**BLOCKED — complete native stack prerequisite remains UNKNOWN.** Mission 8R
implements a separate Proof phase and evaluates unmodified pinned m31 crypto.
The known EC chain falls to 2,224 bytes; the actual ROM multiplier body and
full owner/receiver bounds are still unproved. No installation is authorized
by this result. Local focused regressions pass; retained CI is configured to reproduce the
blocked static gate and cannot establish physical qualification. M8R device
contacts/writes are zero; Parts D-live, E and F are NOT RUN. R3 remains PARTIAL,
R10 BLOCKED. Historical PRs #29–38 remain preserved. The physical authorization
persists, conditional on complete static and rollback gates passing; no new
mission is required to resume once safe. See [M8R report](V08_MISSION_8R_STACK_REMEDIATION.md)
and [evidence](V08_MISSION_8R_STACK_EVIDENCE.json).

---
Historical Mission 8 record (preserved):

# Mission 8 review gate

30 September 2026, Europe/Paris. Exact parent
`84129daa7359c73e738272b1c01131b3292dc315`.
Branch `feature/shino-tv-v08-device-qualification`.

**Final engineering status: BLOCKED before installation.**
The actual linked ECDSA/SDK path reserves at least **4,384 bytes** against a
**4,096-byte** continuation stack. The nested receiver + crypto path is at least
**5,904 bytes**, excluding owner/loop/entry overhead. This is a concrete static
fit failure, not an arbitrary heap threshold or an observed physical crash.

| Gate | Result |
|---|---|
| Exact clean start / separate branch | PASS at Mission 7 head |
| Mission 7 report/resource/matrix/gate read | PASS; historical evidence unchanged |
| PRs #29–37 | PASS live verification: all preserved OPEN/Draft |
| Actual installed lineage | Consistent with retained V2.1 review-003: exact size, matching Digest credentials, heap schema and capabilities; no device SHA/version label exposed |
| Physical baseline LCD / four metrics | PASS limited baseline: direct owner observation plus two fresh changing device GET readings |
| Local rollback artifacts | PASS: exact V2.1 and OEM bytes/hashes verified; no modification |
| Current OEM factory-return capability | PASS read-only: exact pinned identity and `write_enabled:true`; no rollback write |
| Instrumented Mission 8 candidate | NOT BUILT; early linked-stack precondition failed |
| Inherited app flash fit | Arithmetic PASS, not final candidate fit or OEM acceptance |
| Inherited native stack fit | **BLOCKED** from actual linked prologues, call edges, SDK assembly and continuation size |
| Installation / normal reboot / recovery | NOT RUN; stopped before first write |
| Several-minute candidate baseline | NOT RUN |
| Authentication-only physical qualification | NOT RUN; no ESP8266 ECDSA latency/body-denial proof |
| Coverless / 32x32 / 48x48 repetitions | NOT RUN; zero physical transfers |
| Heap/fragmentation/allocation/cleanup/UI margin | HOLD for future safe candidate; existing saturated V2.1 observer is not candidate evidence |
| R3 freshness | PARTIAL; no persistent freshness primitive introduced |
| R10 production provisioning | BLOCKED; no production private key/provisioning/sender introduced |
| Merge / public deployment / Mission 9 | Not performed |

This mission made its first authorized physical **GET-only** device contact.
It did not qualify a native media receiver on hardware and is not a production
GO. Local full links and the static negative gate are reproducible. The new CI
job executes the Mission 8 review head and expects proof of the **BLOCKED**
static result; green CI means the stop evidence is reproducible, not safe to
flash. Mission 7's own lab is preserved at its exact historical head because its
runner enforces Mission 7's allowed diff. All other retained jobs remain.

See [device qualification](V08_MISSION_8_DEVICE_QUALIFICATION.md),
[runtime/resources](V08_MISSION_8_RUNTIME_RESOURCES.md),
[recovery log](V08_MISSION_8_RECOVERY_LOG.md),
[sanitized device evidence](V08_MISSION_8_PREFLIGHT_EVIDENCE.json), and
[linked-stack evidence](V08_MISSION_8_STACK_EVIDENCE.json).

No automatic reviewer approval or attestation is fabricated. Stop at this Draft
review gate. The blocker requires an explicitly reviewed stack/memory change
before resuming instrumented build and physical qualification. The current
SmallTV, rollback packages, frozen V2.1 source, production firmware, SHINO LINK
and earlier PRs/evidence remain preserved.
