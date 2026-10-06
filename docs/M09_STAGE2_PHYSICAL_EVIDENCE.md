# Mission 9 Phase G — Stage-2 physical evidence record

**Phase H OFFLINE continuation, 6 October 2026:**
[Dedicated mount-probe qualification](M09_LITTLEFS_MOUNT_PROBE_QUALIFICATION.md)
PASS for profile **2** opt-in source/build/host/link/resource evidence only.
Profile 0 unchanged, profile 1 remains prohibited; no full-normal activation.
LOCAL probe **407440 B**, SHA-256
`ca92cc2f4a8a67f70bd305875bd37be90d0cdff74bf7b338339856407dceef8b`,
future application touched extent **0x000000..0x063FFF / 409600 B**, protecting
all bytes from **0x064000** onward. Single mount with autoformat disabled,
read-only callbacks, all 24 file payloads streamed/validated, ConfigManager/
SecureStorage/STA/writers bypassed. **MOUNT_PROBE_PHYSICAL_GATE HOLD / NOT_RUN;
NORMAL_PROFILE_LITTLEFS_MOUNT_GATE NOT_RUN;
NORMAL_PROFILE_RUNTIME_GATE NOT_RUN.** Current app remains **399168 B FS-less**;
the physically installed FS range/hash and owner-provided Phase G evidence below
are unchanged. No probe was installed or device contacted. All Phase H action
counters **0**, PR #42 Draft/open/unmerged. **STOP after H; no probe flash or
normal-profile activation.** This supersedes the next-work plan only; it does
not rewrite or add physical evidence to this historical Stage-2 receipt.

**6 October 2026 — OWNER-PROVIDED PHYSICAL EVIDENCE.** The owner performed the
physical Stage-2 operation after Phase F and **before this documentation-only
pass**. This document records the supplied sanitized observations; the agent
did not execute, contact the device or independently repeat the physical run.
No additional timestamp, measurement or unit identifier is inferred.

Documentation continuity verified before edits: clean
`feature/shino-tv-m9-flash-layout-liberation` at
`f92b42deaa87e3df7b6204f1010886a8ed343043`; existing
[PR #42](https://github.com/shinobione/SHINO-TV/pull/42) Draft, open, unmerged.
The [active roadmap](ROADMAP.md) records the documentation-only authorization.
No branch/PR creation, firmware/companion/tool/script/platform/workflow change,
local application/FS rebuild, Stage-3 activation or device operation in this pass.

## Evidence classes and gate conclusion

[Phase F](M09_STAGE2_LITTLEFS_QUALIFICATION.md) qualified pinned source/range
models, the exact retained local FS package and synthetic PRE/POST comparisons
offline. Its physical **HOLD / NOT_RUN** statements were correct at that time
and remain unchanged as dated evidence. Host/CI PASS is not device PASS.
[Phase E](M09_STAGE1_PHYSICAL_EVIDENCE.md) records the earlier physical Stage-1
installation. The separate owner-performed Stage-2 evidence below supersedes
only the named Stage-2 physical gates.

| Gate | Result | Owner-provided evidence scope |
| --- | --- | --- |
| STAGE2_PHYSICAL_WRITE_GATE | **PASS** | exact frozen raw LittleFS write at `0x200000`, executor hash ACK |
| STAGE2_POSTWRITE_PRESERVATION_GATE | **PASS** | full physical PRE/POST before boot; protected lower and tail exact |
| STAGE2_RTC_BOOT_TRANSITION_GATE | **PASS** | physical RTC 0/0 readbacks, continuous power, GPIO0 release then existing RST |
| STAGE2_BOOT_GATE | **PASS** | `(3,7)` / `v00061740` / `~ld`, no observed `cp:` COPY path |
| STAGE2_RUNTIME_GATE | **PASS** | 180-second four-value runtime and stale/recovery, no observed reboot |
| STAGE2_FS_IMAGE_PHYSICAL_GATE | **PASS** | full POST FS slice equals the exact frozen image |
| MISSION9_4M2M_PHYSICAL_LAYOUT_GATE | **PASS** | exact FS installation and protected-range write-event preservation |
| NORMAL_PROFILE_LITTLEFS_MOUNT_GATE | **NOT_RUN** | current Stage-1 bridge remains FS-less; no mount/parse/use proof |
| NORMAL_PROFILE_RUNTIME_GATE | **NOT_RUN** | normal profile not activated or observed |

P1/M8/full-product qualification remains unchanged. This record does not promote
Home-LAN STA, artwork/music scenes, generic signed native OTA or release safety.
R3 remains PARTIAL and R10 BLOCKED. The 6-second telemetry TTL and 8-second
native-media transaction deadline remain unchanged. Historical cold-power
qualification remains HOLD; the observed path retained main power and used RST.

## New-session ROM qualification and fresh PRE

After the previous clean power-down, the owner reconnected using the already
qualified reversible hook wiring, with **no soldering**. ROM download entry
`boot mode:(1,6)` was observed twice. PuTTY was closed before esptool access.
The same pinned **Python 3.12.10 / esptool 5.4.0 / stub version 2** environment
was used. Physical chip-id returned **ESP8266EX**; physical flash-id returned
**Detected flash size: 4MB**. No MAC address is published.

**A fresh distinct 4 MiB PRE-STAGE2 was captured, privately hashed and retained
immediately before the physical Stage-2 write.** The owner observed
`Read 4194304 bytes from 0x00000000` and `Staying in flasher stub.` This fresh
PRE was distinct from factory MASTER, Stage-1 PREWRITE, Stage-1 POSTWRITE and
the previous session's G0 PRE. It remains a private rollback authority; neither
its binary, SHA-256 nor local path is included or reopened in this pass.

## Immediate frozen-package and executor/source revalidation

The owner reports `m9_stage2_fs_candidate.py` returned immediately before write:

| Field | Recorded value |
| --- | --- |
| status | `PASS_OFFLINE_STAGE2_PACKAGE_PHYSICAL_HOLD` |
| STAGE2_IMAGE_FREEZE_GATE | `PASS_OFFLINE_EXACT_FILE_ONLY` |
| environment | `env:esp12e_m9_4m2m` |
| target | `2097152 / 0x200000` |
| end_exclusive | `4169728 / 0x3FA000` |
| image_bytes | **2072576** |
| erase_start / erase_end_inclusive | `0x200000 / 0x3F9FFF` |
| sector_count | **506** (4096-byte erase sectors) |
| fs_block_bytes / fs_page_bytes | **8192 / 256** |
| frozen image SHA-256 | `d7ce9133b34fb5937d5640db81ff863a8f22a3717255c4b23057aea9ed2ef045` |
| frozen image MD5 | `1c28417e91dc8359f35a5a403839050b` |
| image_inventory_exact / image_file_count | **true / 24** |
| parser | `littlefs-python==0.15.0` |
| parser_autoformat | **false** |
| parser_backing | `READ_ONLY_MEMORY` |
| parser_writes | **0** |

This is immediate **offline package revalidation** of the retained file, not
a filesystem mount by the installed application or an interchangeable CI image.
The tool's PHYSICAL_HOLD status describes its offline authority; the subsequent
physical write relied on the separate exact owner authorization below.

Immediately before write, `m9_stage2_executor.py` returned:

| Field | Recorded value |
| --- | --- |
| status | `PASS_OFFLINE_STAGE2_EXECUTOR_SOURCE_MODEL` |
| STAGE2_EXECUTOR_MODEL_GATE | **PASS** |
| STAGE2_RAW_WRITE_BOUNDS_GATE | **PASS** |
| selected_executor | `DIRECT_UART_RAW_LITTLEFS_WRITE_PRINT_ONLY` |
| esptool_version / python_version | **5.4.0 / 3.12.10** |
| external_interpreter_pin_checked | **true** |
| stub_version / stub_release | **2 / v1.2.2** |
| core_version / platform_version | **3.1.2 / 4.2.1** |
| source_pins_checked | **true** |
| target / end_exclusive | `0x200000 / 0x3FA000` |
| erase_start / erase_end_inclusive | `0x200000 / 0x3F9FFF` |
| header_rewrite / compression | **false / false** |
| GPIO0_LOW_required_through_PRE_write_POST | **true** |

These statuses retain their source/model meaning. No tool was executed against
the device by this documentation pass.

## Exact owner authorization and physical write

The owner explicitly authorized **GO Stage 2 write**, applying **only** to the
reviewed frozen LittleFS SHA-256
`d7ce9133b34fb5937d5640db81ff863a8f22a3717255c4b23057aea9ed2ef045`
at **0x200000**. This prior exact-operation approval is evidence, not generic
filesystem-write permission or approval for any further action.

The qualified esptool **5.4.0 raw UART write completed**. Sanitized observations:

- `Flash will be erased from 0x00200000 to 0x003f9fff...`
- `Wrote 2072576 bytes at 0x00200000`
- `Hash of data verified.`
- `Staying in flasher stub.`

The exact destructive erase/write range was **0x200000..0x3F9FFF**, inclusive,
**2072576 B / 506 sectors**. No erase-all occurred, no application-area write
occurred, and no reserved-tail write was requested. No HTTP/U_FS writer or
automatic rollback was used.

## Full physical POST and independent preservation before first boot

Before **any normal application boot after Stage-2 write**, a fresh full physical
4 MiB POST-STAGE2 was captured. The owner observed
`Read 4194304 bytes from 0x00000000` and `Staying in flasher stub.` No POST
binary, digest, private path or raw bytes are published or reopened here.

The owner reports `m9_stage2_readback_verify.py` returned
**PASS_LOCAL_STAGE2_READBACK_MODEL**, with **4194304 bytes per readback**,
**2072576 image bytes**, the exact public frozen image SHA-256 above, and:

| Region | Inclusive physical range | Bytes compared | Result |
| --- | --- | ---: | --- |
| Application + future OTA arena | `0x000000..0x1FFFFF` | **2097152** | `lower_protected_exact = true`; POST equals fresh PRE |
| SHINO LittleFS | `0x200000..0x3F9FFF` | **2072576** | `filesystem_exact = true`; POST equals frozen image |
| Reserved/system tail | `0x3FA000..0x3FFFFF` | **24576** | `tail_protected_exact = true`; POST equals fresh PRE |

The local verifier status name is retained verbatim. In this owner-reported run
the inputs were **independent full physical PRE/POST readbacks**, distinct from
Phase F's synthetic captures. The recorded pre-first-boot proof is:

```text
POST[0x000000:0x200000] == PRE[0x000000:0x200000]
POST[0x200000:0x3FA000] == exact frozen LittleFS image
POST[0x3FA000:0x400000] == PRE[0x3FA000:0x400000]
```

Slices use exclusive ends. **2097152 + 2072576 + 24576 = 4194304 bytes**.
The post-Stage2 physical map above is established across this write event
**before first post-Stage2 boot**. It proves geometry and current contents, not
all 1 MiB + 1 MiB OTA behavior, atomic updates, fixed A/B recovery or continuing
tail immutability. Later SDK/system-tail housekeeping is outside this proof.
Historical OEM bytes in `0x100000..0x1FFFFF` were preserved, not erased/reclaimed
by this write. OEM application-only return is not a filesystem rollback.

## RTC neutralization and first post-Stage2 boot

RTC words were explicitly neutralized and physically read back:

| Word | Physical readback |
| --- | --- |
| `0x60001200` | `0x00000000` |
| `0x6000127C` | `0x00000000` |

Continuous main power was retained; GPIO0 remained LOW until after verification.
GPIO0 was then released while powered, and the existing exposed RST pad pulsed.
The owner observed **`rst cause:2` / `boot mode:(3,7)` / `v00061740` / `~ld`**.
No `cp:` COPY path was observed. **0x61740 == 399168 bytes**, matching the
installed Stage-1 application. No cold-power or EN-path qualification is inferred.

The current application therefore remains the known **FS-less Stage-1
FIRST_BOOT_BRIDGE**, with **PROGRAM_FLASH_ONLY UI / RAM_ONLY metrics**.
The physical LittleFS installation does **not** establish that this application
mounted, parsed or used it. No new Stage-2 status/resource measurement is supplied;
Phase E's **33072 B** heap snapshot is historical, not a Stage-2 heap value.
Stage-2 heap, largest free block and stack high-water remain unrecorded/unknown.

## LCD, host Wi-Fi association and bounded runtime

The **240×240 display initialized normally**, all four CPU/GPU/RAM/GPU TEMP
cards were visible, and no orientation regression was observed. Windows
initially was not associated with the SmallTV AP; the first SHINO // LINK
one-shot returned **RETRYING**. The owner manually reconnected Windows to the
existing private SHINO AP. No SmallTV reboot or firmware change was required;
the subsequent one-shot returned **CONNECTED**. This is a **host Wi-Fi
association condition**, not a firmware or filesystem failure, and does not
qualify household STA operation.

During **180 seconds** of continuous SHINO // LINK runtime observation, the four
cards remained visible and CPU/GPU/RAM/GPU TEMP updated dynamically. No reboot,
boot loop or display corruption was observed. The sender then stopped and cards
transitioned to stale/empty; after sender restart all four values recovered.
No reboot occurred during stale/recovery. No precise stale latency is supplied
or inferred; the telemetry contract remains **6 seconds from last accepted sample**.

Owner result: **A = 180 s stable = OK; B = stale after stop = OK;
C = recovery after restart = OK; D = reboot observed = NO.** This is bounded
runtime evidence, not long-term stability or exhaustive resource qualification.

## Concise owner-performed state sequence

New-session ROM `(1,6)` twice
→ chip / flash qualification
→ fresh PRE-STAGE2
→ frozen package revalidation
→ executor/source revalidation
→ owner GO Stage 2 write
→ raw LittleFS write at `0x200000`
→ full POST-STAGE2 before boot
→ exact PRE/POST validation
→ RTC **0/0**
→ GPIO0 release while powered
→ existing RST
→ `(3,7)` / `v00061740` / `~ld`
→ Stage-1 FS-less LCD
→ manual Windows AP reassociation
→ telemetry **CONNECTED**
→ **180-second** runtime
→ stale/recovery
→ no observed reboot.

This sequence records prior owner evidence; it is not an executable packet or
authority to repeat an operation.

## Remaining gates, privacy and documentation validation

**NORMAL_PROFILE_LITTLEFS_MOUNT_GATE = NOT_RUN** is the next unresolved gate;
**NORMAL_PROFILE_RUNTIME_GATE = NOT_RUN**. Next work is separately authorized
normal-profile LittleFS mount/use qualification. **Do not activate normal profile
or Stage 3 in Phase G.** PR #42 remains Draft/open/unmerged.

No private PRE/POST binary or digest, factory MASTER or private MASTER digest,
absolute backup path, owner-specific bytes, credential/password, MAC address,
screenshot, raw identifying serial transcript, private policy header or binary
artifact is committed or published. Only the already-public frozen FS digests
are recorded. No private backup inspection is needed for this documentary record.

Local validation is **documentation consistency only**: six Markdown-file scope,
historical-text preservation, relative links, exact range/byte arithmetic, gate
and supplied status consistency, privacy review and unchanged executable paths.
Existing workflow behavior is unchanged; exact-head CI results are recorded in
PR #42 after completion. CI host tests/disposable builds are separate from the
owner's physical evidence and do not rebuild/replace the retained local app/FS.

```text
PHASE G DEVICE CONTACTS = 0
PHASE G SERIAL I/O = 0
PHASE G FLASH WRITES = 0
PHASE G RTC WRITES = 0
PHASE G REBOOTS = 0
PHASE G FILESYSTEM WRITES = 0
```

**PHASE G DOCUMENTATION-PASS DEVICE ACTIONS: 0.** These counters apply to
actions on the SmallTV during this documentation pass. The physical actions
above were owner-performed **before** it. **STOP after Phase G documentation;
do not touch the SmallTV, activate normal profile or merge PR #42.**
