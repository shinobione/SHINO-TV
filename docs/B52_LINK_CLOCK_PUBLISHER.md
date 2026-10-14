# B5.2 LINK clock publisher — owner review, 14 October 2026

**READY_FOR_OWNER_REVIEW — PC software/HOST evidence only.** Development branch
`codex/b52-link-clock-publisher`, isolated from PR48 at
`372d20f934db9bbd6b7c0ecbb784d57f40c393d5`. Frozen B5.1/PR47 remains
`244334edac07701dc25b5ffc494715152ae1bfa5`. No commit, push, merge, external
network access, device contact, private-file read or firmware build occurred.
PR/CI was not refreshed over the network in this offline mission.

## Bounded integration

- Default **OFF**. Only `--run`/`--tray` accept `--clock-b52-host`; the argument
  asserts that the owner already verified B5.2 at that exact configured IPv4.
  Mismatch/public/invalid addresses are refused before credentials/network.
  This is an out-of-band owner assertion, not a firmware identity measurement.
  There is no automatic probe of the currently installed B5.1.
- One existing worker collects and publishes the unchanged four metrics and
  invokes **only `publish_clock()`** for the clock. No new sender thread,
  listener, endpoint, generic authentication layer or persisted option.
  The clock transport's existing deadline Timer only closes its sockets.
- Initial sync follows a fresh successful metric ACK. Later opportunities are
  at least **60 seconds after completion** of the last clock operation. This
  leaves half the maximum120s lease for a delayed future opportunity. A failed
  metric prevents clock work; after reconnection, an initial fresh operation
  may be eligible. Unknown/unsupported/retarget holds remain latched.
- Clock needs **1.25s of remaining slack**, rechecked after creating its fresh
  transport. It never moves the next metric deadline: the existing2s delay
  after the metric exchange and2/4/8/16/30s failure backoff remain unchanged.
  It makes one zero-wait attempt at the existing interprocess Digest lock.
  Busy means no clock GET or POST. A pre-POST/source failure waits for the next
  periodic opportunity and builds an entirely fresh operation; no request or
  frame is saved for retry.
- The existing **1.0s total exchange deadline**, maximum3 HTTP requests
  (one unauthenticated GET, one Digest GET, one preauthenticated POST), and
  **one POST** limit are preserved. No POST refresh/retry, including401 or
  missing/unknown response. Such outcomes suspend clock until an explicit new
  companion session; metrics keep running. Missing404/405 or incompatible
  protocol/disabled clock suspends before any POST.
- Every operation constructs a fresh `ClockTransport`, obtains current boot
  and challenge, then samples UTC and OS local offset. No challenge, boot,
  frame or transport is retained by the publisher. A changed LAN target
  latches `CLOCK_TARGET_REVERIFY_HOLD`, including a return to the old address.
  Metrics retarget normally; clock requires a new explicit verified session.
- Core Digest has a mutable shared challenge. After a clock exchange, LINK
  discards its metric opener so the next scheduled metric obtains a fresh
  challenge. Busy coordination does not invalidate the metric cache. The
  metric sender, allowed realms, endpoint, bounded body and HTTP coordinator
  are unchanged. Clock cancellation checks before POST do not alter its proof.
- All sender CLI modes, including clock-off/`--once`, take a separate fixed
  per-user instance lock using the existing OS-lock primitive. It is global
  across target addresses. An active engine also rejects a second worker.
  Lock files remain; OS ownership is released on exit. Tray shutdown joins
  the original worker before releasing the instance lock. It may wait for
  preexisting metric I/O; a replacement is never started while it remains active.

Config schema, credential file handling, startup command and Windows registry
behavior are unchanged. Diagnostics add only bounded fixed result codes,
counts and durations (16 clock records); no addresses, UTC samples, credentials,
headers, boot/challenge tokens, frames or raw exceptions are retained.

## Evidence and commands actually executed

Python **3.12.10**, Windows HOST. Working directory for Python commands:
`<isolated-worktree>/companion`. All data/credentials are public inert fixtures.
Pure HOST tests forbid sockets/DNS. TCP tests bind only127.0.0.1 and intercept
both high-level connections and raw socket connect/DNS to reject any other
destination. Temporary OS-lock files use disposable test directories.

| Check | Result and scope |
| --- | --- |
| Existing focused baseline | 72 PASS /3.676s |
| New policy before implementation | Expected RED:16 tests,17 assertion/subtest failures for missing scheduler/instance guard; no import/syntax error |
| First integrated regression | 88 PASS /3.935s |
| Activation/worker + real Digest/HMAC boot smoke | 20 PASS /0.528s |
| Final targeted HOST/protocol/HTTP tests | **117 PASS /26.620s**, zero failures/skips |
| Loopback scenarios | **6 PASS /79.126s**, including the actual60s cadence |
| Concurrent-lock stress | **1 PASS /10.331s**; forced early clock due times in this test only |
| Test-watchdog follow-up | **2 PASS /14.648s**, load and slow GET only; long cadence was not rerun |

There are **124 distinct passing test methods** across the final targeted and
loopback sets; follow-up executions are not counted as additional unique tests.
The final test-only watchdog prevents a regression from leaving the lab running
forever; the relevant watchdog paths were rechecked without repeating the62s run.
Product runtime source was unchanged throughout these measured runs.

```text
python -B -m unittest test_shino_link test_clock_sync test_clock_sync_deadline test_shino_digest_coord test_push_fsless_metrics
python -B -m unittest -v test_link_clock
python -B -m unittest test_link_clock test_shino_link test_clock_sync test_clock_sync_deadline test_shino_digest_coord test_push_fsless_metrics
python -B -m unittest test_link_clock test_link_clock_loopback.LoopbackTests.test_new_boot_fresh_transport_and_secret_not_in_diagnostics
python -B test_link_clock_loopback.py
python -B -m unittest test_link_clock test_shino_link test_clock_sync test_clock_freshness test_clock_sync_deadline test_shino_digest_coord test_shino_http_coordination test_push_fsless_metrics
python -B test_link_clock_loopback.py LoopbackTests.test_concurrent_lock_load_with_clock_enabled_preserves_metric_ttl
python -B test_link_clock_loopback.py LoopbackTests.test_concurrent_lock_load_with_clock_enabled_preserves_metric_ttl LoopbackTests.test_slow_get_headers_and_body_timeout_without_post
git diff --check
```

Raw sanitized evidence: [targeted HOST](b52-link-clock/targeted-host.log),
[TCP loopback](b52-link-clock/loopback.log),
[concurrent load](b52-link-clock/concurrent-load.log),
[watchdog follow-up](b52-link-clock/watchdog-check.log).
[Structured measurements/current source hashes](b52-link-clock/concurrency.json).

| Measured scenario | Metrics / duration | Maximum accepted-ACK interval | Clock result |
| --- | --- | --- | --- |
| Actual60s cadence | 32 /62.344s | **2.032s** | 2 fresh proofs accepted,2 POST total |
| Lock held at clock opportunity | 2 /2.015s | 2.015s | No clock GET/POST |
| Slow GET headers/body | 2 per case /~2.0s | <=2.031s | Deadline/source hold,0 POST |
| Slow POST / unknown /401 | 2 per case /~2.0s | <=2.032s | 1 POST then latched hold |
| Missing/incompatible route | 2 per case /~2.0s | <=2.032s | Compatibility hold,0 POST |
| Concurrent lock load, two runs | 6 per run /10.282–10.454s | **2.125s** | 65 competing lock holds/run;4–5 fresh POSTs, no replay |

No metric TTL overrun in these clock-enabled TCP cases. The other-client stress
compresses only clock scheduling (each fresh metric ACK can become eligible),
leaving actual2s metrics,1s exchange budget and OS locking intact. It is not a
second measurement of the production60s cadence. Existing HTTP coordination
regressions separately exercised simulated concurrent GETs:6 accepted metric
posts, maximum3.172s ACK interval; no native receiver timing follows from that.

Invalid PC UTC (NaN/out of supported range) stops before POST. Both DST directions
produce a42s lease for a transition50s away, then the new local offset on a fresh
UTC sample. Boot change and companion restart produce new proofs; no saved POST
is resent. Retarget, POST uncertainty and missing firmware do not disturb the
four-value metric payload. Stop after GET prevents POST; the Windows OS instance
lock was tested across separate processes, then released normally for restart.

## Limits and physical HOLD

The configured exchange budget is1s, **not a measured hard OS scheduling bound**.
Total caller duration, including construction/lock/cleanup and scheduling,
reached **1.062s** in the first slow-body run. The1.25s admission reserve covered
the observed overhead; no larger timeout was introduced. Arbitrary Windows
pauses, packet loss, an unavailable receiver or noncooperating clients cannot
have a guaranteed6s metric interval. Existing collector (NVIDIA timeout1.5s),
metric lock wait1.5s, metric HTTP timeouts and failure backoff remain independent
limits. Actual device metrics expire honestly after6s; ACK timing is not device
`metrics_fresh` measurement. Native/LAN latency and LCD behavior remain HOLD.

A correctly signed plausible wrong2020 PC clock is still a source assertion at
an unanchored cold boot; the HOST regression explicitly demonstrates this
limitation. No Windows time accuracy/service state was inspected or altered.
Existing firmware anti-backward/proof/lease checks are unchanged. A shortened
lease around DST may expire before the next60s opportunity: the native honest
TIME NOT SYNCED state is expected, not an old offset extended as valid.

The process guard covers this updated LINK and cooperating launches. A legacy
LINK that predates the guard must be stopped by the owner before future use.
Directly starting another historical client cannot be retroactively prevented.
An IP assertion does not detect DHCP reassignment before HTTP: after a target
change/reassignment the owner must reverify B5.2 before opting in again. The
synthetic missing-route test is not permission to probe installed B5.1.

No firmware, BIN/ELF, LittleFS,4m2m layout, memory threshold, renderer, B5.1 or
PR48 content was changed or rebuilt. No new native RAM/heap/stack measurement,
ASan/UBSan run, CI run, physical test or claim of UTC accuracy is made here.
Private artifacts, credentials, backups, receipts and attempt markers were
neither read, copied nor modified.

## Future owner activation — DOCUMENTATION ONLY, NOT EXECUTED

Preconditions: separate owner approval for physical use; B5.2 already installed
and positively identified in a separately authorized session; current configured
private IPv4 still belongs to that B5.2; PC time/timezone trusted by the owner;
old LINK stopped; reviewed PC dependencies/config already in place. The currently
installed B5.1 has no clock routes and must not receive this operation.

From the reviewed checkout, with `$B52_VERIFIED_IPV4` supplied by that future
owner session (no value is provided or inferred here):

```powershell
py -3 companion/shino_link.py --run --clock-b52-host $B52_VERIFIED_IPV4
```

This starts the one sender with the existing local credential file reference;
it writes no configuration/autostart entry. `--tray` can replace `--run` after
review. No startup script has been changed to pass the option. A later launch
without it remains clock-off. A target/compatibility/unknown-result HOLD means
STOP clock publication, retain diagnostics, verify the target/outcome; never
replay a captured POST or start a second sender. A newly authorized session
always constructs a new challenge/proof, not a resumed transfer.

**One next action:** owner reviews this isolated PC diff and the HOST evidence
before any publication or activation. Physical B5.2 qualification remains HOLD.
