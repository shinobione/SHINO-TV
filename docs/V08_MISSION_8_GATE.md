# Mission 8 continuity continuation: PC client corrected, V2.1 gate running

1 October 2026, Europe/Paris. Continue the existing branch and Draft PR #39
from `977aed52ec9f631d532f0970faaef15fb32ebc50`. No new branch or PR.

**Current gate: HOLD before further firmware writes.** The corrected PC client
is undergoing repeated no-flash V2.1 Wi-Fi interruption/recovery and three-minute
freshness observations. No candidate reinstall, media request or ECDSA has occurred
in this continuity continuation. The reviewed 446144-byte candidate remains
byte-identical (`8dc18cf5135b4c7da8486d4f00bcc9b944d4bb5e4956a3f9dcbad7603ce47fea`).

Actual Windows Python 3.12 urllib reproduction proves a PC failure mode: network
failure inside a Digest retry bypasses the stock success-only retry-counter reset.
After enough interruptions, the long-lived opener stays at `retried > 5` and
rejects all later challenges even after the transport returns; a fresh opener
succeeds. Device challenge rotation alone succeeds. This proves a mechanism, not
the uninstrumented prior incident's exact cause.

The PC-only correction retains the endpoint, JSON schema, tray states/menu and
2/4/8/16/30-second backoff measured after attempt completion. Auth/network failure
discards the opener before the next scheduled attempt; three malformed replies
also refresh it. A per-client, exact-endpoint Digest handler reuses a successful
challenge, renews rejected/rebooted challenges, and resets urllib's recursion count
in `finally` after an interrupted exchange. The original recursion bound remains.
Steady successful POSTs avoid anonymous re-posts and shared device nonce rotation.
No global state, immediate retry loop or extra sender process is introduced.

Sanitized results distinguish accepted samples, route/timeout, refused/reset,
HTTP 401/403, other HTTP, malformed response, invalid sample and client error.
Optional diagnostics contain only the latest 64 attempts, client generations,
counters and timing; no credential, Authorization, nonce value, URL, exception
text or private path is logged. Existing configuration/autostart is unchanged.

The initial opener-refresh correction recovered automatically from two deliberate
45-second disconnections in the same tray PID, with accepted telemetry returning
after the backoff. Both attempted freshness soaks later encountered isolated
sender timeouts and a stale reading, then self-healed without restart. An observed
~8-second gap between accepted samples exceeded V2.1's 6-second TTL. This was not
staleness while HTTP 200 acceptance continued every ~2 seconds. Those failed
soaks remain preserved, and do not satisfy the reinstall gate. The endpoint-bound
Digest correction is now being tested in a new single process, loaded once before
the test. No process is restarted during network recovery.

Deterministic focused suite: 28 tests PASS, including actual urllib Digest hashes,
historical poisoned state, fresh device challenge, automatic refresh, backoff,
steady-state client retention, sanitized errors and retained legacy bridge contract.
The first PC-fix commit `0a3f2ed8007f742b64915a600c0ca4cef591d80c` passed all 11 jobs
in [PR CI](https://github.com/shinobione/SHINO-TV/actions/runs/36787400691) and
[push CI](https://github.com/shinobione/SHINO-TV/actions/runs/36787395364).
The latest Digest correction must pass its own exact-head CI and physical gate.
Firmware/native receiver/Core and candidate bytes remain unchanged. The native
scope guard adds only named companion files and their necessary contract test.

Only after repeated V2.1 recovery and immediate rollback/LCD/OEM checks pass may
the already-authorized candidate reinstall proceed. Then the complete three-minute
candidate baseline must pass before enrollment/ECDSA, followed directly by the
retained crypto/coverless/32/48 sequence. R3 PARTIAL; R10 BLOCKED. No Mission 9,
production key, new media sender or merge.

---
Historical physical attempt and recovery record at 977aed52 preserved below.

# Mission 8 engineering gate: BLOCKED on telemetry continuity

1 October 2026, Europe/Paris (30 September UTC). Existing branch
`feature/shino-tv-v08-stack-remediation`, Draft PR #39. Installed source
`432263feb139c7af2fecc0ecaa0c348b05304914`; pre-install clean documentation head
`979d2ff3900523a8a46d4fd86677326b515867c2`.

**BLOCKED — physical telemetry continuity failed during the boot baseline.**
The exact StackThunk candidate was installed and booted, but qualification stopped
before any media request, public-point enrollment or ECDSA. Three authenticated
metrics GETs reported `stale:true`; the owner confirmed the LCD numbers had stopped
updating. This is an observed continuity failure with unresolved cause, not a
physical crypto-stack overflow finding or a renewed static ROM UNKNOWN gate.

The documented OEM → retained V2.1 rollback completed. V2.1 reports 405,712 bytes;
dashboard and exact OEM recovery capability respond. Restarting the existing
SHINO // LINK metrics tray companion, with configuration/autostart unchanged,
restored fresh changing telemetry at 22:13:52–22:13:57 UTC. The owner confirmed restored LCD orientation and all four updating cards
are normal, without artifacts. Qualification did not resume after the failure. R3 remains PARTIAL,
R10 BLOCKED; no production key, media sender, Mission 9 work or merge.

SHINO uses its private AP at `192.168.4.1`. The historical OEM LAN address
`192.168.1.70` is never a fixed assumption: after each factory return, the observed
device MAC `c4:d8:d5:10:7e:f0` was matched in LAN neighbors, and live `/v.json`
confirmed `SmallTV-Ultra` / `Ultra-V9.0.44` before `/update`. The actual firmware
form used multipart field `firmware`, POST to its current `/update` URL.

| Physical phase | Result |
|---|---|
| Immediate rollback rehash, V2.1 dashboard/metrics/OEM, owner LCD | PASS at 22:02:51–22:02:56 UTC |
| V2.1 → OEM factory return | HTTP 200 staged, 22:03:13–22:03:24 UTC |
| Live OEM model/version and update form | PASS at 22:04:01 UTC; observed MAC reachable |
| OEM → exact StackThunk candidate | HTTP 200 Update Success, 22:04:13–22:04:21 UTC |
| Candidate AP/dashboard/OEM return | PASS; actual running bytes 446,144 |
| Boot with media untouched | Unenrolled, zero crypto allocations/calls, no body/image/staging |
| Candidate LCD | Owner confirmed correct orientation/four updating cards initially |
| Real PC telemetry POST | HTTP 200 RAM_SAMPLE_ACCEPTED at 22:06:51 UTC |
| Three-minute idle baseline | NOT COMPLETED: client read auth failed after ~5 seconds of baseline |
| Later telemetry continuity | FAIL: stale at 22:08:22, 22:08:23, 22:08:25 and 22:09:40 UTC; owner confirmed frozen numbers |
| Crypto/authentication/coverless/32/48 | NOT RUN; zero media requests, key checks, ECDSA calls or allocations |
| Candidate → OEM recovery | HTTP 200 staged, 22:10:46–22:10:57 UTC |
| Recovery OEM rediscovery | First bounded GET timed out at 22:11:12; live identity/form passed at 22:11:38; no write retried |
| OEM → exact retained V2.1 | HTTP 200 Update Success, 22:11:49–22:11:57 UTC |
| Restored V2.1 telemetry | Fresh changing device readings after restarting existing metrics companion |

All four application writes were single attempts with exact locally rehashed
bytes; all succeeded. Each supported updater scheduled an intentional reboot.
The candidate boot identifier remained `3667675469` with monotonically increasing
uptime before rollback. Reset reason `4` was reported (pinned SDK software restart);
no unexpected reset, watchdog, boot loop or canary event was observed. Continuation
watermark reset actions repaint instrumentation; they do not reboot the device.

The first local client stop was HTTP 403 because it omitted authenticated GET `/`
to obtain the required browser metrics cookie. Source and independent live reads
confirmed that client precondition error, with unchanged boot/no media; the helper
was corrected and its original stop record retained. A later protected GET failed
with HTTP 401 `digest auth failed`; subsequent independent GETs succeeded but
telemetry was stale. Firmware, diagnostic-client Digest behavior and the existing
sender have not been isolated as the cause. Restoring V2.1 did not by itself
restart continuous metrics; a single real sample succeeded, and restarting the
already running metrics companion restored continuity. That recovery does not
qualify the candidate or establish a firmware-only regression.

| Candidate observation before rollback | Measured value / limit |
|---|---|
| Minimum free continuation stack after pinned phase repaint | 2,080 bytes of 4,096 |
| Minimum free heap across recorded diagnostic minima | 16,336 bytes |
| Minimum largest free block across recorded diagnostic minima | 16,240 bytes |
| Maximum recorded diagnostic fragmentation | 22% |
| Maximum observed media-owner poll / service interval | 34,886 / 65,582 microseconds |
| Secondary size / allocations / references / measured use | 6,200 / 0 / 0 / NOT EXERCISED |
| ECDSA/key checks/SHA timing | Zero calls; latency NOT MEASURED |
| Allocation/busy/canary failures | 0 / 0 / 0 reported |
| Receiver pending/body/staged/image/challenges | false / 0 / 0 / 0 / 0 |

These are bounded boot/legacy observations under diagnostic HTTP load, not a
completed idle soak, whole-firmware stack proof, heap trend across transactions
or crypto high-water proof. In particular, unallocated secondary usage `0` and
numeric margin `6200` do not constitute measured crypto margin. No image cycle
was completed, so replacement leaks/fragmentation remain unqualified.

Private candidate: BIN 446,144 bytes, SHA-256
`8dc18cf5135b4c7da8486d4f00bcc9b944d4bb5e4956a3f9dcbad7603ce47fea`;
ELF SHA-256 `34e67a4d3da022fd5d9581628b8e8aa51c2fa0e4273d491a73e910dd1868205e`.
Text/data/BSS: 439207/2840/32704. Authority/Ingress/Receiver: 2104/1432/1120.
Main stack 4096; secondary 6200. Lifecycle B frees secondary crypto before
body/JSON/image; explicit receiver peak 9256 and previous-image+crypto 10808
exclude SDK/TCP/allocator overhead and remain physically untested.

Retained local rollback artifacts are unchanged:

| Image | Bytes | SHA-256 |
|---|---:|---|
| V2.1 review-003 | 405712 | `3252ba5cd1f85683945d4d9a87ce49118568c0977605debc089267f54d7f3b0e` |
| OEM V9.0.44 application | 494144 | `a6421f5bfee7860d97bed26620c346b8008f503e513702d4bfdf6e01010a7718` |
| Manufacturer ZIP | 349377 | `cfbef50754ec552f9791878931c5f3643734de15f3c81cebdecf7ce05b28230f` |

Kit: `C:\Users\jerry\SHINO-PRIVATE\review-003`. The recovery was exercised
successfully for this responsive application. This is application-only rollback;
no full owner flash/filesystem restoration, power-cut safety or nonbooting rescue
is established. Private images, credentials, policy, one-shot packets and device
controllers remain ignored/local. No additional firmware writes followed recovery.

Source/host/linked gates remain PASS: both focused OEM configurations pass
1065 checks with zero failures, 10207 wire cases and 37 profile cases agree;
202 signed packets / 190 receiver records were checked offline. Clean source
head `432263feb139c7af2fecc0ecaa0c348b05304914` rebuilds the same private bytes.
Pre-install head `979d2ff3900523a8a46d4fd86677326b515867c2` passes all 11 jobs in
[PR CI](https://github.com/shinobione/SHINO-TV/actions/runs/36781108025) and
[push CI](https://github.com/shinobione/SHINO-TV/actions/runs/36781102151).
CI proves retained software checks; physical qualification remains BLOCKED.

---
Historical records preserved below; their gates and zero-contact statements describe those earlier runs.

# Current Mission 8 / 8R engineering gate

**BLOCKED — complete native stack prerequisite remains UNKNOWN.** Mission 8R
implements a separate Proof phase and evaluates unmodified pinned m31 crypto.
The known EC chain falls to 2,224 bytes; the actual ROM multiplier body and
full owner/receiver bounds are still unproved. No installation is authorized
by this result. Local focused regressions pass; retained CI is configured to reproduce the
blocked static gate and cannot establish physical qualification. M8R device
contacts/writes are zero; Parts D-live, E and F are NOT RUN. R3 remains PARTIAL,
R10 BLOCKED. Historical PRs #29–38 remain preserved. The physical authorization
persists, conditional on complete static and rollback gates passing; no new
mission is required to resume once safe. See [M8R report](V08_MISSION_8R_STACK_REMEDIATION.md)
and [evidence](V08_MISSION_8R_STACK_EVIDENCE.json).

---
Historical Mission 8 record (preserved):

# Mission 8 review gate

30 September 2026, Europe/Paris. Exact parent
`84129daa7359c73e738272b1c01131b3292dc315`.
Branch `feature/shino-tv-v08-device-qualification`.

**Final engineering status: BLOCKED before installation.**
The actual linked ECDSA/SDK path reserves at least **4,384 bytes** against a
**4,096-byte** continuation stack. The nested receiver + crypto path is at least
**5,904 bytes**, excluding owner/loop/entry overhead. This is a concrete static
fit failure, not an arbitrary heap threshold or an observed physical crash.

| Gate | Result |
|---|---|
| Exact clean start / separate branch | PASS at Mission 7 head |
| Mission 7 report/resource/matrix/gate read | PASS; historical evidence unchanged |
| PRs #29–37 | PASS live verification: all preserved OPEN/Draft |
| Actual installed lineage | Consistent with retained V2.1 review-003: exact size, matching Digest credentials, heap schema and capabilities; no device SHA/version label exposed |
| Physical baseline LCD / four metrics | PASS limited baseline: direct owner observation plus two fresh changing device GET readings |
| Local rollback artifacts | PASS: exact V2.1 and OEM bytes/hashes verified; no modification |
| Current OEM factory-return capability | PASS read-only: exact pinned identity and `write_enabled:true`; no rollback write |
| Instrumented Mission 8 candidate | NOT BUILT; early linked-stack precondition failed |
| Inherited app flash fit | Arithmetic PASS, not final candidate fit or OEM acceptance |
| Inherited native stack fit | **BLOCKED** from actual linked prologues, call edges, SDK assembly and continuation size |
| Installation / normal reboot / recovery | NOT RUN; stopped before first write |
| Several-minute candidate baseline | NOT RUN |
| Authentication-only physical qualification | NOT RUN; no ESP8266 ECDSA latency/body-denial proof |
| Coverless / 32x32 / 48x48 repetitions | NOT RUN; zero physical transfers |
| Heap/fragmentation/allocation/cleanup/UI margin | HOLD for future safe candidate; existing saturated V2.1 observer is not candidate evidence |
| R3 freshness | PARTIAL; no persistent freshness primitive introduced |
| R10 production provisioning | BLOCKED; no production private key/provisioning/sender introduced |
| Merge / public deployment / Mission 9 | Not performed |

This mission made its first authorized physical **GET-only** device contact.
It did not qualify a native media receiver on hardware and is not a production
GO. Local full links and the static negative gate are reproducible. The new CI
job executes the Mission 8 review head and expects proof of the **BLOCKED**
static result; green CI means the stop evidence is reproducible, not safe to
flash. Mission 7's own lab is preserved at its exact historical head because its
runner enforces Mission 7's allowed diff. All other retained jobs remain.

See [device qualification](V08_MISSION_8_DEVICE_QUALIFICATION.md),
[runtime/resources](V08_MISSION_8_RUNTIME_RESOURCES.md),
[recovery log](V08_MISSION_8_RECOVERY_LOG.md),
[sanitized device evidence](V08_MISSION_8_PREFLIGHT_EVIDENCE.json), and
[linked-stack evidence](V08_MISSION_8_STACK_EVIDENCE.json).

No automatic reviewer approval or attestation is fabricated. Stop at this Draft
review gate. The blocker requires an explicitly reviewed stack/memory change
before resuming instrumented build and physical qualification. The current
SmallTV, rollback packages, frozen V2.1 source, production firmware, SHINO LINK
and earlier PRs/evidence remain preserved.
