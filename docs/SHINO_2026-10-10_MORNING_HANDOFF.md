# SHINO // TV — Morning handoff, 2026-10-10 (owner goes to sleep)

**THIS IS A HANDOFF, NOT A RELEASE APPROVAL.** Resume in the existing
`feature/shino-tv-m9-flash-layout-liberation` branch / Draft PR #42.
No owner physical operation is in progress and no overnight operation is
requested. No OTA B was attempted. Keep the currently installed **A**.

## Physical truth, as directly reported in conversation/screenshots

- ESP8266 GeekMagic SmallTV-Ultra, physical 4 MiB flash, `4m2m` layout.
- Firmware A private BIN installed via owner's explicitly authorized, single UART
  operation on COM8. A = 407,008 bytes, SHA-256:
  `faee8f927ca468978f5ec4bd133e899b6898bfc6c01e1afe471f392026e70a6b`.
- Independent **PRE and POST** full 4,194,304-byte dumps were captured locally.
  The local offline `m9_stage1_readback_verify.py` finally returned exit 0,
  `PASS_LOCAL_STAGE1_READBACK_MODEL`. Candidate A bytes matched, protected
  `[0x064000,0x400000)` = **3,784,704 bytes** matched PRE exactly. The
  verifier itself correctly says capture freshness is *not* independently
  attested, but owner performed live PRE and POST during this session.
- GPIO0-to-GND bridge removed and CH340 disconnected for normal boot.
  A booted, displayed four cards. Private AP `SHINO-TV-StageA` visible and
  Windows connected. LINK `python companion/shino_link.py --once` returned
  `CONNECTED`; four cards temporarily populated. LINK `--run` subsequently
  reported `SHINO // LINK: CONNECTED` with fresh metrics.
- Owner ran `QUALIFY-A.cmd` with continuous LINK actually running; result
  `READONLY_QUALIFICATION_FAILED` (not an OTA firmware update failure).
  The qualify tool catches `(ValueError,OSError)` and strips the actual
  diagnostic. Do not blame stale telemetry or lack of LINK: disproven.
- A **three-request authenticated read-only diagnostic** was performed
  with the companion HTTP client's existing private credential source:
  `/api/v1/update/status` HTTP **200**;
  `/api/v1/m9/normal/status` HTTP **200**;
  `/api/v1/m9/maintenance/result` HTTP **200**.
  Running `sha256`, `build_id`, image bytes matched A; `metrics_fresh=true`,
  `fs_ok=true`. Runtime resource status from the identity handler:
  `heap=31912`, `block=29744`, `stack=1632`, `frag=7`.
  `shino_update.check_status()` rejects *only the observed stack* against
  configured floor `2048`: **416 bytes short**; it throws
  `Running resource floors failed`. Thus the immediate failure
  of `QUALIFY-A.cmd` is explained without assuming any 404 recurrence.
- The earlier installed M9 firmware's `STAGE_A_PREBODY` 404 root cause was
  **never proven**; the new persistent HTTP A has passed these three GETs,
  but cannot yet be declared stable throughout the original full workload.
- Planned B is a *different* private 407,008-byte BIN, SHA-256
  `78fdfbeb2b0b71c2649bcd2033d7d2b3eb8cb19a9cc30b393ad4b75e89336bea`.
  **B has NOT been installed, uploaded, staged, or authorized for a live OTA**.
  A->B remains **NOT_RUN**. No rollback is supported; eboot copy power loss
  could require UART rescue.

## Context (existing source vs specific hypotheses)

- Source at `ota/firmware/Normal.cpp`: `identity()` calls `budget()`
  (including `ESP.getFreeContStack()`), then uses a **768-byte local**
  `char body[768]` and `snprintf`; C++ compiler may allocate the frame on
  entry, so the reported `stack=1632` can include the identity handler's own
  peak frame. `metrics()` also uses a local 768-byte buffer. This is a
  **concrete hypothesis** requiring disassembly/frame analysis; not a proven
  sole root cause, and *not* evidence that the upload path has enough stack.
- `ota/firmware/ShinoHttpOta.h:Budget::safe()` and
  `companion/shino_update.py:check_status()` require
  stack >= 2048. Upload uses deeper HMAC, Core Updater/flash/readback/CRC
  paths. Do not lower or bypass these floors merely to obtain a PASS.
- Original CI on pre-handoff HEAD `7d49ab995da354574ac67bf8fdd9dd9af2ddf339`
  passed 11/11 workflows **offline**, but physical upload high water was
  not established. This docs-only handoff commit is *not* a new firmware build.
- Private local packet:
  `research-local/m9-owner/http-ota-20261010-ab/`.
  Includes private A/B artifacts, manifests, `QUALIFY-A.cmd`,
  `UPDATE-B.cmd`, `QUALIFY-B.cmd`, PRE/POST, UART receipts, etc.
  Never upload or overwrite private BIN, keys, dumps, credentials, or secrets.

## Codex: what to do next WITHOUT owner intervention

1. **Do not reflash A, attempt B, reset, connect to COM8 or contact the
   SmallTV.** Physical contact or OTA requires a separate user-authorized
   action. The owner is sleeping and should not be a CI operator.
2. Diagnose actual continuation-stack depth on `/api/v1/update/status`
   using compiled ELF, disassembly, compiler frame/stack reports and
   host-side low-memory tests. Distinguish instantaneous
   handler-context free stack from steady loop observer free stack and
   the worst-case OTA path. Identify stack savings *without* weakening
   thresholds or introducing unguarded reentrancy.
3. Implement the **smallest robust firmware change** in
   `ota/firmware/Normal.cpp` and/or associated code if needed (e.g.
   move bounded JSON formatting scratch out of the continuation stack,
   with explicit lifetime ownership and DRAM/static budget review).
   Audit update receiving, HMAC, flash staging verification, CRC,
   checksum, `ESP.restart` path and future OTA headroom. A superficial
   fix of the identity JSON alone is not sufficient.
4. Improve `companion/shino_qualify.py` and related Windows launchers
   so a read-only failure prints a **specific sanitized reason**, expected
   vs observed floors and exact failing operation/cycle, without exposing
   auth/HTTP headers or private credentials. Avoid false success prints.
   Consider startup sequencing for live metrics but do not blame telemetry
   without evidence.
5. Execute local end-to-end, pinned Core and parser tests; verify no
   LittleFS or flash-layout regression, RAM static costs, actual compiler
   frames and no accidental private asset modification. Keep Draft PR #42.
6. Provide owner an **actionable short report**: proven root vs hypotheses,
   files changed, test evidence, static/stack tradeoffs, whether installed A
   might qualify for OTA **without another UART** (note immutable running A),
   and **one minimum physical experiment**, only after asking approval.
   Never assert that source-only tests prove native memory safety.
7. **No new mission phases, no new device-wide reflashes, no B upload,
   no re-run of a failed state-changing action without new consent**.

## Morning user goal

The owner worked late, understandably exhausted. **Protect their time.**
The endpoint goal is exactly: validated physical A -> authenticated Wi-Fi OTA
to B -> independently verified boot, four cards, LINK freshness,
LittleFS preservation and *future OTA readiness* -> close the enclosure.
No more claims of completion until this happens.

## Safe state at end of session

A is confirmed booted with working screen, AP, LINK, and 3 HTTP 200s;
A native OTA admission is **HOLD** at measured stack 1632 (< 2048).
No OTA attempted. Owner can stop LINK with Ctrl+C, disconnect USB-C
and power off PC; flash and FS are nonvolatile. UART/CH340 disconnected;
keep GPIO0 bridge removed. No change to device on this handoff commit.
