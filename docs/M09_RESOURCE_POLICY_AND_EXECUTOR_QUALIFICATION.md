# Mission 9 Phase K — resource policy and single-attempt executor qualification

> **Phase L continuation, 6 October 2026:** the separate
> [physical session runner](M09_SINGLE_ATTEMPT_PHYSICAL_RUNNER.md) supplies
> explicit-port/fresh-ROM acquisition under offline source/fake-serial
> qualification. The K executor, all firmware and frozen candidate are unchanged.
> K's "not implemented" acquisition statements below are preserved dated history.
> L grants no physical authority; resource physical remains HOLD/NOT_RUN,
> overall PARTIAL/HOLD, both normal gates NOT_RUN. No device operations occurred.

6 October 2026. **OFFLINE ONLY — NO DEVICE CONTACT.** Continuity verified:
clean `feature/shino-tv-m9-flash-layout-liberation` at
`063553fd70772527edc13168e59c83088453dd1a`, existing
[PR #42](https://github.com/shinobione/SHINO-TV/pull/42) Draft/open/unmerged.
[Roadmap](ROADMAP.md) records the new owner decision before implementation.
This is an engineering review and host/source qualification, not a fabricated
human attestation or physical safety proof. No port is opened or enumerated.

## Frozen candidate and gates

| Gate | Phase K result |
| --- | --- |
| PHASE_K_RESOURCE_POLICY_GATE | **PASS/OFFLINE** |
| PHASE_K_SINGLE_ATTEMPT_EXECUTOR_GATE | **PASS/OFFLINE** |
| PHASE_K_FROZEN_CANDIDATE_IDENTITY_GATE | **PASS/OFFLINE — retained local file rehashed** |
| PHYSICAL_RESOURCE_THRESHOLD | **DEFINED_SCOPED_ACCEPTANCE_POLICY** |
| MOUNT_PROBE_RESOURCE_PHYSICAL_GATE | **HOLD / NOT_RUN** |
| MOUNT_PROBE_PHYSICAL_GATE | **PARTIAL / HOLD** |
| NORMAL_PROFILE_LITTLEFS_MOUNT_GATE | **NOT_RUN** |
| NORMAL_PROFILE_RUNTIME_GATE | **NOT_RUN** |

Frozen J source `7779248082975472ce5f62edf1613d8288b75b6e`, BIN **411136 B**,
SHA-256 **`2ce2fa8da00de5c60109d0675c7bcf58ab41df2138d913b607fde25994e5a835`**,
target **0x000000**. Payload **0x000000..0x0645FF**, end **0x064600**;
sector-rounded destructive extent **0x000000..0x064FFF / 413696 B**,
end **0x065000**. Whole protected interval **0x065000..0x3FFFFF / 3780608 B**.
FS **0x200000..0x3F9FFF / 2072576 B**. Identity was checked against the retained
regular local BIN including image checksums/Arduino CRC; it was not rebuilt,
substituted, published or installed. [103 LF-normalized tracked firmware pins](../tools/m9_phase_k_sources.json)
prove no firmware change; no default/probe local build is relevant or performed.
Unchanged J linked/frame results remain dated evidence, not new physical data.
The installed uninstrumented H/Phase I candidate remains separate and untouched.

## Actual workload and evidence audit

Scope is **RESOURCE_POLICY_SCOPE = M9_PROFILE2_INSTRUMENTED_MOUNT_PROBE_ONLY**,
and the exact frozen candidate above. Reviewed source:
[main](../firmware/src/main.cpp), [bridge](../firmware/src/boot/FirstBootBridge.cpp),
[probe](../firmware/src/boot/M9LittleFsMountProbe.cpp),
[stream validator](../firmware/include/boot/M9ProbeStream.h),
[resource adapter](../firmware/src/boot/M9MountProbeResources.cpp),
[observer](../firmware/include/boot/M9ResourceObserver.h),
[bounded JSON](../firmware/include/boot/M9ResourceJson.h) and profile/env guards.

Private WPA2 AP only (max two AP stations), one port-80 server, Digest controls,
four RAM telemetry cards, accepted telemetry body 16..384 B and six-second TTL.
Read-only LittleFS single mount/exact inventory, 256-byte streaming **stack**
buffer, BearSSL SHA-256 context <=128 B, read-only adapter <=512 B, and the
scalar observer. Resource response has exact maximum 1157 B; separate fixed
768-byte stack buffers, compiler frames 800/944 B. These stack buffers are not
new heap-allocation requirements. Core HTTP/header/TCP and ArduinoJson still
allocate; this is not an allocation-free or hostile-traffic safety guarantee.
No media receiver/image arena/ECDSA, Home-LAN STA, OTA writer, SecureStorage,
ConfigManager or EEPROM migration is reachable in this profile.

Audited physical records (point observations, sampled extrema and prospective
budgets kept distinct; no deduction of a new measurement by subtraction):

| Exact record | Observed/budget values | Meaning for K |
| --- | --- | --- |
| [M8 device qualification](V08_MISSION_8_DEVICE_QUALIFICATION.md), current focused table and preserved new-boot table | Transient heap/block 11768/10176; settled 18736/16504/12%; continuation 1728. Earlier extrema 11768/9400, frag 32%, continuation 1680 | More complex receiver survived exercised paths; not universal minima |
| [8R remediation](V08_MISSION_8R_STACK_REMEDIATION.md), current table, preserved earlier checkpoints, historical native-resource table | 1728 current; historical 1680 and 1776/4096; block 10592 / frag 29% in historical auth/crypto subset | Different windows/crypto/secondary-stack ownership; never combined into one synthetic physical sample |
| [M8 gate](V08_MISSION_8_GATE.md), current equal-ownership paragraph and held 48 budget | Settled block 16504, transient frag maxima 17/19%; prospective heap 14904/block 11304 includes 4096 reserve, necessary but insufficient | Concrete reserve precedent, not an applicable M9 allocation calculation |
| [M8 runtime resources](V08_MISSION_8_RUNTIME_RESOURCES.md), current comparison | Old settled heap18528..18944/block16768..17568; new 18736/block16504; no equal-state causal allocator claim | Supports requiring substantial clean headroom rather than borrowing transient troughs |
| [P1 owner gate](home-lan/OWNER_INSTALL_GATE.md), refreshed read-only evidence; [installation receipt](home-lan/DEVICE_INSTALLATION_2026-10-02.md), native measurement table | M8 lineage point19592/16672/1728; post-attempt18584/16672/11%/1728; inherited11568/10296 minima | Neither installed P1 resource proof nor fresh M9 minima; no P1 threshold transferred |
| [Phase I receipt](M09_MOUNT_PROBE_PHYSICAL_EVIDENCE.md), mount/runtime tables | Probe mount/inventory heap36144; minima29744 initially,27808 after180s; functional/stale/recovery PASS | Closest workload evidence; block/frag/continuation unknown, so not a resource PASS |
| [Phase J receipt](M09_MOUNT_PROBE_RESOURCE_INSTRUMENTATION.md), windows/paired receipt/threshold audit | +80 static RAM, +3708 flash, max individual944; physical threshold REVIEW_REQUIRED at J | No physical instrumented values. K supersedes next-work policy only; all J history retained |

## Explicit scoped acceptance criteria and rationale

These are **new conservative engineering acceptance criteria**, not numbers
historically approved for M9, not universal ESP8266 floors, not a proof of every
allocator transient or whole-call-chain capacity. The exact engineering choices
and extra reserves are explicit here; no silent adoption or human identity/date
is inferred. They can reject this simpler probe even if an older, different
workload passed below them. A result below any criterion means HOLD/STOP, never
lower the floor to fit the observations.

| Criterion | Numeric policy | Exact rationale and scope limit |
| --- | ---: | --- |
| M9_PROBE_MIN_FREE_HEAP_BYTES | **20480** | Take the documented larger media prospective14904 including its 4096 reserve, require another full 4096 reserve (19000), then round UP to five 4096 units (20480). This deliberately exceeds the historical media budget and transient 11768/13200 observations. Closest simpler Phase I sampled 27808 exceeds it by 7328, but that does not predict J will pass. Known probe leaves are much smaller; SDK/HTTP allocation uncertainty retains this additional slack. Not a transferred media/OTA budget. |
| M9_PROBE_MIN_LARGEST_BLOCK_BYTES | **16384** | Require more than documented prospective 11304 plus another 4096 contiguous reserve (15400), rounded UP to four 4096 units. Also exceeds physically exercised transient 9400/10176/10592 blocks; near documented settled 16504+ blocks despite excluding retained images/arena/crypto. A fresh measured J minimum must meet it. No future large allocation is authorized by this reserve. |
| M9_PROBE_MAX_FRAGMENTATION_PERCENT | **25** | Explicit Core L2 concentration criterion: require sqrt(sum(free hole size^2))/total-free >=0.75. Current complex M8 clean 12% and exercised 17/19% fit; historical 29/32% do not. The simpler no-image/no-crypto workload must maintain the stricter 75% concentration reserve throughout sampled windows. Largest-block check remains independent. This is not the heuristic100*(1-largest/free), nor proof that all transient fragmentation was captured. |
| M9_PROBE_MIN_CONT_STACK_FREE_BYTES | **2048** | Require at least HALF of pinned 4096 continuation stack to remain, versus physical 1680/1728/1776 in more complex historical workloads: extra 368/320/272 B above those observations. This is an explicit substantial-fraction reserve choice, not a compiler-frame conversion. Apply to both mount and runtime windows; new nested status frames must actually fit and leave this margin. Passing media numbers cannot qualify the new JSON call chain. |

All four apply to post-probe snapshot, runtime latest/min/max, and stack starts/
minima as appropriate. The old **minimum_observed_free_heap** plus mount/inventory
heap fields must also satisfy 20480: this denser observer catches some transients
missed by the one-second sampler. Low/high structural bounds remain independent.
No criteria authorize normal profile, media/image/ECDSA, Home-LAN, OTA, hostile
traffic or future product workloads. Any source/workload change needs new review.

## Fail-closed evidence evaluator

[m9_resource_policy.py](../tools/m9_resource_policy.py) reads local JSON only.
Both start/end snapshots must be true/enabled/valid, zero rejected samples,
zero blocked writes, attempted/autoformat-disabled/mounted/inventory/config true,
writer false, exact 24 files/181402 B and FS geometry. Strict integer types reject
booleans/nulls/negative/overflow. Heap/block/frag must be structurally consistent;
stack <=4096, aligned4 and monotone within windows; no unknown zero sentinel.
Cached minima/maxima must agree with latest values. Thresholds apply inclusively.

Count must advance (saturated nonadvancing counters fail); mount/window fields
must remain identical across the same boot; minima cannot increase, maxfrag
cannot decrease. Separate supplied owner observations must explicitly establish
same boot, Digest status, >=180 s stable LINK, successful stale/recovery, no reboot
and no display corruption. Missing/unknown facts fail. A local evaluator PASS
only validates the **supplied evidence**; it cannot prove authenticity, completeness,
same-unit identity or close the physical gate. Preserve original captures and
owner observations separately. Sparse heap snapshots cannot prove unseen minima;
continuation watermark is the window high-water, with the J measurement limits.

## Pinned retry finding and supported API choice

Exact installed **esptool 5.4.0 / esp-pylib 1.1.5 / pyserial 3.5** audited locally;
complete53-file esptool manifest/digest reused from
[m9_executor_sources.json](../tools/m9_executor_sources.json), including pinned v2
JSON binary. Package digest `e5f3db49216d341df8afe2c36a1e51d6b1c07abbe27561f2ba06c2c448f604d0`.
Stub release v1.2.2/revision `23959b780454adf885916d42f2274ec648e96a94`;
library `d61983fa4d1f66b9c088608c1f702ad877121279`; all seven prior source pins pass.

- `loader.py:409` fixes WRITE_FLASH_ATTEMPTS=2. `cmds.py:1771..1863` saves the
  original image and loops. `SerialException` during Begin/data triggers port
  close/open, default connect/reset, stub reload and image restart if attempts
  remain. Some erase/programming may already have occurred. Finish/MD5 happen
  outside that retry loop, with their own lower command behavior.
- `loader.py:117,1198..1219`: write_block_attempts defaults3; `flash_block`
  resends on FatalError, including uncertain timeout/malformed/status failures.
  A supported config can reduce this packet count, but does not disable the
  separate fixed whole-write loop. No supported high-level write_flash argument
  or CLI option disables that whole-loop contract; mutating internals is not the
  selected qualification. `--connect-attempts1` only bounds initial connection.
- Public low-level `check_command` / `command` (`loader.py:571..702`) sends ONE
  request; its up to 100 response-read loop consumes unmatched sync responses and
  does not resend. The adapter uses this API, bypassing both retrying wrappers.
- Stub command_handler: Begin 225..263 starts the first conditional sector erase;
  data 423..441 ACKs before post-processing 1059..1063. Programming 287..311 clamps
  padded wire data to remaining payload and advances internal offset. No data
  sequence deduplication/whole-transaction retry is implemented there. Therefore
  repeating an ambiguously acknowledged block is not proven idempotent.
  Error is propagated to the next command. Target flash 83..89 invokes ROM write
  once; library handles bounded chunks/erase readiness, no whole-image restart.
  Opaque ROM-internal electrical programming behavior is not host retry proof.

Stock CLI with the J flags cannot meet strict single-attempt acceptance. The
selected tool is [m9_single_attempt_app_write.py](../tools/m9_single_attempt_app_write.py).
Its **CLI only audits local files/source and prints**: no port/open/connect/reset
arguments, no subprocess executor. `SingleAttempt` consumes its session before
preflight; checks external exact frozen hash, regular file, size/image/extent and
separate exact-operation GO before invoking a transport factory. File bytes are
cached before contact; mutable pathname cannot substitute later write bytes.
The GO string is a fail-closed input guard, not proof of human consent; the
future operator must separately establish actual exact-operation owner approval.
The injected transport factory is trusted/test plumbing, not an authorization
boundary or an alternative to the reviewed pinned production adapter.

Future `PinnedStubTransport` accepts an already connected **fresh ESP8266 ROM**,
checks actual chip magic and JEDEC 4 MiB before RAM stub upload; rejects existing
unknown stub, other class/chip/capacity. It loads only pinnedv2, with a private
['2'] lookup (no v1 fallback/plugin), verifies exact returned stub/capacity and
sets RAM SPI geometry. It never opens/closes/reconnects a serial port. Stock RAM
stub upload can have RAM-packet retries; these precede any flash Begin and do
not replay a flash transaction. No claim of zero retries for every RAM/read
operation is made. Fresh-ROM/session acquisition and physical DTR/RTS isolation
remain future separately reviewed/authorized integration; they are not built
into a runnable physical CLI in K.

The qualified flash transaction is **ONE Begin**, exactly **101 unique 4096-byte
data packets** with sequence 0..100, **ONE Finish** with pinned no-reboot parameter,
then one MD5 read barrier. Begin declares 411136 B at zero, not padded 413696 B;
last wire block 4096 contains 1536 payload +2560 FF. Pinned stub clamps programming
to payload end 0x064600 and erases only through 0x064FFF. No compression, encryption,
header rewrite, erase-all/FS write, reboot, recovery write or rollback. Any
exception, interruption or mismatch propagates STOP; no cleanup Finish is sent
after failed data, no repeated command/reconnect/second Begin, no second call on
the consumed session. MD5/ACK success is insufficient: full POST/exact SHA bytes
and protected comparison still mandatory before first boot.

## Validation and CI evidence boundaries

**189 local tests PASS, zero failures/errors/skips**: 186 across all Mission 9 suites,
Phase K policy/executor tests and first-boot/dashboard/policy/OEM regressions.
Three additional legacy/probe route parity/mutation checks also PASS.
Host compiler fixtures use MSVC locally and g++ in existing Linux CI. Final
exact-head CI links are recorded in PR #42 after completion.
Harness uses synthetic bytes/owner facts, never the retained image as a fake
hardware target. Success:1 Begin/101 unique blocks/1 Finish; clamping/padding exact.
Faults at Begin, EVERY 101 data boundary, Finish and MD5, across timeout/OSError/
ValueError/KeyboardInterrupt: 416 injected faults, zero resend/second transaction.
Also wrong hash/size/nonregular file/GO before factory, wrong chip/flash/stub before
Begin, invalid package/config/source pins before import, MD5 mismatch, consumed
session, policy missing fields and inclusive-boundary failures. Real pinned
check_command/command/SLIP write tested with fake serial for FatalError,
SerialException, timeout, failed status and unmatched replies: one request only.
Fresh ROM chip/capacity/unknown-stub guards and v2-only selection tested with
synthetic methods on actual loader classes; no real transport is instantiated.

K CI publishes only two exact safe JSON reports (policy/source). It checks 103
firmware pins and package/stub pins, but has no retained private candidate: its
identity gate is **NOT_READ_BY_THIS_RUN**. Local rehash is the separate identity
PASS. Existing J CI's disposable builds/FS checks are not the retained frozen
candidate/FS; no substitution, private binary publication or installation.

## Future qualification packet — PRINT ONLY

Only after BOTH offline prerequisite gates PASS, the audited tool prints the
packet for the exact frozen candidate. No authority is granted by this document.

1. Fresh same-unit ROM/chip/4MiB qualification, continuous power/GPIO0 LOW and
   physical DTR/RTS isolation; fresh private independent full 4 MiB PRE.
2. PRE FS slice equals frozen Stage-2 bytes; candidate exact rehash; separately
   verified recovery captures/rollback authority; explicit owner GO for exact
   image/hash/operation. No GO is inferred from this offline milestone.
3. Same fresh ROM session, pinnedv2-only adapter and single-attempt core; one
   application-only target-zero transaction, no compression/header rewrite/erase-all.
   GPIO0 LOW through PRE/write/full POST; no automatic retry/reboot/rollback.
4. Independent full POST before first app boot: exact frozen payload at zero,
   **POST[0x065000:0x400000] == PRE** continuously, including lower arena/FS/tail.
5. Powered RTC 0/0 verification, GPIO0 release/existing RST, normal app boot;
   exact mount/inventory/config/no-write status; valid advancing diagnostics.
6. Mount/post-probe thresholds; then 180 s stable LINK/stale/recovery with no reboot
   or corruption; final status/count/minima/maximumfrag remain scoped-policy PASS.
   Owner authenticity and physical gate review remain separate from local JSON PASS.
7. Any missing/uncertain fact or operation = STOP; no automatic repeat/recovery.
   Full normal-profile mount/runtime remain NOT_RUN; no merge or activation.

```text
PHASE K DEVICE CONTACTS = 0
PHASE K SERIAL I/O = 0
PHASE K FLASH WRITES = 0
PHASE K RTC WRITES = 0
PHASE K REBOOTS = 0
PHASE K DEVICE FILESYSTEM WRITES = 0
```

**STOP after Phase K. DO NOT FLASH. DO NOT REBOOT CURRENT SMALLTV.
DO NOT ACTIVATE NORMAL PROFILE. DO NOT MERGE PR #42.**
