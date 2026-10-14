# B5.2 clock freshness correction — offline, 14 October 2026

Owner authorizes only the proven freshness/replay correction in the existing
`codex/b52-clock-foundation` worktree, tests and a new public inert build. Frozen
B5.1 `244334edac07701dc25b5ffc494715152ae1bfa5`, scenes, private artifacts,
receipts and attempt markers stay intact. No device contact, private build,
commit, push, merge or automatic SHINO LINK publication.

## Minimal protocol decision

Keep the same authenticated GET status and POST sync routes, Digest admission,
HTTP ownership and PC one-second total deadline. Version2 GET issues one new
128-bit challenge, replacing the previous pending challenge, valid for2000ms of
device monotonic time. A separate128-bit boot token is initialized once from the
pinned Core hardware nonce source while Wi-Fi is active. Public write authority
remains closed. Zero/repeated entropy fails closed; this is a basic health gate,
not a physical proof of entropy quality.

Frame64 bytes: `SHINOCL2`(8), UTC uint32LE(4), offset int16LE(2), lease uint16LE(2),
challenge(16), HMAC-SHA256(32). Old16-byte frames are refused. GET supplies public
boot/challenge hex and their2000ms lifetime; no secret or derived key is returned.

Derive `Kclock = HMAC-SHA256(UTF8(existing Digest password),
ASCII("SHINO-PC-CLOCK-KEY-2\\n"))` (the domain ends in an actual LF).
Proof is HMAC under Kclock over actual-LF domain `SHINO-PC-CLOCK-SYNC-2`, followed
by raw boot16 and the exact first32 frame bytes. That binds protocol, POST sync
operation, UTC/offset/lease, boot and challenge. No OTA key access is needed.
Use the already pinned BearSSL implementation. Borrow the existing aligned
transfer-storage arena under the same response/HTTP lease; no second crypto
arena, new generic authentication framework or heap allocation.

Reserve/consume the matching challenge before verification/application, with a
reentry guard. Incorrect proof or invalid/backward time consumes that attempt,
never renews the clock lease. Duplicate/concurrent posts have at most one effect.
No yield occurs between consumption and time application. New GET replaces an
unconsumed challenge. Boot-state reset rejects all previous boot proofs.

PC validates challenge shape and captures system UTC/offset only after receiving
it under the existing full exchange lock. No POST retry. Old/expired challenge,
body modification, wrong key, reentry or unknown result fail closed.

UTC is nondecreasing relative to the last accepted UTC in the same boot; while
the prior lease remains valid it cannot rewind the currently projected clock.
No backward tolerance. Local DST offset changes still permit UTC to increase.
Lease<=120s and the existing six-second metric TTL remain independent.

## Trust boundary

An unanchored ESP8266 can prove a timely response to its unpredictable challenge
from someone holding the existing secret. It cannot prove true current UTC.
A paired PC freshly signing a plausible but incorrect2020 time at cold boot is
still a valid source assertion; explicitly test/document that limitation.
Without a fresh proof, boot/replay/expiry leaves TIME NOT SYNCED. No retained RTC
clock, flash write, compile-date assumption or invented absolute-time PASS.

Core3.1.2 Crypto.cpp uses ESP.random for nonce generation; Esp.cpp reads the
hardware random register with2us spacing and documents uncertainty for ESP8266
and reduced entropy with Wi-Fi off. Require active Wi-Fi, retain physical RNG
quality/latency/memory qualification as HOLD, and make no stronger claim.

## Targeted validation and cost

Reuse the four retained HOST reproductions as rejection regressions. Add genuine
fresh success, old boot/old challenge, expiry, modified body/MAC, wrong key,
simultaneous duplicates, reentry, entropy failures and no lease renewal. Preserve
calendar/DST and byte-identical five240×240 C++ renders. Measure loopback exchange
durations/request counts; no assumption of a physical1s exchange.

Compare one new public ELF/BIN against the retained B5.2 pre-fix artifact. Keep
the original2048B total static increment budget relative to B5.1, all resource
floors and4m2m geometry. Report exact delta and known frames; native memory,
physical latency and absolute PC clock accuracy remain unmeasured.

## Closure — READY_FOR_OWNER_REVIEW, software only

The three P2 corrections are complete. The prior replay HOLD is superseded for
this local source only; earlier reports and all physical limits remain intact.

| Correction | Executed proof |
| --- | --- |
| P2-1: same-instant projections | Old T/since0, incoming T+1/started1500/validation2100 is refused; old T+2 and lease117900ms remain. Fresh T+3 is accepted. Zero backward tolerance. |
| P2-2: irreversible expiry | Gate.expire latches pending validity off from existing B52Clock::step. Issue100, expire2100, then low counter110 after a full wrap rejects. Actual native-loop HOST test advances2s, services loop, then completes2^32ms and rejects.1999ms accepted,2000ms refused; fresh near-wrap and single-use covered. |
| P2-3: post-MAC deadline | Native monotonic callback sampled after HMAC and before State application. Start1990, pre-MAC1999, completion2000 rejects; existing clock remains T+2/118000ms. |
| Post-body resources | Fresh unchanged execution-floor check immediately before placement-new. HOST heap drops to20479 after complete body:503 CLOCK_RESOURCE_HOLD, prior clock/lease preserved. |

**Loop service assumption:** with only32-bit millis, the owner must service an
expiry tick at least once in `[issued+2000ms, issued+2^32ms)`. Normal cooperative
loop service satisfies this; no guarantee is claimed if service is suspended
for a complete49.7-day cycle while retaining RAM. The native loop invokes expiry
through its existing render step; no64-bit clock or persistent service added.
Watchdog/reset behavior and maximum physical service gaps are unqualified. Reset
constructs a new gate/boot token instead of retaining a challenge.

### Executed targeted validation

- **21 proof cases/59 checks**, real pinned BearSSL C and gate C++ under MSVC
  ASan, including exact P2s, bad/mutated proofs, same-nonce/different-boot binding,
  reentry, expiry and no clock lease renewal on rejection.
- **49 actual parser/Digest/clock/telemetry loopback cases**: four original replay
  reproductions now rejected; fresh success, concurrent duplicates with at most
  one application, old boot, incomplete HTTP, public authority closed, post-body
  budget failure, authenticated telemetry recovery, four values and TTL6s.
- **17 clock/calendar/render cases/1721 checks under ASan**: both DST transitions,
  midnight/date/year/leap cases, disconnection/reconnect, invalid time and four
  cards/bars. All five240×240 PNG hashes equal the retained pre-fix captures;
  SceneEngine.h is byte-identical to pre-fix B5.2.
- **23 Python clock tests**, including absolute deadline/trickles, lock release,
  capture after challenge, strict proof shape, no retry and sanitized failures;
  **3 public generator guards**. No automatic SHINO LINK publication.
- Source-only independent re-review closed the three P2s and post-body check;
  it did not run tests or qualify hardware. UBSan unavailable; no installation.
  Massive OTA/SceneEngine campaigns were not rerun. No new CI/commit/push.

Final5 genuine publisher exchanges measured **31–32ms on HOST loopback**:
first GET401 + authenticated GET + one POST; subsequent authenticated GET + one
POST. Earlier completed slice measured31–47ms. The existing total1000ms PC
deadline and2000ms challenge deadline are unchanged. Five samples do not bound
physical Freebox/Wi-Fi latency. Rejections/unknown results never cause POST retry.

The added telemetry fixture initially used stale Digest authorization after its
intentional unauthenticated POST rotated Core's challenge. A local reproduction
showed401 with the old cache and200 after the explicit preparation GET. Only the
fixture sequence changed; the final HOST executable was reused, no firmware or
Digest behavior was altered. Earlier failing tests/build probes remain local.

### Public native resources

Final public BIN **421552 B**, SHA-256
`4db6a94f4c2675882925a287b2b7d22fe4d9a48cecc8682415f3eb10542d0672`;
ELF `f97e3ff2a33d6c729ab321f19779db057a11d32ec5937e8d91a7b5cc642b1d44`.
Public clock/OTA authority false; this is not an owner installation candidate.

| Resource | Pre-fix B5.2 public | Final | Delta |
| --- | ---: | ---: | ---: |
| BIN |420224|421552|+1328 B|
| Static DRAM |46492|46720|+228 B|
| .data |2516|2516|0|
| .rodata |13592|13780|+188|
| .bss |30328|30368|+40|
| .noinit |56|56|0|

Gate40 B; ClockState20 B and renderer868 B unchanged. Crypto workspace **416 B**
is borrowed from the existing aligned transfer arena and wiped on exit. Target
Xtensa sizeof probe confirms416/40. No new firmware heap allocation/framebuffer;
temporary32-byte derived key and32-byte comparison output are included in the
measured frames. Digest/lwIP/Core/GFX allocation peaks remain unknown.

Frames independently matched between compiler.su and linked Xtensa prologues:
clockSync64, B52Clock::synchronize32, Gate::accept96, tag80, clockStatus96,
Gate::issue64, entropy32, ESP.random48 B. Known proof prefix400 B;
real SHA256 vtable resolution identifies key_init304 → process_key304 →
sha_update48 → sha_round384 (+decode_words0), giving **1440 B** known compiled
path. HMAC output path is1232 B including hmac_out320, SHA out wrapper0 and its
**128 B tail target**, then round384. Zero wrapper frame does not mean zero
callee cost. Render prefix432 B remains partial.

The retained and final ELF audits both compute **1616 B for the same selected
OTA path set**, with full function/frame lists and ELF hashes in the resource
report. This is not an exhaustive or physical OTA maximum. ROM memcpy/memset/
strlen, other indirect ROM calls, libc formatting, GFX/SPI descendants, RNG
micros/delay/guard callbacks, SDK/IRQ/lwIP and allocator high-water are unbounded
by this analysis. Native heap/largest block/fragmentation/continuation are
**NOT_MEASURED**, never inferred from static RAM or HOST results.

Cumulative static increment vs retained public B5.1 is1816 B, leaving232 B in
the unchanged2048 B offline budget; this is not a free-heap margin. Unchanged OTA
floors: admission heap25600, execution20480, largest16384, continuation2048 B,
fragmentation<=25%.4m2m symbols remain FS0x40400000..0x405fa000 and
EEPROM0x405fb000. No old BIN or firmware was rebuilt, changed or substituted.

### Evidence and preserved scope

[Validation/source hashes](b52-clock-freshness/VALIDATION.json),
[proof ASan](b52-clock-freshness/PROOF_ASAN.json),
[HTTP/Digest/telemetry](b52-clock-freshness/HTTP_REPORT.json),
[render ASan](b52-clock-freshness/RENDER_ASAN.json),
[native resources](b52-clock-freshness/NATIVE_RESOURCES.json),
[target sizes](b52-clock-freshness/TARGET_SIZES.json).
Existing [five captures](b52-clock/README.md) are retained.

This correction changes ClockFoundation, B52 native clock/proof/HTTP files,
PC clock library/tests, B52 generator/targeted labs/runners/resource reporter,
and these active summaries/evidence only. It preserves the preexisting untracked
B5.2 work, SceneEngine rendering, other PR40 prototypes, normal OTA/LAN/metrics/
Digest implementations and the clean principal worktree at frozen244334e.
Private BINs, MASTER, credentials, receipts and attempt markers were not touched.
No device contact, physical GET/POST, actual reboot, Wi-Fi change, private build,
commit, push or merge occurred. HOST boot-state reset is a RAM fixture operation.

**Next action:** owner reviews the local P2 diff and evidence offline. Physical
qualification, private candidate preparation and any Git publication require a
separate next mandate; this review grants none of them.
