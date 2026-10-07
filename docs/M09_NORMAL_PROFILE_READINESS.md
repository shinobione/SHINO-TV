# Mission 9 — offline normal-profile 4m2m readiness and staged design

> **Historical readiness checkpoint at2bd225a.** The following design-only
> decision and deferred implementation are preserved as provenance. The later
> [Phase N owner instruction](https://github.com/shinobione/SHINO-TV/pull/42#issuecomment-6043431763)
> authorizes StageA implementation; [current implementation receipt](M09_PHASE_N_STAGE_A.md)
> supersedes candidate/environment status and explicitly defers media/full scenes.
> Both normal physical gates remain NOT_RUN. The readiness audit now labels its
> historical scope; current StageA qualification uses a separate source/link gate.

Owner scope: [latest PR #42 comment](https://github.com/shinobione/SHINO-TV/pull/42#issuecomment-6042956937),
7 October 2026; start clean `1b696e530d6d2b0d1bfa6503b5fe320214ac621f`,
existing `feature/shino-tv-m9-flash-layout-liberation`, Draft/open/unmerged PR.
The [physical receipt](M09_SUCCESSOR_PHYSICAL_ACCEPTANCE.md) is recorded first
as **owner-supplied evidence**. Probe physical/resource gates PASS for the exact
411152 B profile-2 successor. Normal mount/runtime gates remain **NOT_RUN**.

**Decision: OFFLINE DESIGN RECEIPT GO; NORMAL CANDIDATE HOLD.** The comment
permits implementation/freeze only if defensible. Source inspection establishes
that enabling the held normal branch would change authentication, metrics/media
ownership, persistence and recovery together. This pass therefore completes the
readiness/design option, retains the compile prohibition, and freezes **no normal
candidate**. A profile-0/2 image cannot be renamed as a true normal candidate.
No production firmware, private policy, existing writer binding or thresholds
change. Implementation of the staged design remains future work.

## Source hazards at the starting head

Line references below were inspected at the starting head; the new offline
`tools/m9_normal_readiness.py` emits current exact anchors/line numbers and LF
hashes after verifying all103 firmware pins plus runner/transaction/policy pins.
It fails on drift; it does not derive current physical state from older helpers'
historical HOLD labels.

| Source / trigger | Actual behavior / consequence | Chosen design requirement |
| --- | --- | --- |
| `ShinoBootProfile.h:8-9` | Profile1 compilation prohibited | Keep prohibition now; later permit1 only with exact normal qualification flag/environment and fail-closed target guard |
| `main.cpp:157`, `ConfigManager.cpp:35,184` | Startup mounts; load/save mount again | One central no-autoformat mount owner; configuration receives proven mounted state; never mount in readers/save/status/GIF |
| `ConfigManager.cpp:53-56` | Allocation based on unbounded file size; read length not checked | Bounded read-only config loader, exact seed/length/types/rotation validation, reject partial/trailing/oversize/nonblank credentials, no migration |
| `ConfigManager.cpp:77-101,186-216` | Credential/token migration uses SecureStorage and save; save writes config and Wi-Fi storage | Explicit separate read-only load mode; save/migration unreachable in first normal qualification stage |
| `SecureStorage.cpp:68-84,194-218` | Missing/invalid store initializes and flushes; put may call begin then commit | No EEPROM begin/get/put/remove in stageA; later explicit read-only store API and separately reviewed initialization/write contract |
| `main.cpp:182-184` | Missing API token provisioned into persistent storage | Retained generated private identity in RAM only; status says persistence disabled; no new secret or token migration |
| `RescueMode.cpp:93-159`, `main.cpp:188,267` | Startup/stable marking writes RTC and persistent counters | No legacy checkBootLoop/markBootStable in stageA; RAM fault state, no claim of cross-boot rescue detection; external STOP on reset |
| `main.cpp:170`, `WiFiManager.cpp:60-71,103-118` | Persistence false precedes normal Wi-Fi; station begin still unconditional on empty seed | StageA explicitly secure AP/volatile only, no station begin or assumed SDK credentials; later STA loading/onboarding bounded and separate |
| `Api.cpp:55-176,204-211` | Legacy normal route list, Bearer gate; token/rotation/NTP/Wi-Fi writers, reboot, GIF mutations registered | New small qualification route allowlist with existing reviewed Digest/body/authority contracts; never register legacy list wholesale |
| `Api.cpp:370,417-422,495,760,877,1077,1186`; `Gif.cpp:573,610` | Even status remounts; GIF path may remount/unmount; runtime filesystem writes | Global read-only FS adapter denying API mutations and physical prog/erase; zero retries/repair/end; no GIF writer/play-all routes |
| `SceneManager.cpp:25,178-186,266-287`; `DashboardManager.cpp:14,36,144` | Scene TTL60 s; normal metrics are a six-tile HTTP-pull graph; normal API is not the qualified signed receiver | Integrate reviewed four-value RAM telemetry at6 s and signed32px media at8 s with exclusive SceneEngine; preserve cryptographic/transaction ownership and native renderer tests |
| `FirstBootBridge.cpp:61-62` | Additional consumer asserts profile0/2 only | Audit all profile consumers; do not remove the header error alone or call FirstBootBridge::run as a disguised normal implementation |
| `Webserver.cpp:84-95` | Public beginFS helper can remount, autoformat rejected | Remove repeated mount ownership from first normal graph; keep format prohibition |
| `FactoryRollback`, native OTA flags | Distinct exact-OEM application return contract; native OTA disabled | Preserve exact signed OEM escape implementation/identity separately; no new normal writer route or native OTA activation |

The normal SceneManager60 s TTL is a legacy scene push freshness rule, not a
measurement of the qualified telemetry TTL. It still demonstrates that the
normal route/scene graph is a different product path. Legacy normal assets use
the legacy API; serving them does not establish working Digest/product flows.

## Geometry and reserved ownership

Pinned platform **espressif8266@4.2.1**, Arduino Core **3.1.2** / package
**3.30102.0**, board esp12e, DIO/4MB; future environment
`esp12e_m9_4m2m_normal_qualification` is **DESIGNED, NOT IMPLEMENTED**.
Ordinary default `esp12e`/4m3m, opt-in profile0 `esp12e_m9_4m2m`, and profile2
environments remain unchanged.

| Physical interval | Contract |
| --- | --- |
| `0x000000..0x0FFFFF` | 1 MiB application region; actual BIN/sector-rounded extent measured per candidate |
| `0x100000..0x1FFFFF` | Remaining pre-FS layout; no OTA use in this milestone |
| `0x200000..0x3F9FFF` | Frozen LittleFS,2072576 B;24 files/181402 B; never buildfs/rewrite/format for normal readiness |
| `0x3FA000..0x3FFFFF` | Reserved24 KiB end-of-flash system/EEPROM/SDK area; no application persistence authority |

Actual4m2m linker provides `_FS_start=0x40400000`, `_FS_end=0x405FA000`,
`_FS_block=8192`, `_FS_page=256`, `_EEPROM_start=0x405FB000`.
Subtract0x40200000 for physical offsets. Pinned Core EEPROM constructor uses
`(_EEPROM_start-0x40200000)/SPI_FLASH_SEC_SIZE`; commit erases/writes that sector.
Thus normal SecureStorage commit would touch **0x3FB000**, inside the reserved
tail, not a harmless write within config.json. This is an additional reason
to withhold an unchanged normal build. Tail reservation does not prove which
old SDK/EEPROM contents are valid, nor imply persistent credentials exist.

## Smallest defensible staged normal design

StageA is a real normal qualification integration, **not implemented here**:
normal main startup/loop, ConfigManager, DisplayManager and Webserver services
with explicit capability changes; one central4m2m mount/config owner, normal
read consumers and reviewed signed receiver/scene/telemetry components. It must
not delegate startup/loop to the existing FirstBootBridge profile or simply use
the profile2 probe with a new label. Enable profile1 only under
`SHINO_M9_NORMAL_QUALIFICATION=1` and the exact application-only environment;
target guard rejects upload/uploadfs/buildfs/erase/program. Defaults unchanged.

1. Before consumer startup, verify actual flash geometry and reserve ownership.
   Install a common global LittleFS read-only implementation derived from the
   proven adapter; deny all write opens/mutations/format and physical prog/erase.
   Single mount only after successful `LittleFSConfig(false)`. Preserve reviewed
   bounded256 B streaming/hash/seed checks, one408 B scratch workspace/reentry
   guard. Exact inventory/hash mismatch or mount failure stays failure; no
   fallback to unrestricted LittleFS, repair, second attempt, credential reset
   or reboot. Keep protected AP/status available using a reviewed normal service
   failure branch; no filesystem consumer on failed readiness.
2. Add explicit `loadMountedReadOnly` semantics to ConfigManager; read canonical
  85 B seed exactly and retain zero credential fields. No SecureStorage API calls
   even for get (get may initialize). API/Digest/media identities remain owner
   private build inputs used in RAM, never copied to config or logs. Rotation
   comes from reviewed seed/owner LCD contract; verify physical orientation later.
3. Normal Webserver owns one authenticated runtime/status graph. Closed read-only
   static asset allowlist with path/traversal checks; deny `/config.json` and all
   mutation routes. Legacy interactive web UI withheld until its API contract is
   adapted; use a bounded program-flash qualification inspector. Authentication
   must precede body/expensive processing with existing reviewed ingress owner;
   no stock-server/overlay ABI mixture. Digest telemetry and signed media reuse
   exact ownership/deadline/replay rules; four metrics keep ingesting in music,
   metric cards only in IDLE. Clock/weather unknown until valid providers exist.
4. StageA Wi-Fi is explicitly volatile private AP, not home-LAN qualification:
   `persistent(false)` before every mode/state operation; no empty-credential STA
   begin, saved-SDK assumption, disconnect-erase or automatic onboarding. Normal
   WiFiManager must expose this explicit mode instead of its current unconditional
   STA attempt. Secure AP failure closes network service without open fallback.
5. Replace implicit rescue counter persistence in this stage with RAM-only fault
   reporting. No RTC writes, startup token save, EEPROM or storage migration.
   Preserve exact OEM return contract separately; no new writer activation in
   stageA. Normal signed OTA flag remains0; upload route absent. Any future OEM
   operation retains separate exact-operation authority and signature/MD5 review.
6. Normal resource observer brackets **whole normal setup**, the narrower FS
   window, and steady runtime after setup. Sample only at cooperative loop end,
   at most1 Hz; no HTTP/FS/timer/ISR sampler or runtime watermark reset. Status
   exposes profile/environment/layout, FS/seed/inventory result, write capability
   states, denied attempts, identity-free boot/sample counters, invalid/rejected
   counts, heap/block/fragmentation minima/maxima and separate setup/mount/runtime
   continuation starts/minima. Authenticated cached bounded scalar output; no
   passwords, saved SSID, token, MAC or private captures. Media receive/render,
   status, static reads and LINK stale/recovery workloads included in qualification.

Expected future source scope: profile header/main/PlatformIO target guard;
ConfigManager header/source; shared read-only FS owner/observer; WiFiManager;
Webserver qualification route registration; normal scene/receiver integration
and RescueMode capability handling. Existing native ingress, receiver/renderer
and resource tests must exercise actual linked normal entry points. This spans
multiple safety owners, so this pass does not fabricate a small passing candidate
by suppressing assertions or disabling required product paths.

StageB is a separate intentional-persistence milestone after StageA acceptance:
define exact sector/key ownership, read-only store validation, owner-local
credential onboarding/readback, persistent SDK transitions, power-loss/reconnect
and secure AP fallback. First invalid store must not imply initialization consent.
No boot counter or token commit merely because a getter was called. Frozen FS
remains protected; any intentional config write needs a reviewed explicit
contract and separate acceptance, not automatic legacy migration. StageC native
signed OTA remains outside this request and separately gated.

## Resource policy and offline evidence

Existing probe policy is unchanged and remains scoped to profile2:
heap>=20480 B, largest block>=16384 B, fragmentation<=25%, continuation>=2048 B
in both windows. Profile2 mount2336 B leaves only288 B above its floor; do not
assume that budget accommodates normal config/static/scene/crypto calls.
The future normal policy is **REVIEW_REQUIRED**; those four bounds are retained
as minimum design constraints, not blindly asserted to qualify the new workload.
Require additional setup/status/static/media/crypto/render call-chain analysis,
allocation lifetimes, largest allocation plus margin, secondary-stack separation,
and measured physical workload reserves before declaring normal thresholds.
No weaker value is proposed. Compiler frames never establish physical margin.

A disposable **public-fixture profile0**4m2m build uses tracked current source,
no private policy reads, no upload/buildfs, local-only `-fstack-usage` for analysis.
It measures the currently buildable reference; it is **not a normal build**.
Expected profile1 header preprocessing rejection is verified without bypassing
the guard. The retained installed successor BIN/ELF/FS are never rebuilt or
substituted by that reference build.

| Measured local reference evidence | Result |
| --- | --- |
| Environment / profile | `esp12e_m9_4m2m` / **0**, disposable public-fixture copy |
| BIN bytes / rounded extent | **399168 B** / **401408 B**, end `0x062000` |
| Linked application flash | **395011 B** |
| Static RAM (`.data+.rodata+.bss`) | **40344 B** |
| `.noinit` (separate) | **56 B** |
| Major own compiler frames | Digest authenticate368 B; authenticate256 B; JSON serializer256 B; dashboard paint240 B; acceptMetrics224 B; request parser208 B; status192 B |
| Linker proof | `_FS_start=0x40400000`, `_FS_end=0x405FA000`, `_EEPROM_start=0x405FB000`; FS-block8192/page256 verified in pinned linker source |
| Image evidence | ESP8266 boot/application checksums and Arduino CRC PASS; BIN alone does not prove linker geometry |
| Profile1 expected rejection | Actual Xtensa preprocessor rejects `ShinoBootProfile.h:9`; guard not bypassed |
| Preservation | All103 firmware files match existing successor source pins; retained411152 B successor rehash exact; pinned15 Core FS/resource sources PASS |

Compiler rows are individual own frames from main/bridge source reports, not
whole nested stacks, signed-media resource measurements or physical free stack.
The public-fixture reference is deliberately not frozen for installation. Local
reports/logs/generated BIN/ELF remain ignored under `research-local/`; no private
policy was read or published by the reference builder. PlatformIO initially
could not write its external cache under sandbox; the authorized offline build
then passed with cache access. No device was involved.

**Normal application size/static RAM/.noinit/major frames: UNAVAILABLE — profile1
is compile-prohibited and no normal implementation exists. Normal build/link/
resource/identity gates HOLD; no frozen normal BIN.** Reference numbers do not
fill those fields. Source/design receipt and matching CI are distinct from those
normal candidate gates.

## Future physical packet — PRINT ONLY / HOLD

No executable normal flash command or valid GO token can be prepared: there is
no qualified normal candidate/hash or writer binding. Existing writer remains
bound to installed profile2 successor and must reject any future normal bytes.
Future packet prerequisites only: reviewed StageA implementation/resource policy,
all offline tests/link/identity gates, one exact frozen local normal BIN/hash,
separately reviewed no-retry writer binding, fresh exact-operation owner approval,
qualified fresh ROM/4MiB/pinned-v2 session, independent private full4MiB PRE,
protected frozen FS/tail verification, one application transaction, independent
full POST **before boot**, exact candidate at0 and POST beyond rounded end
PRE-equal, separate reviewed powered RTC transition and boot authority, bounded
normal status/telemetry/media/static/resource windows. Stop on reset, unsafe
heap/stack, corruption, preservation mismatch or unavailable recovery. No retry,
substitute image, automatic rollback, normal promotion or merge by inference.

## Exact changed files and validation

This pass changes exactly11 tracked files:

- `docs/M09_SUCCESSOR_PHYSICAL_ACCEPTANCE.md`: new owner-evidence receipt.
- `docs/M09_NORMAL_PROFILE_READINESS.md`: this focused hazards/design/resources receipt.
- `docs/AGENT_HANDOFF.md`, `docs/ROADMAP.md`: active owner decision/current gates.
- `docs/M09_FLASH_LAYOUT_LIBERATION.md`, `docs/M09_MOUNT_PROBE_PHYSICAL_EVIDENCE.md`,
  `docs/M09_RESOURCE_POLICY_AND_EXECUTOR_QUALIFICATION.md`,
  `docs/M09_PHYSICAL_WRITER_REBIND.md`: current-evidence pointer above intact dated history.
- `tools/m9_normal_readiness.py`, `tools/test_m9_normal_readiness.py`: immutable
  source/evidence/reference qualification and failure-closed tests.
- `.github/workflows/m9-flash-layout.yml`: exact-head readiness test/report and
  actual expected profile1 compiler rejection in the existing offline workflow.

All103 tracked firmware sources, firmware settings/scripts, native experiments,
resource policy, physical runner, transaction and writer binding are unchanged.
Ignored local public-fixture build/test drivers and logs are not tracked outputs.

Local matching regression suite: **226 tests**, **224 PASS initially**; two
existing hardlink readback tests were denied by the sandbox filesystem, then
both **PASS** on a scoped rerun allowing workspace-local hardlinks. Final all226
cases PASS; zero assertion failures or unresolved errors, zero skips. Initial
two infrastructure errors remain in the local log rather than being hidden.
Coverage includes new readiness nonpromotion/drift gates, actual native stream/
workspace host faults, five bounded SYNC positions and416 transaction fault
positions, source/geometry/seed/readback/resource/writer/package regressions.
Public reference build/link/image/source/Core gates and expected profile1
compiler refusal PASS. Documentation/diff checks PASS.

Exact-head CI is recorded in existing PR #42 after commit/push; no merge.
CI is source/host/build evidence, not normal physical acceptance or flash authority.

Counters for this complete offline pass: **DEVICE CONTACTS=0; SERIAL I/O=0;
FLASH WRITES=0; RTC WRITES=0; REBOOTS=0; DEVICE FILESYSTEM WRITES=0**.
**STOP after offline readiness qualification. DO NOT FLASH. DO NOT MERGE.**
