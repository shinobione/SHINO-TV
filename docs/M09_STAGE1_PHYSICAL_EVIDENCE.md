# Mission 9 Phase E — Stage-1 physical evidence record

**Phase G superseding Stage-2 evidence, 6 October 2026:**
[Stage-2 physical receipt](M09_STAGE2_PHYSICAL_EVIDENCE.md) records owner actions
completed after Phase F and before the documentation-only pass. Frozen
**2072576 B** LittleFS physically installed at **0x200000..0x3F9FFF**;
fresh full physical PRE/POST before first post-Stage2 boot prove lower
**0x000000..0x1FFFFF / 2097152 B** and tail
**0x3FA000..0x3FFFFF / 24576 B** preserved exactly, FS exact to frozen image.
Stage-2 physical write/preservation/RTC transition/boot/runtime/FS-image and
**MISSION9_4M2M_PHYSICAL_LAYOUT_GATE PASS**. Powered RTC 0/0 and existing RST
gave `(3,7)` / `v00061740` / `~ld`, no observed COPY; normal LCD/four dynamic
cards, 180-second runtime and stale/recovery without observed reboot. Initial
LINK RETRYING was host AP non-association, resolved by manual Windows
reassociation then CONNECTED without SmallTV reboot or firmware change.
The **399168 B Stage-1 bridge remains FS-less**, PROGRAM_FLASH_ONLY UI /
RAM_ONLY metrics; it did not mount, parse or use the installed LittleFS.
**NORMAL_PROFILE_LITTLEFS_MOUNT_GATE = NOT_RUN;
NORMAL_PROFILE_RUNTIME_GATE = NOT_RUN**. Next work is separately authorized
normal-profile mount/use qualification; P1/M8/full-product gates unchanged.
The original Stage-1 write-event preservation proof below remains historical;
it does not assert equality across the later intentional Stage-2 write.
Earlier Stage-2 HOLD/NOT_PERFORMED statements below remain correct dated history.
Phase G device actions **0**, PR #42 Draft/open/unmerged. **STOP after Phase G;
do not touch SmallTV or activate normal profile.**

**Phase F continuation, 5 October - OFFLINE DESIGN / PACKAGE QUALIFICATION ONLY:**
[Stage-2 LittleFS package/executor qualification](M09_STAGE2_LITTLEFS_QUALIFICATION.md)
passes pinned source/range models, exact local image freeze and synthetic
PRE/POST comparisons. Stage 2 physical write **HOLD**, runtime **NOT_RUN**,
not performed. Stage-1 owner physical PASS and frozen 399168-byte FS-less app
remain unchanged; no firmware change/rebuild or new device operation. Direct
raw image target `0x200000..0x3F9FFF`, protected lower **2097152 B** and tail
**24576 B** require fresh full PRE/POST before normal boot. Current app still
does not mount FS. All Phase F device-operation counters **0**. STOP after F;
no SmallTV contact, physical Stage 2, normal-profile activation or merge.
Historical dated paragraphs below remain their original evidence.

**5 October 2026 — OWNER-PROVIDED PHYSICAL EVIDENCE.** The owner reports the
observations below from their single SmallTV-Ultra on 2026-10-05, after Phase D
and **before this documentation-only pass**. This receipt records that evidence;
the documentation agent did not perform or independently repeat these actions.
No private dump, raw serial receipt, screenshot, credential or unit identifier
is attached. No additional measurement or operation timestamp is inferred.

Documentation starting state verified: clean
`feature/shino-tv-m9-flash-layout-liberation` at
`e7163f8012be34d8a57ab55ca4b7d0f8632637a1`; PR #42 Draft, open, unmerged.
No branch/PR creation, device contact, network request to the SmallTV, candidate
rebuild/replacement, firmware/tool/script/workflow change or Stage 2 in this pass.
The [active roadmap](ROADMAP.md) records this documentary authorization.

## Evidence classes and gate conclusion

[Phase A geometry](M09_FLASH_LAYOUT_LIBERATION.md),
[Phase B first-migration design](M09_FIRST_PHYSICAL_MIGRATION.md),
[Phase C executor/readback models](M09_PHYSICAL_EXECUTOR_QUALIFICATION.md) and
[Phase D RTC neutralization](M09_RTC_EBOOT_NEUTRALIZATION.md) remain their dated
**source/host/CI** evidence. Those results did not perform or authorize a device
operation. The separate owner-performed physical evidence below closes the
specified Stage-1 gates without rewriting historical HOLD/NOT_RUN statements.

| Gate | Result | Exact scope of owner-provided physical evidence |
| --- | --- | --- |
| PHASE E STAGE-1 PHYSICAL EVIDENCE | **PASS** | sanitized record of the completed owner run |
| STAGE1_PHYSICAL_WRITE_GATE | **PASS** | reviewed frozen application at zero, executor success |
| STAGE1_POSTWRITE_PRESERVATION_GATE | **PASS** | independent full PRE/POST and protected comparison before first Stage-1 boot |
| RTC_RST_PHYSICAL_TRANSITION_GATE | **PASS** | RTC sentinel retained across existing RST; zero/zero then powered normal boot |
| STAGE1_BOOT_GATE | **PASS** | normal flash boot, `v00061740`, `~ld`, no observed `cp:` path |
| STAGE1_RUNTIME_GATE | **PASS** | bounded 180-second LCD/AP/auth/four-value telemetry observation and stale/recovery |
| STAGE1_FSLESS_GATE | **PASS** | read-only status: program-flash UI, RAM-only metrics, migration/native OTA writers disabled; no LittleFS operation reported |
| STAGE2_LITTLEFS_GATE | **HOLD / NOT PERFORMED** | no filesystem provisioning or Stage-2 authorization |
| Historical EBOOT_COLD_START_GATE | **HOLD** | successful path retained power and used RST; cold-power path rejected/unqualified |

These are **Stage-1-specific** physical results, not generic physical-write
permission. The installed candidate is the conservative Mission 9 FS-less
bridge. This run does not promote unrelated private P1/P1.1, M8 signed media,
PR #40 artwork/music scenes, Home-LAN STA, native SHINO OTA or full-product
qualification. Historical product requirements remain in force.

## Owner-reported hardware and ROM qualification

Existing reversible micro-hooks were used, with **no soldering**. Known header:
**RST — GPIO0 — 3V3/VCC — RX — TX — GND**. CH340 UART adapter, **3.3 V logic**;
the SmallTV used its normal USB-C supply. The adapter did **not** power the
SmallTV through 3V3/5V. EN/CH_PD availability is not inferred from RST.

Stable ROM-download entry was repeatedly demonstrated with `boot mode:(1,7)`.
Three consecutive operations through the existing RST pad, with GPIO0 LOW,
each produced `(1,7)`. Chip was physically identified as **ESP8266EX** and flash
as **4 MiB / 4194304 B**. The known exposed RST pad physically operated.
No MAC address or other unnecessary unit-unique identifier is recorded.

## E0 — board-specific RTC retention and transition proof

Initial RTC contents were physically read, but are not recorded as stable or
important provenance. The deliberate volatile retention test was:

| Word | Before existing-RST pulse | After pulse, physically read back |
| --- | --- | --- |
| Magic `0x60001200` | `0x00000000` | `0x00000000` |
| CRC `0x6000127C` | `0xA5A5A5A5` sentinel | `0xA5A5A5A5` sentinel |

Main power remained continuous, GPIO0 stayed LOW, and one pulse used the known
RST pad. Equal readbacks **physically demonstrated RTC retention across this
unit's exposed RST path**. Zero magic kept the eboot command invalid during the
sentinel test; the sentinel was not a proposed boot command.

The sentinel was then removed and neutral state physically verified:
**`0x60001200 = 0x00000000`, `0x6000127C = 0x00000000`**. Without power loss,
GPIO0 was released while powered and one RST pulse produced normal flash
`boot mode:(3,7)`, eboot `~ld`, with no `cp:` COPY path observed. This preflight
proof and the postwrite first-boot evidence below close Phase D's board-specific
retention/normal-boot question. They do not prove RTC invalidity after power-on
or validate an EN reset. No other RTC words are claimed zero.

## Fresh PREWRITE and frozen candidate

**Fresh 4 MiB PREWRITE was byte/hash identical to the private custody MASTER.**
It was captured immediately before the Stage-1 write. Private files, custody
digests, PRE/POST digests and owner-local backup paths remain outside Git/CI;
they are not re-opened or reverified during this documentation pass.

The existing frozen candidate was revalidated immediately before the owner's
write; it was not regenerated:

| Item | Recorded value |
| --- | --- |
| Candidate bytes | **399168 / 0x61740** |
| Public frozen candidate SHA-256 | `cd99139121fa47fedd6286a185fb16e8fb9e120280ecd75f1c6b41b905e31011` |
| Target | **0x000000** |
| Payload, inclusive | **0x000000..0x06173F** |
| Sector-rounded destructive range, inclusive | **0x000000..0x061FFF** |
| Protected range, inclusive | **0x062000..0x3FFFFF** |

The owner explicitly authorized **GO Stage 1 write**. This prior exact Stage-1
decision is provenance; it grants no later physical action here.

## Stage-1 executor result and pre-first-boot preservation

The reviewed esptool **5.4.0** command completed successfully. Owner-reported
executor output: erase range **0x00000000..0x00061FFF**, wrote **399168 bytes at
0x00000000**, **“Hash of data verified.”**, and remained in the flasher stub.
No erase-all, filesystem image, Stage 2 or LittleFS operation was performed.

Before **any normal boot of the newly written Stage-1 application**, a fresh
independent full **4194304-byte POSTWRITE** was captured. The existing local
Stage-1 readback verifier returned **PASS**, with these owner-provided results:

| Verifier fact | Recorded result |
| --- | --- |
| Candidate exact | **true** |
| Candidate bytes | **399168** |
| Payload range | **0x000000..0x06173F** |
| Touched sector range | **0x000000..0x061FFF** |
| Protected comparison range | **0x062000..0x3FFFFF** |
| Protected bytes compared | **3792896** |
| Protected byte exact | **true** |

Thus POSTWRITE `0x062000..0x3FFFFF` was byte-for-byte identical to PREWRITE in
that range. This covers historical OEM/old filesystem bytes from that boundary
onward, including the old FS region and system tail, **across the Stage-1 write
event before first Stage-1 boot**. Independent full physical reads and local
comparison establish preservation beyond the executor's payload hash ACK.

Final-sector slack `0x061740..0x061FFF` lies inside the authorized touched sector;
slack equality is deliberately not required and **preservation is not claimed**.
Later SDK runtime may legitimately change SDK/system tail parameters. No later
full-flash equality, continuing tail immutability or runtime absence of all
flash writes is inferred from this pre-first-boot PRE/POST proof.

## First normal boot and bounded runtime

After POST verification, RTC magic/CRC were physically re-established and read
back as **0/0**. Power remained continuous; GPIO0 was released while powered;
RST was pulsed. Owner observed `boot mode:(3,7)`, `v00061740`, and `~ld`.
`0x61740 == 399168`, matching the frozen candidate size. No `cp:` COPY path was
observed. This records physical evidence of eboot rejection of the COPY path
and LOAD_APP of the Stage-1 application at zero.

- **240×240 LCD** initialized, orientation correct; all four metric cards visible.
  Initial cards were stale/empty before telemetry, as expected.
- Protected SHINO first-boot AP was reachable; **192.168.4.1** responded on that
  private AP. Matching private build credentials authenticated successfully.
  Credential values are not included.
- SHINO // LINK one-shot telemetry returned **CONNECTED**. All four real values
  **CPU / GPU / RAM / GPU TEMP** populated and updated dynamically.
- For **180 seconds** of continuous observation, cards stayed visible and values
  continued updating; no reboot, boot loop or display corruption was observed.
- Sender stopped: cards became stale/empty shortly afterward. Owner estimated
  about **2 seconds from Ctrl+C to visible stale state**. This is not a firmware
  TTL measurement: TTL remains **6 seconds from the LAST ACCEPTED sample**;
  elapsed sample age at Ctrl+C was not measured or inferred.
- Telemetry restarted: all four values recovered, with no reboot observed during
  stale/recovery.

This is the reported bounded Stage-1 runtime PASS, not long-term stability,
stress testing or exhaustive allocator/stack qualification. Unrecorded fields
below remain unmeasured; they cannot support broader resource-safety claims.

## Authenticated read-only runtime status

The owner reports an authenticated **read-only** status request returned:

| Field | Recorded value |
| --- | --- |
| `mode` | `FIRST_BOOT_BRIDGE` |
| `physical_flash_bytes_observed_at_runtime` | **4194304** |
| `running_application_bytes` | **399168** |
| `available_heap_bytes` | **33072** |
| `browser_ui_source` | `PROGRAM_FLASH_ONLY` |
| `pc_metrics_storage` | `RAM_ONLY` |
| `filesystem_migration_writes_compiled` | **false** |
| `native_ota_writer_compiled` | **false** |

**33072 B is the recorded available-heap snapshot**, not a measured minimum
over the entire run. Largest free block and stack high-water were **not
physically recorded / unknown**. No endpoint/timestamp/resource value beyond
the supplied evidence is invented. No filesystem migration or Stage 2 occurred.

## Concise owner-performed state sequence

ROM `(1,7)`
→ E0 RTC sentinel retention proof through existing RST (and powered normal-boot preflight)
→ fresh full PREWRITE / private MASTER equality
→ frozen candidate revalidation
→ separately owner-authorized Stage-1 application write at zero
→ independent full POSTWRITE in ROM/stub
→ exact payload and protected-region comparison PASS before first Stage-1 boot
→ RTC **0/0** readbacks
→ GPIO0 release while powered
→ existing RST pulse, continuous main power
→ normal `(3,7)` / `v00061740` / `~ld`, eboot LOAD_APP at zero
→ LCD / protected AP / authentication / telemetry
→ **180-second** runtime observation
→ telemetry stale/recovery without reboot
→ authenticated read-only runtime status.

This sequence is supplied owner evidence, not an executor or instruction to
repeat it. Earlier owner operations are not counted as actions by this pass.

## Remaining scope, privacy and validation

**Stage 2 LittleFS remains HOLD and NOT PERFORMED.** No LittleFS provisioning,
mount/format/migration test or later physical filesystem operation is authorized
by this receipt. Stage-1 FS-less success and preservation do not establish a
working new filesystem, storage reclamation, provisioned FS image or OTA release.
Stage-2 work needs its own explicit bounded owner decision.

No private MASTER/PREWRITE/POSTWRITE content, private digest, owner backup path,
password/token, MAC address, raw identifying serial receipt, generated private
policy, screenshot or binary is committed or published. The already-public
frozen candidate digest is retained. No private files were needed for this record.

Local validation is documentation consistency only: scope/diff, historical text
preservation, relative links, exact ranges/byte arithmetic, provided gate/status
values, privacy of added text and absence of code/workflow changes. Existing CI
runs unchanged on the resulting exact head; its host tests/disposable builds
are not a new physical observation or a rebuild of the retained LOCAL candidate.
Exact-head CI/check evidence is recorded in existing Draft PR #42 after it passes.

```text
PHASE E DEVICE CONTACTS = 0
PHASE E SERIAL I/O = 0
PHASE E FLASH WRITES = 0
PHASE E RTC WRITES = 0
PHASE E REBOOTS = 0
PHASE E FILESYSTEM WRITES = 0
```

These counts concern actions on the SmallTV in this documentation pass, not
ordinary repository document/CI file creation. The physical Stage-1 actions
described above were owner-performed **before** the pass. **STOP after Phase E;
do not start Stage 2, touch the SmallTV or merge PR #42.**
