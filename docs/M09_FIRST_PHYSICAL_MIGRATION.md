# Mission 9 Phase B — first physical migration protocol (OFFLINE ONLY)

**Phase D continuation, 5 October:** [RTC neutralization](M09_RTC_EBOOT_NEUTRALIZATION.md)
qualifies a deterministic source/model overlay after verified full POST: clear
magic+CRC, read both zero, release GPIO0 while continuously powered, existing RST
as EXT_RST, eboot rejects COPY and loads app at zero. First normal boot replaces
the blocked cold-power recommendation, whose historical gate stays HOLD.
RST/GPIO0/RX/TX/GND and prior micro-hook ROM/full-read access are known owner
evidence; EN is not exposed/assumed. Physical transition/runtime NOT_RUN;
no Stage 1 authority, new hardware access or photos; frozen candidate unchanged.

**Phase C continuation, 5 October:** [exact executor qualification, A–K
print-only packet and PRE/POST preservation gate](M09_PHYSICAL_EXECUTOR_QUALIFICATION.md)
supersede the provisional executor/sequence recommendations below. Phase B
evidence remains historical. Official esptool 5.4.0's modeled bounded retry
passes with explicitly pinned version-2 RAM stub; its internal reconnect can
reset despite initial `--before no-reset`. Cold first-boot RTC invalidation
remains **HOLD**, so no physical migration is authorized. Fresh independent
4 MiB PRE/POST files, captured before any application boot, are selected for
preservation; the older private MASTER remains separate rollback authority.
Frozen LOCAL payload unchanged; no firmware edit or local rebuild in Phase C.

5 October 2026. Existing Draft PR #42; starting clean branch
`feature/shino-tv-m9-flash-layout-liberation` at
`1c39e2ac791145be9ef79dc6d98fd70526614d7f`.

**PHASE B OFFLINE FIRST-MIGRATION DESIGN: PASS** subject to the exact-head
test/build evidence in PR #42. **PHYSICAL WRITE: HOLD.** No device contact,
serial access, physical write/erase/upload/reboot, filesystem mount or format
is authorized or performed in Phase B. Future commands below are PRINT ONLY.
Phase A evidence and prior owner observations remain dated provenance.

## Selected model and its limits

Select **Stage 1: application only at zero, FS-less boot**, followed by a
separately reviewed, separately owner-authorized **Stage 2: SHINO LittleFS
provisioning**. This selection follows the actual profile-0 source and compiled
public candidate, not an assumption that changing a linker migrates storage.

The current public `esp12e_m9_4m2m` graph is the Phase A foundation build. Its
disposable credentials differ from the installed owner's private P1 candidate;
Home LAN, generic native OTA and optional OEM return writer are disabled. It is
not a replacement qualification of private P1, M8 signed receiver or P0 scenes.
No firmware source, production credentials, media protocol, TTL or transaction
deadline changes in Phase B. R3 PARTIAL / R10 BLOCKED remain. No release BIN.

Source independence from filesystem contents is established offline. Actual
first boot, LCD, network, heap/block/stack, stable telemetry and physical
preservation remain **NOT RUN**. Source independence is not reliable-boot proof
for this one unit, nor a claim that all firmware/core flash writes are absent.

## Current and target maps

All byte ranges below are inclusive; reports use explicitly named exclusive
ends. Sector size is 4,096 bytes; physical flash is 4,194,304 bytes.

| Region | Current 4m3m | Target 4m2m |
| --- | --- | --- |
| Application + available OTA staging arena | `0x000000..0x0FFFFF` | `0x000000..0x1FFFFF` |
| Filesystem | historical OEM LittleFS `0x100000..0x3F9FFF`, 3,121,152 B | future SHINO LittleFS `0x200000..0x3F9FFF`, 2,072,576 B |
| Reserved tail | `0x3FA000..0x3FFFFF`, 24,576 B | same |
| EEPROM sector (unused by profile 0) | `0x3FB000..0x3FBFFF` | same |
| RF calibration / SDK Wi-Fi parameters | `0x3FC000..0x3FFFFF` | same |

The Core 3.1.2 `eagle.flash.4m2m.ld` maximum linkable sketch remains
**1,044,464 B / 0xFEFF0**. The default/deployed `esp12e` stays **4m3m**;
`esp12e_m9_4m2m` remains opt-in. Phase A maps and max-to-max OTA two-sector
margin are in [M09_FLASH_LAYOUT_LIBERATION.md](M09_FLASH_LAYOUT_LIBERATION.md).

### Exact Stage-1 effects

For a frozen candidate of `N` bytes, at address zero:

- payload bytes: `0x000000..N-1`;
- potentially erased/touched sectors: `0x000000..R-1`, where
  `R = ceil(N / 4096) * 4096`;
- last-sector slack `N..R-1` is not preserved;
- untouched **by the rendered application command**: `R..0x3FFFFF`;
- mandatory invariant: `R < 0x100000`, as well as `N <= 0xFEFF0`.

The candidate geometry observed during preparation is `R = 0x062000`
(401,408 B): touched `0x000000..0x061FFF`; untouched
`0x062000..0x3FFFFF`. The final clean-head freeze must independently match this
extent, with its exact size/hash/commit recorded in PR #42 and the local receipt.

In particular the entire `0x100000..0x3FFFFF` remains outside Stage-1
application erase/write operations: historical OEM FS `0x100000..0x3F9FFF`
and reserved tail `0x3FA000..0x3FFFFF`. **Stage 1 does not physically erase or
reclaim `0x100000..0x1FFFFF`.** It only changes the linked meaning of that range
to potential future OTA arena. There is no partition-table rewrite on ESP8266.
The new SHINO FS is **not provisioned**, and no mount is attempted.

The untouched statement describes the application command, not subsequent
SDK runtime. Wi-Fi/RF initialization may maintain system parameters in the
reserved tail. Do not claim whole-chip byte preservation across a reboot without
readback evidence. Boot must start without a pending RTC eboot copy command:
Core `eboot.c` consumes such a command before `setup()` and can copy staging
flash. A separately authorized cold-start/recovery procedure must address this;
the profile-0 source invariant alone does not suppress bootloader/SDK effects.

## Critical source audit — SHINO_BOOT_PROFILE == 0

| Entry / dependency | Audited behavior |
| --- | --- |
| `firmware/src/main.cpp::setup` | Serial/log startup, `FirstBootBridge::run()`, watchdog enable, return. Nonzero profile is compile prohibited. Legacy LittleFS/config/EEPROM/RescueMode startup is in excluded `#else`. |
| `main.cpp::loop` | Only `FirstBootBridge::loop()` then return. Legacy scene/boot-counter paths excluded. |
| global `ConfigManager` / `SecureStorage` | Constructors initialize strings, JSON and size only. No `secure.begin`, EEPROM init/commit, load/save or migration. |
| pinned Core LittleFS / EEPROM globals | LittleFS constructor initializes RAM configuration and `_mounted=false`; no mount/format. EEPROM constructor stores sector identity, not `begin` or `commit`. Dormant LittleFS virtual methods remain linked via vtable; absence of all LittleFS symbols is not the criterion. |
| `FirstBootBridge::run/loop` | No LittleFS/SPIFFS/EEPROM operations. `WiFi.persistent(false)` precedes RAM AP operations. Default Home LAN is 0. No first-boot FS writer. |
| UI | `FslessWebUI::PAGE` and `SCRIPT` are `PROGMEM`; `server.send_P` serves program-flash assets, never historical/future LittleFS assets. |
| telemetry | `FslessMetrics::Snapshot state` is RAM; only validated `state=next` updates, 6,000 ms TTL, no persistent telemetry. |
| display | Explicit `DisplayManager::begin(0)` uses RAM rotation and SPI/vendor LCD init; `lcdEnsureInit` does not load config or play a GIF. Dormant FS GIF methods are not called. |
| native OTA / migration | Mandatory `SHINO_ENABLE_NATIVE_SIGNED_OTA==0` and `SHINO_ENABLE_FS_MIGRATION==0` static assertions remain unchanged. Only read-only native capabilities route. |
| optional exact OEM return | Compile gated separately; **0 in frozen public Phase B candidate**. Existing guarded code remains intact, but application-only OEM return under 4m2m can stage inside historical FS and cannot serve as preservation rollback. |

`tools/m9_fsless_gate.py` regression-pins startup branches and constructors,
checks RAM/flash asset paths and disabled safety gates, and consumes local
`nm -C` output to verify actual `_FS_start=0x40400000`, `_FS_end=0x405FA000`,
`_EEPROM_start=0x405FB000`. It rejects linked EEPROM init/commit, SecureStorage
begin/flush, config load/save, active Updater begin/write/end, OEM upload and Home
LAN entry symbols. LittleFS vtable methods can remain linked but are inactive.
Manual disassembly review confirms the setup dispatch and RAM-only constructors;
symbol inspection is corroboration, not a universal indirect-call proof.

Thus filesystem bytes, whether old, zero, erased, corrupt or unknown, are not
inputs to this audited boot/UI/metrics path. No physical test of those cases was
performed. A differently generated policy, overlay or changed source needs a new
audit and freeze; a BIN header alone cannot establish linker/boot profile.

## Comparison of the four migration approaches

| Approach | Write/power-loss exposure | Recovery consequence | Decision |
| --- | --- | --- | --- |
| Application first, FS later | Only bounded app sectors initially. App is not atomic; old/new code can be unbootable mid-write. Old FS remains outside command until a later action. | Verified full MASTER can restore all bytes; no dependency on running HTTP app. | Selected: smallest initial destructive span, audited FS-less prerequisite met. |
| FS first, app later | Erases `0x200000..0x3F9FFF` while old 4m3m app still expects a coherent FS rooted at `0x100000`. | Old app may start with damaged FS; failure occurs before new app qualification. | Reject. |
| App + FS in one esptool write | Two disjoint write ranges; command is not a transaction. Loss after either range leaves partially migrated state. | Original FS lost without first proving new runtime. MASTER needed. | Reject. |
| Synthesized full 4 MiB image | Rewrites app, historical FS and tail/config/calibration; synthesis must preserve owner-specific bytes accurately. Largest failure window. | Entire chip potentially mixed/partial; no safer atomicity. Private-data exposure risk. | Reject. Never synthesize from private MASTER here. |

Application first is **safer in touched range, preserved FS and diagnosis order**
than immediate FS provisioning because profile 0 does not need a filesystem.
It is not atomic, guaranteed bootable or physically qualified. No invented
power-loss probabilities, measured duration or guaranteed recovery success.

## Future sequence and success/abort gates (not executed)

| Step | Required success criteria | Abort / next action |
| --- | --- | --- |
| 0. Exact-operation review | Owner independently verifies private MASTER custody/two prior matching reads, target ESP8266EX/4 MiB, recovery access, stable power, candidate commit/hash/policy/linker/extent and actual esptool executable/version. Exact Stage-1 authorization plus separate boot/readback scope. | Missing backup, target mismatch, unavailable ROM recovery, unfamiliar adapter/access method, unknown credentials, unsafe resource baseline or missing consent: HOLD without contact/write. |
| 1. Authorized ROM identification | Chip/flash ID match owner unit and exactly 4 MiB. Any RAM stub loading/reset implications explicitly covered. No automatic device discovery. | Mismatch/error: STOP. No write. Prior owner identification is provenance, not a fresh check. |
| 2. Rehash immediately; app-only write | Exactly one address/file pair at zero, no erase-all/FS image/tail writes/header rewriting. Candidate report PASS and `R<0x100000`. Command succeeds with verification. Remain in stub, no automatic reboot. | Any timeout/write/verification uncertainty: STOP. Do not attempt Wi-Fi, format, FS provisioning or automatic MASTER restore. See retry constraint below. |
| 3. Authorized readback before boot | Candidate payload equals frozen BIN byte/hash; historical FS reads match private pre-write bytes if physical preservation is to be claimed. Record last-sector slack distinctly. No new public owner dump. | Mismatch: no boot or Stage 2; exact MASTER rollback review required. |
| 4. Separately covered first boot | Clean eboot start; valid linked 4m2m identity/map, protected AP + Digest browser/status, volatile metrics/four values and TTL, bounded heap/block/stack, stable LCD and no resets/corruption across an owner-agreed observation period. | Reset, unsafe heap/stack, corruption, authentication failure, uncertain bootloader state or unavailable recovery: immediate STOP/HOLD. No retry/reprovisioning; decide rollback with owner. |
| 5. Stop after FS-less success | Record **4m2m linker active = PASS**, **SHINO 4m2m FS provisioned = NO**. Preserve evidence. | Stage 1 success does not authorize any additional write. |
| Stage 2, separate future mission | Exact new FS image/hash, target `0x200000..0x3F9FFF`, power-loss/restore review, explicit owner authorization; never autoformat on boot. | Not implemented/authorized here. Provisioning destroys the historical 4m3m filesystem's coherence. |

Later OTA staging can write into `0x100000..0x1FFFFF` (this-sized target starts
at `0x19E000`); a successful Stage-1 boot grants no OTA consent. Even exact-OEM
application return under the target linker needs its own overlap review. Generic
native OTA remains disabled; global signing/MD5 safety gates are unchanged.

## Power-loss / failure matrix

"May" is conditional, never a guarantee. FS preservation below means the
historical `0x100000..0x3F9FFF`, assuming only the reviewed ranges are written.
ROM UART is the authoritative fallback independent of either application,
conditional on intact hardware/flash, stable power, access and owner consent.

| Loss point | Old app may boot? | New app may boot? | Historical FS untouched? | Recovery decision |
| --- | --- | --- | --- | --- |
| Before application write | Yes, unchanged; prior runtime HOLD still applies | No new activation | Yes | Stop; no restore needed solely because preparation stopped. |
| During app-sector erase/write | Possibly, but assume invalid/mixed app | Possibly, but unproven; do not boot partial image | Yes | ROM UART + exact MASTER review; no Wi-Fi guarantee or blind retry. |
| Immediately after completed verified write | Old app is replaced | Yes, plausible complete candidate, runtime unqualified | Yes | Verify/readback and owner-authorized clean first boot, else MASTER decision. |
| During first reboot | Old app not a fallback | May boot on a later approved clean start | Yes unless pending eboot copy or unexpected writer; SDK tail may change | STOP on reset; inspect existing evidence offline, no repeated reboot loop. ROM fallback. |
| After first successful FS-less boot | Old app not resident fallback | May boot; prior success helps, not atomic rollback | Yes absent later OTA/FS actions; tail not guaranteed byte-identical | Retain FS-less state or separately authorize MASTER rollback. |
| During future LittleFS provisioning | Old app/FS combination no longer reliable | FS-less candidate may boot independently of partial FS | **No**; upper OEM FS overwritten/partially erased | STOP Stage 2; no mount/autoformat. Full MASTER for factory restore. |
| During full MASTER restore | Maybe if app sectors completed, not authoritative | Maybe stale if sectors remain; not a fallback | **No guarantee**; every byte may be partially restored | Remain HOLD. ROM access + new exact restore consent; full readback before success. |

There is no fixed A/B rollback partition and no proven application-write atomicity.
An old sector-rounded staging copy is historical evidence, not an automatic
recovery image. Full MASTER restore itself has a power-loss window.

## PRINT-ONLY UART command packet

Syntax comes from repo-pinned **esptool 5.4.0** in the Mission 9 workflow and
the locally verified v5.4.0 CLI/source. PlatformIO also carries **esptool 3.0.0**
for its uploader; do not substitute that underscore-syntax package here. Offline
`image-info` and `--help` were used; no chip/flash/serial command was executed.

`tools/m9_first_migration.py --render-commands` prints all commands with
`<PORT>`/file placeholders. Base flags preserve ROM/stub state, use no automatic
reset/reboot and one connection attempt; default RAM stub is required. Physical
ROM entry, RAM stub loading and later reboot require separately scoped consent.

```text
READ-ONLY CHIP/FLASH IDENTIFICATION — NOT AUTHORIZED BY PHASE B
python -m esptool --chip esp8266 --port "<PORT>" --baud 115200 --before no-reset --after no-reset-stub --connect-attempts 1 chip-id
python -m esptool --chip esp8266 --port "<PORT>" --baud 115200 --before no-reset --after no-reset-stub --connect-attempts 1 flash-id

STAGE-1 APPLICATION WRITE — NOT AUTHORIZED BY PHASE B
python -m esptool --chip esp8266 --port "<PORT>" --baud 115200 --before no-reset --after no-reset-stub --connect-attempts 1 write-flash --flash-mode keep --flash-freq keep --flash-size keep --no-compress 0x000000 "<CANDIDATE_BIN>"

FULL PRIVATE MASTER RESTORE — NOT AUTHORIZED BY PHASE B
python -m esptool --chip esp8266 --port "<PORT>" --baud 115200 --before no-reset --after no-reset-stub --connect-attempts 1 write-flash --flash-mode keep --flash-freq keep --flash-size keep --no-compress 0x000000 "<PRIVATE_MASTER_BIN>"

FULL POST-RESTORE READBACK — NOT AUTHORIZED BY PHASE B
python -m esptool --chip esp8266 --port "<PORT>" --baud 115200 --before no-reset --after no-reset-stub --connect-attempts 1 read-flash 0x000000 0x400000 "<PRIVATE_READBACK_BIN>"
```

No `--erase-all`, `--force`, `--no-stub`, file merge or second FS address.
`keep` preserves the exact first four header bytes, important for whole-MASTER
equality. Esptool host `write_flash` pads to four bytes and reports sector-rounded
erase ranges; stub flash-begin limits remaining erase sectors and trims final
transport-block padding. The ESP8266 stub avoids the ROM erase-size workaround.
Corroborating [official stub source](https://github.com/espressif/esptool-legacy-flasher-stub/blob/master/flasher_stub/stub_write_flash.c)
is not a physical qualification; actual installed v5.4.0 loader/command source
was checked locally. Changing stub/version/options reopens the extent gate.

**Executor retry gate: HOLD.** The inspected v5.4.0 loader hard-codes
`WRITE_FLASH_ATTEMPTS=2` and `write_flash` can retry the entire same-address image
after a serial exception. `--connect-attempts 1` does not turn that into one write
attempt. The rendered commands are accurate templates, not approved executors.
Future exact-operation review must explicitly accept the built-in bounded retry
or separately review a one-attempt executor. Never claim this template is
single-attempt or silently patch the installed esptool. No retry wrapper exists
in Phase B tooling. No physical approval is sought in Phase B.

## MASTER rollback gate and decision tree

`tools/m9_master_restore_preflight.py` retains inspection-only mode and adds a
separate offline restore-prerequisite gate requiring all of:

1. Regular local private MASTER (no symlink), exactly **4,194,304 B**.
2. Expected SHA-256 externally supplied from private custody; no owner digest
   embedded in Git, tests, logs or CI.
3. Plausible ESP8266 boot header/4 MiB header; nonuniform contents and matching hash.
4. Confirmed same owner-unit **ESP8266** and **4 MiB physical flash**.
5. Fresh explicit owner consent for that exact full-MASTER operation/hash.

The CLI assertions record externally supplied evidence; they neither verify a
live target nor confer permission. Inspection-only cannot pass the restore gate.
No real MASTER was read, copied, supplied to tests or uploaded in this pass.

```text
Before app write failed? -> STOP; keep current bytes. No automatic restore.
App write started or boot/readback unsafe/unknown?
  -> STOP; do not rely on HTTP recovery. Check MASTER and ROM recovery prerequisites offline.
  -> Any prerequisite missing? HOLD; no write.
  -> Prerequisites present? Request separate exact full-MASTER action authorization.
FS-less runtime succeeds?
  -> Stop with linker active / FS unprovisioned; no rollback needed for layout alone.
Future FS/OTA has touched historical FS?
  -> OEM application-only restore is insufficient. Exact full MASTER is recovery authority.
```

After a future full restore, **before declaring factory recovery successful**:
read all `0x000000..0x3FFFFF` into a distinct private file, verify exactly 4 MiB,
compare **every byte and SHA-256** against the private MASTER/custody hash using
`--readback`. An esptool write ACK/MD5 alone is insufficient. Keep the device in
stub/ROM until readback matches; then separately covered reboot plus actual OEM
identity/display confirmation. Local-file equality does not prove readback
provenance or factory runtime: those need the future physical receipt.

## Offline validation and clean-head freeze

Synthetic fixtures only: bundled ESP image/CRC, range boundaries, malformed and
oversized inputs, source/policy mutation, MASTER prerequisite closure and full
readback equality/mismatch. Import/AST checks exclude subprocess, serial,
network/dynamic execution and embedded MASTER digests in Phase B tooling.
Phase A geometry tests retain exact FS/tail/default/opt-in contracts. Existing
first-boot and FS-less dashboard regressions run alongside Phase B tests.

CI remains device-free and needs no private MASTER. It retains Phase A's offline
LittleFS image construction/integrity gate (not a device mount/format/write),
adds actual candidate policy/linker/symbol and eboot/application/CRC checks,
and publishes only five safe JSON evidence files. No BIN, ELF, private policy,
credentials, symbol dump or filesystem image is published. Both application
builds and read-only esptool image-info remain in the existing workflow.

After committing this focused milestone, build a fresh clean-head
`esp12e_m9_4m2m`, record the exact source commit, candidate bytes/SHA-256, linked
flash/static RAM, rounded range, tool/dependency versions and image-info result
in ignored `research-local/m9-phase-b/freeze.json` and PR #42's body. This avoids
a self-referential commit hash and freezes the **final resulting commit**.
CI builds with disposable independent credentials; its hashes are different
from the retained local candidate and must be labelled separately. Wait for
matching exact-head CI and keep PR #42 Draft/unmerged. Stop after Phase B.
