# Mission 9 Phase I — physical LittleFS mount-probe evidence

**Phase J OFFLINE continuation, 6 October 2026:**
[Separate resource-instrumented successor](M09_MOUNT_PROBE_RESOURCE_INSTRUMENTATION.md)
adds observability only in a new opt-in profile-2 environment. No FS/inventory/
telemetry/authentication behavior change or new physical evidence. The original
installed **407440 B** candidate and all supplied Phase I evidence below remain
unchanged. **MOUNT_PROBE_PHYSICAL_GATE PARTIAL / HOLD;
MOUNT_PROBE_RESOURCE_PHYSICAL_GATE HOLD / NOT_RUN; both normal-profile gates
NOT_RUN; PHYSICAL_RESOURCE_THRESHOLD REVIEW_REQUIRED.** Clean successor build
freeze pending at the J implementation checkpoint. Six J device counters **0**.
No permission to flash/reboot/modify the current unit, activate normal profile
or merge; this banner changes next-work status only, preserving the dated receipt.

**6 October 2026 — OWNER-PROVIDED PHYSICAL EVIDENCE; DOCUMENTATION ONLY.**
The owner performed the supplied physical run after Phase H and before this
documentation pass. The agent records the sanitized results without contacting
the SmallTV, inspecting private PRE/POST dumps or repeating any physical action.
No additional timestamp, reviewer identity or unit identifier is inferred.

Continuity before edits: clean `feature/shino-tv-m9-flash-layout-liberation`
at **5ea433b2e72455a93c0a8fca80903c8c8acffbd4**;
[PR #42](https://github.com/shinobione/SHINO-TV/pull/42) Draft/open/unmerged.
The [active roadmap](ROADMAP.md) records documentation-only authorization.
Firmware, tools, companion, scripts, PlatformIO and workflows are unchanged.
No local candidate/FS rebuild, instrumentation implementation or device operation.

## Gate conclusion and evidence boundary

[Phase H](M09_LITTLEFS_MOUNT_PROBE_QUALIFICATION.md) established source/host/build
qualification only. Its HOLD/NOT_RUN statements remain correct dated evidence.
The owner-performed run below advances only the named profile-2 functional and
preservation gates; host/CI results are separate from owner-unit observations.

| Gate | Current result | Supplied physical evidence / remaining condition |
| --- | --- | --- |
| MOUNT_PROBE_FS_FUNCTIONAL_GATE | **PASS** | Authenticated mount, exact inventory/payloads and blank seed |
| MOUNT_PROBE_RUNTIME_FUNCTIONAL_GATE | **PASS** | 180 s stable; telemetry stale/recovery; no observed reboot/corruption |
| MOUNT_PROBE_APPLICATION_PRESERVATION_GATE | **PASS** | Exact new candidate payload at zero and protected PRE/POST equality before boot |
| MOUNT_PROBE_FILESYSTEM_PRESERVATION_GATE | **PASS** | PRE FS equals frozen image; POST FS equals PRE before boot |
| MOUNT_PROBE_NO_FS_WRITE_GATE | **PASS** | Autoformat disabled, active writer policy false, zero blocked attempts; no observed mutation |
| MOUNT_PROBE_PHYSICAL_GATE | **PARTIAL / HOLD** | Physical largest-free-block and continuation-stack margin evidence missing |
| NORMAL_PROFILE_LITTLEFS_MOUNT_GATE | **NOT_RUN** | Profile 2 is not the full normal profile |
| NORMAL_PROFILE_RUNTIME_GATE | **NOT_RUN** | Full normal profile remains prohibited |

The application-preservation result refers to the **new exact probe payload**
and bytes outside its touched extent; the prior Stage-1 application was replaced.
Preboot full-chip equality proves preservation across this application write,
not perpetual SDK/system-tail immutability. Mounted file checks do not recompute
the raw FS image hash. The no-FS-write gate is bounded to the supplied run,
status indicators and observations; no post-runtime full raw readback is claimed.
No P1/M8/Home-LAN/native OTA or full-product qualification is promoted.

## Installed candidate and pre-write qualification

| Item | Owner-reported value |
| --- | --- |
| Profile / environment | **SHINO_BOOT_PROFILE=2 / esp12e_m9_4m2m_mount_probe** |
| Candidate bytes | **407440** |
| Candidate SHA-256 | `ca92cc2f4a8a67f70bd305875bd37be90d0cdff74bf7b338339856407dceef8b` |
| Phase H clean implementation freeze | `5f3db19e29398ef6498b08b02de29cae48f9b59a` |
| Physically qualified chip / flash | **ESP8266EX / 4 MiB** |
| Physical executor / stub | **esptool 5.4.0 / stub version 2** |
| Fresh full PRE-PROBE | **4194304 bytes**; private binary/digest/path unpublished |
| PRE FS slice | `PRE[0x200000:0x3FA000]` equals retained frozen Stage-2 FS; **FS_EXACT=true** |
| Frozen FS bytes / SHA-256 | **2072576** / `d7ce9133b34fb5937d5640db81ff863a8f22a3717255c4b23057aea9ed2ef045` |

The owner explicitly authorized **GO Mount Probe write** for this exact
candidate at **0x000000**. This records a completed owner operation; it grants
no authority to repeat it or install any successor.

Observed esptool erase: **0x00000000..0x00063FFF**. Observed write:
**407440 bytes at 0x00000000**, **Hash of data verified**, **Staying in flasher
stub**. No erase-all, filesystem write or reboot immediately after write.

## Full POST before first application boot

The owner captured independent full **4194304-byte POST** before any normal
application boot. Existing `m9_stage1_readback_verify.py` returned
**PASS_LOCAL_STAGE1_READBACK_MODEL** using the physical PRE/POST and exact
probe candidate. The verifier's legacy name does not turn these supplied
physical inputs into synthetic captures or activate the full normal profile.

| Comparison | Owner-reported result |
| --- | --- |
| Candidate bytes / SHA-256 | **407440** / exact candidate identity above |
| Exact application payload | **0x000000..0x06378F**, exact at target zero |
| Touched erase sectors | **0x000000..0x063FFF / 409600 bytes** |
| Continuous protected range | **0x064000..0x3FFFFF / 3784704 bytes** |
| protected_byte_exact | **true** |
| Lower unused arena | `POST[0x064000:0x200000] == PRE[0x064000:0x200000]`, **1687552 bytes** |
| LittleFS | `POST[0x200000:0x3FA000] == PRE[0x200000:0x3FA000]`, **2072576 bytes** |
| Reserved/system tail | `POST[0x3FA000:0x400000] == PRE[0x3FA000:0x400000]`, **24576 bytes** |

Thus `POST[0x064000:0x400000] == PRE[0x064000:0x400000]` continuously protects
the lower unused arena, FS and tail across the write. Slice ends are exclusive;
**1687552 + 2072576 + 24576 = 3784704** and
**409600 + 3784704 = 4194304**. Final-sector slack within the touched range is
outside this protected comparison. PRE/POST binaries, digests and private paths
are neither included nor published.

## RTC and first boot

Physical RTC reads before first boot were already:

```text
0x60001200 = 0x00000000
0x6000127C = 0x00000000
```

**No RTC write was required.** Continuous USB-C power was retained. The owner
released GPIO0 and pulsed existing RST; this was the owner-run boot transition,
not a reset performed during the documentation pass.

```text
rst cause:2
boot mode:(3,7)
v00063790
~ld
```

No `cp:` COPY path was observed. **0x63790 == 407440** candidate bytes.
LCD returned with four telemetry cards visible.

## Authenticated physical mount result

The existing authenticated probe endpoint returned these sanitized values:

| Field | Owner-reported physical value |
| --- | --- |
| attempted | **true** |
| autoformat_disabled | **true** |
| mounted | **true** |
| inventory_checked / inventory_exact | **true / true** |
| checked_file_count | **24** |
| checked_payload_bytes | **181402** |
| config_seed_exact | **true** |
| write_paths_compiled | **false** |
| blocked_write_attempts | **0** |
| filesystem_start | **2097152 / 0x200000** |
| filesystem_end_exclusive | **4169728 / 0x3FA000** |
| filesystem_bytes | **2072576** |
| available_heap_after_mount | **36144 bytes** |
| available_heap_after_inventory | **36144 bytes** |
| Initial minimum_observed_free_heap | **29744 bytes** |

This demonstrates mounted LittleFS with autoformat disabled, all reviewed
24 files found/read with exact reviewed payload inventory and canonical blank
config, and no denied FS write attempt. `write_paths_compiled=false` retains
Phase H's active application writer-policy meaning; generic Core virtual writer
symbols may remain linked behind the denying adapter. The full raw image SHA
was established by the PRE/POST slice evidence, not by mounted payload hashes.

## Telemetry and bounded runtime

SHINO // LINK one-shot reported **CONNECTED**. Owner-reported continuous
**180-second** runtime then passed:

| Observation | Result |
| --- | --- |
| A: 180 s stable | **OK** |
| B: stale after sender stop | **OK** |
| C: recovery after sender restart | **OK** |
| D: reboot observed | **NO** |
| Display corruption observed | **NO** |
| Filesystem mutation observed | **NO** |

After runtime, authenticated status still reported **mounted=true**,
**inventory_exact=true**, **checked_file_count=24**,
**checked_payload_bytes=181402**, **config_seed_exact=true** and
**blocked_write_attempts=0**. Final observed minimum free heap: **27808 bytes**.
These are cooperative sampled heap minima, not exhaustive transient allocation
minima or a largest-block/fragmentation/continuation-stack measurement.

## Remaining blockers and next bounded work

**MOUNT_PROBE_PHYSICAL_GATE remains PARTIAL / HOLD.** Phase H required physical
largest-free-block and continuation-stack margin evidence before closure.
The installed candidate does not expose those two metrics, so both remain
**UNKNOWN / NOT_MEASURED**; free heap and individual compiler frames cannot
substitute for them. Heap fragmentation is also not supplied. The requirement
is preserved, not weakened or retroactively removed.

Next work is a separately reviewed **offline** instrumented profile-2 candidate
that preserves exact mount/inventory behavior and additionally exposes read-only
free heap, largest free heap block, heap fragmentation percent and continuation
stack free/high-water evidence using pinned Core APIs only:
**ESP.getHeapStats(...)**, **ESP.getFreeContStack()** and
**ESP.resetFreeContStack()**. Stack watermark reset is RAM instrumentation,
not a device reset; its measurement boundary must be reviewed in that future
phase. No instrumentation is implemented here and no successor physical run
is authorized by Phase I.

No FS behavior change, ConfigManager, SecureStorage, STA, OTA writer or FS writer
belongs in that bounded work. Full normal-profile mount/runtime gates remain
**NOT_RUN**; profile 1 remains prohibited.

## Documentation validation, privacy and counters

This pass checks documentation identity/geometry/arithmetic/status consistency,
relative links, preservation of historical text and a five-Markdown-file-only
diff. Exact resulting commit and exact-head CI run links are recorded in PR #42.
CI remains offline and does not repeat or supplement this owner physical run.
No local application/FS rebuild or firmware/tool regression execution is needed
for this documentation-only change.

No private PRE/POST/MASTER binary, digest or path, credential, Wi-Fi/Digest
password, MAC, identifying serial transcript, screenshot, policy or BIN/ELF
artifact is committed/uploaded. Public candidate/frozen-FS identities and the
supplied sanitized numeric/boot/status evidence only are recorded.

The following counters apply to **this Phase I documentation pass**, separately
from the completed owner-performed physical run:

```text
PHASE I DEVICE CONTACTS = 0
PHASE I SERIAL I/O = 0
PHASE I FLASH WRITES = 0
PHASE I RTC WRITES = 0
PHASE I REBOOTS = 0
PHASE I FILESYSTEM WRITES = 0
```

**STOP after Phase I documentation. DO NOT MODIFY OR REBOOT THE CURRENT
SMALLTV. DO NOT ACTIVATE NORMAL PROFILE. DO NOT MERGE PR #42.**
