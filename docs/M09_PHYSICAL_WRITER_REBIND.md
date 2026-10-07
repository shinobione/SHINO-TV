# Mission 9 — targeted frozen-successor physical-writer rebind

> **Current Phase O writer binding, 7 October 2026:**
> [Normal StageA rebind receipt](M09_PHASE_O_WRITER_REBIND.md) selects only399264 B /
> SHA-256 `78a8d2d50409974fc775dd3dc9f3dbec4ac8eda839f6d9b338cadf35aab2467c`,
> rounded0x062000,98 packets; last1952 payload/2144 FF. Future physical packet
> PRINT ONLY/not authorized. Both normal physical gates NOT_RUN; no firmware/
> freeze/FS change. Installed profile2 probe PASS is historical owner evidence.
> Older transaction geometries below remain dated history. STOP/no flash/reboot/merge.

> **Current owner evidence, 7 October 2026:** the exact411152 B mount-stack
> successor is now owner-reported installed; dedicated profile2 physical/resource
> gates **PASS**. Both normal-profile gates **NOT_RUN**. See the
> [owner-supplied acceptance](M09_SUCCESSOR_PHYSICAL_ACCEPTANCE.md) and
> [offline normal-readiness design](M09_NORMAL_PROFILE_READINESS.md).
> The dated receipt below retains its original results as historical evidence;
> recording this update performed no device operations and grants no authority.

Owner decision, 7 October 2026: continue exact clean
`849d430f6736f349a089cbac7acf2c9648e9b887` on
`feature/shino-tv-m9-flash-layout-liberation`, existing Draft/open/unmerged
PR #42. This receipt qualifies an OFFLINE binding only. No physical operation
is authorized; successor installation/resource acceptance remains NOT_RUN.
Installed J's owner-reported mount continuation1776 B still FAILS the2048 B
floor; physical resource gate HOLD and both normal-profile gates NOT_RUN.

## Exact retained identity and transaction geometry

| Field | Binding |
| --- | --- |
| Retained local BIN | `research-local/m9-mount-stack/frozen-successor-resource-probe.bin` |
| Existing firmware source freeze | `9f86a73d999168d052e2037a4fcb999cfe9a2e2c` |
| Bytes | **411152** |
| SHA-256 | `e1852e56d99801b694f37d235b08a201188cf36d5a25f3f6f59d059a129bc27e` |
| Target | **0x000000** |
| Payload end exclusive | **0x064610** |
| Sector-rounded end exclusive | **0x065000 / 413696 B** |
| Protected interval inclusive | **0x065000..0x3FFFFF / 3780608 B** |
| Uncompressed DATA blocks | **101**, sequences **0..100**,4096 B each |
| Last block start | **0x064000 / 409600 B** |
| Last block | **1552 B payload +2544 B0xFF padding** |

The retained BIN is rehashed and inspected locally, never rebuilt, substituted,
committed or uploaded. All103 tracked `firmware/**` files remain unchanged from
the required starting HEAD. Historical J/K candidate/source manifests remain
unchanged: the qualification report now separates current `candidate` binding
from `historical_j_candidate`. Only the application writer's identity constants,
selection wording, dependent LF source pins and CI candidate expectations change.
The mount-stack manifest's existing tool-pin field now pins the authorized
writer binding; its firmware, observer/policy and physical-runner pins are intact.

## Preserved gates and evidence boundaries

Phase M acquisition/physical runner is byte-for-byte unchanged: maximum five
pre-stub ROM SYNC requests, one5 s/16384 B/256-read global budget,50 ms bounded
retry delay; one handle, no reset/reopen/reconnect. Fresh ROM/chip magic and exact
pinned-v2 stub required; measured uncached post-stub capacity0x16 BEFORE Begin.
No raw-ROM capacity assertion is reintroduced.

Exact successor selection/size/SHA/image inspection must pass before any
transport factory or serial acquisition. The writer revalidates before invoking
the factory. Historical J hash/GO, wrong size or altered successor bytes close
the gate before contact. Success has one FLASH_BEGIN,101 unique FLASH_DATA,
one no-reboot FLASH_END and one MD5 barrier. After transaction start: zero
flash retry, reset/reconnect/reopen or rollback/recovery write. Exceptions consume
the session without cleanup Finish or a second attempt. Full independent4 MiB
POST before boot remains mandatory: candidate exact at zero and every protected
byte PRE-equal, including frozen LittleFS/tail. MD5 acknowledgement closes no
physical gate and never permits automatic boot.

Unchanged physical thresholds, scoped to this profile2 probe: heap>=20480 B,
largest block>=16384 B, fragmentation<=25%, continuation stack>=2048 B in both
mount/runtime windows, with existing sample-validity/no-write/runtime requirements.
Host/fake serial and CI establish offline behavior only. They do not prove an
installed successor or physical margin. Existing CI comparison builds remain
ephemeral source checks; the retained frozen BIN is neither read nor replaced
by CI and no CI output becomes the physical candidate.

## Validation

**223 local checks PASS:**196 complete Mission9 tests plus27 related checks
(first-boot bridge, FS-less dashboard, FS provisioning and three scoped port80
source checks). Zero failures/errors/skips on the completed run with installed
MSVC and workspace temporary fixtures. Earlier sandbox runs failed on temporary
directory/hardlink access and unavailable compiler environment; these were host
environment failures, preserved in ignored local logs, with no production fix.
Tests exercise fake transports only, including all416 flash-fault cases and
Phase M bounded acquisition cases. New tests verify exact successor selection,
last-block payload/padding, unique sequence/MD5/POST barriers, historical J hash/
GO rejection and real SHA mismatch before acquisition.

Approved Python3.12.10 identity and pinned esptool5.4.0/esp-pylib1.1.5/pyserial3.5
source audit PASS, including103 firmware and28 serial source files. Local actual
BIN image/size/SHA inspection PASS; Phase M candidate gate PASS/OFFLINE. The
unchanged runner default audit returns `AUDIT_PRINT_ONLY_NO_PORT_OPEN` for the
successor, with physical_authorization=false and serial_io=0. AST comparison
confirms both SingleAttempt/PinnedStubTransport class implementations unchanged;
Git comparison confirms firmware/runner/policy/historical J manifest/Phase M
source pins unchanged from required HEAD. No local firmware build performed.

Exact-head CI links and commit identity remain visible on existing PR #42 after
push, without another firmware freeze. Only ephemeral CI comparison graphs may
build; the physical frozen candidate stays the rehashed retained local file.

Changed files: `tools/m9_single_attempt_app_write.py`,
`tools/m9_phase_k_qualification.py`, `tools/m9_phase_l_sources.json`,
`tools/m9_mount_stack_sources.json`, `tools/test_m9_single_attempt_app_write.py`,
`tools/test_m9_single_attempt_physical_runner.py`; the three
`.github/workflows/m9-phase-{k,l,m}.yml` candidate expectations;
`docs/ROADMAP.md`, `docs/AGENT_HANDOFF.md`, this receipt and current-binding
cross-references atop `docs/M09_RESOURCE_POLICY_AND_EXECUTOR_QUALIFICATION.md`,
`docs/M09_SINGLE_ATTEMPT_PHYSICAL_RUNNER.md`, `docs/M09_PHASE_L_SYNC_HOTFIX.md`,
`docs/M09_MOUNT_STACK_REMEDIATION.md`. Older receipts remain dated history.

**DEVICE CONTACTS =0; SERIAL I/O =0; FLASH WRITES =0; RTC WRITES =0;
REBOOTS =0; DEVICE FILESYSTEM WRITES =0. STOP. DO NOT FLASH.**
