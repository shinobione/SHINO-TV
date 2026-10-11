# SHINO // TV — B3 physical READ-ONLY PASS; OTA readiness gate (2026-10-11)

**Device qualification: PASS for the recorded read-only workload; OTA installation: HOLD / NOT RUN.** This report records owner-supplied physical output and a separate inspection of the existing source at PR #47, not an agent-executed test. [Draft PR #47](https://github.com/shinobione/SHINO-TV/pull/47) remains open and unmerged.

## 1. Frozen identities and scope

- Actually installed owner-private **B3**, application **407,552 bytes**, SHA-256 `e1d03b44ab3bd0b3693285ba6c4033de8a2925c55f2e86a3924185d779eb0042`, build ID `6c2d07928b341ad0097f3ffb68f14bd6bde010000c9ee9c7dd794af2814ac096`, source commit of installed B3 packet **`26e1ace98dcd4713c4a227c3847bc4b5cf74dee5`**.
- Windows B3-paced qualifier/diagnostics: PR #47 commit **`ce57c1399c13899dc58429cb8bfebb7bdbef6b36`**; this newer Git head is **not a newly installed firmware image**.
- Earlier independent owner PRE/POST 4MiB comparison reported application payload exact and `0x064000..0x3fffff` unchanged, then successful B3 cold boot / four cards / SHINO LINK.
- Owner-only receipt (retained ignored/local; do not upload credentials, BIN, or the receipt itself): `research-local/m9-owner/B3-readonly-coordinated-20261011-152306-88765fa45c41486890c8312fab32b842.json`.

## 2. Physical qualification evidence received

Owner's PowerShell output reports **`PHYSICAL_READONLY_QUALIFICATION_PASS`**, exit code **0**:

| Property | Owner-observed value | Scope |
| --- | ---: | --- |
| Cycles completed | 30 / 30 | Read-only coordinated qualification, paced B3 |
| HTTP GET outcomes | 90 `http_200`; no recorded failures | 3 logical endpoints/cycle |
| Heap minimum | 29,560 B | Floor 20,480 B; separate OTA admission heap floor 25,600 B |
| Largest free block minimum | 28,152 B | Floor 16,384 B |
| Continuation stack minimum | **2,272 B** | Floor 2,048 B; **224 B margin** |
| Maximum fragmentation | 6% | Ceiling 25% |
| Metrics freshness | true at checked GETs | LINK + HTTP coexistence in this run |
| Boot stability | true | Boot ID did not change within the checks |
| LittleFS check | `fs_hash_inventory_verified=true` | Reported device status + qualifier; not a fresh raw-flash read |
| Writes / reboots by this qualification | 0 / 0 | Client READ-ONLY test |

The diagnostic recorded 90 HTTP 200 outcomes and retains up to the last 64 timings. Sampled GET time under the lock was below the B3-paced 1,000 ms ceiling, with the exposed retained values typically about 78–157 ms and observed lock waits up to 109 ms. These measurements do **not** independently prove every radio/firmware instantaneous stack peak.

Historical comparison: the old burst qualifier stopped at **cycle 22** with `LINK_METRICS_NOT_FRESH`; this new, paced run completed all 30 cycles. The scheduling change demonstrably succeeded in this instance. The exact causal contribution of prior Digest contention to the earlier failure remains **not proven**. Earlier 203 s B3 capture reported stack 2,288 B, heap 27,696 B, block 27,120 B, fragmentation 10% and does not replace the new result.

**Verdict:** `B3_PHYSICAL_READONLY_30_CYCLE_GATE=PASS`; **not** `OTA_TRANSACTION_GATE=PASS`. Never lower or reset the 2,048 B floor to obtain apparent acceptance.

## 3. Offline source inspection: actual installed application OTA path

Source inspected at the **installed B3 source commit** `26e1ace` and unchanged firmware paths in `ce57c139`, especially:
- `ota/firmware/Normal.cpp` (`route`, `beforeBody`, `upload`, `uploadHealthy`, `identity`);
- `ota/firmware/ShinoHttpOta.h` (`Transfer::begin/add/finish/abort/read/stagedImage/segments`);
- `companion/shino_update.py` (`inspect`, `check_status`, `install`, `Transport.upload`);
- `companion/shino_coordinated_qualify.py` / `shino_digest_coord.py` (only GET pacing/telemetry coexistence).

**Transport/authentication.** Actual normal-profile upload is `POST /api/v1/update` on the protected private AP with a build-specific SHA-256 HMAC proof, single-use nonce and exact image/build/device checks. Ordinary status and LINK requests use Digest authentication. This HMAC route is **not equivalent to asymmetric signed release verification**; do not describe the current user-visible updater as an independently verified public-key-signed OTA. There is no evidence here of resume or A/B rollback.

**Admission.** Client and device separately check matching device identity, exact image SHA/build, bounded size, layout `4m2m`, staging separation, heap >=25,600 B on admission, stack >=2,048 B, block >=16,384 B, fragmentation <=25%. Client pins expected current SHA when requested and creates a durable one-shot marker **before the POST**. Missing/ambiguous receipts cannot authorize a second upload.

**Transfer.** ESP8266 Core `Updater.begin(bytes,U_FLASH)` stages in unused flash before `FsStart=0x200000`, with 512-byte receive chunks and SHA256/CRC + image-segment readback verification. `Transfer::finish()` alone commits through `Updater.end(false)`; errors call `shinoAbort()`. The earlier unaligned `ESP.flashRead` bug was corrected in this installed B3 source, but its branch and the real runtime stack under 400+ KiB transport/verification **have not been physically exercised by this read-only PASS**.

**Boot/recovery.** After an accepted staged response, device code requests `ESP.restart()` and Core eboot copies the staged image. There is **no guaranteed automatic rollback** during eboot copy/power interruption. The client may report `UNKNOWN_NO_RETRY` or `POSTBOOT_ACCEPTANCE_UNCONFIRMED`; it must not automatically re-upload. The manual 4MiB PRE/POST and UART recovery history remain indispensable, but no new PRE, restore or UART operation is authorized.

## 4. Remaining proof obligations (OFFLINE first, physical HOLD)

1. **Distinct successor release.** No owner-private successor B4 exact BIN/build ID/SHA has been approved or shown here. Do not reuse B3 or confuse a public-inert firmware with a deployable owner image. Any new release requires pinned source commit, independent review, private compile and local BIN/manifest verification under an explicitly scoped offline mandate.
2. **Real OTA path stack/memory.** The 224 B post-GET stack margin is narrow. Compiler callgraph of HMAC, 512-byte write, staged CRC/SHA/segment scan, Updater and eboot must be rechecked on the **successor source and currently installed B3**. Offline frames/host mocks cannot prove a native high-water floor under upload; plan an explicit abort-on-low-margin policy, **not** a lowered threshold.
3. **Power and interruption semantics.** Verify how `Updater` stages, `end(false)` arms eboot, what bytes of 4m2m are touched before/after commit, interrupted upload/response loss/reset, and preserving LittleFS `0x200000..0x3f9fff` + reserved end `0x3fa000..0x3fffff` in pinned Core 3.1.2. No claim of atomic swap or field-safe rollback.
4. **One-shot PC sender.** Audit that the exact future command binds expected installed B3 SHA, distinct target SHA, private device/build, new attempt marker and receipt, and aborts before POST on failed preflight; never auto-retry on unknown results.
5. **Physical authorization (FUTURE).** Only after offline review/CI and a distinct owner-approved SHA, make a separate explicit risk/recovery decision. Current 30-cycle GET PASS is **not consent** for flash/OTA, diagnostic POST, reboot or changing LINK/Wi-Fi.

### Safe next offline deliverable

One coherent review of the **actual Core 3.1.2 Updater/eboot copy path**, existing OTA host regression and source-level HMAC/verification stack geometry, plus a fail-closed owner-local candidate-pair preflight spec. Reuse current tools/tests and existing Draft PR, avoid new firmware or custom script proliferation unless a concrete gap is demonstrated. Report source-grounded open risks and exact-head CI.

**NO DEVICE CONTACT in preparing this report.** No serial, AP/HTTP GET/POST, OTA, flash, reboot, RTC/FS write, LINK restart, local private artifact reading/upload, PR merge, or rollback was performed or authorized by this documentation change.

## 5. Additional exact upstream Core 3.1.2 / eboot source audit (2026-10-11)

Read the pinned public Arduino ESP8266 Core **3.1.2**, separate from the owner's firmware, from:
- [`cores/esp8266/Updater.cpp`](https://github.com/esp8266/Arduino/blob/3.1.2/cores/esp8266/Updater.cpp) (notably `UpdaterClass::begin`, `_writeBuffer`, `end`);
- [`bootloaders/eboot/eboot.c`](https://github.com/esp8266/Arduino/blob/3.1.2/bootloaders/eboot/eboot.c) (`copy_raw`, `main`);
- [`bootloaders/eboot/eboot_command.c`](https://github.com/esp8266/Arduino/blob/3.1.2/bootloaders/eboot/eboot_command.c) (RTC magic+CRC command lifecycle).

**Concrete findings, source-proven but not device-qualified:**

1. `UpdaterClass::begin(size,U_FLASH)` calculates `updateEndAddress=FS_start-0x40200000`, then `start=updateEndAddress-rounded(size)`, refusing overlap with the current rounded sketch. This agrees with SHINO's `FsStart=0x200000` staging formula **if and only if** the actual linked `FS_start` is the expected 4m2m boundary on the target. An independent exact linked-layout assertion remains mandatory.
2. At begin, Core dynamically allocates an **extra 4,096-byte buffer when free heap >8,192 bytes** (otherwise 256 bytes). With B3's read-only observed free heap minimum of 29,560 B, that is significant unmeasured *additional* OTA workload, **not** a guaranteed 4,096-B reduction in the runtime watermark: allocations and scheduling differ during the upload. The admission heap must therefore be sampled throughout the transfer, not inferred from GETs.
3. `Updater::_writeBuffer` erases/writes staging sectors; when the new image flash mode byte differs from the current flash hardware mode, Core modifies the stored header byte for the physical flash and then restores its RAM buffer. SHINO subsequently SHA/CRC-checks the staged image. **Candidate first-sector flash-mode compatibility must be checked offline** to avoid an avoidable real mismatch. It is not proof of a mismatch in any existing B3/B4 image.
4. `UpdaterClass::end(false)` writes the **RTC `ACTION_COPY_RAW` instruction** with source=staging, destination=0, size=image bytes. No application code swaps the images atomically in-place.
5. On reboot, `eboot::copy_raw` performs 4-KiB sector reads and destination erases/writes. The code treats destination sector zero specially: it skips it only when the entire sector already matches. **The bootloader's post-copy compare is compiled out with `#if 0`** (source comment cites overlap issue #7458). Its copy operation therefore does not provide a full independent destination verification before boot.
6. If eboot receives a valid RTC command, it attempts the copy and clears the command afterward; copy failure may lead to reset, but **does not restore a previous application**. Power loss during destructive destination writes may leave an unbootable partial application. The physically validated UART/PRE/POST custody is a rescue option, not automated rollback.

**New specific offline acceptance tests before any successor OTA candidate:**

- Inspect pinned linker variables `FS_start`, `FS_end`, current/pending image extents, and prove `[stage,stage+rounded(bytes))` never reaches `[0x200000,0x400000)` or the running sketch.
- Assert target BIN header flash-mode compatibility with the owner's known working B3/flash mode; avoid silently rewriting candidate bytes or weakening image digest checks.
- Replay official Core `Updater::begin`'s 4096/256-byte allocation branches and failure handling using exact linked build/host tests, including the RAM floor checks after allocation and after each 512-byte delivery.
- Simulate interrupted staging, `end(false)` commit failure, lost success response, and **each 4-KiB eboot destination-sector interruption**; assert no implied recovery, no retry and correct `UNKNOWN/HOLD` classification.
- Explicitly test preserved `[0x200000,0x400000)` sectors and no bootloader sector rewrite except as defined by the pinned Core; require fresh real PRE/POST review on any separately authorized physical transaction.
- Keep the existing owner-private B3 installed until a new successor release is separately built, hash-pinned and approved. No physically executed OTA is implied by these source checks.

**Source-level verdict:** `OTA_CORE_STAGING_REVIEW=SOURCE_INSPECTED`; `OTA_EBOOT_ATOMIC_ROLLBACK=NO`; `OTA_NATIVE_RAM_STACK_GATE=NOT_MEASURED`; `OTA_ONE_SHOT_TRANSACTION=HOLD`. New core-specific assertions should be integrated into the *existing* offline simulator; do not declare OTA PASS from any prior 30-cycle GET report.
