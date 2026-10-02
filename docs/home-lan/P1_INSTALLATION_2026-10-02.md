# Authorized OEM→P1 installation — upload ACK / post-boot HOLD

2 October 2026, Europe/Paris. Starting Draft PR #41 HEAD
`e9cca6ba5bf5216e2b8fd034cd2487fcc1d69722`. Jerry Quinet explicitly authorized
ONE genuine OEM `/update` application installation of the retained SHINO V2.2 +
P1 candidate, **464544 bytes**, SHA-256
`31e3f225744bd806df3302dbf3355770a313f8b71f65b33fd6e2f431449b0be5`, and its
expected reboot. This authorization is consumed. The approved binary was not
rebuilt, regenerated, modified or substituted.

**HARD STOP / PRE-PROVISIONING HOLD:** after installation the owner saw SHINO
cards that did not update and repeated reboots about every ten seconds. After
LINK was paused, the owner reports **stable display, stale cards**. The first
authenticated post-install GET ended with `ConnectionResetError` before any
application identity or resource response. No three-minute baseline, additional
device reads after that reset report, firmware retry/rollback, diagnostic control,
extra reboot request, Change/Forget or household credential write followed.

## Actual immediate preflight and one upload

Fresh owner confirmation: OEM display normal, stable USB power. Exact private P1,
OEM, M8 and V2.1 image hashes and retained ELF matched; private pairing passed.
Live owner-unit MAC match, HTTP 200 `/v.json` SmallTV-Ultra / Ultra-V9.0.44 and
HTTP 200 genuine 790-byte `/update` form passed. The form specifies POST,
multipart/form-data and file field `firmware`; it is an application upload, not
a filesystem route. Existing protected SHINO AP profile available. One existing
LINK sender, no competing uploader.

LINK was suspended at **09:49:29.504 CEST**, then the live OEM identity/owner MAC
and genuine form were checked again. The approved P1 image was rehashed at
**09:49:33.554 CEST**, immediately before the one POST. Its multipart envelope
was 464760 bytes, one `.bin` file part, no auth retry, redirect, proxy or cookie.

**HTTP 200 / complete acknowledged response, 7969.000 ms**:

```text
Update Success! Rebooting
```

Safe headers: `Content-Length: 74`, `Content-Type: text/html`. The response was
74 bytes and framing complete. The sanitized receipt is retained. LINK resumed
as the same single process at **09:49:41.519 CEST**; configuration, credentials
and autostart compared unchanged. No automatic upload retry occurred.

## Physical boot observations and stop

Windows joined the already-existing protected SHINO AP profile and received an
AP-subnet address. A TCP port-80 connection was established. The initial
authenticated GET `/` at **09:51:53–09:51:56 CEST** reset before returning an
application response. That attempt stopped, and the baseline was not started.
There is no runtime boot token, post-install application-size response or measured
heap/block/continuation to report. HTTP upload acceptance and visible SHINO cards
are distinct from a qualified boot.

Owner's current physical report: **"visible cards, but not updating, and
repeatedly rebooting every 10sec or so."** This triggers the installation gate's
unexpected-reset rule. No further device request was made after this report.
A diagnostic script prepared beforehand did not execute network I/O because it
failed at import; it was not rerun after the owner reset report.

At **09:56:13 CEST**, the same LINK process was suspended again, solely to halt
automatic telemetry POSTs during the incident. Configuration, private credentials
and autostart remain unchanged; the process is retained rather than restarted or
retargeted. **LINK remains paused** pending the owner-led next step.
After watching for about thirty seconds with LINK paused and no observer device
requests, owner reports: **"Display is now stable, but cards remain stale."**
This is a quiet-state physical observation, not a successful telemetry baseline
or a recovered runtime reset/resource measurement. The pause coincides with
stability; it does not isolate whether telemetry or other HTTP load triggered
the earlier resets, or establish a root cause.

## Result and precise uncertainty

| Requested qualification | Actual result |
| --- | --- |
| Exact image, OEM identity/form, owner unit, rollback kit and USB preflight | PASS |
| One OEM application upload and bounded acknowledgement | PASS; no retry |
| Post-install LCD | Initial SHINO/stale cards/repeated resets; stable display with stale cards after LINK pause — HOLD |
| New boot identity / running 464544-byte application | Not recovered via HTTP |
| Protected AP | Host association and TCP reachability observed; stable HTTP recovery unverified |
| Four fresh LINK metrics | NOT PASS; owner reports cards not updating |
| Three-minute normal baseline / actual heap, block, stack | NOT STARTED / UNAVAILABLE due hard stop |
| Runtime 4 MiB/storage geometry / persistent Wi-Fi availability | Source/private-image evidence retained; post-boot runtime verification unavailable |
| OEM-only recovery / disabled native OTA | Compiled approved-image evidence retained; live capability not verified |
| Pre-provisioning gate | **HOLD; no Freebox-Shino credential-write approval requested** |

Reset cause is **undetermined**: there is no new runtime reset reason, stack or
heap observation. Do not attribute the TCP reset or roughly ten-second physical
reboot pattern to watchdog, allocation failure, radio, HTTP parsing or bad image
without evidence. The exact approved P1 hash and complete upload acknowledgement
are confirmed, but they do not prove stable runtime or recovery availability.
R3 PARTIAL / R10 BLOCKED remain open.

Installation authority does not authorize an extra upload, rollback, reboot,
image change or household provisioning. The requested Freebox-Shino authorization
gate has not been reached. Leave firmware and retained private artifacts intact;
any further device diagnosis/recovery needs a separately bounded owner decision.

[Sanitized installation receipt](p1-installation-2026-10-02.json),
[applicable physical abort rules](OWNER_INSTALL_GATE.md#explicit-physical-abort-gates),
[prior verified OEM return](OEM_SINGLE_HOP_2026-10-02.md).
