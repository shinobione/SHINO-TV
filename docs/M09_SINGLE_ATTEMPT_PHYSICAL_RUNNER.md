# Mission 9 Phase L — physical single-attempt session runner

6 October 2026. **OFFLINE ONLY — NO DEVICE CONTACT.** Continued clean
`feature/shino-tv-m9-flash-layout-liberation` at
`c7ddb45c3ddc0702c7d7a191268f7634a3c5550d`, existing
[PR #42](https://github.com/shinobione/SHINO-TV/pull/42) Draft/open/unmerged.
The active [roadmap](ROADMAP.md) records the owner decision before implementation.
Phase K history remains intact. This report supplies no physical authorization.

## Frozen bytes and gates

All **103 tracked firmware files**, the Phase K executor and its dependency
sources remain unchanged. The locally retained J resource probe was rehashed,
not rebuilt or substituted:

| Property | Exact identity |
| --- | --- |
| Local retained BIN | `research-local/m9-phase-j/frozen-resource-probe.bin` (ignored/private) |
| Bytes | 411136 |
| SHA-256 | `2ce2fa8da00de5c60109d0675c7bcf58ab41df2138d913b607fde25994e5a835` |
| Firmware source freeze | `7779248082975472ce5f62edf1613d8288b75b6e` |
| Target / payload | `0x000000` / `0x000000..0x0645FF` |
| Sector-rounded destructive extent | `0x000000..0x064FFF` (end-exclusive `0x065000`) |
| Protected interval | `0x065000..0x3FFFFF` |
| Retained LittleFS interval | `0x200000..0x3F9FFF` |

| Gate | Result |
| --- | --- |
| PHASE_L_PHYSICAL_RUNNER_SOURCE_GATE | PASS/OFFLINE |
| PHASE_L_PORT_CONTROL_GATE | PASS/OFFLINE — supported API only, no electrical proof |
| PHASE_L_SINGLE_TRANSACTION_INTEGRATION_GATE | PASS/OFFLINE — fake serial only |
| PHASE_K_RESOURCE_POLICY_GATE / SINGLE_ATTEMPT_EXECUTOR_GATE / FROZEN_CANDIDATE_IDENTITY_GATE | PASS/OFFLINE preserved, local candidate rehash |
| MOUNT_PROBE_RESOURCE_PHYSICAL_GATE | HOLD / NOT_RUN |
| MOUNT_PROBE_PHYSICAL_GATE | PARTIAL / HOLD |
| NORMAL_PROFILE_LITTLEFS_MOUNT_GATE / NORMAL_PROFILE_RUNTIME_GATE | NOT_RUN / NOT_RUN |

The owner unit remains on the earlier physically tested **uninstrumented H**
image (407440 bytes, SHA `ca92cc2f4a8a67f70bd305875bd37be90d0cdff74bf7b338339856407dceef8b`).
No new heap/block/fragmentation/continuation, device, boot or installation evidence
was collected. The [K scoped resource acceptance policy](M09_RESOURCE_POLICY_AND_EXECUTOR_QUALIFICATION.md)
is still pending physical measurement of the instrumented successor.

## Runner contract

[`tools/m9_single_attempt_physical_runner.py`](../tools/m9_single_attempt_physical_runner.py)
owns acquisition only and imports the unchanged K `SingleAttempt` and
`PinnedStubTransport`. It never duplicates the flash transaction or invokes
`connect`, `detect_chip`, stock `write_flash`, packet retry wrappers, port
enumeration, erase/readback, RTC access, reset, boot-mode control or rollback.
Its trusted sibling import path comes from `__file__`, allowing isolated `-I`
execution without cwd/PYTHONPATH imports. A session is consumed on first entry,
including preflight failure; a second call cannot create another executor/port.

Before any serial object/open, every argument, candidate and package/source pin
must pass. `--execute` plus exact owner GO is mandatory for execution; default
mode only audits. Required candidate, external hash and explicit strict
`COM[1-9][0-9]*` port have no defaults. Empty, lower-case, zero/leading-zero,
wildcard, URL/socket/rfc2217/loop, path, whitespace, Unicode-digit and multi-port
strings fail closed. Duplicate valued flags and abbreviated flags are rejected.
No guessed COM8 is embedded in the runner.

Execution requires the approved Windows interpreter at
`C:\Users\jerry\AppData\Local\Programs\Python\Python312\python.exe`,
Python 3.12.x (locally verified 3.12.10), binary SHA
`4d6f5f81a4bca11191c4c7c6b43632694d0a4ce74e068619d8fdc161d469859a`.
K checks enforce esptool 5.4.0, esp-pylib 1.1.5, pyserial 3.5,
configuration/environment rejection, exact 53-file esptool inventory and seven
pinned upstream stub/library sources. L adds all **28 pyserial Python files**
and five unchanged executor/helper source hashes in
[`m9_phase_l_sources.json`](../tools/m9_phase_l_sources.json).
Missing/drifted pins fail before open. CI uses Python 3.12 and public sources;
it never qualifies the private Windows executable or reads/recreates the BIN.

## Windows control-line source audit

Exact pyserial 3.5 `SerialBase.__init__` (`serialutil.py`) initializes stored
DTR/RTS true, but `port=None` returns closed. Its setters update only the stored
value while closed; `_update_dtr_state`/`_update_rts_state` run only when open.
The runner sets both false **before** assigning the literal and opening once.
Hardware/software handshake settings are explicitly disabled, exclusive open
is requested, and disabled states are checked before protocol traffic. The
runner never assigns either control line after open.

`serialwin32.Serial.open` calls Windows `CreateFile`, then `_reconfigure_port`.
The reviewed DCB configuration uses `DTR_CONTROL_DISABLE` and
`RTS_CONTROL_DISABLE` with the stored false values, with no reset pulse or
`EscapeCommFunction` control setter from this path. Pinned esptool's exact
`ESP8266ROM` constructor receives the **already opened object**, avoiding its
string-port open path. Its baud/write-timeout changes reapply the same disabled
DCB states. `close/_close` restores timeouts, cancels pending I/O and closes
handles; it does not call either control setter or reset/Finish.

**Unavoidable limit:** the API cannot configure the DCB until `CreateFile`
returns. Windows, the USB driver, adapter hardware, disconnect/close and wiring
may produce an electrical transient outside Python's control. Source and spy
tests prove only supported API behavior, not electrical levels or isolation.
Future physical operation still requires the separately reviewed **isolated
DTR/RTS** setup and manual GPIO0/RST ownership; software false is not proof of
isolation. No physical setup was inspected or altered in L. If that isolation
and manual fresh-ROM state cannot be established, the future operation stays
HOLD. No automatic entry/exit boot mode, EN/RST pulse or power cycle exists.

## Fresh ROM, one transaction and failure boundary

An exact `ESP8266ROM` object receives one pinned `sync()` request and eight
response packets (the remaining seven `command()` calls send no packet).
Each reply must have the consistent SYNC envelope, nonzero ROM value and two
or four zero status/padding bytes. The four-byte form is present in
[Espressif's ESP8266 ROM SYNC trace](https://docs.espressif.com/projects/esptool/en/latest/esp8266/advanced-topics/serial-protocol.html#tracing-esptool-serial-communications);
the protocol also defines two-byte ESP8266 status. Other sizes, length/status
mismatches or nonzero status bytes fail before upload. In particular,
even a mixed zero/nonzero reply stream is rejected as an unknown stub.
Read-only acquisition is bounded by a **5-second read deadline, 16384 bytes,
256 reads and at most 0.1 second per read**. These are host budgets, subject to
OS scheduling, not physical timing guarantees. Noise budget exhaustion, empty
reads, protocol mismatch or sync fault stops before stub upload/flash Begin.
No SYNC resend or reset recovery occurs.

Before Begin, K requires exact class, `IS_STUB=false`,
`sync_stub_detected=false`, ESP8266 magic `0xFFF0C101` at `0x40001000`,
JEDEC capacity byte `0x16` (4 MiB). K uploads only its pinned v2 stub with
`STUB_SUBDIRS=['2']`, no v1 fallback/plugins, validates exact stub class and
4 MiB geometry, and owns the sole transaction: one Begin, 101 unique
4096-byte uncompressed data packets, one no-reboot Finish, one MD5 barrier.
Existing reviewed RAM-stub upload behavior is unchanged; K's zero-flash-retry
contract remains intact. There is no reconnect after adapter construction or
Begin, no second executor and no transaction restart.

After an open attempt, any exception, serial timeout/disconnect, MD5 mismatch
or KeyboardInterrupt emits exactly the safe status
**STOP — PHYSICAL FLASH STATE MAY BE UNKNOWN**, exits nonzero and closes only
the host handle. Even an uncertain open failure uses this conservative status.
No error internals are exposed. A mid-data failure sends no cleanup Finish,
reset, rollback or recovery. Preflight failures emit `STOP_PREFLIGHT_NO_PORT_OPEN`.
Upstream stdout/stderr are suppressed; success prints only candidate SHA/size,
target/extent, Begin=1/data=101/Finish=1, retries=0/reconnects=0/reboots=0,
`full_post_verified=false`, `physical_gate_closed_by_this_receipt=false`, and
`APPLICATION_TRANSACTION_ACKNOWLEDGED_FULL_POST_STILL_REQUIRED`.

Success leaves the flasher stub active: closing the host port is not a chip
reset or app boot. The runner never automates private 4 MiB PRE/POST captures.
Those remain separate visible operator steps, with protected-range/FS/tail
verification before any first app boot, separate RTC neutralization/readback
and manual transition authority. MD5 is not the required full POST.

## Offline validation

[`test_m9_single_attempt_physical_runner.py`](../tools/test_m9_single_attempt_physical_runner.py)
uses a spy serial object with real pinned ESP8266ROM constructor/SYNC/SLIP,
K `SingleAttempt`, v2 specification and `PinnedStubTransport` flash packet APIs.
Chip reads and RAM-stub upload are explicitly mocked, never physical proof.
There is no real serial backend construction in these tests.

| Matrix | Offline coverage |
| --- | --- |
| Flash faults | 104 positions (Begin + all 101 data + Finish + MD5) × SerialException / TimeoutError / KeyboardInterrupt / ValueError = **416** faults; failure follows recorded packet transmission |
| Lifecycle faults | Open / sync / stub upload / host close × SerialException / TimeoutError / KeyboardInterrupt = **12** faults |
| Pre-Begin rejection | Wrong chip, wrong capacity, all-zero and mixed-zero unknown stub replies; no upload/Begin |
| Pre-open rejection | Package/version/source/interpreter/hash faults, invalid port, missing GO, wrong GO; missing execute audits without port/executor |
| Control/one-shot assertions | At most one port open and K executor; no duplicate flash packet/Begin, second session, post-open control assignment, reset/reconnect/rollback or mid-data cleanup Finish |
| Additional checks | MD5 mismatch; bounded noise/clock/read budgets; real pyserial closed setters; source pin mutation; safe CLI error receipt; forbidden API scan |

Local validation: **205 checks PASS** — 202 complete Mission 9/supporting
regressions (including all 16 L tests and all 24 K policy/executor tests) plus
three bounded port-80/probe source checks; zero failures/errors/skips. J/H host
fixtures use MSVC; none of these are device resource/rendering evidence. Exact
package/source pins, approved local interpreter and retained-candidate `-I`
audit passed. Existing firmware/K dependency hashes and Git diffs passed; all
earlier document lines remain in order, with only the handoff's latest/previous
label advanced. The exact-head CI receipt is recorded with
the final Phase L commit in PR #42. Source-only CI artifacts explicitly mark
the private candidate and approved local interpreter identity **NOT_READ**.
Retained-candidate isolated CLI audit ran without `--execute` or owner GO and
reported `AUDIT_PRINT_ONLY_NO_PORT_OPEN`; it verified the actual local pins/hash.

## Future command — PRINT ONLY, DO NOT EXECUTE IN PHASE L

This is the sole future physical command template. COM8 is an explicit example
literal pending owner port identification; no port was inspected/enumerated.
The default source audit directory must still contain all seven pinned source
files, and all separate physical PRE/recovery/control-line/fresh-ROM conditions
must be met with a new exact-operation GO. **This text is not that GO.**

```powershell
& "C:\Users\jerry\AppData\Local\Programs\Python\Python312\python.exe" -I "C:\Users\jerry\SHINO-TV-V06-AUDIT\tools\m9_single_attempt_physical_runner.py" --port COM8 --candidate "C:\Users\jerry\SHINO-TV-V06-AUDIT\research-local\m9-phase-j\frozen-resource-probe.bin" --expected-sha256 2ce2fa8da00de5c60109d0675c7bcf58ab41df2138d913b607fde25994e5a835 --execute --owner-go "GO SINGLE ATTEMPT 2ce2fa8da00de5c60109d0675c7bcf58ab41df2138d913b607fde25994e5a835"
```

**PHASE L DEVICE CONTACTS = 0; SERIAL I/O = 0; FLASH WRITES = 0; RTC WRITES = 0;
REBOOTS = 0; DEVICE FILESYSTEM WRITES = 0.** STOP after L. PR #42 remains Draft,
open and unmerged. Both normal-profile gates remain NOT_RUN.
