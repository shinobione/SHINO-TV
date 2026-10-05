# Mission 9 Phase D — deterministic RTC / eboot neutralization (OFFLINE ONLY)

**Phase E physical evidence, 5 October — owner-performed before documentation:**
[Stage-1 receipt](M09_STAGE1_PHYSICAL_EVIDENCE.md) closes the board-specific
RTC/existing-RST question left NOT_RUN below: magic zero and CRC sentinel
`0xA5A5A5A5` survived a powered RST pulse with GPIO0 LOW; sentinel was removed,
zero/zero read back, GPIO0 released while powered, RST produced `(3,7)` / `~ld`
without observed `cp:`. After verified Stage-1 POST, the zero/zero transition
was repeated for first boot, with `v00061740` and 180-second runtime PASS.
These are owner-provided physical observations, distinct from Phase D source/
model PASS. Cold-power gate remains HOLD; no EN availability/path is inferred.
Phase E documentation device actions **0**; **Stage 2 LittleFS HOLD / NOT
PERFORMED**, no new hardware authorization. Historical text below is preserved.

5 October 2026. Started from verified clean
`a702c90c285189eff7ee19ea8f1da8bbc0274fa0`, existing branch
`feature/shino-tv-m9-flash-layout-liberation`, PR #42 Draft/OPEN/unmerged.
No branch switch/new PR, firmware edit, local candidate build or device contact.
The active [roadmap](ROADMAP.md) records both this phase and the owner's hardware
correction. Earlier Phase B/C results remain dated evidence.

| Gate | Result / scope |
| --- | --- |
| PHASE D RTC/EBOOT NEUTRALIZATION | **PASS** — deterministic pinned-source / synthetic model qualification |
| RTC_MEMORY_ACCESS_GATE | **PASS** — exact esptool 5.4.0 / version-2 stub and two aligned mapped RTC words |
| RTC_NEUTRAL_STATE_GATE | **PASS** — zero magic rejects COPY regardless of remaining words; zero CRC mirrors Core clear |
| RTC_TO_NORMAL_BOOT_TRANSITION_GATE | **PASS** — source-supported powered EXT_RST path via existing RST pad; physical retention NOT_RUN |
| Historical EBOOT_COLD_START_GATE | **HOLD** — power-on remains unsuitable; Phase D does not promote Phase C's cold path |
| PHYSICAL_RUNTIME_GATE | **NOT_RUN** |
| PHYSICAL WRITE | **HOLD** — Stage 1 is not authorized by Phase D |

These PASS results describe a conditional source/model procedure, never a
physical RTC read/write/reset observation. DEVICE CONTACTS / SERIAL I/O / RTC
WRITES / FLASH WRITES / REBOOTS / device FILESYSTEM WRITES are all **0**.
Ordinary local source/test/document files and disposable CI build products are
not device filesystem writes. No real MASTER/PRE/POST is read or uploaded.

## Established owner hardware and remaining question

The owner explicitly confirms this same unit's exposed header:
**RST — GPIO0 — 3V3/VCC — RX — TX — GND**. RST/GPIO0/RX/TX/GND availability,
UART ROM download and full 4 MiB reads using reversible micro-hooks are known
owner evidence. Do not ask for soldering, new PCB access or new photographs.
EN/CH_PD is **not known/exposed** and must not be inferred from RST.

The remaining physical question is whether operating the known RST pad produces
the documented **EXT_RST** reset while preserving RTC on this board, rather than
interrupting power or pulling EN low. The source contract below qualifies that
mechanism; Phase D has not measured this pad's electrical behavior or retained
RTC across a reset. Availability is known; physical transition qualification is
NOT_RUN. Future preflight uses the existing project wiring record and owner's
established access, with separate exact-operation approval before contact.

## Unchanged frozen candidate and resource boundary

LOCAL `research-local/m9-phase-b/candidate-4m2m.bin`: **399168 B**, SHA-256
`cd99139121fa47fedd6286a185fb16e8fb9e120280ecd75f1c6b41b905e31011`.
Source `02b4be4cd4c2e0651d376001c030f1505123adb6`; environment
`esp12e_m9_4m2m`. Phase D only rehashes retained evidence; no rebuild/replacement.
Payload `0x000000..0x06173F`, destructive sectors `0x000000..0x061FFF`,
protected PRE/POST equality `0x062000..0x3FFFFF` (**3792896 B**).
Final-sector slack **2240 B** is still outside required payload equality.

No firmware runtime/static-resource change: retained linked flash **395015 B**,
static RAM **40340 B + 56 B noinit**. New model transforms **128 B** locally;
future clear concerns **8 RTC bytes**, leaving the other **120 bytes** untouched.
No new MCU code/heap/stack cost. Runtime heap/stack and recovery remain NOT_RUN.
Default 4m3m, opt-in 4m2m, disabled native/FS/OEM optional writers, profile 0,
Digest, telemetry TTL, media deadline, R3 PARTIAL / R10 BLOCKED are unchanged.

## Exact Core invalidation contract

[Core 3.1.2 command header](https://github.com/esp8266/Arduino/blob/210897ef83305496947c4e73c937bab52a33cb48/bootloaders/eboot/eboot_command.h)
and [implementation](https://github.com/esp8266/Arduino/blob/210897ef83305496947c4e73c937bab52a33cb48/bootloaders/eboot/eboot_command.c)
are pinned in `tools/m9_executor_sources.json`, rechecked by the Phase C identity
gate before the Phase D gate. Xtensa 32-bit enum/uint32 layout is 32 words:
magic, action, args[29], CRC. Size **128 B**, CRC offset **124 / 0x7C**.

| Property | Exact contract |
| --- | --- |
| RTC_MEM / magic | volatile uint32 pointer / **0x60001200** |
| CRC word | **0x6000127C**, aligned to 4 bytes |
| Magic accepted | `(magic & 0xFFFFF000) == 0xEB001000` |
| Command accepted | magic condition **AND** CRC of preceding 124 bytes matches stored CRC |
| Invalid result | `eboot_command_read()` returns 1 |
| Valid COPY | valid command with action 1 |
| Official clear | two volatile 32-bit stores of zero: magic then CRC; no other word cleared |

Zero magic fails the mask comparison even if action/args remain a valid COPY
and CRC happens to match. Zero CRC is not independently relied on to reject;
clearing it reproduces the official stronger two-word neutral state. No random
probability or reset-reason heuristic is used. The pinned
[eboot main](https://github.com/esp8266/Arduino/blob/210897ef83305496947c4e73c937bab52a33cb48/bootloaders/eboot/eboot.c)
selects LOAD_APP with args[0]=0 when command read fails: **pending_copy=false,
default load app at zero**. That excludes eboot's retained COPY writer, not all
possible later SDK/application flash activity. First normal boot still requires
the valid verified Stage-1 app and separately gated runtime/recovery observation.

Read-only disassembly of the already installed Core `eboot.elf` confirms CRC
load offset 124 and two zero stores; literal pool addresses are 0x60001200 and
0x6000127C, read loop ends at 0x60001280. No compiler/rebuild was invoked.
Source hashes are the machine-enforced identity; ELF inspection is supplementary.

## Exact esptool 5.4.0 path

Pinned identities and hash rules are inherited from
[Phase C](M09_PHYSICAL_EXECUTOR_QUALIFICATION.md): esptool
`5ac7935ee036f64080a4b2f5cda6c9a6188ae93b`, version-2 stub v1.2.2
`23959b780454adf885916d42f2274ec648e96a94`, library
`d61983fa4d1f66b9c088608c1f702ad877121279`, Core
`210897ef83305496947c4e73c937bab52a33cb48`. The complete 53-file esptool
inventory remains pinned. Phase D adds reset-primitive and library macro hashes,
and verifies the existing pinned stub handler/main as actual files in local/CI
source audits. No stub/helper is rebuilt. Public release provenance links the
distributed binary to the source; this is not a reproducible stub-build claim.

| Trace | Audited behavior |
| --- | --- |
| `esptool/__init__.py` CLI | `write-mem ADDRESS VALUE [MASK]`, default positional mask `0xFFFFFFFF`; `read-mem ADDRESS`; `AnyIntType` supports hex |
| `cmds.write_mem` | `esp.write_reg(address, value, mask, 0)`; no flash image/header processing |
| `cmds.read_mem` | prints `ADDRESS = VALUE`, each `#010x`, e.g. `0x60001200 = 0x00000000` |
| `loader.write_reg` | WRITE_REG 0x09, packed `<IIII`: address/value/mask/delay=0; optional extra delayed write is not used |
| `loader.read_reg` | READ_REG 0x0A, packed `<I` address, response uint32 value |
| ESP8266 target | inherits these primitives; no target-specific whitelist excluding these addresses |
| v2 `s_write_reg` | little-endian 32-bit entries; `value & mask`, combines old bits only for partial mask; `REG_WRITE(addr, write_value)` |
| v2 `s_read_reg` | single 4-byte address; `REG_READ(addr)` in response value |
| Library macros | dereference `volatile uint32_t*`; RTC data range **0x60001200..0x600013FF** explicitly mapped in ESP8266 `soc.h` |
| Alignment | CLI accepts integers without validating 4-byte alignment; this packet restricts exactly the two aligned words above |

The CPU mapping plus Core's official RTC volatile accesses and v2 direct access
qualify these addresses; an integer API alone would not suffice. Selected full
mask replaces the complete word with zero; partial masks are excluded. No flash
erase/program/header rewrite or filesystem operation occurs in these two
handlers. Stub setup uploads/executes RAM code, initializes SPI/controller state
and DRAM BSS, but does not run eboot/app or erase/program the flash array. The
packet does not claim that only two UART transactions occur: sync/chip info/stub
preparation accompany each command.

ROM and stub both expose the register protocol in the official
[serial protocol documentation](https://docs.espressif.com/projects/esptool/en/latest/esp8266/advanced-topics/serial-protocol.html).
The opaque ROM implementation does not provide the same address-specific source
proof. **PASS is for the selected explicit version-2 stub; `--no-stub`/fallback
is not qualified by Phase D.** Exact round-trip comparison of address and uint32
readback is possible, but has not been performed on the owner unit.

### Reset, reopening and completion

`prepare_esp_object()` opens/connects, syncs, reads chip info and runs/detects
the stub. `--before no-reset --connect-attempts 1` prevents a requested entry
reset; default port-open count is 1. Reject `ESPTOOL_OPEN_PORT_ATTEMPTS`, config
or stub overrides. WRITE_REG/READ_REG have no whole-flash-write retry/reconnect
wrapper: loader packet-response scanning is not a fresh memory-write retry.
Failure means STOP; never auto-rerun a failed word operation under this protocol.

Teardown calls `reset_chip`; `--after no-reset-stub` only logs staying in the
stub, then closes the port. Command success itself requests no reset. Distinct
CLI steps reopen/close the port; OS/adapter modem-line behavior cannot be proven
away with flags. **DTR/RTS must be electrically isolated from GPIO0/RST/EN**.
Unexpected port-induced reset, power interruption, loss of stub, or application
boot invalidates the sequence and requires a separate new decision. Use no
terminal program with implicit reset control between verification and RST.

`--after hard-reset` uses `esp_pylib.serial_reset.hard_reset()` to pulse RTS
for standard EN wiring. `--after no-reset` from stub calls `soft_reset(True)`;
it is not interchangeable with `no-reset-stub`. ESP8266 `watchdog_reset()` falls
back to hard reset. None is selected. Phase C's Stage-1 flash writer still has
its separately documented internal retry/default-reset reconnect behavior;
postwrite capture/comparison must complete before this RTC sequence starts.

## Reset retention and option comparison

The official [Non-OS SDK API Guide v1.5.4, system_get_rtc_time note, printed page 31](https://www.espressif.com/sites/default/files/2c-esp8266_non_os_sdk_api_guide_en_v1.5.4.pdf)
documents RTC memory retention for EXT_RST, watchdog and system_restart, while
power-on and CHIP_EN leave RTC memory random. Retention therefore requires
continuous main power and no EN reset after the two-word readback. This is a
published chip behavior, not observed board behavior.

[Boot-mode selection](https://docs.espressif.com/projects/esptool/en/latest/esp8266/advanced-topics/boot-mode-selection.html)
documents GPIO0 selection on reset: low enters download, released high selects
flash. GPIO2/GPIO15 must retain their normal boot levels. The
[ESP8266EX datasheet](https://www.espressif.com/sites/default/files/documentation/0a-esp8266ex_datasheet_en.pdf)
separates active-low EXT_RSTB (pin 32) from CHIP_EN (pin 7). Applying external
reset with normal straps yields ROM flash boot, then the candidate eboot at zero;
no app is required to trigger that reset. No new loss of power is involved.

| Option | RTC / straps / eboot | Source proof and hardware | Writes / complexity / recovery decision |
| --- | --- | --- | --- |
| **A clear → verify → release GPIO0 powered → existing RST / EXT_RST** | retained / sampled on external reset / flash eboot then invalid-command app at zero | SDK + boot contract; known RST/GPIO0/UART/GND, stable power, EN left alone | no new flash command; official stock primitives, manual external reset; **selected source PASS**, physical behavior NOT_RUN; abort on unexpected reset/loss |
| B system/software restart | SDK RTC retention documented; ROM/stub trigger and normal strap path not qualified | Core `EspClass::restart` calls SDK from app, not an audited callable stock loader procedure; watchdog also not selected | would add helper/call mechanism or run app before reset; **HOLD**, not rendered; no recovery claim |
| C esptool `run` | no reliable reset/strap/eboot transition on selected v2 | loader `run()` uses zero-length FLASH_BEGIN/FLASH_END; v2 FLASH_END reboot TODO; `RUN_USER_CODE` soft-reset alternative also TODO | zero-length begin is not array erase, but **rejected** boot path; do not substitute legacy behavior |
| D power-cycle / EN pulse | destroys deterministic RTC evidence | SDK; existing USB-C power is not a substitute for EXT_RST | **rejected**, prior neutral receipt invalid; must not attempt probabilistic boot/retry |
| E custom RAM helper | would need independent retention/strap/entry proof | not needed because A is source-supported | extra code/trust/recovery risk; **not implemented**, no extra binary or command |

If the known RST pad cannot be used as EXT_RST without power/EN interruption,
transition is **HOLD**; no alternate helper/power-cycle is automatically approved.
An eboot LOAD_APP result does not prove successful LCD/network/runtime behavior.

## Future hardware requirements and operator checklist (no action now)

| Capability | Classification | Evidence / future check |
| --- | --- | --- |
| Existing GPIO0 | **REQUIRED / KNOWN** | reversible strap retained through PRE/write/POST/clear/readbacks; release only after both zeros, with power still on |
| Existing RST pad | **REQUIRED / KNOWN** | selected EXT_RST control; existing access needs no new PCB work; actual retained transition NOT_RUN |
| Existing RX/TX/GND | **REQUIRED / KNOWN** | prior same-unit ROM/full-read access; correct crossed RX/TX and common GND, compatible 3.3 V UART logic |
| Stable main USB-C power | **REQUIRED** | continuous through verification, GPIO0 release and RST; no adapter-power substitution/back-power |
| EN/CH_PD access | **NOT REQUIRED; not known/exposed** | leave existing enable circuit undisturbed; no probing/new access required by Phase D; reset on EN is forbidden after clear |
| UART DTR/RTS | **OPTIONAL adapter feature; FORBIDDEN connected controls in selected packet** | omit/isolate both from target, regardless of auto-reset defaults |
| 3V3/VCC pad | **KNOWN, not a required power source** | no 5 V logic, no short to adjacent pad, no second supply/back-power path |
| Solder/new PCB access/new photos | **EXCLUDED** | existing reversible micro-hooks and established project wiring suffice for planning |

Before any future separately approved contact, compare these conditions against
the already established header/wiring record; do not reopen the availability
question or request new photographs:

1. Confirm planned use of the **existing RST** as external reset, not EN/power
   control; keep USB-C supply continuous and control lines isolated. Any unresolved
   pad-reset mechanism keeps physical preflight HOLD; no new PCB access assumed.
2. Preserve normal GPIO2/GPIO15 levels and release only the GPIO0 strap while
   powered after final zero/zero verification. Keep micro-hooks mechanically
   isolated; no adjacent RST/3V3/GPIO0 bridging. No invented pulse duration.
3. Confirm exact interpreter/package/Core/stub pins, no overrides, same unit and
   4 MiB, frozen candidate rehash, separate MASTER custody/recovery gate and
   explicit authorization covering internal Stage-1 retries/resets and reads.
4. Require fresh independent PRE/write/POST verification in ROM/stub before RTC
   steps; no application between write and protected-region comparison.
5. Require both successful zero writes, then address-matched zero readbacks with
   successful exit status, no reset/power loss/reconnect. ACK alone is insufficient.
6. No further CLI/terminal connection after final readback; GPIO0 release and
   existing RST external reset must retain that receipt. An unexpected event
   means STOP; preserve uncertainty, no automatic repeat/restore/reboot.
7. First normal boot/runtime/LCD/resources remain separate NOT_RUN evidence;
   use existing Phase C bounded runtime/recovery criteria under later approval.
   Pinned eboot prints `~` for command rejection, then `ld` for LOAD_APP;
   valid COPY instead enters `@` / `cp:`. A later approved passive boot record
   can corroborate rejection and app entry. It cannot replace the zero readbacks,
   preserved reset contract or prove absence of all later flash writes.

## Updated S0–S12 sequence

This overlay supersedes only Phase C I/S8–S10 cold-power transition. Phase C
capture, candidate, internal retry and MASTER gates remain. S8/S9 are folded
into S7C/S7D; **S10 FIRST_NORMAL_BOOT** is not a cold power-on. All physical
states are future design, unexecuted. Flash column distinguishes planned
operations from possible boot/SDK activity; no runtime no-write claim.

| State | CPU / GPIO0 | RTC expected | eboot / app | Flash risk | Failure / abort |
| --- | --- | --- | --- | --- | --- |
| S0 offline review | no contact / unknown | unknown | none by Phase D | none by Phase D | absent exact authority/recovery → HOLD |
| S1 separate exact physical approval | no operation yet / planned low | unknown | none by protocol | none | missing approval → STOP |
| S2 enter download | ROM / low | unknown, COPY possible | neither | no app; unexpected eboot may copy | entry/control mismatch → STOP |
| S3 same-unit identity and 4 MiB | ROM/stub / low | unknown | neither | no array write requested | mismatch/loss/reset → STOP |
| S4 private MASTER + fresh PRE gates | ROM/stub / low | unknown | neither | reads only | missing custody/freshness/recovery → STOP |
| S5 rehash exact Stage-1 candidate | ROM/stub / low | unknown | neither | local only | drift → STOP |
| S6 separately approved app write | stub / low | unknown | neither expected | sectors 0..0x061FFF; internal retry/reset caveat | write error/unexpected app/unsafe reset → STOP |
| S7 POSTWRITE_VERIFIED | stub / low | still unknown | neither | read-only full POST; payload/protected compare | any mismatch → STOP, no boot |
| S7A RTC_COMMAND_NEUTRALIZED | stub / low | two successful zero stores, not yet verified | neither | no array write in RTC handlers | failure/loss/reset → STOP |
| S7B RTC_NEUTRALIZATION_VERIFIED | stub / low | **magic=CRC=0**, both read back; other words unconstrained | neither | reads only | wrong/missing value/exit/address → STOP |
| S7C GPIO0_RELEASED_WHILE_POWERED (replaces S8) | stub remains / released high | retain verified zeros | neither | no array operation | power/EN/reset/interruption → receipt invalid, STOP |
| S7D RTC_RETAINING_NORMAL_BOOT_RESET (replaces S9) | existing RST EXT_RST → ROM normal straps / high | retain zeros by source contract | ROM then eboot; app only after rejection/load | eboot COPY excluded by zeros; load reads app | wrong reset/strap/uncertainty → HOLD, no retry |
| S10 FIRST_NORMAL_BOOT | app at zero / high | zeros retained; invalid command does not call Core clear again | eboot rejects COPY, LOAD_APP zero; app runs | later SDK/app activity not proven absent | reset/unsafe resources/corruption/lost recovery → STOP |
| S11 bounded runtime qualification | app / high | no new RTC operation authorized | app under separate approval | writer policy remains gated; runtime NOT_RUN | any reset/failure → S12, no timer restart |
| S12 abort / separate recovery decision | preserve observed mode / no assumed change | unknown if sequence disturbed | no new boot authorized | only separately approved exact MASTER restore can write | no automatic recovery/Stage 2 |

## PRINT ONLY RTC packet — NOT AUTHORIZED BY PHASE D

LOCAL interpreter: **Python 3.12.10**, executable
`C:\Users\jerry\AppData\Local\Programs\Python\Python312\python.exe`, SHA-256
`4d6f5f81a4bca11191c4c7c6b43632694d0a4ce74e068619d8fdc161d469859a`.
Exactly esptool 5.4.0, esp-pylib 1.1.5, pyserial 3.5, version-2 stub. The local
renderer rejects interpreter identity drift; CI checks source/model with its
own interpreter and does not render a substituted physical packet. `<PORT>`
is deliberately never resolved. No command below was executed.

**RTC MAGIC CLEAR — NOT AUTHORIZED BY PHASE D**

```powershell
& "C:\Users\jerry\AppData\Local\Programs\Python\Python312\python.exe" -I -m esptool --chip esp8266 --port "<PORT>" --baud 115200 --stub-version 2 --before no-reset --after no-reset-stub --connect-attempts 1 write-mem 0x60001200 0x00000000 0xFFFFFFFF
```

**RTC CRC CLEAR — NOT AUTHORIZED BY PHASE D**

```powershell
& "C:\Users\jerry\AppData\Local\Programs\Python\Python312\python.exe" -I -m esptool --chip esp8266 --port "<PORT>" --baud 115200 --stub-version 2 --before no-reset --after no-reset-stub --connect-attempts 1 write-mem 0x6000127C 0x00000000 0xFFFFFFFF
```

**RTC MAGIC READBACK — NOT AUTHORIZED BY PHASE D**

```powershell
& "C:\Users\jerry\AppData\Local\Programs\Python\Python312\python.exe" -I -m esptool --chip esp8266 --port "<PORT>" --baud 115200 --stub-version 2 --before no-reset --after no-reset-stub --connect-attempts 1 read-mem 0x60001200
```

**RTC CRC READBACK — NOT AUTHORIZED BY PHASE D**

```powershell
& "C:\Users\jerry\AppData\Local\Programs\Python\Python312\python.exe" -I -m esptool --chip esp8266 --port "<PORT>" --baud 115200 --stub-version 2 --before no-reset --after no-reset-stub --connect-attempts 1 read-mem 0x6000127C
```

Required future readback lines are `0x60001200 = 0x00000000` and
`0x6000127c = 0x00000000` (numeric comparison; case does not change value).
No dump/file capture, flash command, Stage 2, `run`, soft/hard reset or helper is
included in this packet. GPIO0 release / existing RST are manual future steps
outside the printed CLI packet and need later exact approval.

## Validation and remaining gates

`tools/m9_rtc_neutralization.py` performs local source reads, deterministic byte
models and text rendering only. No serial/esptool-runtime/subprocess import or
physical executor. Source drift or an override fails closed. The sequence
validator returns **PASS_SYNTHETIC_SEQUENCE**, never a device receipt, even when
all supplied conditions are true. An invalid/corrupted RTC block alone is never
classified as deliberately verified neutral.

**23 new offline tests** cover valid COPY/masked magic/CRC, zero magic with
independent args and matching CRC, preservation of 120 bytes, corruption vs
deliberate verification, length/alignment, exact sequence/order/readback/reset
failures, reset matrix, exact packet, no executor, source drift/config override,
unchanged Phase C cold gate/frozen constants, rehash of the retained LOCAL BIN
when present (absence/private-input exclusion in CI), and five-JSON privacy allowlist.
Existing Phase A/B/C and source/policy tests remain required. Dedicated CI now
runs **100 focused tests** (previous 77 +23), plus independent baseline/opt-in/FS
builds and the full installed/Core/stub/library RTC source gate. No private
candidate/MASTER/readbacks/policy enter the allowlist; public source checkouts
are read-only audit inputs. Resulting exact commit/check URLs go in PR #42.

Before physical preflight: exact separate owner authorization, existing RST's
EXT_RST behavior and continuous-power/control isolation review, private MASTER
custody/recovery, same-unit/4 MiB and exact candidate/interpreter revalidation,
fresh PRE/write/POST protocol with disclosed internal retries, then zero/zero
and first-normal-boot/runtime evidence under bounded later approval. Known pad
availability is not a blocker. No EN access, new photos, soldering or new PCB
access is requested. **STOP after Phase D; keep Draft PR #42 unmerged.**
