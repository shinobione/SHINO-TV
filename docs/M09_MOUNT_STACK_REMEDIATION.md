# Mission 9 — targeted Resource Probe mount-stack remediation

> **Current Phase O writer binding, 7 October 2026:**
> [Normal StageA rebind receipt](M09_PHASE_O_WRITER_REBIND.md) selects only399264 B /
> SHA-256 `78a8d2d50409974fc775dd3dc9f3dbec4ac8eda839f6d9b338cadf35aab2467c`,
> rounded0x062000,98 packets; last1952 payload/2144 FF. Future physical packet
> PRINT ONLY/not authorized. Both normal physical gates NOT_RUN; no firmware/
> freeze/FS change. Installed profile2 probe PASS is historical owner evidence.
> Older transaction geometries below remain dated history. STOP/no flash/reboot/merge.

> **Prior profile2 writer binding (before Phase O), 7 October 2026:** [Targeted successor rebind](M09_PHYSICAL_WRITER_REBIND.md)
> selects only411152 B / e1852e56...9bc27e. Phase M acquisition and physical
> thresholds unchanged; historical J binding statements below are dated evidence.
> This offline rebind grants no physical authority. STOP. DO NOT FLASH.

7 October 2026. **OFFLINE ONLY; no device contact.** Continued clean
`96c5804f5435a71fc1e3cd7b04004af438a650ac` on
`feature/shino-tv-m9-flash-layout-liberation`, existing
[PR #42](https://github.com/shinobione/SHINO-TV/pull/42) Draft/open/unmerged.
The owner decision was recorded in the active roadmap before implementation.
Earlier J/K/L/M receipts remain dated history. This receipt supersedes their
NOT_RUN description of the installed J candidate only where the owner provided
the physical observations below. It does not make a new physical measurement.

## Owner-supplied physical receipt — installed J predecessor

The owner explicitly reports installation and boot of the exact **411136-byte**
instrumented J image, SHA-256
`2ce2fa8da00de5c60109d0675c7bcf58ab41df2138d913b607fde25994e5a835`.
The retained local BIN is rehashed only; never recreated, overwritten or
substituted. No private flash dump digest, MAC or credential is published.

| Owner status field | Observed value |
| --- | ---: |
| attempted / autoformat_disabled / mounted | true / true / true |
| inventory_checked / inventory_exact / config_seed_exact | true / true / true |
| checked_file_count / checked_payload_bytes | 24 / 181402 |
| blocked_write_attempts | 0 |
| resource_diagnostics_enabled / resource_measurements_valid | true / true |
| resource_rejected_sample_count | 0 |
| heap_after_probe_free / largest_block / fragmentation | 36064 / 35904 / 1% |
| minimum_observed_free_heap (existing denser observer) | 29664 |
| lowest_observed_free_heap / largest_free_block | 30624 / 29584 |
| highest_observed_fragmentation_percent | 4% |
| mount_phase_cont_stack_start / min_free | 3956 / **1776** |
| runtime_cont_stack_start / min_free | 3940 / **3296** |
| resource_sample_count | 89 |

Phase K free heap>=20480, largest block>=16384, fragmentation<=25% and runtime
continuation>=2048 pass for these reported measurements. Mount continuation
**1776 < 2048 fails by272 B**. **MOUNT_PROBE_RESOURCE_PHYSICAL_GATE = HOLD**.
The floor remains2048 B; neither the recorded1776 nor any compiler result is
reclassified as PASS. Full180-second LINK/stale/recovery acceptance was not
supplied in this receipt. Normal-profile mount/runtime gates remain NOT_RUN.

## Exact bounded change

Only two tracked firmware files change: `M9ProbeStream.h` and
`M9LittleFsMountProbe.cpp`. Profile2 owns one fixed BSS `payloadWorkspace`:
256-byte read buffer, BearSSL SHA256 context, 32-byte computed digest and a
busy flag. The linked object occupies **408 B**. No scratch malloc/new,
replacement object on the continuation stack, growing String or persistence.
The existing read-only FS adapter allocation is unchanged.

`validate()` receives this workspace by reference. An automatic small lease
sets its busy flag and clears it on every return; nested validation during an
observer/yield callback is rejected before touching scratch, reader, hash or
checked-byte counter. It is a synchronous reentry guard, not a cross-thread
locking claim. The probe's existing one-attempt begin latch remains unchanged.

Streaming order, positive short-read handling, exact EOF/extra-byte rejection,
SHA256 and blank seed comparisons, checked-byte accounting, file closure,
write-denial counters and yield/heap observations remain exact. Single
LittleFS.setConfig(false) precedes the single LittleFS.begin; no repair, format,
retry, second mount, ConfigManager, SecureStorage, EEPROM migration, STA, OTA
or writer is added. Manifest24 files/181402 bytes/hashes/blank seed is unchanged.
Resource observer/source APIs/windows/cadence/threshold policy are pinned
unchanged. Phase M physical runner and K transaction are pinned unchanged.

J and K historical manifests remain unchanged on disk. A separate
`m9_mount_stack_sources.json` pins the two current successor transformations;
qualification reports103 firmware files checked,101 unchanged and two explicitly
named changes. Historical J candidate identity stays in the K report with role
HISTORICAL_J_PREDECESSOR_ONLY. This does not rebind the physical writer to new
bytes. CI source assertions were adjusted to reflect this distinction.

## Compiler and paired resource audit

Initial isolated predecessor/successor builds used identical retained local
policy, pinned platform/Core/toolchain and build-version context. These are
comparison builds, not a recreation or replacement of the installed frozen J
image. Four-profile receipts, complete SU files, linked symbols and disassembly
remain ignored under `research-local/m9-mount-stack/`.

| Quantity | Before uninstrumented | After uninstrumented | Delta | Before instrumented | After instrumented | Delta |
| --- | ---: | ---: | ---: | ---: | ---: | ---: |
| Static RAM | 40656 | 41064 | **+408** | 40736 | 41144 | **+408** |
| Linked flash | 403287 | 403303 | **+16** | 406995 | 407011 | **+16** |
| .noinit (separate) | 56 | 56 | **0** | 56 | 56 | **0** |
| BIN bytes (comparison only) | recorded locally | 407456 | — | recorded locally | 411168 | — |

| Linked mount-path compiler frame | Predecessor | Successor, both profiles |
| --- | ---: | --- |
| begin | 272 | **272** |
| exactInventory | inlined into begin | inlined into begin |
| checkPayloads | **576** | **inlined into begin; no separate linked frame** |
| validate / SHA adapter / lease | inlined into checkPayloads | inlined into begin |
| Relevant begin+checkPayloads own-frame sum | **848** | **272**, reduction **576** |

The linked predecessor calls its576-byte checkPayloads from272-byte begin.
Successor disassembly reserves0x110=272 B for begin and contains the validation
calls there; symbol/SU reports have no separate checkPayloads/validate symbol.
Predecessor checkPayloads disassembly reserves0x240=576 B. This is not adding a
fictitious zero-byte out-of-line frame. All other parsed probe frames are
unchanged; new lease/hash/validation helpers are inlined. One new startup
initializer has compiler label `cpp)`, frame **0 B**, linked symbol
`_GLOBAL__sub_I__ZN20M9LittleFsMountProbe5beginEv` (13 code bytes): disassembly
sets the busy flag to zero without a call or allocation. No new individual
frame>1024 B. Existing JSON80/64 B (un/instrumented) and observer16/32/32/800/944 B are unchanged.
BearSSL/Core/library child frames are unchanged; this sum is not a total
worst-case continuation bound. **Do not infer physical stack PASS.**

Offline target>=384 B compiled reduction, <=512 B static RAM, <=4096 B linked
flash, unchanged noinit and no new frame>1024 B all pass. Instrumented versus
uninstrumented successor remains +80 B RAM / +3708 B linked flash, unchanged
observer cost. Final clean successor identity and final paired receipt follow
only after all offline tests pass; comparison images above are not frozen.

## Host validation and successor freeze

**222 local checks PASS**, zero failures/errors/skips:219 in the full Mission9
and related source/host suite, plus3 scoped port80 source checks. Host compiled
tests exercise the actual validator's short reads/faults/EOF/digest/seed cases,
zero scratch heap allocation, nested-call rejection without reader/hash/counter
mutation, and lease release after success/failure. Existing24-file/181402-byte
manifest/hash/blank-seed checks, write-denial mutations, observer fault-injection,
five bounded SYNC cases and416 flash fault matrix all pass. Exact Core/package/
source pins and installed J rehash pass. The CI safe JSON allowlist explicitly
adds only `m9-mount-stack.json`; no private inputs/BIN/ELF upload is added.
**Clean firmware source freeze:** `9f86a73d999168d052e2037a4fcb999cfe9a2e2c`.
After the passing host/source/initial build gates, both predecessor comparison
and successor profiles were built again in isolated projects with identical
clean version context, retained policy and pinned toolchain. Per-environment
BIN/ELF/SU/symbol/section/disassembly artifacts were escrowed before switching
profiles. The initial comparison receipt remains `initial-paired-audit.json`;
its extra4 B version context is not a code/resource regression.

| Final clean paired quantity | Before uninstrumented | Successor uninstrumented | Delta | Before instrumented | Successor instrumented | Delta |
| --- | ---: | ---: | ---: | ---: | ---: | ---: |
| Static RAM | 40652 | **41060** | **+408** | 40732 | **41140** | **+408** |
| Linked flash | 403283 | **403299** | **+16** | 406991 | **407007** | **+16** |
| .noinit | 56 | **56** | **0** | 56 | **56** | **0** |
| BIN bytes | 407440 | **407456** | +16 | 411136 | **411152** | +16 |

Both final profiles retain begin272 B, checkPayloads/validate inlined into begin,
848->272 own-frame sum (**-576 B**), one408 B BSS workspace, zero-byte startup
initializer and all other probe/observer frames unchanged. Exact Core/source,
layout/link/writer exclusions, image checksums/Arduino CRC and all review budgets
pass. Comparison predecessors use old source with current build-version context;
they are not the installed retained J bytes and are never substituted for them.

One clean **instrumented** successor is frozen locally, never uploaded:

| Frozen successor identity | Value |
| --- | --- |
| BIN | `research-local/m9-mount-stack/frozen-successor-resource-probe.bin` |
| ELF | `research-local/m9-mount-stack/frozen-successor-resource-probe.elf` |
| Bytes | **411152** |
| SHA256 | **`e1852e56d99801b694f37d235b08a201188cf36d5a25f3f6f59d059a129bc27e`** |
| Target / payload extent | 0 / `0x000000..0x06460F`, exclusive end `0x064610` |
| Sector-rounded extent | **413696 B / 0x065000**, touched `0x000000..0x064FFF` |
| Rounded margin below0x100000 | **634880 B** |
| Rounded margin below FS start0x200000 | **1683456 B** |
| Protected after rounded end | `0x065000..0x3FFFFF` |
| Physical successor acceptance | **NOT_RUN**; installed predecessor resource gate **HOLD** |

Final receipt `freeze.json` records source checkpoint, paired audits, candidate
identity, passed tests and six zero operation counters. The documentation-only
receipt commit does not rebuild or replace these bytes. BIN/ELF remain ignored;
the installed J BIN rehash is still exact. Exact-head CI is separately recorded
in existing Draft/open/unmerged PR #42, with no private input or BIN/ELF upload.

## CI reporting correction — same frozen firmware

At receipt HEAD `e24df9efa2c4d474378c73fdeb4e6e357234781f`, both layout CI runs
([PR](https://github.com/shinobione/SHINO-TV/actions/runs/37543922741),
[push](https://github.com/shinobione/SHINO-TV/actions/runs/37543916915)) built the
uninstrumented probe successfully, then the older H resource parser rejected
its missing separate checkPayloads SU entry. The old parser required three
separate frames even though the successor now correctly inlines validation.

The parser now accepts the missing frame only with linked symbols proving
checkPayloads/validate absence, one bounded BSS workspace and the separate
>=384 B frame reduction gate. CI's existing symbol capture adds `-S` for the
actual workspace size. Existing H static RAM limit and768 B individual-frame
review bound remain unchanged, as does the physical2048 B floor. A new test
rejects absent linked proof and inconsistent linked checkPayloads symbols.
The full H CLI path passes locally against retained clean compiler artifacts.
No firmware source, runner, frozen successor or installed J byte changes;
no build/freeze repetition. **Final223 local checks PASS**, zero failures/errors/
skips (220 full suite+3 unchanged scoped port80 source checks), plus the exact H
resource CLI passed against clean retained artifacts. Exact-head CI receipt is
recorded in PR #42 after this reporting-only correction; the earlier222-check
freeze receipt remains history.

## Future replacement packet — PRINT ONLY / DO NOT EXECUTE

All offline gates above pass; the single exact instrumented successor is
411152 B / `e1852e56d99801b694f37d235b08a201188cf36d5a25f3f6f59d059a129bc27e`,
rounded end0x065000. A future operation requires separate owner GO
for those exact bytes and operation, fresh qualified ROM and existing pinned-v2
RAM-only stub, current same-unit full4 MiB PRE/preservation proof and separate
rollback authority. The current physical runner intentionally remains pinned
to historical J; its candidate gate does **not** accept the successor. Separate
review of successor binding is required before any executable write command.
Do not substitute the stock retrying write-flash path or alter the M runner.

Required future sequence, print only:

1. Maintain continuous power/manual GPIO0 boot-state control; fresh ROM/magic,
   pinned-v2 acquisition, uncached post-stub4 MiB qualification. No automatic
   reset/control-line change/reconnect or uncertain flash retry.
2. Fresh current full-chip PRE; exact retained FS slice and current protected
   bytes verified. Rehash exact new application; application-only target0 write
   under separately reviewed one-attempt authority. No FS/RTC write.
3. Full independent POST before app boot: exact successor payload at0; every
   byte from its rounded end through0x400000 equals PRE, including FS and tail.
4. Powered RTC0/0 verified; owner-controlled normal boot. No automatic reboot.
5. Digest resource status: single no-autoformat mount,24 files/181402 payload
   bytes/hashes/config exact, zero blocked writes/rejected samples, valid and
   advancing samples. Mount stack>=2048, runtime stack>=2048, both heap windows
   >=20480, largest block>=16384, fragmentation<=25%; retain denser heap minimum.
6. Then180-second LINK plus controlled stale/recovery, no reset/display
   corruption, final exact status and advancing counters. Any threshold miss,
   missing fact, rejected sample or ambiguity = HOLD/STOP, no automatic retry
   or rollback. Do not activate full normal profile.

**Agent DEVICE CONTACTS / SERIAL I/O / FLASH WRITES / RTC WRITES / REBOOTS /
DEVICE FILESYSTEM WRITES = 0. STOP. Do not flash, reboot the current SmallTV,
lower the2048 B floor or merge PR #42.**
