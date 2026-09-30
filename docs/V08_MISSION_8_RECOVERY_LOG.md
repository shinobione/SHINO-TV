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

# Mission 8 installation and exercised V2.1 recovery

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

# Recovery status after Mission 8R

**No M8R device contact, installation, write, induced reset or recovery.**
Local review-003 V2.1/OEM files and manufacturer ZIP were rehashed unchanged
at 19:11:50 UTC / 21:11:50 Europe/Paris on 30 September 2026. Existing paths
were reused; no credentials or artifact contents were published. Immediate
live Part D revalidation is NOT RUN because the complete stack gate is
UNKNOWN. Earlier live OEM-return capability below is historical, not a new
availability claim. See [M8R gate](V08_MISSION_8R_STACK_REMEDIATION.md).

---
Historical Mission 8 record (preserved):

# Mission 8 rollback preflight and recovery log

30 September 2026, Europe/Paris. **No installation, device write, reset or recovery
attempt was performed.** Existing V2.1 review-003 remains the running baseline.

## Positively identified retained packages

Files below were read and SHA-256 hashed locally against the retained
`C:\Users\jerry\SHINO-PRIVATE\review-003\REVIEW-ONLY-MANIFEST.json` and the
repository's immutable OEM reference. No artifact, credential or policy was
modified. No binary/private policy was committed or uploaded.

| Priority / exact local file | Bytes | SHA-256 | Expected state / installation mechanism |
|---|---:|---|---|
| 1: `C:\Users\jerry\SHINO-PRIVATE\review-003\SHINO-TV-V21-HEAP-PRIVATE-NOT-A-FLASH-APPROVAL.bin` | 405,712 | `3252ba5cd1f85683945d4d9a87ce49118568c0977605debc089267f54d7f3b0e` | V2.1 review-003, source `8cef03012ae4a4864d69cbe20e02f141a36e2d54`; supported stock OEM `/update` after a successful OEM return |
| 2: `C:\Users\jerry\SHINO-PRIVATE\review-003\OEM-V9.0.44-APPLICATION-ONLY.bin` | 494,144 | `a6421f5bfee7860d97bed26620c346b8008f503e513702d4bfdf6e01010a7718` | GeekMagic Ultra-V9.0.44 application; existing authenticated OEM-only factory-return multipart path |
| Original `C:\Users\jerry\SHINO-PRIVATE\FW-Smalltv-Ultra-V9.0.44.zip` | 349,377 | `cfbef50754ec552f9791878931c5f3643734de15f3c81cebdecf7ce05b28230f` | Exact manufacturer archive; application member byte/hash matched pinned reference |

The current live factory-return **GET** reports the pinned OEM identity,
494,144-byte size and `write_enabled:true`. Review-003 source requires matching
Digest authentication, `factory_v9_0_44` multipart file field, `.bin` filename,
physical 4 MiB flash, sufficient staging, exact expected bytes and OEM digest.
It does not accept an arbitrary SHINO image. No multipart request was sent.

The supported Wi-Fi chain is SHINO → exact OEM application → SHINO via the OEM
update page. Its prior owner-tested history is retained in
[Wi-Fi return-chain audit](V21_WIFI_ONLY_RETURN_CHAIN_AUDIT.md); historical
review-002 wording there is not used to identify today's device. Today's
review-003 identity and OEM capability were checked live in Mission 8.
The exact V2.1 package cannot be uploaded directly to the OEM-only return route.

**Rollback artifact/hash availability and current OEM-return capability PASS.**
Future candidate OEM-return implementation, boot recovery window, post-candidate
rollback and OEM `/update` acceptance were not physically qualified here. No
claim is made of nonbooting rescue: there is no hardware recovery path, no
full-chip backup, and application-only OEM return cannot restore unknown stock
filesystem contents. Existing recovery availability depends on a booting Wi-Fi
application. This is why the stack failure stops installation.

## Timestamped log

| Time, 30 September 2026 | Action / result |
|---|---|
| Before contact | Clean exact Mission 7 parent verified; separate branch created; PRs #29–37 preserved |
| Preflight, before device diagnostics | Retained review-003/OEM binaries and original ZIP hashed; all exact pins matched |
| 19:57:12.459 Europe/Paris / 17:57:12.459 UTC | GET factory-return HTTP 200; exact OEM bytes/hash and `write_enabled:true` |
| 19:57:12.538 Europe/Paris / 17:57:12.538 UTC | GET OTA capabilities HTTP 200; generic native writer/upload route absent |
| After preflight | Owner confirmed normal four-card physical display and orientation |
| Static pre-installation inspection | Linked crypto/receiver stack exceeds 4,096-byte Core stack; escalation stopped |
| Installation start/end | NOT STARTED / NOT APPLICABLE |
| Upload HTTP/result | NO UPLOAD REQUEST |
| Candidate SHA/binary | NO activated/instrumented Mission 8 candidate built |
| Post-install version | NOT APPLICABLE; device was not changed |
| Recovery action | NONE; no blind reflash, power cycle or factory return |

## Resets and boot reasons

No reset, reboot or watchdog event was observed/reported during the short
GET preflight, and no reset was induced. The current endpoints expose no reset
reason or boot counter. **Actual boot/reset reason is UNKNOWN**; absence of a
reported event does not prove absence of historical resets. Candidate reset,
boot and watchdog evidence is NOT RUN. The stack finding is static evidence,
not a concealed or inferred physical watchdog event.

Stop retained: leave the known-good installed device and both rollback images
unchanged. Resume only after reviewed stack remediation, a real bounded
instrumentation candidate, its exact image/policy/geometry checks, and all
remaining Mission 8 gates. No destructive recovery experiment is authorized.
