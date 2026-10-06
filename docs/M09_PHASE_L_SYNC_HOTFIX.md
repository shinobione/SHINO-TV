# Mission 9 Phase M — bounded no-reset ROM SYNC hotfix

6 October 2026. **OFFLINE ONLY — NO DEVICE CONTACT.** Continued clean
`feature/shino-tv-m9-flash-layout-liberation` at
`2ea22809028f1b1e11ffecd3dbc471079d04b547`, existing
[PR #42](https://github.com/shinobione/SHINO-TV/pull/42) Draft/open/unmerged.
The new owner decision was recorded in the active [roadmap](ROADMAP.md) first.
The [Phase L report](M09_SINGLE_ATTEMPT_PHYSICAL_RUNNER.md) remains dated history;
its offline qualification did not establish physical acquisition compatibility.

## Owner physical failure receipt — after the L offline work

The following evidence was supplied explicitly by the owner in the Phase M
request. This agent neither contacted the unit nor reread private device dumps.
No private PRE/readback digest, MAC or credential is published.

| Owner-reported operation/result | Evidence |
| --- | --- |
| Physical L runner attempt | Occurred; returned `STOP — PHYSICAL FLASH STATE MAY BE UNKNOWN` |
| Boot-state setup | Owner manually pulsed RST with GPIO0 LOW |
| Immediate independent full 4 MiB readback | PRE == POST, `PRE_UNCHANGED=true`; no app boot before this readback |
| Candidate payload | `CANDIDATE_PAYLOAD_EXACT=false`; instrumented J candidate was not installed |
| Changed byte contents | Total=0, `0x000000..0x064FFF`=0, protected=0 |
| Protected interval | `PROTECTED_065000_TO_END_EXACT=true` |
| Filesystem / tail | `FS_EXACT_AFTER_FAILURE=true`, `TAIL_EXACT_AFTER_FAILURE=true` |
| Acquisition diagnostic | Port open PASS; `STOP_AT_FRESH_SYNC` before Begin |
| RX-purge diagnostic | Preflight/open/purge PASS; still `STOP_AT_FRESH_SYNC` |
| Stock reset-free diagnostic | `rom.connect(mode="no-reset", attempts=1, detecting=True, warnings=False)` PASS; `STUB_DETECTED=false`, `FLASH_COMMANDS_SENT=0`; no stub upload |

The independent owner comparison proves **zero changed flash byte contents**
for the failed attempt, including LittleFS and tail preservation. The original
conservative UNKNOWN was appropriate at failure time; subsequent readback
resolved content preservation. This was **not a successful flash transaction**,
installation, boot acceptance or instrumented resource measurement.

`PHASE_L_SINGLE_SYNC_ASSUMPTION = REJECTED_BY_PHYSICAL_EVIDENCE`.
The owner evidence establishes failure of the strict L path and success of the
supported no-reset path. The successful stock diagnostic's inner attempt number,
reply values and finer timing cause were not supplied and remain unknown.
Do not invent a physical trace or claim that a particular retry number was used.

## Exact pinned source review and root cause

Existing K package/configuration/source checks remain unchanged: esptool 5.4.0,
esp-pylib 1.1.5, pyserial 3.5, the complete 53-file esptool inventory and seven
stub/library source pins. Existing L pins still cover 28 pyserial files and
five unchanged executor/helpers. New [M source pins](../tools/m9_phase_m_sources.json)
bind the full LF-normalized `loader.py` and these exact function spans:

| esptool 5.4.0 `loader.py` | Lines | Reviewed behavior |
| --- | --- | --- |
| `connect()` | 856–984 | Outer lifecycle attempts; constructs reset strategies and may close on failure; not called by production runner |
| `_connect_attempt()` | 748–800 | `mode="no-reset"` skips reset/boot-log block; up to five inner flush/SYNC exchanges; catches FatalError and sleeps 0.05 s |
| `sync()` | 708–722 | One SYNC request plus seven response-only `command()` calls; detector is AND of all eight `value==0` tests |
| `command()` | 571–651 | Writes only when op is supplied; response-match loops read without resending; temporarily changes timeout |
| `slip_reader()` | 2211–2309 | Maintains partial/escaped SLIP state; empty reads/malformed SLIP raise FatalError; ordinary timeout alone does not bound continuous input |

**Outer connect attempts are not inner SYNC attempts.** `attempts=1` allows
up to five pre-flash SYNC exchanges in the known-good stock no-reset path.
L allowed only one exchange and also rejected individual zero values before
pinned sequence classification completed. Its acquisition assumptions were
stricter than the reviewed supported path. M supplies bounded pre-stub retries
and whole-sequence classification; it does not adopt stock connection lifecycle,
USB/port discovery/reset strategies, retrying flash wrappers or failure cleanup.

`serialwin32.py` buffer resets invoke `PurgeComm` RX/TX clear/abort, not GPIO,
DTR/RTS, RST or EN. Legacy stock `flushInput/flushOutput` map to these buffer
reset operations. The local runner uses the explicit buffer APIs, avoiding
blocking output-drain `flush()` and all stock `connect()` calls.

## Bounded acquisition contract

Only the ROM acquisition function in
[the existing runner](../tools/m9_single_attempt_physical_runner.py) changes
production behavior. The K `SingleAttempt` and `PinnedStubTransport`, serial
open/control/close/latches, firmware and retained candidate remain unchanged.

| Limit | Scope |
| --- | --- |
| `MAX_SYNC_ATTEMPTS=5` | At most five SYNC requests; no sixth request |
| Global deadline | Five seconds starting at `fresh_sync()` entry, shared across all attempts |
| Global bytes | At most 16384 bytes returned by serial reads across all attempts |
| Global reads | At most 256 `read()` calls across all attempts |
| Read / SYNC write timeout | At most 0.1 s, reduced to remaining global time |
| Retry delay | Exactly 0.05 s before the next attempt, only when global budgets permit |
| Serial lifecycle | Same already-open object; at most one open, zero reopen/reconnect |
| Hardware controls | DTR/RTS false before open; no assignments after open, no reset/boot/power operation |

One shared budget is created outside the loop. Before each attempt, the same
handle's incomplete receive/output buffers are purged, a fresh SLIP generator
is created, and global budgets are checked again before sending one SYNC.
Failed reads/partial frames consume global bytes/read/time; discarded unread
driver-buffer bytes are not counted as host bytes returned by `read()`.
Purges, retry delays and writes occur within the shared clock budget. There is
no catch-up and no separate five-second allowance for a later attempt.

Only pinned `FatalError` during SYNC permits another acquisition attempt.
Five such failures stop before stub upload, without a final unnecessary delay.
SerialException, TimeoutError, KeyboardInterrupt, global exhaustion, malformed
completed envelopes or ROM/stub inconsistency are terminal. Pinned raw SLIP
FatalError can consume another pre-stub attempt; an accepted acquisition must
still contain a complete coherent new eight-reply sequence after purge.
No failure handler is installed around stub upload or the flash transaction.

The original write timeout is restored after successful acquisition, preserving
K's flash transport timing. Deadline exhaustion after a slow read or delay
prevents another SYNC/upload. Windows/driver calls and OS scheduling cannot be
made hard real-time by Python; these are checked host budgets, not device timing
proof. The existing DTR/RTS electrical-isolation caveat remains unchanged.

## Exact accepted/rejected reply sequences

Every completed reply must have direction 1, opcode SYNC, a consistent declared
length of two or four zero status/padding bytes, and the exact corresponding
packet length. No per-reply nonzero-value assertion exists.

The real pinned `rom.sync()` must consume all eight replies first. Its
`sync_stub_detected` flag must equal `all(value==0 for all eight values)`.
All-zero identifies a known existing stub and is rejected. A fresh ROM sequence
has the flag false and **eight identical valid packets**, with the same nonzero
ROM value and the same two- or four-byte zero status/padding form. The usual ROM
value is `0x20120707`; classification does not invent an additional exact-value
pin. Mixed zero/nonzero, differing nonzero values or differing forms fail the
whole-sequence consistency check, even though upstream's aggregate flag alone
would be false. Malformed completed envelopes fail immediately. Thus upstream
classification is preserved without accepting mixed inconsistent sessions.

Exact ESP8266ROM class, `IS_STUB=false`, detector false, chip magic and 4 MiB
capacity are still required before pinned v2 upload. No plugin/v1 fallback is
added. A successful fifth SYNC permits one existing upload path, then exactly
one K Begin / 101 unique DATA packets / no-reboot Finish / MD5 barrier.
After Begin: **zero retry, repeated block, reconnect, reopen, reset, second
Begin, recovery write or automatic rollback**. The safe failure receipt and
independent full POST requirement remain unchanged. No future command was run.

## Offline evidence and gates

[M tests](../tools/test_m9_bounded_rom_sync.py) use a fake clock and fake serial
with the real pinned ROM sync/command/SLIP APIs and existing K integration.
They cover success positions 1–5, all five failures/no sixth request, stale
partial-frame removal, one shared budget, global deadline/oversleep/byte/read
exhaustion, malformed/stub/mixed replies, whole-sequence detector semantics,
serial disconnect/timeout/interruption, source/version mutation and one stub
upload/transaction after fifth-attempt success. Spy controls reject every
post-open DTR/RTS assignment. No real serial backend is constructed.

**216 local checks PASS:** 213 complete Mission 9/supporting regressions,
including all 11 M tests, all 16 L tests and all 24 K policy/executor tests,
plus three bounded route/probe source checks. Zero failures/errors/skips.
Approved Python 3.12.10 binary identity, exact package/source pins, local
candidate qualification and isolated `-I` audit passed without execute/owner GO.
All earlier documentation lines were retained in order, advancing only the
handoff's latest/previous label.

L's full 416-position flash fault matrix (104 positions × four exception types)
and 12 lifecycle faults remain in the regression suite. K's executor tests
remain unchanged. Local full regression counts and exact-head CI receipts are
published with the final commit in the existing PR. Source-only CI marks the
private BIN and approved Windows interpreter identity NOT_READ; local audit
rehashes the retained BIN and validates the approved interpreter independently.

| Gate | Result |
| --- | --- |
| PHASE_M_SYNC_ROOT_CAUSE_GATE | PASS/OFFLINE — exact source plus owner-supplied diagnostic facts |
| PHASE_M_BOUNDED_SYNC_SOURCE_GATE | PASS/OFFLINE |
| PHASE_M_RUNNER_REGRESSION_GATE | PASS/OFFLINE — fake serial/clock only |
| PHASE_M_FROZEN_CANDIDATE_IDENTITY_GATE | PASS/OFFLINE — local retained BIN rehash |
| MOUNT_PROBE_RESOURCE_PHYSICAL_GATE | HOLD / NOT_RUN |
| MOUNT_PROBE_PHYSICAL_GATE | PARTIAL / HOLD |
| NORMAL_PROFILE_LITTLEFS_MOUNT_GATE / NORMAL_PROFILE_RUNTIME_GATE | NOT_RUN / NOT_RUN |

All **103 firmware files** and the K executor/dependencies are unchanged.
Candidate remains **411136 bytes**, SHA-256
`2ce2fa8da00de5c60109d0675c7bcf58ab41df2138d913b607fde25994e5a835`;
no rebuild/substitution. Target0, rounded extent `0x000000..0x064FFF`, protected
`0x065000..0x3FFFFF`, LittleFS `0x200000..0x3F9FFF` remain the same.

**PHASE M DEVICE CONTACTS = 0; SERIAL I/O = 0; FLASH WRITES = 0; RTC WRITES = 0;
REBOOTS = 0; DEVICE FILESYSTEM WRITES = 0.** The owner physical attempt above
preceded this offline hotfix work; it is not reclassified as agent activity.
STOP after M. No current-unit flash/reboot, normal-profile activation or merge.
