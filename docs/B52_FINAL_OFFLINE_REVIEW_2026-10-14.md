# B5.2 final offline review — 14 October 2026

**Verdict: HOLD.** Local `codex/b52-clock-foundation`, HEAD
`244334edac07701dc25b5ffc494715152ae1bfa5`; B5.2 remains uncommitted.
This review uses the existing public build and HOST receiver. No device contact,
private build, firmware rebuild, commit, push or merge. Main B5.1 worktree is
clean at the frozen reference. No private artifacts, receipts or attempt markers
were read or changed.

## Proven blocker: clock messages lack freshness and replay protection

`firmware/include/display/ClockFoundation.h:39–45` validates epoch range, offset,
lease and current request duration, then unconditionally replaces the clock and
starts a new lease. It has no message age, last accepted sample or one-use proof.
`experiments/b52_clock/native/B52ClockHttp.inc:26` calls that policy after the
existing Digest admission. The pinned Core authenticates `qop=auth` but does not
consume/check the nonce count; an unchanged authenticated request can be reused
while its Digest challenge remains current. No Digest implementation was changed.

Four **new targeted reproductions** on the retained actual HOST parser/Digest/
native clock executable, with only `127.0.0.1` and public fixtures:

| Reproduction | Observed result | Required gate |
| --- | --- | --- |
| Plausible 2020 UTC at unsynchronized boot | HTTP200; clock marked valid | HOLD: initial sample freshness unproven |
| Identical body AND Digest Authorization at +60s | HTTP200; UTC rewinds60s; remaining lease59951 →119983 ms | HOLD: exact replay accepted |
| Same replay after120s expiration | HTTP200; old sample restores valid time | HOLD: expiration bypassed by replay |
| UTC one day earlier, new valid authentication | HTTP200; clock rewinds one day | HOLD: older sample accepted |

The 120s expiry is correct **between accepted samples**; it cannot establish the
age of a received sample. Request duration<=2s is not the age of the message.
Disabling automatic POST retry on the PC is not receiver anti-replay protection.
An increasing-UTC check alone would not prove freshness at initial boot or after
state loss, nor bind the clock body to a source proof. No partial policy patch or
protocol redesign was made during this short review.

Probe and sanitized result are retained locally in
`research-local/b52-final-offline-review-20261014/replay_probe.py` and
`replay-report.json`. The probe verifies current native source copies and guards
Python connections/resolution to loopback; the C++ listener binds loopback.
SDK/flash writes and restarts are zero. Failed freshness requirements remain
HOLD, not passing conformance tests.

## Other review points

| Point | Result and limit |
| --- | --- |
| UTC/local/DST/calendar | PASS HOST: UTC plus configured PC OS offset; both DST directions expire/resync, midnight/year/leap dates covered. No device timezone database. Windows time-service accuracy/manual timezone changes remain unverified. |
| Input/expiry/disconnection | PASS source/HOST for fixed16-byte frame, range2020–2099, offset-720..840, lease1..120, bad input preserving prior state, latched expiry, millis wrap and fresh reconnect. Old/replayed valid-range samples: HOLD above. |
| Source trust | Existing paired-PC Digest admission preserved. Display source is explicit; Digest alone does not establish sample freshness or body integrity. Clock never controls authentication/OTA deadlines. |
| Five captures | PASS HOST inspection: actual C++ renderer and pinned GFX font, all240×240. No overlaps or lost cards; invalid time/metrics shown honestly. Physical LCD readability remains NOT_RUN. |
| Memory | PASS artifact/source budget; physical heap/block/fragmentation/stack remain NOT_MEASURED. No floor lowered. |
| Future LINK | PASS structural compatibility: separate routes/body, existing same-host Digest lock, full-body lock ownership, no wait when busy, total1s exchange and one POST. No automatic publication was added. Future scheduling/nonce-cache coexistence under load and six-second telemetry continuity remain unqualified. Same Windows profile/coordinator is required. |

Captures examined, with hashes checked against retained HOST_REPORT.json:

1. [Synchronized](b52-clock/idle-synced.png):14:26/date, all four numbers/bars.
2. [Unsynchronized](b52-clock/idle-unsynced.png):TIME NOT SYNCED, four cards.
3. [Expired](b52-clock/idle-expired.png):PC CLOCK EXPIRED, no valid hour/date.
4. [PC disconnected](b52-clock/idle-pc-disconnected.png):bounded holdover;
   four stale metrics show `--` and neutral bars.
5. [Midnight](b52-clock/idle-midnight.png):00:00, date14/10/2026 after13/10.

Valid synthetic fixture times are explicitly labelled. Existing image files were
not overwritten or replaced with mockups. ASan-rendered PPMs match all five
retained C++ PPMs byte for byte. Small label fonts remain a physical review limit.

## Resources and targeted validation

Existing public BIN420224 B / SHA-256
`80fd47a874b5671536936739359e0c4c5ac01249ed491161a6a39b930b08f0d4`
and ELF/manifest/source hashes reverified. Public B5.1 baseline reused, not rebuilt.
Static DRAM44904 →46492 B: **+1588 B** = .data+868, .rodata+744, .bss-24.
The 2048 B offline static increment budget has460 B remaining; this is **not a
free-heap margin**. Installed private B5.1 is a different artifact.

ClockState20 B, renderer868 B including448 B scanline, LCD adapter4 B. The clock
code has no new dynamic allocation or full framebuffer; renderer observed zero
allocations in HOST tests. Existing HTTP/Core/GFX/SDK allocations still have
unknown native peaks. No second renderer/dashboard is linked. Two identical
12-byte month tables remain at distinct DRAM addresses0x3ffe8e0c and0x3ffe8e18:
a potential12 B saving, not an unsafe-memory finding; no optimization was made.
Moving the renderer from .data to .bss would not save static RAM. Its music fields
and scanline belong to the existing later music ownership seam; no refactor here.

Known compiled OTA path maximum remains1616 B; clock-sync/draw prefixes272/432 B
exclude libc/GFX/SPI/SDK/ROM/IRQ descendants and are not physical stack bounds.
4m2m layout and LittleFS/EEPROM symbols unchanged. Floors remain heap25600 B at
admission,20480 B during execution; block16384 B; continuation2048 B; frag<=25%.

New validation only:

- Four replay/old-message reproductions: blocker confirmed, HOLD.
- **MSVC ASan PASS:17 C++ cases /1722 checks**, existing16 cases plus missing
  spring DST case; zero ASan diagnostics and identical retained renders.
- Two new PC-source spring DST checks:lease shortened to42s before a transition
  50s away; refusal inside the final8s transition window.
- UBSan NOT_RUN: no usable compiler found; no installation/download attempted.
- Public ELF/manifest/source/capture integrity and `git diff --check` PASS.

First ASan wrapper renamed `main` to an ordinary function and lost C++'s implicit
zero return; its run is invalid. The wrapper was corrected by inserting the new
case into the real lab main. Both runs/logs are preserved; no firmware fault was
inferred from that harness error. Successful evidence:local `asan-report.json`,
`resources.json`, `retained-evidence-checks.json` in the review directory.
Previously documented Python18, generator3, parser23 and SceneEngine33 suites
were inspected and not rerun. No new CI was run.

**One next action:** a bounded offline correction of clock sample freshness,
binding a short-lived one-use proof to the current boot and the exact sample,
while preserving Digest/telemetry/lock/deadlines; use the four reproductions above
as rejection regressions. No physical operation is requested or authorized.
