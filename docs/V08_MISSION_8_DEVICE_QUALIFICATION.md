# Mission 8 continuation through Mission 8R

**Current gate: BLOCKED before installation.** Mission 8R starts at exact M8
head `5179eb04ea51c2a92c7f796f07ebb963e2167e00`. The phase split and pinned m31
candidate reduce the accounted EC chain to 2,224 bytes, but complete owner,
ROM multiplier and receiver bounds remain UNKNOWN. There was no M8R device
contact. The earlier physical LCD confirmation and GET evidence below remain
historical baseline evidence; no candidate physical qualification is claimed.
The already-authorized physical sequence remains conditional on all static
and immediate rollback gates passing. See [M8R report](V08_MISSION_8R_STACK_REMEDIATION.md).

---
Historical Mission 8 record (preserved):

# Mission 8 physical SmallTV qualification: stopped before installation

30 September 2026, Europe/Paris. **BLOCKED at the pre-installation stack gate.**
Exact clean starting head: `84129daa7359c73e738272b1c01131b3292dc315` (Mission 7).
Separate branch: `feature/shino-tv-v08-device-qualification`.

The user authorized controlled Wi-Fi contact and conditional installation for
this mission. That supersedes earlier missions' no-device authorization limits;
it does not waive Mission 8's static and rollback prerequisites. USB-C remains
power only. No UART, JTAG, soldering, repartitioning, bootloader modification,
production credentials, production sender, public deployment or merge occurred.

## Phase 0: provenance and actual installed baseline

The tree was clean before branch creation. All four Mission 7 reports were read.
Live GitHub inspection confirmed PRs #29–37 remain OPEN/Draft at these heads:

| PR | Preserved head |
|---|---|
| 29 | `f578e11e19b4f7c7a4e78b8f6a0a7c2b4a09f702` |
| 30 | `c5cac0ab87f0ade5bf1e2bd62934b61cedc1a4c5` |
| 31 | `273b386070802cc6aba0a16c8cd8b5a6dc7abf00` |
| 32 | `7cf56a6c0466a07f1d738f97c6ba3e049355ca98` |
| 33 | `80ad35766528a3bf02b697a6ddebf70f852a9f0a` |
| 34 | `799e69a17730c117e1c599912b0b57919d64cea2` |
| 35 | `7d40df9f69bead1aa3a8c7ebd88dbfa0121968e0` |
| 36 | `4d6180959b843c64e92b72425134c2dfc6688c88` |
| 37 | `84129daa7359c73e738272b1c01131b3292dc315` |

Frozen known-good source is V2.1 review-003:
`8cef03012ae4a4864d69cbe20e02f141a36e2d54`. Its retained private manifest,
exact binary and matching-build Digest credentials were identified locally.
Source review confirms a read-only native OTA manager and separate conditional
OEM-only factory return; there is no generic SHINO upload route.

Actual GET-only device inspection ran 19:57:11–19:57:17 Europe/Paris
(17:57:11–17:57:17 UTC). Windows was connected to the SHINO WPA2 private AP,
chip suffix `107ef0`, device `192.168.4.1`. An initial unauthenticated status GET
returned 401 with the expected `SHINO-FirstBoot` Digest realm. The authenticated
preflight completed six application GETs, with normal Digest retries: dashboard,
status, metrics, factory-return, OTA capabilities, and a second metrics read.
All six completed with HTTP 200. No write, reboot, media or endpoint-discovery
request was sent. Credentials and cookies stayed local and are absent from evidence.

| Before-installation observation | Actual evidence |
|---|---|
| Mode | `FIRST_BOOT_BRIDGE`; `RAM_ONLY` metrics; program-flash browser UI |
| Running application | **405,712 bytes**, matching retained review-003 |
| Physical flash | **4,194,304 bytes** reported by device |
| Free sketch space | **638,976 bytes**; linker report, not OEM acceptance proof |
| Browser dashboard | Authenticated HTML returned, 4,735 bytes, SHINO marker present; no browser-render claim |
| Metrics | Fresh, received, GPU available; all four values changed between reads |
| Physical LCD | Owner directly confirmed correct orientation, four visible updating CPU/GPU/RAM/GPU TEMP cards, no corruption, mirroring, artifacts or abnormal behavior |
| OEM return | `write_enabled:true`; exact 494,144-byte V9.0.44 application/hash |
| Native update manager | `READ_ONLY_DESIGN_GATE`; writer and upload route both false |
| Firmware/version label | No installed version label/source SHA/flash SHA-256 exposed by these diagnostics |

Installed identity is **consistent with review-003 lineage**, using matching
credentials, exact size, heap schema and capabilities. It is not an independent
rehash of installed flash. The OEM version in factory-return describes the
**rollback target**, not the currently running firmware. No material installed
lineage discrepancy was observed. Baseline details and sanitized readings:
[preflight evidence](V08_MISSION_8_PREFLIGHT_EVIDENCE.json).

| Metric | First GET | Second GET, approximately 5 seconds later |
|---|---:|---:|
| CPU usage | 7.8 | 5.0 |
| GPU usage | 39 | 42 |
| RAM used, GB | 10.74 | 10.82 |
| GPU temperature, C | 56 | 55 |

Both reads were nonstale with six-second freshness. This is real device GET
evidence of active existing telemetry plus the owner's LCD observation, not a
several-minute candidate soak or an exhaustive browser acceptance test.

## Stop and sequence accounting

Before building an activated diagnostic candidate, pre-installation inspection
resolved Mission 7's compiler-frame concern into a concrete linked-stack blocker.
The actual native verifier/SDK assembly has a reachable **4,384-byte** nested
path against the Core's **4,096-byte** application continuation stack, even
before HTTP receiver frames. Including the receiver gives at least **5,904 bytes**.
See [runtime/resources](V08_MISSION_8_RUNTIME_RESOURCES.md).

This is a static engineering inference from linked machine code and actual
call edges. It is not an observed physical reset or target high-water reading.
An unchanged-path instrumented activation cannot be treated as installable.
No new instrumented Mission 8 candidate was built, activated or installed;
the unchanged guarded Mission 7 links were reproduced to verify the stop.
The planned Phase 2 instrumentation and Phase 3 final candidate comparison are
therefore incomplete. The blocker was checked early to avoid constructing and
installing an unsafe activation. It must be resolved in reviewed engineering work
before this mission can resume to an exact instrumented candidate.

| Stage/test sequence | Count/result |
|---|---|
| Starting clean-head and PR preservation checks | PASS |
| Rollback artifacts and original ZIP hashes | PASS; files not modified |
| Authenticated application diagnostic GETs | 6 successful completions |
| Display observation | 1 direct owner confirmation |
| Guarded inherited full native links | 2 environments passed locally |
| Linked nested-stack gate | BLOCKED, reproducible offline |
| Activated Mission 8 build / installation / reboots | 0 / 0 / 0 |
| Candidate several-minute boot baseline | NOT RUN |
| Gate 1 unknown/expired/used/wrong operation/key/revoked/header-only cases | 0 physical cases |
| Coverless, Abort and interrupted transactions | 0 physical cycles |
| 32x32 valid/adversarial/replacement transfers | 0 physical cycles |
| 48x48 nine-tile/adversarial/replacement transfers | 0 physical cycles |
| Recovery writes | 0 |

No physical ECDSA latency, media memory margin, cleanup, body-read denial,
watchdog safety or image ownership/display qualification is claimed.
Existing production firmware, sender and all historical evidence are preserved.
