# SHINO // TV — Agent handoff / operational source of truth
Last product contract update: **2026-10-01**. This document is primarily for ChatGPT, Codex and successor coding agents, not a short end-user marketing summary. It deliberately points to historical records instead of deleting them. Always check live branch HEAD and exact CI again at execution time.

**Active OFFLINE physical-writer rebind, 7 October 2026:**
[Focused receipt](M09_PHYSICAL_WRITER_REBIND.md). Owner authorizes only the
successor binding from clean849d430f6736f349a089cbac7acf2c9648e9b887,
same branch/Draft PR42. Retained411152 B successor SHA256
e1852e56d99801b694f37d235b08a201188cf36d5a25f3f6f59d059a129bc27e,
target0, payload end0x064610, rounded0x065000, protected0x065000..0x3FFFFF.
101 DATA blocks; final1552 B payload/2544 B0xFF padding. No firmware change,
rebuild/substitution or device contact. Phase M runner/acquisition/post-stub
capacity gate unchanged; one Begin/unique DATA/Finish/MD5, zero flash retry/
reconnect/reset/reopen/recovery write. Full independent POST before boot required.
Historical J identity stays separately recorded; current writer now selects only
the frozen mount-stack successor. Numeric physical floors unchanged; installed
J mount1776 remains FAIL/HOLD, successor physical NOT_RUN, normal gates NOT_RUN.
Six agent counters ZERO. STOP. DO NOT FLASH; no merge or physical authority.

**Active owner physical update and OFFLINE mount-stack remediation, 7 October 2026:**
[Focused mount-stack receipt](M09_MOUNT_STACK_REMEDIATION.md). Owner reports
exact411136-byte J candidate2ce2fa8d...e5a835 installed/booted, no-autoformat
mount/inventory/config exact,24 files/181402 bytes, zero blocked writes/rejected
samples. Resource samples valid; mount continuation1776 B **FAILS** unchanged
2048 B floor by272 B; runtime3296 B passes. Physical resource gate **HOLD**;
do not retain prior NOT_RUN as today's owner-reported installation status or
reinterpret1776 as PASS. Normal-profile gates remain NOT_RUN.
Offline remediation moves256-byte buffer/SHA context/32-byte digest into one
408-byte profile2 BSS workspace with synchronous reentry rejection. Only two
firmware sources change,101 remain pinned unchanged; J/K historical source
manifests and retained installed BIN stay intact. M physical runner/transaction,
resource observer/windows/thresholds unchanged. Initial paired gates pass:
compiled mount frames848->272 (checkPayloads/validate inline into begin),
static RAM+408, linked flash+16, noinit0 delta. Compiler frames are not physical
margin. Host validation includes a reporting-only H parser correction for
linked/proven checkPayloads inlining; no safety bound or firmware byte changes.
Final223 checks PASS (220+3), no failures/errors/skips; exact H resource CLI and
source/Core/package
pins and installed J rehash PASS. Clean source freeze9f86a73d999168d052e2037a4fcb999cfe9a2e2c:
one new instrumented BIN411152 B, SHA256
e1852e56d99801b694f37d235b08a201188cf36d5a25f3f6f59d059a129bc27e,
rounded0x065000, margins634880/1683456 B. Final clean resource RAM40732->41140,
flash406991->407007, noinit56 unchanged. Ignored local BIN/ELF; receipt commit
does not rebuild it. Successor physical NOT_RUN; future packet PRINT ONLY.
No successor physical acceptance or writer rebind. All six agent counters ZERO.
STOP after offline receipt/CI; no flash/reboot/threshold lowering/merge.

**Previous OFFLINE work — small Phase M compatibility addendum, 7 October 2026:**
[Exact targeted capacity fix and owner diagnostic](M09_PHASE_L_SYNC_HOTFIX.md#small-physical-compatibility-addendum--7-october-2026).
Starting clean d4052a842b0faa5f11184c03375ca0557621d8cd, same branch/PR #42.
Owner no-flash evidence: bounded SYNC/magic/v2 RAM stub/geometry PASS,
raw ROM capacity0x00, post-stub0x16, Begin/DATA0/0; earlier owner readback
unchanged PRE/FS and zero changed bytes. RAW_ROM_FLASH_CAPACITY_GATE =
REJECTED_BY_PHYSICAL_EVIDENCE; POST_STUB_4MIB_CAPACITY_GATE = REQUIRED.
Remove only raw-ROM capacity assertion and refresh its helper hash; keep all
fresh-ROM/magic/pinned-v2/exact stub guards and post-stub0x16 BEFORE Begin.
M runner/SYNC, SingleAttempt transaction, all103 firmware sources and frozen J
bytes unchanged. Host tests/source pins are offline evidence only; physical
resource gate HOLD/NOT_RUN, overall PARTIAL/HOLD, both normal gates NOT_RUN.
Offline218 checks PASS, zero failures/errors/skips; five bounded SYNC cases and
full416 fault matrix PASS. Package/source/candidate pins PASS, default audit
opens no port. Exact-head CI receipt stays in existing PR #42 after push.
All six agent device counters ZERO. STOP; no flash/reboot/merge; PR #42 Draft.

**Previous OFFLINE work — Mission 9 Phase M, 6 October 2026:**
[Bounded no-reset ROM SYNC hotfix](M09_PHASE_L_SYNC_HOTFIX.md) supersedes L's
single-SYNC assumption, REJECTED_BY_PHYSICAL_EVIDENCE. Owner's later L attempt
stopped before Begin with conservative UNKNOWN; immediate independent 4 MiB
readback proved PRE==POST, zero changed bytes, protected/FS/tail preserved,
candidate absent and no app boot before readback. RX purge alone did not fix
acquisition. Stock no-reset connect(attempts=1) passed with no stub/flash;
pinned 5.4.0 source allows five inner SYNC exchanges per outer attempt.
Current runner changes acquisition only: maximum five requests on one handle,
one global 5 s/16384-byte/256-read budget, 50 ms delay between retryable failures,
fresh buffered state per attempt, complete eight-reply stub classification plus
consistency check. No stock connect, reset, post-open DTR/RTS, reopen/reconnect.
After Begin zero retry; K executor and all103 firmware files/candidate unchanged.
M gates PASS/OFFLINE (fake serial/clock and local artifact checks); resource
physical HOLD/NOT_RUN, overall PARTIAL/HOLD, both normal gates NOT_RUN.
All six M device counters ZERO; no new physical operation/installation proof.
Owner diagnostic facts are attributed, no private dumps/digests published.
STOP after M; existing PR #42 Draft/open/unmerged. L receipt below is history.

**Previous OFFLINE work — Mission 9 Phase L, 6 October 2026:**
[Single-attempt physical session runner](M09_SINGLE_ATTEMPT_PHYSICAL_RUNNER.md)
adds explicit strict COM literal, approved local Python 3.12.x identity and
exact package/source checks before open. Default audits only. Future execution
requires every latch and separate exact-operation GO. Serial is created closed,
DTR/RTS stored false before open and never assigned after open; Windows DCB
disables both. API/source/spy evidence is not electrical glitch/isolation proof:
isolated controls and owner manual GPIO0/RST remain physical prerequisites.
One bounded reset-free SYNC accepts fresh ROM only; unchanged K transport checks
exact magic/4 MiB and uploads pinned v2 only, then owns one Begin/101 packets/
no-reboot Finish/MD5. No flash retry/reconnect/reset/rollback/PRE/POST automation.
Any post-open uncertainty stops with safe status and no cleanup Finish.
All 103 firmware files and exact frozen 411136-byte J BIN/hash unchanged.
L source/port-control/integration gates PASS/OFFLINE (fake serial only).
Resource physical HOLD/NOT_RUN, overall PARTIAL/HOLD; both normal gates NOT_RUN.
All six physical-operation counters ZERO. No device contact or installation;
future command PRINT ONLY. STOP after L; existing Draft PR #42 unmerged.
The Phase K statement below about missing acquisition is dated K history;
the separate L runner supplies it without changing the K executor.

**Previous OFFLINE work — Mission 9 Phase K, 6 October 2026:**
[Scoped acceptance policy and single-attempt executor qualification](M09_RESOURCE_POLICY_AND_EXECUTOR_QUALIFICATION.md)
preserves all103 tracked firmware files and exact frozen J **411136 B** BIN,
SHA-256 `2ce2fa8da00de5c60109d0675c7bcf58ab41df2138d913b607fde25994e5a835`;
no local rebuild/substitution. Scope **M9_PROFILE2_INSTRUMENTED_MOUNT_PROBE_ONLY**:
free heap>=20480 B, largest block>=16384 B, Core fragmentation<=25%,
continuation free>=2048 B in both mount/runtime windows. Explicit rationale and
additional reserves are in the new report; these are new engineering acceptance
criteria, not universal floors or transferred M8/P1/product authority.
Strict local JSON/owner-fact evaluator fails missing/invalid/rejected/nonadvancing
measurements, failed mount/no-write/telemetry, reboot or display corruption.
Pinned esptool5.4.0 whole-write SerialException retry and FatalError packet retries
make stock write-flash unsuitable. One-shot adapter uses direct check_command:
1 Begin/101 unique4096-byte packets/1 Finish, no flash retry/reconnect/reset.
CLI audits/prints only; future adapter needs an already qualified fresh ROM
session and separate exact-operation GO. No physical serial acquisition wrapper.
Resource-policy/executor/frozen-identity gates **PASS/OFFLINE**; actual resource
physical gate **HOLD / NOT_RUN**, overall physical **PARTIAL / HOLD**, both normal
gates **NOT_RUN**. Physical thresholds defined only for this exact probe; actual
measurements pending. Six K device counters **0**, PR42 Draft/open/unmerged.
STOP after K; no current-unit flash/reboot/modification, activation or merge.
Original J/I and older dated records below remain exact history.

**Latest OFFLINE work — Mission 9 Phase J, 6 October 2026:**
[Separate instrumented profile-2 observer](M09_MOUNT_PROBE_RESOURCE_INSTRUMENTATION.md)
adds read-only heap/largest-block/fragmentation/continuation-watermark evidence
under explicit `esp12e_m9_4m2m_mount_probe_resources` /
`SHINO_M9_MOUNT_PROBE_RESOURCE_DIAGNOSTICS=1`. Original profile 0/default and
uninstrumented probe semantics pinned unchanged; profile 1 remains blocked.
Two mount/runtime watermark windows; at most one loop-end sample per second,
no runtime reset or HTTP/FS-callback sampler. Cached scalar JSON retains Digest
and uses two prevalidated 768-byte chunks, exact maximum body 1157 B.
Source/Core/regression/paired-build checks PASS offline; clean firmware freeze
`7779248082975472ce5f62edf1613d8288b75b6e`: **411136 B**, SHA-256
`2ce2fa8da00de5c60109d0675c7bcf58ab41df2138d913b607fde25994e5a835`.
Rounded extent **0x065000 / 413696 B**; paired linked flash **+3708 B**,
static RAM **+80 B**, .noinit **0 delta**, largest new frame **944 B**.
All three review budgets PASS; compiler frames are not physical margins.
Candidate remains ignored/local and is not rebuilt by the docs receipt.
Threshold audit:
**PHYSICAL_RESOURCE_THRESHOLD REVIEW_REQUIRED**; M8 observations/media budgets
are not M9 physical floors. **MOUNT_PROBE_PHYSICAL_GATE PARTIAL / HOLD;
MOUNT_PROBE_RESOURCE_PHYSICAL_GATE HOLD / NOT_RUN; both normal-profile gates
NOT_RUN.** Current installed unit remains the owner-reported Phase I H candidate
below. No successor installation, device operation or physical promotion.
All six J device counters **0**; PR #42 Draft/open/unmerged. STOP after J;
no flash/reboot/current-unit modification, normal-profile activation or merge.
Original Phase I receipt and older dated evidence below remain unchanged.

**Latest owner-provided physical state — Mission 9 Phase I, 6 October 2026:**
[Mount-probe physical receipt](M09_MOUNT_PROBE_PHYSICAL_EVIDENCE.md) records the
owner-performed run after H, before this documentation-only pass. Exact H
profile **2** / `esp12e_m9_4m2m_mount_probe` installed: **407440 B**, SHA-256
`ca92cc2f4a8a67f70bd305875bd37be90d0cdff74bf7b338339856407dceef8b`.
Fresh full 4 MiB PRE/POST before boot prove candidate exact at zero and
**0x064000..0x3FFFFF / 3784704 B** PRE-equal, including frozen FS and tail.
RTC already 0/0, no RTC write; powered GPIO0 release/existing RST yielded
`rst cause:2` / `(3,7)` / `v00063790` / `~ld`, no observed COPY path. Four
telemetry cards returned. Authenticated status: autoformat disabled, mounted,
exact **24 files / 181402 payload B**, canonical blank seed, zero blocked writes.
Heap after mount/inventory **36144 B**; sampled minimum initially **29744 B**,
after **180 s** stable/stale/recovery **27808 B**. No observed reboot,
display corruption or FS mutation. Mounted payload hashes do not prove raw FS
image SHA; full raw FS preservation is the separate preboot PRE/POST result.

**MOUNT_PROBE_FS_FUNCTIONAL_GATE, MOUNT_PROBE_RUNTIME_FUNCTIONAL_GATE,
MOUNT_PROBE_APPLICATION_PRESERVATION_GATE,
MOUNT_PROBE_FILESYSTEM_PRESERVATION_GATE and MOUNT_PROBE_NO_FS_WRITE_GATE PASS**
within the supplied run's evidence scope. **MOUNT_PROBE_PHYSICAL_GATE
PARTIAL / HOLD**: physical largest-free-block and continuation-stack margin
not exposed/measured. Do not substitute free heap/compiler frames or remove
Phase H's requirement. **NORMAL_PROFILE_LITTLEFS_MOUNT_GATE NOT_RUN;
NORMAL_PROFILE_RUNTIME_GATE NOT_RUN.** Full normal profile 1 remains blocked;
no P1/M8/Home-LAN/native OTA/full-product promotion.

Next bounded work: separately reviewed offline profile-2 instrumentation only,
preserving FS behavior and all bypasses/writer exclusions; expose free heap,
largest block, fragmentation and continuation-stack free/high-water using
pinned Core `ESP.getHeapStats(...)`, `ESP.getFreeContStack()` and
`ESP.resetFreeContStack()`. Not implemented or physically authorized by I.
Phase I modifies documentation only; firmware/tools/companion/scripts/platform/
workflows unchanged, no local rebuild or unit operation. Six documentation-pass
device counters **0**; PR #42 remains Draft/open/unmerged. **STOP after I;
do not modify/reboot SmallTV, activate normal profile or merge.** Dated H/G/F/E
paragraphs below are preserved history; their then-current installed/NOT_RUN
claims are superseded only by this owner-provided receipt, not rewritten.

**Latest OFFLINE work — Mission 9 Phase H, 6 October 2026:**
[Dedicated read-only LittleFS mount-probe qualification](M09_LITTLEFS_MOUNT_PROBE_QUALIFICATION.md)
**PASS offline**; new explicit `esp12e_m9_4m2m_mount_probe` / profile **2**,
4m2m, Core 3.1.2 / platform 4.2.1. Profile 0 startup/loop unchanged, default
esp12e still 4m3m; profile 1 and unknown profiles compile-blocked. ConfigManager
load/save duplicate mounts and credential migration/writes make the held normal
path unsafe for this probe; profile 2 bypasses ConfigManager/SecureStorage/
EEPROM/STA/OTA/FS writers. Single mount only after autoformat-disable success;
read-only adapter denies mutation and physical prog/erase callbacks. All 24
reviewed files / 181402 payload bytes streamed with 256 B buffer, exact lengths/
SHA-256 and 85-byte canonical blank config. Per-file hashes are not raw FS hash.
Private AP/Digest GET `/api/v1/m9/fs-probe/status`, serial 115200 and existing
RAM telemetry reused; failure does not format/repair/retry/reboot-loop.

Clean source freeze `5f3db19e29398ef6498b08b02de29cae48f9b59a`: LOCAL probe
**407440 B**, SHA-256
`ca92cc2f4a8a67f70bd305875bd37be90d0cdff74bf7b338339856407dceef8b`,
linked flash **403283 B**, static RAM **40652 B +56 B .noinit** (+312 RAM vs
paired baseline), future touched **0x000000..0x063FFF / 409600 B**. Candidate
retained ignored, not installed/published; Stage-1/Stage-2 frozen files unchanged.
**155 local tests PASS**, default/probe application builds and source/link/Core/
image/resource gates PASS; exact-head CI recorded in Draft PR #42.
**MOUNT_PROBE_PHYSICAL_GATE HOLD / NOT_RUN;
NORMAL_PROFILE_LITTLEFS_MOUNT_GATE NOT_RUN;
NORMAL_PROFILE_RUNTIME_GATE NOT_RUN.** Current physical state remains Phase G
below: 399168 B FS-less app plus installed, unmounted LittleFS. Next gate is
separately authorized physical mount-probe qualification, not full normal path.
All six Phase H device-operation counters **0**. **STOP after H; do not touch
SmallTV, flash probe, activate normal profile or merge.** Historical evidence
below remains unchanged; no P1/M8/full-product promotion.

**Latest owner-provided physical state — Mission 9 Phase G, 6 October 2026:**
[Stage-2 physical evidence](M09_STAGE2_PHYSICAL_EVIDENCE.md) records the owner's
completed operation after Phase F and before this documentation-only pass.
Exact frozen LittleFS **2072576 B**, SHA-256
`d7ce9133b34fb5937d5640db81ff863a8f22a3717255c4b23057aea9ed2ef045`,
physically installed at **0x200000..0x3F9FFF**, end exclusive **0x3FA000**.
Full independent physical PRE/POST before first post-Stage2 boot prove lower
**0x000000..0x1FFFFF / 2097152 B** and tail
**0x3FA000..0x3FFFFF / 24576 B** byte-exact to fresh PRE, FS byte-exact to
frozen image. Stage-2 physical write/preservation/RTC transition/boot/runtime/
FS-image and **MISSION9_4M2M_PHYSICAL_LAYOUT_GATE PASS**. Geometry/current
contents proven; all 1 MiB + 1 MiB OTA behavior and continuing tail immutability
are not physically qualified.

Powered RTC 0/0 readbacks, GPIO0 release and existing RST produced
`rst cause:2` / `(3,7)` / `v00061740` / `~ld`, no observed `cp:`. Current
**399168 B FIRST_BOOT_BRIDGE remains FS-less**, PROGRAM_FLASH_ONLY UI /
RAM_ONLY metrics; it has **not mounted, parsed or used the installed LittleFS**.
Normal 240×240 LCD/four dynamic cards, no orientation regression; initial LINK
RETRYING was Windows AP non-association, resolved by manual host reassociation
then CONNECTED without SmallTV reboot/firmware change. **180-second** runtime
and stale/recovery PASS; no observed reboot/loop/corruption. No new Stage-2
heap/block/stack measurement; Phase E heap is historical. TTL remains 6 s.

**NORMAL_PROFILE_LITTLEFS_MOUNT_GATE = NOT_RUN;
NORMAL_PROFILE_RUNTIME_GATE = NOT_RUN.** Next unresolved work is normal-profile
LittleFS mount/use qualification under a separate bounded owner decision.
P1/M8/full-product qualification unchanged; R3 PARTIAL / R10 BLOCKED and native
OTA disabled. Phase G started clean `f92b42deaa87e3df7b6204f1010886a8ed343043`;
PR #42 stays Draft/open/unmerged. Six Markdown files only, no local rebuild or
new device operation; all six Phase G action counters **0**. Private dumps,
digests, backup paths, credentials and identifiers remain unpublished.
**STOP after Phase G; do not touch SmallTV, activate normal profile or merge.**
The Phase F/E and earlier HOLD/NOT_RUN paragraphs below remain correct dated
history; their Stage-2 pending state is superseded by this Phase G record.

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

**Latest owner-provided physical state — Mission 9 Phase E, 5 October:**
[Stage-1 physical evidence](M09_STAGE1_PHYSICAL_EVIDENCE.md) records owner actions
completed before this documentation pass. Frozen **399168 B** Mission 9 FS-less
bridge installed at zero; Stage-1 write, protected PRE/POST preservation,
RTC/existing-RST powered transition, first boot, bounded runtime and FS-less
gates **PASS**. This is the latest reported installed state, superseding older
dated installed-state statements below; no unrelated P1/M8/media/Home-LAN
qualification is promoted. CH340 3.3 V logic, normal USB-C power, reversible
micro-hooks/no solder; known RST/GPIO0/RX/TX/GND, no adapter VCC power.
RTC sentinel retained through existing RST; zero/zero then GPIO0 release while
powered and RST gave `(3,7)` / `v00061740` / `~ld`, no observed COPY path.
Independent full PRE/POST protected equality **0x062000..0x3FFFFF / 3792896 B**
applies before first Stage-1 boot; slack equality and later system-tail
immutability are not claimed. Correct LCD/four real values, protected AP/auth,
180 seconds without observed reboot/corruption and stale/recovery PASS.
Authenticated status: FIRST_BOOT_BRIDGE, 4 MiB, 399168 B app, heap **33072 B**,
PROGRAM_FLASH_ONLY UI / RAM_ONLY metrics, migration/native OTA writers false.
Largest free block/stack high-water unrecorded; ~2 s after Ctrl+C is not TTL:
TTL remains 6 s from last accepted sample. **Stage 2 LittleFS HOLD / NOT
PERFORMED; EBOOT_COLD_START_GATE HOLD.** No private dumps/digests/credentials
published. Phase E started clean `e7163f8012be34d8a57ab55ca4b7d0f8632637a1`,
existing Draft PR #42; documentation only, all device action counts **0**.
**STOP after Phase E; no SmallTV contact, Stage 2 or merge authorized.**
Earlier Phase A–D and physical paragraphs remain dated historical evidence.

**Mission 9 Phase D, 5 October — OFFLINE RTC/eboot neutralization PASS:**
continue existing Draft PR #42 from verified clean
`a702c90c285189eff7ee19ea8f1da8bbc0274fa0`.
[Exact source, deterministic model, PRINT ONLY four-word-operation packet,
powered existing-RST transition and sequence](M09_RTC_EBOOT_NEUTRALIZATION.md).
RTC_MEMORY_ACCESS_GATE / RTC_NEUTRAL_STATE_GATE /
RTC_TO_NORMAL_BOOT_TRANSITION_GATE PASS for pinned source/synthetic models.
Magic `0x60001200` and CRC `0x6000127C` must both read zero before releasing
GPIO0 while powered and using existing RST as EXT_RST. No power-cycle/EN pulse;
Phase C EBOOT_COLD_START_GATE remains HOLD. Owner correction: known header
**RST — GPIO0 — 3V3/VCC — RX — TX — GND**, established reversible micro-hook
ROM download/full 4 MiB reads on this unit. No new photos, soldering or new PCB
access needed. EN/CH_PD not known/exposed; access not required. The existing
RST's physical retained transition remains NOT_RUN, separately approved later.
Frozen candidate 399168 B / SHA `cd99139121fa47fedd6286a185fb16e8fb9e120280ecd75f1c6b41b905e31011`
unchanged, no firmware edit/rebuild. Physical runtime NOT_RUN; physical write
HOLD; DEVICE CONTACTS / SERIAL I/O / RTC WRITES / FLASH WRITES / REBOOTS /
device FILESYSTEM WRITES **0**. **STOP after Phase D.** Prior Phase C/B sections
below are dated history, not authority to follow their cold-power packet.

**Mission 9 Phase C, 5 October — OFFLINE executor qualification HOLD:**
continue existing Draft PR #42 from verified clean
`02b4be4cd4c2e0651d376001c030f1505123adb6`.
[Pinned source audit, local verifier, A–K print-only packet and state machine](M09_PHYSICAL_EXECUTOR_QUALIFICATION.md).
Official esptool 5.4.0 / version-2 stub bounded-range source model PASS;
initial no-reset / one-connect flags do not constrain its internal default-reset
reconnect. EBOOT_COLD_START_GATE HOLD: RTC contents after full power-on are
random, not guaranteed invalid; eboot checks magic/CRC without reset reason.
STAGE1_READBACK_MODEL PASS (synthetic only); PHYSICAL_RUNTIME_GATE NOT_RUN.
Select independent full 4 MiB fresh PRE/POST before any normal boot; protected
`0x062000..0x3FFFFF` must match exactly. Frozen Phase B LOCAL candidate remains
399168 bytes / `cd99139121fa47fedd6286a185fb16e8fb9e120280ecd75f1c6b41b905e31011`.
No `firmware/**` edits or local candidate rebuild; default/opt-in gates retained.
**Physical write HOLD; all device/serial/write/reboot/FS operation counts 0.**
No transition below is authority to touch the SmallTV; STOP after Phase C.

**Mission 9 Phase B, 5 October — OFFLINE first-migration design:** existing
Draft PR #42 continues from verified clean `1c39e2ac791145be9ef79dc6d98fd70526614d7f`.
[Protocol, FS-less source audit, command packet, power-loss and MASTER gates](M09_FIRST_PHYSICAL_MIGRATION.md).
Application-only at zero is selected before separately gated future FS
provisioning. Stage 1 changes the linker without physically reclaiming
`0x100000..0x1FFFFF`; no filesystem is needed or mounted by audited profile 0.
Default 4m3m, disabled native/FS writers and private MASTER custody preserved.
Fresh clean-head candidate and exact-head CI are recorded in PR #42; public
foundation build is distinct from the private P1/M8/P0 graphs. Firmware source
unchanged. **Physical write HOLD; device contacts/writes 0.** Esptool's internal
whole-write retry behavior needs a separate executor gate before future approval.
Prior physical paragraphs below remain dated provenance, not new device reads.

**Latest offline review, 2 October — PREPARED / NOT EXECUTED:** owner review
#5949087791 authorizes offline investigation only. Retained approved BIN/ELF,
P1 shadow, HomeLan loop, pinned parser/first Digest challenge and original
private GET client inspected without rebuild or device contact. Original
TimeoutError phase cannot be recovered: client used one socket timeout and
recorded neither successful connect nor send. Corrected phase-instrumented
single-transaction client and private default-deny wrapper pass 10 public + 2
private simulated-socket tests; **no proposed live diagnostic executed**.
[Finding, hashes, evidence limits and exact next test](home-lan/P1_STATUS_DIAGNOSTIC_REVIEW.md).
LINK remains owner-stopped/autostart owner-disabled; no changes made. P1 and
Freebox gate HOLD. STOP for fresh explicit authorization before any device I/O.

**Latest bounded diagnostic, 2 October 11:13 CEST — STOP / HOLD:** owner comment
#5948806085 authorizes one status GET only, with at most one 401/authenticated-GET
pair. Local checks confirm LINK is absent and Windows already on the protected
WPA2/CCMP SHINO AP with its subnet route. Initial unauthenticated GET attempt
times out in 3015 ms before any HTTP status/challenge; no authenticated GET,
retry, other endpoint or write. Boot/reset/heap/block/continuation/Wi-Fi/failure
counters remain unavailable. Exact transport timeout phase and reset cause are
unresolved. Owner manually terminated LINK and disabled autostart before this
diagnostic; neither was modified/restarted. The LINK-paused state below is dated
provenance. Receipt retained locally at
`research-local/p1-one-status-comment-5948806085.json`. Further device action
needs fresh owner authorization; three-minute functional baseline remains HOLD.

**LATEST physical state, 2 October — P1 UPLOAD ACK / POST-BOOT HOLD:**
one separately owner-authorized genuine OEM `/update` installation of the exact
464544-byte P1 SHA `31e3f225744bd806df3302dbf3355770a313f8b71f65b33fd6e2f431449b0be5`
from starting PR #41 `e9cca6b` returned HTTP 200 / complete
`Update Success! Rebooting` in 7969 ms. No rebuild/substitution/retry.
Protected AP association/TCP access observed; first authenticated GET reset before
new application identity/resources. Owner reports SHINO cards visible but stale
and repeated ~10-second reboots. Mandatory hard STOP applied; no baseline,
additional device reads after that report, firmware retry/rollback or provisioning.
Existing LINK is **PAUSED** to halt automatic telemetry POSTs; same process and
configuration/credentials/autostart retained. After ~30 seconds owner reports
stable display with stale cards. Cause remains undetermined; network-load
association is a clue, not proven watchdog/heap/parser attribution. No new boot
token, runtime size/geometry or memory/stack/recovery response recovered.
**PRE-PROVISIONING HOLD; no Freebox-Shino credential-write approval requested.**
Further device action requires a new bounded owner decision. R3 PARTIAL / R10
BLOCKED. [Actual P1 installation and hard-stop evidence](home-lan/P1_INSTALLATION_2026-10-02.md).
The OEM/M8-running paragraphs below are dated prior-state provenance, superseded
by this latest P1 operation and hard stop.

**Latest physical state, 2 October 09:23 CEST — OEM BOOT IDENTITY PASS / STOP:**
one separately authorized corrected M8→exact OEM upload at PR #41 `0bae281`
returned HTTP 200 / complete `staged` acknowledgement in 10765 ms. LINK was
temporarily suspended across the final fresh Digest challenge/upload and resumed
as the same single process; configuration, credentials and autostart are unchanged.
Read-only MAC rediscovery and live `/v.json` verify SmallTV-Ultra / Ultra-V9.0.44
on the home LAN. Owner confirms OEM display normal and correctly oriented,
without corruption. Current firmware is **OEM**;
M8 observations below are dated prior-state provenance, not the current boot.
P1 NOT INSTALLED / DEVICE NOT RUN; no Hop 2, retry or household credential write.
The newest single-hop stop supersedes older two-hop consent. No further actual
upload without fresh explicit owner authorization. R3 PARTIAL / R10 BLOCKED.
[Actual receipt, fresh preflight and LINK preservation](home-lan/OEM_SINGLE_HOP_2026-10-02.md).

The earlier installation/correction/preparation paragraphs below retain their
original scope and historical results; their M8-running/authorization-pending
statements are superseded by the latest physical state above.

**2 October bounded upload-client correction — OFFLINE READY / physical HOLD:**
review #5942560005 addressed using the actual retained private uploader and
installed-M8/Core source. Original HTTPError code/body are unrecoverable; exact
multipart and private Digest calculation match the installed contract offline.
Original client preserved; corrected private method delegates to tested bounded
one-attempt transport with error status/safe headers/body/timing and exclusive
receipt. Ten loopback tests pass for shared transport and the same ten through
the actual private method; no device contact or P1 rebuild. Shared nonce rotation
is a supported mechanism, not a proven cause. [Precise evidence, client and new
single-Hop-1 review plan](home-lan/OEM_UPLOAD_CLIENT_INVESTIGATION.md).
Await new owner authorization before any POST; M8 remains running.

**2 October controlled installation attempt — HOLD:** owner explicitly authorized
the exact M8→OEM and OEM→P1 hashes from starting PR #41 HEAD `d63b58b`.
Immediate hashes/pairing/current-M8/LINK/resource/recovery/LCD preflight passed.
One OEM-return POST raised an HTTP error without a staged acknowledgement; the
client did not preserve the code/body. No retry or Hop 2 was performed. Subsequent
GETs show responsive M8 446944 B, unchanged boot 2962927510, fresh telemetry,
heap/block/continuation 18584/16672/1728 B, zero failure counters and enabled exact
OEM capability. Owner confirms normal LCD after the attempt. OTA staging writes
are unknown; no installation reboot observed. P1 remains NOT INSTALLED / DEVICE
NOT RUN; no persistent Wi-Fi write or credential confirmation yet. Preserve the
responsive application and single-attempt stop; do not automatically retry or
rollback. [Actual device attempt and evidence limits](home-lan/DEVICE_INSTALLATION_2026-10-02.md).
R3 PARTIAL / R10 BLOCKED. The preparation paragraphs below are prior-state evidence.

**2 October owner preparation gate:** existing PR #41 continues from accepted
`ce718f0`. Actual private active P0+P1 candidate is 464544 B, SHA-256
`31e3f225744bd806df3302dbf3355770a313f8b71f65b33fd6e2f431449b0be5`;
matching retained credentials/media identity and OEM/V2.1/M8 rollback are locally
verified outside Git. New owner profile adds read-only numeric runtime/LCD counters
to existing authenticated status, without exposing qualification write controls
on LAN. [Exact image, lifetime review, abort limits and physical sequence](home-lan/OWNER_INSTALL_GATE.md).
Fresh GET-only current-M8 preflight: 446944 B, boot 2962927510, actual 4 MiB,
exact OEM capability enabled, native OTA absent. No upload/reboot/network switch or
persistent credential write. **STOP at new exact-image/chain owner approval.**
Installation consent must name both M8→OEM and OEM→exact P1 hops; first credential
write needs a later separate confirmation after boot/display/AP/telemetry checks.
P1 physical qualification remains NOT RUN, R3 PARTIAL/R10 BLOCKED unchanged.

**P1 offline implementation update:** owner requires persistent Wi-Fi, configured
once locally and retained across normal failures/boots. Follow-on branch
`codex/shino-tv-p1-home-lan` starts from verified PR #40 `a3d9fdb`; older Home
Wi-Fi "unimplemented" rows below are prior-state provenance. Opt-in active
FirstBoot P1 now loads reviewed SDK parameters (`0x3FD000–0x400000`), writes only
on Digest/AP/one-use-intent protected Change/Forget with readback, reconnects and
retains secure AP fallback. LINK supports live local IP retargeting. Three native
guarded graphs compile; P1 versus P0 adds 11,136 BIN / 1,180 static DRAM bytes.
183 shared assertions, 34 target-handler loopback checks and 33 real signed
receiver/scene cases at each AP/LAN authority pass locally. See
[P1 contract, exact local password procedure, resource evidence and HOLD gates](home-lan/README.md).
**P1 device/release remains HOLD:** persistence under real power loss, native
heap/block/stack, radio/DHCP and OEM return after saved-config writes NOT RUN.
No owner-device contact/install/provision/migration; current M8 remains installed.
Recheck final branch SHA and exact-head CI; host SDK/radio models are not DEVICE PASS.

**V2.2 implementation update (offline only):** PR #40 now has exclusive scenes,
160px integer artwork (128px alternative also built/tested), clipped title/artist
marquees, explicit provider leases and a disabled-by-default paused timeout seam.
33 actual native-receiver host cases pass at both sizes; the final linked delta
versus the previous PR #40 graph is +1,080 static DRAM / +5,456 BIN bytes.
See [current implementation and eight 240×240 previews](artwork-pilot/README.md)
and active roadmap P0. The older mixed-screen row below is retained prior-proof
provenance, superseded for current UI implementation. Physical UI NOT RUN;
installed M8 candidate and PR #39 remain unchanged. Recheck exact-head CI.

## Latest engineering update (supersedes older PR #40 pilot snapshot below)

> **LATEST VERIFIED P0 STATUS — 1 October 2026, PR #40 `332eaa48580de60eba06faaa6dbb67c301b2b1be`: OFFLINE GO / PHYSICAL LCD HOLD.** The mutually exclusive `IDLE`, `PLAYING`, `PAUSED`, `NO ARTWORK`, `OFFLINE` C++ scene engine, 160×160 5× cover upscale and bounded title/artist scrolling are implemented. Actual eight independently produced 240×240 renderer previews. 33 host scenarios pass for both 128 and 160px artwork, ASan/UBSan pass, exact-head push and PR CI each 12/12. Public paired build delta against preceding PR #40 pilot: **+5,456 padded BIN bytes, +1,080 static DRAM bytes, 448-byte row buffer, zero observed renderer dynamic heap; Receiver Begin compiler frame +64 B.** No live native LCD timing/heap/stack has been measured, providers for clock and weather do not exist yet, and no device flash/reboot has occurred. The IDLE concept-city background is not a requirement to store or render large native art without resource proof. `GPU TEMP` bar remains neutral until a documented scale is approved. The next implementation priority is **P1 secure normal-home-LAN STA with protected private-AP fallback**, followed by P2 integrated signed SHINO→SHINO OTA. Do not conflate OFFLINE GO with physical approval.

## A. Quick state — differentiate firmware, experiments and future goals

| Axis | Verified current engineering evidence | Gap / prohibition |
| --- | --- | --- |
| Single physical Ultra | Owner-approved Mission 8 private candidate **446,944 B**, SHA-256 `269fcf2be7e61b4f581f892f36c519cca5ebf1ef41759d9923d9df90aad682fa` installed through verified OEM round-trip; private AP `192.168.4.1`; four PC metrics update via SHINO // LINK Windows tray. | Not yet home-router STA. No hardware recovery if no application boots. Do not expose private material. |
| Mission 8 / PR #39 | Frozen validated `9fce7137f9fadd83678887442bf91cf60ea86b2e`, Draft. Actual current candidate 32×32 RGB565LE Commit in 3.672 s post-Begin and replacement in 4.016 s; image Abort and signed wrong-CRC Gate2 rejection PASS; actual ArduinoJson temporary peak **1,984/2,048 B**; persistent image **2,048 B**. Actual crypto StackThunk secondary max **2,708/6,200 B**; no observed reset/canary/allocation failure in reported windows. | Receiver owns **inert RAM**; those tests do not show physical LCD artwork. Overall M8 HOLD for optional 48 and separately 6-second strict long-term telemetry (historical recovered 7.266 s gap). R3 PARTIAL; R10 BLOCKED. |
| Optional 48×48 | Old candidate managed one nine-tile transfer; optimized current candidate has not executed it. Current conservative projection **10.142 s against unchanged 8 s**; replacement not proven on a retained 4,608 B image state. | Do not make 48 mandatory for first music product; no blind 48 hardware attempt or deadline weakening. |
| Artwork LCD / PR #40 | `codex/shino-tv-32-artwork-display-pilot`, based on PR #39. Offline actual native ST7789/receiver renderer passes 16 host scenarios including signed receiver and cancellation; scanline **192 B**; cover enlarged **32→96 px**; **+520 B static DRAM** and **+96 B Receiver Begin frame**; no added renderer heap/full-screen framebuffer. New renderer runs cooperatively after HTTP owner with `networkReady` guard. Latest report says exact-head 12/12 in both CI runs; recheck latest SHA because subsequent docs commits may have occurred. | PR #40's current **music + all 4 cards in one scene** is a functional proof, explicitly REJECTED as target UX. The pilot binaries are guarded/offline and not installable owner builds. Physical LCD cover/latency/high-water **NOT RUN**. |
| Native OTA | `GET /api/v1/bridge/ota/capabilities` is READ-ONLY; reports `native_ota_writer_compiled=false`, `native_ota_upload_route_registered=false`. Signed-SHINO / signed+exact-OEM contracts, payload geometry, one-use intent, precommit gates and Core 3.1.2 review exist as host/compile-only research. | Current field sequence is SHINO→pinned OEM V9.0.44→SHINO. Native SHINO→SHINO update is NOT shipped; no native uploader route and no independent brick recovery. Do not claim otherwise. |
| Home Wi-Fi | Active FS-less FirstBoot bridge uses private SHINO AP, while OEM can use household STA. | Home-STA onboarding/secure credential storage/recovery/AP fallback and authenticated LAN API are a high-priority **unimplemented** deliverable. |
| Music PC side | SHINO // LINK V0.1 live telemetry; V0.2 GSMTC monitor and V0.3–V0.4 preview experimental PC-side. | Permanent authenticated production cover sender not yet connected to actual display/scene engine. |
| Time and weather | Product visual reference shows clock, date, city/weather. | Actual wall-clock synchronization, freshness/timezone/DST, provider/city/caching and offline fallback require implementation. Concept data are illustrative, never live measurements. |

## B. Requirement keywords: MUST / MUST NOT / OPEN

**MUST:** all individual LCD views exactly `240×240` (1:1); square cover without stretch; IDLE screen uses prominent time (only when genuinely synced), optional fresh/cached weather and FOUR metric cards simultaneously in a 2×2 layout; adaptive bar colours; received media retained securely in RAM, no partial tiles painted; PLAYING screen only art/title/artist/progress/status (no metric cards); PAUSED/music-without-cover likewise never shows metric cards. Keep accepting metric POSTs invisibly during music. Long title scrolling must be slow, bounded, horizontally clipped with an initial pause, endpoint dwell/loop and reset on track change. Use bounded font glyph / UTF-8 fallback; do not shrink titles to fit.

**MUST NOT:** reuse PR #40 mixed screen as product approval; display clock if not synced, stale telemetry as fresh, fake weather, empty GPU temp as 0; add mini-graphs above metrics; enlarge 6 s telemetry TTL or 8 s signed-media transaction deadline merely to pass; share production credentials/signing keys; merge/flash by inference; promise that OEM app BIN is full-flash backup or can rescue no-boot failure; interpret source/CI builds as device tests.

**OPEN decisions, present to owner only when needed:** precise PAUSED→IDLE timeout or immediate transition; weather provider/city (Lezignan displayed as *concept example*, not approved hardcoded setting), normalization of GPU temperature and RAM bars, exact marquee speed/dwell and Unicode fallback, brightness/night mode, clock sync PC vs NTP once STA exists, home STA vs AP fallback timeout, any manual scene override.

## C. State machine and visibility (product intent)

| Event or state | Visible scene | 4 metrics painted? | Receiver/clock consideration |
| --- | --- | --- | --- |
| Boot before valid time and PC contact | explicit SHINO waiting/offline | Unknown cards only if meaningful | No made-up clock; AP or STA recovery accessible |
| NO_SESSION / STOPPED with validated time | IDLE | YES, all four as valid/stale/unknown | Grace/debounce owner choice |
| PLAYING + committed 32px cover | PLAYING | NO | Square cover and clipped title, progress if reliable |
| PLAYING without artwork, or incoming valid Begin before Commit | NO ARTWORK / music fallback | NO | Existing receiver intentionally drops prior cover at accepted Begin; invalid metadata leaves existing image unchanged. Never show partially staged cover. |
| PAUSED | PAUSED artwork/placeholder | NO | Position freezes; exact timeout to IDLE is OPEN |
| Playback ended / source lost after bounded grace | IDLE / offline | YES if known, otherwise unknown | Keep time freshness independent |
| Music while telemetry POST continues | stays music | NO | Still accept/age all numeric values, no false firmware network change |
| No PC / router / Internet | clock if genuinely synchronized, else offline | Only actual safe last-valid state with explicit age | Weather cache age shown or hidden if unknown |

## D. Layout/source asset contract

`docs/design-reference/` contains **four canonical vector references** with root `width="240" height="240" viewBox="0 0 240 240"` plus a clipped marquee state. Those are mood/position **targets**, not production binary pixel evidence. Render with an SVG rasterizer at EXACT 240×240 to create reference PNGs and assert dimensions; then produce independent actual C++ software-LCD previews from the pinned 6×8 GFX font and ST7789 driver. Compare readability and geometry. No rectangular 16:9 panels with "240×240" labels. Source high-level original ChatGPT illustrations were 1254×1254 concepts, not proof of native 240px legibility.

Preferred layout baseline, to be reviewed with physical readability:
- IDLE top city/clock/weather region `x=4..235, y=4..117`. Clock large; date/weather read only if valid. Four cards: `(8,124,110,50), (122,124,110,50), (8,181,110,50), (122,181,110,50)`. No top-line curves. CPU 37.5% must display **yellow** according to the owner's 20–50 threshold; older imagery using green at 37% is illustrative and wrong.
- PLAYING/PAUSED/NO ARTWORK: album/placeholder **square** `(41,10,158,158)`; mode/title/artist/status and optional elapsed/total in remaining `y=170..236`. Minimum rendered metadata must be verified with real GFX font, clipped title line and bounded slow marquee. Small 32×32 RGB565 cover may enlarge by nearest-neighbour without new 240×240 frame allocation. No 4 cards anywhere in music scene.
- Proposed bar palette is GREEN [0,20), YELLOW [20,50), DARK_ORANGE [50,80), BURGUNDY [80,100]; exact inclusive boundaries and hysteresis must be consistent between native and PC preview. RAM percent = used/valid total; GPU temp requires an *explicit reviewed reference scale* before applying 0–100 colour thresholds; until agreed label and treat as informational rather than invented percent.

## E. Current native contracts that future edits must preserve

- Pinned ESP8266 Arduino Core 3.1.2 and exact private OEM application hash; network ingress bounds before body, ECDSA P256 on isolated 6,200 B StackThunk, transaction replay/ownership, signature and Content-Digest/Gate2 CRC/SHA validation. No new generic FS/updater surface.
- M8 RAM receiver `DisplaySink` moves a complete staging image only after signed Commit. Legacy source intentionally releases previous committed image on valid Begin; ensure mode fallback matches that contract or separately review an ownership/memory-safe redesign. Renderer borrows image during one cooperative main-loop slice only; cannot hold pointer across owner mutation; no LCD draw inside ingress callback. Pilot 192 B line buffer, 2,048 B temporary metadata arena, zero renderer dynamic heap.
- Preserve numeric schema and normal LINK sender cadence (~2 s), **six-second freshness TTL**; current qualified 32 transfer/replace and OEM recovery. Distinguish historical PC Digest observer failures from native server failures; one 7.266 s self-recovered sender gap remains strict-continuity HOLD.
- Four metrics always exist in state/backend, but paint them ONLY in IDLE. Source `firmware/include/display/ArtworkPilot.h`, `experiments/artwork_pilot/native/ArtworkAdapter.inc`, `firmware/src/boot/FirstBootBridge.cpp`, `firmware/src/boot/FslessMetrics.cpp`, actual display manager and `companion/shino_link.py` must be inspected before edits.
- Source docs: `docs/artwork-pilot/README.md` for as-built offline mixed pilot (not final UX), `docs/V08_MISSION_8_GATE.md` for owner physical proof, `docs/V21_NATIVE_OTA_MANAGER_SAFETY_GATE.md` for OTA barriers, `docs/V21_WIFI_ONLY_RETURN_CHAIN_AUDIT.md` for application-only OEM return.

## F. Delivery dependencies and tests (the roadmap order)

1. **P0 UI:** restructure PR #40's tested renderer into mutually exclusive scenes; marquee; square scene reference proof; deterministic host tests for new track, pause, unavailable cover, Abort/expiry, metadata rejection, stale LINK, missing clock/weather, long UTF-8 names, no mixed card painting. Before physical installation independently measure linked BIN/DRAM/stack and rendering slices. Keep PR #39 untouched.
2. **P1 normal LAN:** audit active AP-only FirstBoot, explicit secure STA onboarding (no stock FS autoformat/unsafe EEPROM shortcut), AP fallback and no-lockout transitions, DHCP/address discovery, PC target updates, Digest/origin/host/auth review on both interfaces, tests for router loss and reconnection. Avoid assumptions that `192.168.4.1` can be globally replaced. No routine device write without approved exact owner build.
3. **P2 genuine signed native OTA:** integrate reviewed bound/one-use privileged request before unbounded POST body, stream signed SHINO to staging, pinned trusted owner public key, precise image/layout/transport length, safe Updater semantics and error/power interruption analysis; preserve separate **signed AND pinned raw OEM** return. Core's global signature mode can skip legacy OEM MD5 check, so do not simply enable `installSignature` alongside old OEM route. No claimed resume/atomic guarantee absent evidence. An OEM-assisted one-time bootstrap of self-updater might still be needed.
4. **P3 physical platform gate:** agree scope, verify exact local candidate hashes/boot/recovery and owner LCD, obtain fresh approval for any firmware change, test STA+AP recovery and safe native OTA with actually measured heap/block/stack. Single device with NO UART rescue: stop on regressions.
5. **P4 music end-to-end:** GSMTC input opt-in, metadata bounded, cover change only, PC-crop to 32×32 RGB565LE, signed private media sender separate from numeric telemetry; verify actual LCD art and marquee plus playback transitions. Unsupported players and no cover get deterministic fallback, never promises Spotify direct without review.
6. **P5 clock/weather:** authenticated PC time first or reviewed NTP on STA, timezone/DST/age, configurable weather city/provider freshness cache, independent-power caveat (USB PC off may remove power), privacy/brightness/night controls.
7. **P6 optional:** 48×48 if demonstrated timing and same-state 4,608 B retained image memory; longer strict telemetry reliability; R3 freshness persistence and R10 production trust provisioning as release gates; future widgets.

## G. Agent execution protocol / evidence ledger

- Before coding, retrieve exact PR #40 current HEAD and compare to PR #39 baseline. Never overwrite a newer concurrent Codex commit; fast-forward or stop and reconcile. This documentation commit may have moved the head beyond the last functional CI. Re-run CI on the actual final head.
- Choose one bounded milestone and output real changed files, tests, resource delta and visual preview. Do not restart multi-day Missions 1–8 or propose yet another audit as a deliverable when code can be implemented offline.
- Label each result one of: SOURCE-INSPECTED, HOST-PASS, CI-PASS (with SHA), DEVICE-PASS (with boot/PID/evidence), EXPERIMENTAL, HOLD, BLOCKED, NOT-RUN. Do not promote across categories.
- An offline design or simulator never authorizes field OTA. Preserve all owner-private keys/binaries outside Git, exact hashed factory return, no automatic merge, no production sender/OTA activation, no unsafe debugging endpoints.
- A complete handoff states: exact head/branch and CI, what changed, what is installed (if physically known), image dimensions, measured FLASH/DRAM/heap/stack if relevant, tests, known deficiencies, next bounded action, explicit owner decisions still needed.

## H. Canonical pointers / historical record integrity

- `docs/ROADMAP.md`: current product contract + complete unabridged 28 September historical roadmap.
- `docs/design-reference/README.md`: mockup files and coordinates.
- PR #20 (`feature/v21-native-ota-gated`): OTA safety exploration only, no signed writer.
- PR #21–26: Windows companion, media experiments and initial scene plans.
- PR #27–39: security, bounded HTTP, physically proven M8 32 receiver.
- PR #40: offline LCD artwork pilot (as-built mixed screen, to be refactored).
- `docs/artwork-pilot/README.md`: exact current renderer, 16 scenarios/33,737 host checks, 192 B scanline, +520 B static RAM.
- `docs/V08_MISSION_8_GATE.md` and `docs/V08_MISSION_8R_STACK_REMEDIATION.md`: M8 physical measurements and conditional blockers.
- `docs/V21_NATIVE_OTA_MANAGER_SAFETY_GATE.md`: read-only status, signer/Updater conflict and unshipped writer.
- `docs/ONE_DEVICE_WIFI_PATH.md` and `docs/V21_WIFI_ONLY_RETURN_CHAIN_AUDIT.md`: historically observed OEM path, not full-flash backup.

If requirements collide, preserve the highest-authority newer owner instruction, explicitly document the conflict, and ask only for the essential missing owner choice.
