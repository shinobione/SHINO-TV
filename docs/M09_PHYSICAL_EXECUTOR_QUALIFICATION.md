# Mission 9 Phase C — physical executor qualification (OFFLINE ONLY)

**Phase D continuation, 5 October:** [deterministic RTC clear/readback and powered
existing-RST transition](M09_RTC_EBOOT_NEUTRALIZATION.md) adds source/model PASS
gates and supersedes only packet I / S8–S10 cold-power boot recommendation.
Power-on EBOOT_COLD_START_GATE remains HOLD; Phase C results below are historical.
Owner correction establishes exposed RST/GPIO0/RX/TX/GND and prior same-unit
micro-hook UART ROM/full 4 MiB reads; no new photos/PCB access/soldering needed.
EN/CH_PD is not known/exposed. Selected transition retains power, verifies RTC
magic/CRC zero, releases GPIO0 while powered, then uses existing RST as EXT_RST.
Source mechanism qualified; physical RTC retention/runtime NOT_RUN and all
physical writes HOLD. Frozen LOCAL candidate and firmware remain unchanged.

5 October 2026. Continue clean
`feature/shino-tv-m9-flash-layout-liberation` at
`02b4be4cd4c2e0651d376001c030f1505123adb6`; PR #42 verified Draft, OPEN,
unmerged before edits. No branch switch or new PR. Owner decision is recorded
in the active [roadmap](ROADMAP.md). This document adds executor evidence to
[Phase B](M09_FIRST_PHYSICAL_MIGRATION.md), preserving its dated results.

| Gate | Result and precise scope |
| --- | --- |
| PHASE C OFFLINE PHYSICAL EXECUTOR QUALIFICATION | **HOLD**: deliverables complete, cold first-boot exclusion unresolved |
| EBOOT_COLD_START_GATE | **HOLD**: true power-on does not guarantee an invalid RTC command |
| ESPTOOL_EXECUTOR_GATE | **PASS**: unmodified 5.4.0 / explicit version-2 stub, bounded source model below; physical assumptions still require review |
| STAGE1_READBACK_MODEL | **PASS**: deterministic synthetic local-file evidence only |
| PHYSICAL_RUNTIME_GATE | **NOT_RUN** |
| PHYSICAL WRITE | **HOLD**; no physical step authorized |

Device contacts, serial I/O, physical writes, erases, reboots, filesystem
mounts/formats/writes: **0**. No device discovery, serial import, esptool
execution, or physical-command subprocess. GitHub source retrieval / CI are
offline with respect to the SmallTV. CI builds disposable independent binaries;
the retained LOCAL candidate is never rebuilt/replaced. No `firmware/**` edit.
Default 4m3m / opt-in 4m2m, profile 0, disabled writers, Digest, telemetry TTL,
media transport boundaries and R3 PARTIAL / R10 BLOCKED remain unchanged.

## Frozen proposed payload and array geometry

| Item | Exact LOCAL Phase B value |
| --- | --- |
| Source | `02b4be4cd4c2e0651d376001c030f1505123adb6` |
| Environment | `esp12e_m9_4m2m` |
| BIN bytes N | **399168 / 0x61740** |
| SHA-256 | `cd99139121fa47fedd6286a185fb16e8fb9e120280ecd75f1c6b41b905e31011` |
| Target | `0x000000` |
| Payload | `0x000000..0x06173F` |
| Sector-rounded destructive extent R | **401408 / 0x62000**, `0x000000..0x061FFF` |
| Final-sector slack, equality not required | `0x061740..0x061FFF`, **2240 B** |
| Protected region for PRE/POST equality | `0x062000..0x3FFFFF`, **3792896 B** |
| Historical OEM FS | `0x100000..0x3F9FFF` |
| Future SHINO LittleFS | `0x200000..0x3F9FFF` |
| Reserved tail | `0x3FA000..0x3FFFFF` |
| Expected physical flash | **4194304 B / 4 MiB**, must later be confirmed on same unit |

The linker change does not reclaim the historical FS by itself. No Stage 2
command exists here. The private MASTER is separate rollback authority and was
not opened, hashed, copied or published. Owner PRE/POST files were not opened.

## Exact source provenance and fail-closed identity

[Source manifest](../tools/m9_executor_sources.json) pins 53 esptool package
source/JSON/README files, relevant Core files and seven upstream stub/library
audit files. SHA-256 uses CRLF-to-LF canonicalization for source portability;
the aggregate hashes sorted `name NUL digest LF` records. This is content
identity, not a signature, hardware proof or a full Python supply-chain attestation.

| Source | Immutable revision / evidence |
| --- | --- |
| Arduino 3.1.2, PlatformIO package 3.30102.0 | [`210897ef83305496947c4e73c937bab52a33cb48`](https://github.com/esp8266/Arduino/tree/210897ef83305496947c4e73c937bab52a33cb48) |
| esptool 5.4.0 | [`5ac7935ee036f64080a4b2f5cda6c9a6188ae93b`](https://github.com/espressif/esptool/tree/5ac7935ee036f64080a4b2f5cda6c9a6188ae93b) |
| Actual default version-2 RAM stub v1.2.2 | [`23959b780454adf885916d42f2274ec648e96a94`](https://github.com/espressif/esp-flasher-stub/tree/23959b780454adf885916d42f2274ec648e96a94) |
| Stub's library submodule | [`d61983fa4d1f66b9c088608c1f702ad877121279`](https://github.com/espressif/esp-stub-lib/tree/d61983fa4d1f66b9c088608c1f702ad877121279) |
| Config parser / serial dependency | esp-pylib **1.1.5** (config source hashed), pyserial **3.5** (metadata only; never imported by these tools) |

Installed `cmds.py`, `eboot.c` and actual version-2 `esp8266.json` were compared
byte-for-byte by SHA against immutable official files: all matched. The stub JSON
SHA is `9ce821527ecb67224bf19cf78bef45a4de5b5f03ac08f100daf8de32499972e3`.
It is a public upstream binary, not an owner image. No rebuild of the stub was
used as an identity substitute. Source-to-binary correspondence relies on the
official release provenance, not a locally demonstrated reproducible stub build.

The Phase B legacy-stub discussion was provisional: **5.4.0 defaults to version
2**, confirmed in `__init__.py` and `StubFlasher` selection. The new packet pins
`--stub-version 2`; substitution/fallback/`--no-stub` is rejected operationally.

[Offline identity tool](../tools/m9_executor_preflight.py) never imports esptool
or serial and has no runner. It reads distribution metadata, checks package
inventory/content, verifies Core content, records interpreter path/version/raw
executable SHA, compares externally supplied interpreter/module identity and
validates the exact frozen candidate with the Phase B parser and external SHA.
It reports target zero, R, 4 MiB expectation and policy flags. Config source is
pinned; any `[esptool]` section in cwd, user config directory or home, or
`ESPTOOL_CFGFILE` / `ESPTOOL_STUB_VERSION` override closes the gate. Repeat in the
same cwd/interpreter/environment immediately before the future command. Require
a trusted/quiescent installation and files throughout; this does not eliminate
time-of-check/time-of-use changes or unreviewed Python startup/dependency code.

Recorded LOCAL interpreter: Python **3.12.10**,
`C:\Users\jerry\AppData\Local\Programs\Python\Python312\python.exe`,
SHA `4d6f5f81a4bca11191c4c7c6b43632694d0a4ce74e068619d8fdc161d469859a`.
Module root: its `Lib\site-packages\esptool` directory. Reviewed aggregate:
`e5f3db49216d341df8afe2c36a1e51d6b1c07abbe27561f2ba06c2c448f604d0`.
Future operator must use external recorded values, not accept new values merely
because the tool prints them. Physical templates use the explicit executable
and `-I` to exclude cwd/PYTHONPATH Python module shadowing. CI's interpreter is
independent; its source-only PASS does not approve the LOCAL interpreter.

## Eboot / RTC audit and reset conclusion

Trace actual `bootloaders/eboot/eboot_command.h/.c`, `eboot.c`,
`cores/esp8266/Updater.cpp`, `Esp.cpp`, `core_esp8266_main.cpp` and
`reboot_uart_dwnld.cpp` at the pinned Core revision:

1. The command is **128 bytes / 32 words** at RTC user base **0x60001200**,
   corresponding to SDK word offset 64. Layout: magic, action, 29 arguments,
   CRC at byte 124. `eboot_command_read` copies those words and accepts masked
   magic `(magic & 0xfffff000) == 0xeb001000` plus CRC over the first 124 bytes.
   CRC is seeded `0xffffffff`, polynomial `0x04c11db7`. No reset-reason check.
2. Successful `UpdaterClass::end` for **U_FLASH**, after applicable signature/MD5
   and `_verifyEnd`, writes ACTION_COPY_RAW, source `_startAddress`, destination
   zero, length `_size` into RTC. Conditional atomic U_FS uses the same command
   mechanism with FS destination. The frozen profile-0 graph has no active
   Updater path; that does not invalidate a command left by previous firmware.
3. Before Arduino `setup()`, eboot `main` reads RTC. Invalid command selects
   ACTION_LOAD_APP at zero. Valid COPY calls `copy_raw` with RTC arguments,
   sector-rounds, may decompress gzip, erases/writes the destination and loads
   it on success. It clears magic/CRC in RTC after handling a valid command.
   Failure can leave partial flash and trigger software reset. Not A/B atomic
   recovery; no authenticated/bounded candidate gate on retained copy arguments.
4. `print_version` reads flash metadata; the app loader reads image headers.
   Neither independently requests a copy. The traced eboot graph's sole copy
   trigger is RTC action. This does not establish arbitrary OEM bootloader behavior.
5. `EspClass::reset` calls local restart; `restart` calls `system_restart` then
   suspends. UART-download restart changes CPU/cache/register state and transfers
   into a download path; it supplies no deterministic RTC command invalidation.
   None of those calls is used here or substituted for full removal of power.

Core source does not implement all ROM/SDK reset semantics. Espressif's
[Non-OS SDK API guide, printed page 31](https://www.espressif.com/sites/default/files/2c-esp8266_non_os_sdk_api_guide_en_v1.5.4.pdf)
states RTC data is retained across EXT_RST, watchdog and system_restart; deep
sleep retains user RTC data. Power-on and CHIP_EN reset give **random** RTC data.
This supports loss of retention, **not zeroing or guaranteed rejection** of the
magic/CRC parser. The guide is supplementary hardware/SDK evidence, not the
pinned Core implementation. No probabilistic CRC argument is upgraded to proof.

[Official ESP8266 boot-mode selection](https://docs.espressif.com/projects/esptool/en/latest/esp8266/advanced-topics/boot-mode-selection.html)
places UART download in ROM when GPIO0 is low at reset (other straps must also
be correct). Under actual cold ROM entry, flash eboot does not execute first.
Maintaining the ROM strap through all reconnects prevents a reset from selecting
normal flash boot. These are hardware assumptions to verify later: correct
GPIO0/GPIO2/GPIO15 levels, reliable reset wiring, no UART back-power, alternate
power or retained supply. No arbitrary discharge time is invented.

On the **later normal cold boot**, newly written eboot again accepts any valid
RTC command; UART application write affects flash, not this RTC parser state.
Full power-off twice improves isolation but does **not deterministically prove**
invalid RTC contents at that last boot. Therefore **EBOOT_COLD_START_GATE HOLD**.
No RTC clear/write command or custom bootloader is implemented. A separately
reviewed deterministic exclusion of copy at first normal boot remains required
before authorizing Stage 1, potentially requiring a new reviewed approach.

## Official esptool retry audit and selected policy

Exact pinned `cmds.write_flash`, `loader.flash_begin/flash_block/flash_finish`,
`targets/esp8266.py`, reset/config/CLI selection and version-2 stub source traced.

| Behavior | Actual source result |
| --- | --- |
| Whole-image retry | `SerialException` inside write attempt only; `WRITE_FLASH_ATTEMPTS = 2`. Encrypted branch refuses retry; encryption is excluded here. |
| Retry inputs | Input is read once before attempts; `original_image` retained; reconnect restores it, repeats `flash_begin(uncsize,address)` and resets packet sequence to zero. Same address/size/file bytes. |
| Reconnect | Closes/reopens port, up to default 7 outer iterations on serial errors; `esp.connect()` uses default-reset/default 7 connection attempts. CLI one-connect/before-no-reset do **not** propagate. Fatal reconnect failures abort; this is not a universal 49-reset promise. RAM stub is reloaded after reset. |
| Packet retry | `flash_block` catches `FatalError`, default 3 deliveries of same packet and sequence. Not proven idempotent: version-2 uncompressed handler uses current offset, not sequence deduplication. Lost ACK replay may shift/duplicate data within N. |
| Header | All three `keep` flags return original image unchanged before header rewriting. Input padded to 4-byte alignment; frozen N already aligned. No compression/diff/fast reflash/encryption/multiple files/erase-all permitted. |
| Flash size | `keep` leaves header intact but detects/configures SPI flash parameters; require actual same-target 4 MiB result, abort fallback/unknown/mismatch. Not a request to erase 4 MiB. |
| Stub begin | Host sends exact N and zero. `ESP8266StubLoader.get_erase_size` returns N, bypassing ESP8266 ROM erase-size workaround. 16 KiB packets, last padded FF but stub clamps bytes to remaining N. |
| Stub erase/write | `s_init_flash_operation` rounds start/end to sectors. Conditional blank-sector skip; first dirty sector switches to erases. Library uses aligned 64 KiB only when remaining >=64 KiB, else 4 KiB. Sequential writes decrease remaining/increase offset; duplicates cannot expand N/R. |
| Retry erase | Begin restarts erase cursor/range. Already erased blank sectors may be skipped; dirty programmed sectors can be erased again. Same range, additional wear/time and partial-state exposure, not atomicity. |
| End | `flash_finish(reboot=False)` waits for final processing, sends flag 1. Version-2 handler clears operation state; its reboot branch is TODO and does not run app. `reset_chip(no-reset-stub)` does nothing beyond logging. Closing/reopening adapter can still affect physical reset lines. |
| Verification | Stub MD5 over `base_address,base_size` = payload N (including any 4-byte padding). Normal full-image MD5 mismatch is fatal, not a new fast-reflash cycle. Serial fault during end/MD5 outside write loop aborts. MD5 alone does not prove slack, protected bytes, fresh capture, first boot or recovery. |

Relevant official paths:
[host write command](https://github.com/espressif/esptool/blob/5ac7935ee036f64080a4b2f5cda6c9a6188ae93b/esptool/cmds.py),
[loader](https://github.com/espressif/esptool/blob/5ac7935ee036f64080a4b2f5cda6c9a6188ae93b/esptool/loader.py),
[stub command handler](https://github.com/espressif/esp-flasher-stub/blob/23959b780454adf885916d42f2274ec648e96a94/src/command_handler.c),
[library array operations](https://github.com/espressif/esp-stub-lib/blob/d61983fa4d1f66b9c088608c1f702ad877121279/src/flash.c).
Source operations bound the addressable array; this does not prove hardware fault
behavior or SPI status-register state. ROM SPI primitive internals are a trust
boundary. Stub startup attaches/configures SPI and initializes RAM/BSS, without
invoking eboot or an application/FS writer in the traced graph.

**Policy A selected: official unmodified 5.4.0, bounded retry semantics accepted
for this source model. ESPTOOL_EXECUTOR_GATE PASS.** This is one future explicit
CLI write operation with up to two internal whole writes, not “one physical
attempt”; later owner consent must explicitly include these retries and possible
internal resets. Require continuous ROM strap and correct wiring through port
open/close/reconnect until full power-off. Any unexpected normal boot, lost strap,
failed verification, timeout, unknown ID or changed source closes the physical
gate; no operator rerun or automatic recovery. No custom Policy B one-attempt
writer is warranted by range expansion, and none is implemented. It would need
separate review, while not solving RTC cold-boot uncertainty by itself.

## Fresh full-chip PRE/POST selection and local verifier

Select two **new, private, independent 4194304-byte files**, both captured in
the same ROM/stub isolation session before normal boot. Store receipts locally:
same-unit identity, source/interpreter gate, ordering, command/log results, no
application boot between captures, complete sizes and file SHA. Refuse existing
output filenames operationally; esptool can overwrite files, so a new pathname
is required. Local equality alone cannot authenticate freshness or hardware.

At 115200 baud, each 4 MiB UART transfer has a theoretical minimum ~364 seconds
(10 bits/byte), plus framing/ACK/processing; plan stable power for both reads,
write and verification. Reads do not intentionally erase the array. This cost
buys a whole protected-region comparison including SDK tail. Do not compare
against old MASTER: legitimate SDK changes before PRE are not Stage-1 damage.

[Verifier](../tools/m9_stage1_readback_verify.py) reads local regular non-symlink
files only; rejects missing/directory/symlink inputs and aliases via resolution
and same-file inode checks (including hardlinks). Candidate is inspected using
Phase B image/CRC/extent gate, then rehashed against external custody SHA.
Exactly 4 MiB PRE and POST are required. Prove:

```
SHA256(candidate) == external expected candidate SHA
POST[0:N] == candidate
POST[R:0x400000] == PRE[R:0x400000]       # byte-for-byte
# POST[N:R] can differ; final touched-sector slack is not protected
```

Report explicit ranges, compared bytes, file hashes and all device/authorization
claims false. Candidate/PRE/POST must be quiescent private files; retain reports
locally. Synthetic tests alone run in CI; no owner MASTER/digest/PRE/POST uploaded.
This proves net local byte equality for the selected files, not absence of an
intermediate out-of-range write later restored, or behavior after boot.

## Power / reset state machine (model only, no transition executed)

All rows require **later** separately reviewed owner authorization. Every abort
enters S12; do not perform subsequent transitions or infer rollback permission.
“FS” means historical addressable FS contents, not SDK tail or flash status bits.

| Transition / later action | Expected CPU mode | App can execute? | Eboot can execute? | Array write possible? | Historical FS expected | Abort condition |
| --- | --- | --- | --- | --- | --- | --- |
| S0 NORMAL_DEVICE → S1 FULLY_UNPOWERED: remove **all** power/back-power | running → off | Until off | On unexpected reset | Existing firmware until off | Unknown before PRE | Power path not understood |
| S1 → S2 GPIO0_ROM_STRAP_SET: establish strap while off, correct other straps | off | No | No | No | Unchanged | Unsafe/inaccessible wiring; no ordinary UART/solder dependency assumed |
| S2 → S3 COLD_ROM_BOOT: cold power-on with strap maintained | ROM download | No, conditional on straps | No | No intended array write | Unchanged expected | Any normal boot/ambiguous supply/strap |
| S3 → S4 RAM_STUB_ACTIVE: exact identity, chip/flash identification; load pinned RAM stub | ROM → RAM stub | No | No | No intended array write | Unchanged expected | Wrong/unknown unit/size, stub/source drift, unintended boot |
| S4 → S5 PREWRITE_CAPTURED: full fresh private PRE read, verify complete length/receipt | RAM stub; reconnect must stay ROM/stub | No | No | No intended array write | PRE is baseline | Read failure/alias/existing filename/missing chronology |
| S5 → S6 STAGE1_WRITE_COMPLETED: immediate preflight then single reviewed write operation F | RAM stub; possible internal reset/reload | No if strap holds | No if strap holds | **Yes, R only in accepted model** | Preserved expected | No owner write consent; RTC gate HOLD; lost strap; any write/MD5 failure |
| S6 → S7 POSTWRITE_VERIFIED: full private POST before any app boot; local H passes | RAM stub | No | No | No new intended array write | **Byte equality of protected files required** | Payload/size/hash/protected mismatch or ambiguous capture |
| S7 → S8 FULLY_UNPOWERED_AFTER_WRITE: remove all power with strap retained | stub → off | No | No | No intended array write | Preserved as captured | Incomplete power isolation |
| S8 → S9 GPIO0_STRAP_REMOVED: remove strap while off | off | No | No | No | Preserved | Any residual power |
| S9 → S10 COLD_FIRST_BOOT: fresh normal power-on only with resolved RTC gate | ROM → eboot → app | Yes after load | **Yes** | **Possible RTC copy / SDK tail; unresolved** | **HOLD** until copy excluded | RTC exclusion missing (current state); reset, wrong boot |
| S10 → S11 STAGE1_RUNTIME_QUALIFICATION: bounded owner observation / separately approved telemetry | profile-0 app | Yes | On a reset | No app FS/OTA writer by source; SDK housekeeping possible | Source-expected, not measured after boot | Any reset, heap/stack hazard, corruption, lost recovery |
| Any → S12 HOLD_OR_ROLLBACK: stop; keep uncertain state, preserve private receipts | unknown/off/ROM as observed | Unknown | Unknown | Unknown until isolated | Unknown on failure | No automatic power/reset/write; separate exact MASTER authorization only |

Sequence: **S0→S1→S2→S3→S4→S5→S6→S7→S8→S9→S10→S11**;
failure branches **S12**. Current gate prevents approval of S5→S6 and S9→S10.
No phase transition is performed by a Python tool. No duration rule substitutes
for proven electrical power isolation. PRE/POST gate ends before first app boot;
SDK tail may legitimately change afterward, which must not rewrite its evidence.

## A–K print-only PowerShell packet

Canonical renderer: `python tools/m9_executor_preflight.py --print-commands`.
It only prints JSON strings. The following templates do not execute themselves.
All physical steps are **NOT AUTHORIZED BY PHASE C**. Replace placeholders only
in a separately approved future packet; no real COM port is included.

### A — local interpreter/source/frozen-candidate preflight

Run from the reviewed repository cwd with the externally recorded identities:

```powershell
& "<PYTHON_EXE>" tools/m9_executor_preflight.py --candidate "<CANDIDATE_BIN>" --expected-sha256 "<EXPECTED_CANDIDATE_SHA256>" --expected-python-sha256 "<EXPECTED_PYTHON_SHA256>" --expected-python-version "<EXPECTED_PYTHON_VERSION>" --expected-module-root "<ESPTOOL_MODULE_ROOT>" --core-root "<PINNED_CORE_ROOT>"
```

### B–D — NOT AUTHORIZED BY PHASE C; identify and capture fresh PRE

Prerequisites S1–S4, same unit, exact 4 MiB and continuous ROM strap.

```powershell
& "<PYTHON_EXE>" -I -m esptool --chip esp8266 --port "<PORT>" --baud 115200 --stub-version 2 --before no-reset --after no-reset-stub --connect-attempts 1 chip-id
& "<PYTHON_EXE>" -I -m esptool --chip esp8266 --port "<PORT>" --baud 115200 --stub-version 2 --before no-reset --after no-reset-stub --connect-attempts 1 flash-id
& "<PYTHON_EXE>" -I -m esptool --chip esp8266 --port "<PORT>" --baud 115200 --stub-version 2 --before no-reset --after no-reset-stub --connect-attempts 1 read-flash 0x000000 0x400000 "<PREWRITE_4MB_BIN>"
```

### E — repeat A immediately before F

Same interpreter/cwd/environment, frozen expected SHA, no substitution/rebuild.
A's full offline validation includes rehash. Refuse F unless all prerequisites
and separate physical authorization exist; RTC gate currently prevents F.

### F–G — NOT AUTHORIZED BY PHASE C; Stage 1 then full POST before boot

```powershell
& "<PYTHON_EXE>" -I -m esptool --chip esp8266 --port "<PORT>" --baud 115200 --stub-version 2 --before no-reset --after no-reset-stub --connect-attempts 1 write-flash --flash-mode keep --flash-freq keep --flash-size keep --no-compress 0x000000 "<CANDIDATE_BIN>"
& "<PYTHON_EXE>" -I -m esptool --chip esp8266 --port "<PORT>" --baud 115200 --stub-version 2 --before no-reset --after no-reset-stub --connect-attempts 1 read-flash 0x000000 0x400000 "<POSTWRITE_4MB_BIN>"
```

### H — local independent-file preservation check

```powershell
& "<PYTHON_EXE>" tools/m9_stage1_readback_verify.py "<CANDIDATE_BIN>" "<PREWRITE_4MB_BIN>" "<POSTWRITE_4MB_BIN>" --expected-sha256 "<EXPECTED_CANDIDATE_SHA256>"
```

### I — NOT AUTHORIZED BY PHASE C; manual S8–S10

Full power-off with ROM strap still set; remove strap **while unpowered**;
fresh cold normal boot only after a resolved EBOOT gate and separate approval.
No esptool auto-boot command, no Stage 2. Current I remains blocked.

### J — NOT AUTHORIZED BY PHASE C; separate MASTER restore decision

Re-enter separately approved cold ROM/stub isolation; same unit/4 MiB and
external private MASTER custody digest. The consent flag below records an
external assertion only; it creates no authority. Full exact MASTER, offset zero;
no application-only substitute, no synthetic combined image, no erase-all.

```powershell
& "<PYTHON_EXE>" tools/m9_master_restore_preflight.py "<PRIVATE_MASTER_BIN>" --expected-sha256 "<PRIVATE_CUSTODY_SHA256>" --check-restore-gate --confirmed-chip esp8266 --confirmed-flash-bytes 4194304 --owner-authorized
& "<PYTHON_EXE>" -I -m esptool --chip esp8266 --port "<PORT>" --baud 115200 --stub-version 2 --before no-reset --after no-reset-stub --connect-attempts 1 write-flash --flash-mode keep --flash-freq keep --flash-size keep --no-compress 0x000000 "<PRIVATE_MASTER_BIN>"
```

### K — NOT AUTHORIZED BY PHASE C for read; local comparison afterward

```powershell
& "<PYTHON_EXE>" -I -m esptool --chip esp8266 --port "<PORT>" --baud 115200 --stub-version 2 --before no-reset --after no-reset-stub --connect-attempts 1 read-flash 0x000000 0x400000 "<ROLLBACK_READBACK_BIN>"
& "<PYTHON_EXE>" tools/m9_master_restore_preflight.py "<PRIVATE_MASTER_BIN>" --expected-sha256 "<PRIVATE_CUSTODY_SHA256>" --readback "<ROLLBACK_READBACK_BIN>"
```

Require exact 4 MiB external-SHA and byte equality, then separately authorized
OEM cold boot/display identity. Neither local gate nor MASTER availability proves
working UART access, restore execution, power-failure recovery or OEM runtime.
An interrupted full restore also lacks atomicity. No real MASTER inspected.

## Future first-boot runtime gate — NOT_RUN

Select **180 seconds** continuous observation after first stable display: covers
18 windows of the owner's historically reported ~10-second reset interval and
30 telemetry TTL windows. This is a bounded initial screen/network qualification,
not long-term stability. Reset even once means STOP, not restart the timer/retry.
Network/telemetry transactions require their own bounded later approval.

- Correct 240×240 orientation, legible four CPU/GPU/RAM/GPU TEMP cards; no
  fabricated time/weather/metrics. This foundation graph is not a private P1/M8/P0
  physical qualification; media/scene contract is unchanged by Phase C.
- Expected protected private AP is available; Digest challenge/rejection and
  authenticated access work with existing private credentials; no disclosure or
  provisioning. No Home LAN or generic OTA activation.
- RAM telemetry updates all four real values; cease approved input for >6 s,
  confirm stale indication, resume and confirm recovery without reboot or FS.
- No reset/boot loop, corruption, starvation or lost recovery. Record free heap
  from existing diagnostics with timestamp/context; largest block and stack/high
  water only if already exposed. Unavailable values are **unknown**, never derived
  from static RAM. Required resource evidence missing keeps runtime gate HOLD;
  do not add firmware diagnostics or persistent counters under Phase C authority.
- Profile-0 source/build gates continue to exclude filesystem mount/format and
  OTA/FS writers. Absence of visible activity alone is not runtime proof; record
  existing identity/capability evidence, no active writer test.
- Stage 2 activity **zero**. Heap/stack unsafe, unexpected boot or unavailable
  recovery triggers S12 with no automatic restore/reboot/network changes.

## Tests, CI and remaining decisions

27 new synthetic cases exercise candidate/hash/payload/protected/slack/size
failures, resolved/hardlink aliases, malformed candidate, source/inventory drift,
config overrides, externally pinned interpreter identity, bounded two-attempt
and repeated-packet model, RTC parsing/HOLD, command placeholders, no serial/
subprocess execution imports and full synthetic MASTER/readback equality. No
device simulator is called device proof. Windows sandbox denied hardlink creation;
the identical suite passed with permitted local test execution, no skipped case.

Existing geometry, FS-less/source/policy and MASTER regressions remain required.
Local additional regressions: 8 geometry +18 Phase B +9 firstboot +5 FS-less
+7 factory-return +7 policy-generation PASS. Existing FS verifier has 9 local
passes and one Windows symlink-privilege error (WinError 1314); no test weakened
or skipped. Its complete 10 cases are required in Linux CI.
Dedicated M9 CI runs **77 focused tests** (8 geometry +18 Phase B +27 Phase C +9
firstboot +5 FS-less +10 FS verifier), independent baseline/opt-in builds, linked
policy/symbol gates, image/CRC checks and installed-source/Core identity. Exact
resulting head/run evidence is recorded in PR #42 after checks finish. The safe
artifact allowlist remains exactly five existing JSON files, with no Phase C
private receipts, MASTER, owner digest, readbacks, BIN/ELF or generated policy.

Before first physical write: resolve deterministic first-boot RTC copy exclusion;
review actual cold-power/strap/back-power/reset wiring and recovery availability;
confirm same-unit ESP8266/4 MiB; validate private MASTER custody locally under a
separate bounded authority; refresh frozen candidate/interpreter/source gates;
approve exact operation including internal retries/resets and fresh read captures.
Owner runtime evidence remains NOT_RUN. Source PASS cannot remove these gates.
No further firmware feature, custom writer, Stage 1 or Stage 2 work is authorized.
**STOP after Phase C.**
