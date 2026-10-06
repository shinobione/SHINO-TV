# Mission 9 Phase J — instrumented mount-probe resources (OFFLINE ONLY)

6 October 2026. Started clean on `feature/shino-tv-m9-flash-layout-liberation`
at `9029df6cb40b0f3714fead05247c1411226dfde6`, existing
[PR #42](https://github.com/shinobione/SHINO-TV/pull/42) Draft/open/unmerged.
[Roadmap](ROADMAP.md) records the owner decision before implementation.
This phase performs no device operations and gives no physical installation
authority. Candidate BIN/ELF remain ignored/local; no private dumps are inputs.

## Current gates and unchanged installed baseline

| Gate | Result after clean local qualification |
| --- | --- |
| PHASE_J_RESOURCE_INSTRUMENTATION_SOURCE_GATE | **PASS/OFFLINE** |
| PHASE_J_RESOURCE_INSTRUMENTATION_BUILD_GATE | **PASS/OFFLINE** |
| PHASE_J_RESOURCE_INSTRUMENTATION_REGRESSION_GATE | **PASS/OFFLINE** |
| MOUNT_PROBE_PHYSICAL_GATE | **PARTIAL / HOLD** |
| MOUNT_PROBE_RESOURCE_PHYSICAL_GATE | **HOLD / NOT_RUN** |
| NORMAL_PROFILE_LITTLEFS_MOUNT_GATE | **NOT_RUN** |
| NORMAL_PROFILE_RUNTIME_GATE | **NOT_RUN** |
| PHYSICAL_RESOURCE_THRESHOLD | **REVIEW_REQUIRED** |

[Phase I owner physical evidence](M09_MOUNT_PROBE_PHYSICAL_EVIDENCE.md) remains
unchanged: installed uninstrumented profile 2 / `esp12e_m9_4m2m_mount_probe`,
**407440 B**, SHA-256
`ca92cc2f4a8a67f70bd305875bd37be90d0cdff74bf7b338339856407dceef8b`.
Its FS/runtime/application/FS-preservation/no-FS-write gates remain PASS within
that supplied run. Mounted exact **24 files / 181402 payload B**, canonical
blank config, zero blocked writes; heap mount/inventory **36144/36144 B**,
sampled minima **29744 B** initially / **27808 B** finally, 180-second stable
telemetry/stale/recovery, no observed reboot. Physical largest block,
fragmentation and continuation margin remain unknown for this profile.
FS remains **0x200000..0x3F9FFF**, exclusive end **0x3FA000 / 2072576 B**,
frozen SHA-256 `d7ce9133b34fb5937d5640db81ff863a8f22a3717255c4b23057aea9ed2ef045`.
No P1/M8/Home-LAN/native-OTA/full-product promotion.

## Separate opt-in and exact behavior preservation

New **env:esp12e_m9_4m2m_mount_probe_resources** extends the unchanged
**env:esp12e_m9_4m2m_mount_probe**, retaining profile **2**, 4m2m/littlefs,
platform **4.2.1**, Core **3.30102.0 / Arduino 3.1.2**, GCC **10.3.0**,
PlatformIO **6.1.18**. Its only new build flag is
**SHINO_M9_MOUNT_PROBE_RESOURCE_DIAGNOSTICS=1**. Flag defaults to zero;
unknown flag values or use outside profile 2 fail compilation. The target gate
checks the exact flag/environment pairing and rejects upload/uploadfs/buildfs/
erase/program/upload-prefixed targets. Ordinary default remains esp12e/4m3m;
profile 0 setup/loop remain exact, profile 1 and unknown profiles blocked.

[Public baseline pins](../tools/m9_resource_baseline_sources.json) freeze the
complete original uninstrumented main/bridge/probe source after removing only
the explicit J additions. Manifest, streaming validator, telemetry and program
flash assets are unchanged. Thus the read-only adapter, single begin after
autoformat-disable success, exact enumeration/read/length/SHA/blank seed,
blocked_write_attempts, failure-without-format/repair/retry and every credential/
STA/OTA/FS-writer exclusion remain intact. No local FS image build or replacement.
The original frozen installed candidate is not recreated or overwritten.

Only the instrumented serializer skips the old entry-time observeHeap() call,
so neither old nor new resource APIs are sampled in the HTTP handler. Existing
FS/status fields and formatter remain; mount/chunk/inventory/loop heap
observations still run. Uninstrumented serializer behavior remains exact.

## Pinned Core API audit

[Eight additional LF-normalized Core source pins](../tools/m9_resource_core_sources.json)
cover Esp.h, Esp.cpp, Esp-frag.cpp, cont.h, cont_util.cpp, umm_malloc_cfg.h and
ESP8266WebServer.h/-impl.h. The seven prior LittleFS source pins remain required.
The local gate checks actual exact files from Core 3.1.2, not a substituted SDK
heuristic. Pinned official source commit:
`210897ef83305496947c4e73c937bab52a33cb48`.

- Esp.h's **uint32_t*/uint32_t*/uint8_t*** getHeapStats overload avoids the
  deprecated 16-bit largest-block saturation. Esp-frag.cpp uses the current
  allocator heap, one umm_info traversal and the Core's L2/Euclidean free-hole
  fragmentation metric. It is not the formula 100*(1-largest/free).
- Esp.cpp's getFreeContStack delegates to cont_get_free_stack; cont_util.cpp
  scans painted words and returns bytes. cont.h fixes **4096 B** continuation
  stack. No compiler-frame-to-physical-margin conversion is made.
- resetFreeContStack delegates to cont_repaint_stack: it repaints below current
  SP minus a **64-byte** exclusion. It is a RAM watermark repaint, not a device
  reset and not a promise of an initial 4096-byte free watermark.
- Pinned WebServer source honors declared Content-Length and synchronous
  length-delimited sendContent for the two bounded body chunks. TCP delivery,
  allocator/header behavior and real browser availability remain physical work.

## Measurement windows and observer

Only the instrumented profile-2 setup follows:

1. FirstBootBridge::run completes; beforeMount resets the continuation watermark
   once and immediately records **mount_phase_cont_stack_start**.
2. The existing M9LittleFsMountProbe::begin runs with unchanged mount/inventory
   behavior, including failures; instrumentation performs no FS operation.
3. Immediately on return, afterMount records **mount_phase_cont_stack_min_free**
   first, then one **heap_after_probe_free/largest_block/fragmentation** snapshot.
4. It resets the watermark once more and records **runtime_cont_stack_start**.
   Subsequent setup/WDT/loop work belongs to that new runtime window.

No more watermark reset occurs in runtime. END of ordinary profile-2 loop:
FirstBootBridge::loop, existing probe poll, then resource poll. The first
runtime attempt waits **1000 ms** after startup; subsequent attempts use unsigned
wrap-safe elapsed time and schedule from actual attempt time. Missed periods
produce one sample, never a catch-up burst. Failed samples also consume the
cadence slot. No timer/ISR/task/thread, recursion, HTTP-handler or FS-callback
sampler. The runtime watermark includes observer/HTTP work since reset even
between sample times; heap minima are only sampled, not exhaustive transients.
The post-probe heap call happens after the mount watermark read and before
the runtime reset; its stack usage is not claimed in the captured mount minimum.

Observer stores only fixed scalars: no allocation, String accumulation, report
list or persistence/flash/FS write. A validity latch plus saturated rejection
counter rejects zero/over-81920 free heap, zero/over-free largest block, >100%
fragmentation, >4096/unaligned/increasing watermark readings. These are
structural consistency checks, **not accepted physical safety floors**. Zero
continuation margin is retained honestly. Corrupt heap samples do not overwrite
valid latest/minima; any rejection latches **resource_measurements_valid=false**
until a new boot. sample_count and rejection_count saturate at UINT32_MAX while
observations continue. Zero cached values before a valid phase/sample are
not-measured sentinels; runtime latest/minima require sample_count >0.

## Authenticated status and exact response bounds

Existing **GET /api/v1/m9/fs-probe/status** retains explicit Digest before
status handling; cookies alone remain insufficient. Same single server and
telemetry routes. Only the resource build adds these cached scalar fields:

```text
resource_diagnostics_enabled
resource_measurements_valid
mount_phase_cont_stack_start
mount_phase_cont_stack_min_free
heap_after_probe_free
heap_after_probe_largest_block
heap_after_probe_fragmentation
runtime_cont_stack_start
runtime_min_cont_stack_free
resource_sample_count
latest_free_heap
latest_largest_free_block
latest_fragmentation_percent
lowest_observed_free_heap
lowest_observed_largest_free_block
highest_observed_fragmentation_percent
resource_rejected_sample_count
```

Existing base JSON's exact type-level maximum is **488 bytes**: six longest
booleans, one uint16 field, eight uint32 fields and fixed writer-policy false.
The suffix's exact type-level maximum is **670 bytes**: twelve uint32 fields,
three uint8 fields, enabled true and the longest validity boolean false.
Replacing the base's closing brace gives **488-1+670 = 1157 body bytes**.
NUL storage is separate. Each formatter uses a fixed **768-byte** buffer in
separate compiler frames, not one large frame or a static RAM buffer.
PROGMEM suffix format avoids a persistent RAM copy. Both chunks are validated
before headers/body emission; overflow fails closed with the existing 500
PROBE_STATUS_OVERFLOW response. Declared Content-Length covers both fragments;
no chunked JSON protocol or full String report accumulation. Existing headers
no-store/nosniff retained. Server header/TCP internals can still allocate;
this is not a zero-allocation HTTP claim. Serialization reads cached observer
state only, with no resource sampling.

## Threshold audit — no invented physical PASS

**PHYSICAL_RESOURCE_THRESHOLD = REVIEW_REQUIRED.** No directly applicable
profile-2 largest-block/fragmentation/continuation floor was found.

| Existing evidence / budget | Exact source | Applicability |
| --- | --- | --- |
| 48x48 replacement heap 14904 / block 11304, 4096 reserve | [Mission 8 gate](V08_MISSION_8_GATE.md), latest 48x48 Stop/held replacement and metadata arena section | Media-specific overlap budget, not this FS probe's floor |
| Earlier 48x48 replacement block 13352; measured 12496 caused HOLD | [8R remediation](V08_MISSION_8R_STACK_REMEDIATION.md), replacement stopped before next Begin | Different 4096 metadata arena workload; historical budget |
| Recorded physical heap/block 11768/9400; continuation 1680 | [Mission 8 device qualification](V08_MISSION_8_DEVICE_QUALIFICATION.md), table under new-boot physical qualification | Observed values, not a general accepted safety threshold |
| Focused final corpus block 10592, fragmentation 29%, continuation 1776/4096 | [8R remediation](V08_MISSION_8R_STACK_REMEDIATION.md), final focused physical corpus table | Different signed receiver/crypto/secondary-stack workload; not an M9 floor |

Structural limits 81920/4096 and J's **+512 static RAM / +8192 linked flash /
1024 individual compiler-frame** review budgets are not physical gate criteria.
Physical measurements plus separately reviewed workload-specific margins are
still required. No gate closes because an arbitrary new number looks adequate.

## Clean candidate and paired build receipt

**Clean firmware source freeze: `7779248082975472ce5f62edf1613d8288b75b6e`.**
Both probe applications were built from that clean checkpoint, using the same
retained local policy and pinned toolchain. The following documentation-only
qualification commit does not rebuild or replace the frozen bytes. Default
esp12e compile also passes. All outputs below remain ignored under
`research-local/m9-phase-j/`; no BIN/ELF is published.

| Quantity | Paired uninstrumented | Frozen instrumented | Delta |
| --- | ---: | ---: | ---: |
| BIN bytes | 407440 | **411136** | +3696 |
| Linked flash bytes | 403283 | **406991** | **+3708** |
| Static RAM bytes | 40652 | **40732** | **+80** |
| .noinit bytes (separate) | 56 | **56** | **0** |

Frozen successor SHA-256:
**`2ce2fa8da00de5c60109d0675c7bcf58ab41df2138d913b607fde25994e5a835`**.
Payload occupies **0x000000..0x0645FF**, exclusive end **0x064600**.
Sector-rounded extent is **413696 B / 0x065000**, touched range
**0x000000..0x064FFF**. Rounded margins: **634880 B** below 0x100000 and
**1683456 B** below FS start 0x200000. Future protected interval is the whole
**0x065000..0x3FFFFF / 3780608 B**, including unused lower arena, FS and tail.
4 MiB/DIO image header, both image checksums, Arduino CRC, linked 4m2m FS
symbols and excluded-writer checks pass. Baseline has no resource-observer
symbols; successor links beforeMount/afterMount/poll/sendStatus and all three
pinned ESP resource APIs.

| Compiler frame | Uninstrumented | Instrumented | Delta |
| --- | ---: | ---: | ---: |
| setup / loop | 48 / 16 | 48 / 16 | 0 / 0 |
| Existing begin / checkPayloads | 272 / 576 | 272 / 576 | 0 / 0 |
| Existing base JSON formatter | 80 | 64 | -16 |
| New beforeMount / afterMount / poll | absent | 16 / 32 / 32 | new |
| New sendStatus / emit | absent | 800 / 944 | new |

**All three review budgets PASS:** +80 <=512 static RAM, +3708 <=8192 linked
flash, largest new individual frame 944 <=1024. The 800/944 frames are nested;
these are individual compiler frames, not a combined call-chain bound or
physical continuation margin. Actual physical watermark remains NOT_RUN.
Other common parsed frame deltas are zero; duplicated compiler-generated
lambda names are compared by maximum per normalized function key.

Paired uninstrumented SHA-256 is
`1b249f2da69c1c4d139754286865027b0e20a36d0a7a67e7ef7eb4a3ee5c83e5`.
Its behavior is pinned unchanged; a new build's source/build-version provenance
does not promise identical BIN bytes to installed H. The retained original H
407440-byte image was rehashed and still matches `ca92cc2f...dceef8b`; it was
not recreated or overwritten. Frozen FS is unchanged. Initial compile-check
outputs are not the frozen successor and convey no physical authority.

## Validation and future physical packet

**165 local tests PASS, zero failures/errors/skips**: ten J observer/JSON/profile/
source mutation/API-pin/budget/target/future-packet tests; twelve original H tests;
140 M9/first-boot/policy/factory regressions; three route source/mutation checks.
Actual observer/serializer/profile code compiled under host MSVC. Linux CI
uses g++ and retains the existing real-symlink and unchanged route fixture checks.
Python AST/workflow YAML/source behavior pins/15 Core pins pass. Matching
exact-head CI and the final commit/run links will be recorded in PR #42.

CI adds instrumented application build, paired sections/frames/image gate and
one bounded safe numeric JSON report: **nine exact allowlisted reports only**.
No BIN/ELF/private policy/dump is uploaded. Disposable CI policy/builds are
separate from the retained local physical candidate; no substitution implied.
Historical CI's independent disposable FS checks do not replace the frozen image.

`tools/m9_mount_probe_resources.py` renders **PRINT ONLY / NOT AUTHORIZED BY
PHASE J**. Future separate consent requires fresh same-unit ROM qualification,
full private 4 MiB PRE, exact successor identity and frozen FS slice, reviewed
no-internal-retry executor, application-only target zero with no compression/
header rewrite/erase-all, GPIO0 LOW through PRE/write/full POST, exact payload
and continuous POST[rounded_end:0x400000] == PRE before boot, powered RTC 0/0,
GPIO0 release/existing RST, normal boot, mount/inventory/config PASS and zero
blocked writes. Capture mount continuation margin and post-probe block/frag,
then 180-second LINK stable/stale/recovery, no reboot and runtime heap/block/
fragmentation/continuation minima; final mounted status exact and resource
samples valid/advancing with zero rejections. Threshold review remains required.
Stock connect-attempts=1 does not establish absence of internal write retries;
the command template alone is not executor/no-retry qualification. No executor,
automatic retry/rollback or new physical operation here; ambiguity means STOP.

```text
PHASE J DEVICE CONTACTS = 0
PHASE J SERIAL I/O = 0
PHASE J FLASH WRITES = 0
PHASE J RTC WRITES = 0
PHASE J REBOOTS = 0
PHASE J DEVICE FILESYSTEM WRITES = 0
```

**STOP after Phase J. DO NOT FLASH THE INSTRUMENTED CANDIDATE. DO NOT REBOOT
OR MODIFY CURRENT SMALLTV. DO NOT ACTIVATE NORMAL PROFILE. DO NOT MERGE PR #42.**
