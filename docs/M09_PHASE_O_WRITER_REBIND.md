# Mission 9 Phase O - frozen normal StageA writer rebind, OFFLINE only

Authority: [latest owner Phase O instruction](https://github.com/shinobione/SHINO-TV/pull/42#issuecomment-6044586614),
7 October 2026. Start exact clean `f53de10e2aea6825b53c164eb3cc9b2e7156f654`,
existing `feature/shino-tv-m9-flash-layout-liberation`, Draft/open/unmerged PR42.
Phase N offline qualification is owner-accepted. This phase changes only the
active application binding, dependent numeric receipts/pins/tests and documents.
**Future physical packet is PRINT ONLY / NOT AUTHORIZED BY PHASE O.**

## Exact retained identity and geometry

| Field | Active binding |
| --- | --- |
| Retained ignored local BIN | `research-local/m9-phase-n/frozen-normal-stage-a.bin` |
| Phase N clean firmware/source freeze | `f12a0fe0771222d1e6e2a9ac8387d66d7df8ae11` |
| True normal contract | profile1 / `esp12e_m9_4m2m_normal_qualification` / exact opt-in1 |
| BIN bytes / payload end exclusive | **399264 / 0x0617A0** |
| SHA-256 | `78a8d2d50409974fc775dd3dc9f3dbec4ac8eda839f6d9b338cadf35aab2467c` |
| Target | **0x000000** |
| Sector-rounded end exclusive | **0x062000 / 401408 B**, strictly below0x100000 |
| Protected inclusive interval | **0x062000..0x3FFFFF / 3792896 B** |
| Unique4096 B DATA packets | **98**, sequences **0..97** |
| Final sequence/start | **97 / 0x061000 (397312 B)** |
| Final packet | **1952 B actual payload +2144 B0xFF padding** |

Retained size/SHA, eboot/application segment checksums and Core application
size/CRC inspection **PASS/OFFLINE**. Rehash/inspect only: no candidate rebuild,
substitution, firmware/private policy/linker change or FS image build/rewrite.
The BIN/ELF remain private/local/ignored, not committed or uploaded to CI. HEAD
advancing for this receipt does not change the Phase N freeze identity.

The installed411152 B profile2 successor,
`e1852e56d99801b694f37d235b08a201188cf36d5a25f3f6f59d059a129bc27e`,
remains intact as historical installation/owner evidence. Its former101-packet,
1552/2544-byte final packet and0x065000 geometry are preserved in dated receipts.
Historical J411136 B `2ce2fa8da00de5c60109d0675c7bcf58ab41df2138d913b607fde25994e5a835`
and its original source/candidate manifests are unchanged.

## Binding and acquisition/transaction proof

`m9_single_attempt_app_write.py` changes four active binding constants and the
selection message; its future packet updates normal geometry and keeps RTC/boot
as separate later gates. `candidate()` still requires the exact external SHA,
regular local file, full bytes/hash/image inspection and exact size/rounded end
before any transport factory. `SingleAttempt.write()` consumes the session even
on preflight rejection; it repeats identity validation before invoking a factory.
Runner preflight also validates the candidate before serial acquisition. Old
successor/J hashes and GO, changed/truncated normal bytes and wrong rounded
extent reject before factory/acquisition. No old GO is treated as new authority.

**Entire SingleAttempt and PinnedStubTransport class source text is unchanged**
from f53de10, pinned with LF SHA-256. The entire Phase M physical runner module
is also source-equal after restoring its sole reviewed success-receipt literal
from0x061FFF to0x064FFF. This is a metadata edit, not an acquisition/control-flow
change. Mutation tests fail altered SYNC budget, continuation/session latch,
post-stub capacity and MD5 range. Current helper pins are refreshed only for the
authorized writer binding and numeric runner receipt; historical K/J/Phase M/N
source manifests and the resource-policy implementation remain unchanged.

Preserved acquisition: one strict explicit COM literal, approved Windows Python
3.12.x identity, exact esptool5.4.0/esp-pylib1.1.5/pyserial3.5 source/version pins;
DTR/RTS stored false while closed, one open attempt; maximum five fresh-ROM SYNC
requests sharing5 s/16384 B/256 reads with50 ms pre-stub retry delay. Fresh exact
ESP8266 ROM/chip magic, pinned v2 without plugin/v1 fallback, uncached post-stub
measured capacity byte0x16 BEFORE Begin. Raw-ROM capacity assertion stays absent.
API/source checks do not prove electrical isolation; that remains a later owner
physical prerequisite.

Preserved transaction core with the new constants: **one FLASH_BEGIN;98 unique
FLASH_DATA0..97;one no-reboot FLASH_END;one MD5 barrier over exactly399264 B**.
Zero automatic flash retry/reconnect/reopen/reset after transaction start;
zero rollback/recovery write. Exceptions consume the session; no cleanup Finish,
second Begin or repeated DATA. No stock write_flash path. Acknowledged MD5 closes
no physical gate and cannot authorize boot.

## Continuous preservation and physical boundary

A future separately authorized write requires a fresh private full4MiB PRE.
After the transaction, full independent4MiB POST is mandatory **before first
normal boot**. POST payload at0 must equal the frozen normal BIN and
**POST[0x062000:0x400000]==PRE byte-for-byte**. This continuously protects unused
application arena through0x1FFFFF, frozen LittleFS0x200000..0x3F9FFF and reserved
tail0x3FA000..0x3FFFFF. Final packet padding does not relax this interval. The
shared local comparator remains unchanged; synthetic full-image tests reject a
changed candidate byte and mutations at the protected start, arena/FS boundary,
FS end, tail start and flash end, plus truncated POST. They are host models only.

**RTC neutralization/readback and GPIO0/RST boot transition are separate later
physical gates.** Phase O supplies no physical execution, RTC, reboot or recovery
authority and does not auto-promote normal or full-product operation.

Installed profile2 `MOUNT_PROBE_RESOURCE_PHYSICAL_GATE=PASS` and
`MOUNT_PROBE_PHYSICAL_GATE=PASS` remain [owner-supplied historical probe evidence](M09_SUCCESSOR_PHYSICAL_ACCEPTANCE.md).
They do not transfer to profile1. **NORMAL_PROFILE_LITTLEFS_MOUNT_GATE=NOT_RUN;
NORMAL_PROFILE_RUNTIME_GATE=NOT_RUN.** No media/home-LAN/native OTA promotion.
The old Phase K evaluator still describes its scoped historical probe policy;
the qualification report explicitly labels this scope separately from the new
candidate-role metadata. No resource threshold or policy is weakened or applied
as normal physical acceptance by the rebind.

## Validation and final checkpoint

Raw current Phase N LF pins cover **all113 tracked firmware files**; direct Git
firmware diff from f53de10 is empty. This current-source equality does not rely
on the historical predecessor projection. Separate existing source audits still
validate their dated projection/pins; Phase N's16 exact current source pins and
historical K/J/Phase M records remain unchanged.

New deterministic binding/source tests exercise old identity/GO rejection before
factory/acquisition, actual altered retained-image copies locally (synthetic
wrong bytes in CI), independent wrong-extent rejection, source drift, ignored/
untracked freeze and PRINT ONLY/NOT_RUN policy. Updated real pinned esptool/SLIP
fake-serial tests validate the exact98-packet sequence and1952/2144 last packet,
one no-reboot Finish and exact MD5 range. Both executor and integrated runner
exercise every101 transaction fault position (Begin+98 DATA+Finish+MD5) across
four exception types: **404 fault cases each**. All five bounded SYNC success
positions preserve their original acquisition semantics.

**248 local regression tests PASS;0 failures/errors/skips** with native MSVC and
workspace temporary fixtures. Exact-head CI is recorded in PR42 after push.
An earlier host run found a stale101-packet fixture
expectation; its update also needed an indentation correction. Those test-only
corrections do not change the preserved transaction/acquisition behavior.
Approved interpreter/package/source/stub audits and retained candidate gate
**PASS/OFFLINE**; real runner default audit returned
**AUDIT_PRINT_ONLY_NO_PORT_OPEN**, physical_authorization=false/serial_io0.
Local results are ignored under `research-local/m9-phase-o/`. CI uses source
pins/synthetic fixtures only for this binding; private normal BIN is absent and
`PHASE_O_RETAINED_CANDIDATE_IDENTITY_GATE=NOT_READ_BY_THIS_RUN` in CI. Existing
ephemeral public comparison builds never become or replace the frozen candidate.

Existing PR42 remains Draft/open/unmerged. Final commit/exact-head job links are
recorded in its description and ignored `research-local/m9-phase-o/exact-head-ci.json`
after push. **OFFLINE binding qualification only; future physical packet PRINT
ONLY/not authorized. STOP. DO NOT FLASH/REBOOT/MERGE.**

## Exact changed files

- `.github/workflows/m9-phase-k.yml`
- `.github/workflows/m9-phase-l.yml`
- `.github/workflows/m9-phase-m.yml`
- `docs/AGENT_HANDOFF.md`
- `docs/M09_FLASH_LAYOUT_LIBERATION.md`
- `docs/M09_MOUNT_STACK_REMEDIATION.md`
- `docs/M09_PHASE_L_SYNC_HOTFIX.md`
- `docs/M09_PHASE_N_STAGE_A.md`
- `docs/M09_PHASE_O_WRITER_REBIND.md`
- `docs/M09_PHYSICAL_WRITER_REBIND.md`
- `docs/M09_RESOURCE_POLICY_AND_EXECUTOR_QUALIFICATION.md`
- `docs/M09_SINGLE_ATTEMPT_PHYSICAL_RUNNER.md`
- `docs/ROADMAP.md`
- `tools/m9_mount_stack_sources.json`
- `tools/m9_phase_k_qualification.py`
- `tools/m9_phase_l_sources.json`
- `tools/m9_phase_o_qualification.py`
- `tools/m9_phase_o_sources.json`
- `tools/m9_single_attempt_app_write.py`
- `tools/m9_single_attempt_physical_runner.py`
- `tools/test_m9_bounded_rom_sync.py`
- `tools/test_m9_phase_n.py`
- `tools/test_m9_phase_o.py`
- `tools/test_m9_single_attempt_app_write.py`
- `tools/test_m9_single_attempt_physical_runner.py`

**DEVICE CONTACTS=0; SERIAL I/O=0; FLASH WRITES=0; RTC WRITES=0; REBOOTS=0;
DEVICE FILESYSTEM WRITES=0. STOP before every physical operation.**
