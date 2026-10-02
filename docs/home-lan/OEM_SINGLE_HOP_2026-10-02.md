# Corrected single OEM hop — acknowledged / OEM boot and display PASS

2 October 2026, Europe/Paris. Starting Draft PR #41 HEAD
`0bae281f8d8c4061d12cdfe50781c137e1fb9876`. Owner separately authorized **ONE**
new M8→OEM application upload and its expected installation reboot, requiring
LINK suspension during the final Digest challenge/upload. This authority is
consumed. **STOP: no retry, Hop 2, additional firmware write or household
credential write.** P1 remains NOT INSTALLED / DEVICE NOT RUN.

## Actual request and response

Approved and immediately rehashed image: **494144 bytes**, SHA-256
`a6421f5bfee7860d97bed26620c346b8008f503e513702d4bfdf6e01010a7718`.
The exact approved private wrapper and corrected helper remained byte-identical
to their recorded `0bae281` hashes; the public transport matched the approved
Git blob. A separate ignored execution guard paused/resumed LINK around the
wrapper's final GET/upload seam. It did not replace the reviewed upload method.

One POST `/api/v1/bridge/factory-return`, field `factory_v9_0_44`, preemptive
Digest, one multipart part, 494357-byte complete envelope. No redirect, proxy,
cookie or upload authentication retry. Durable exclusive receipt retained.

**HTTP 200 / ACKNOWLEDGED**, **10765.000 ms**. Observed response is 122 bytes,
matching Content-Length, and the bounded sanitized diagnostic body is:

```json
{"status":"staged","message":"Verified OEM application image; reboot scheduled. Original filesystem restoration unproven"}
```

Safe response headers: `Content-Length: 122`, `Content-Type: application/json`,
`Cache-Control: no-store`, `X-Content-Type-Options: nosniff`.
No automatic retry occurred. The application-only return does not establish
original filesystem restoration or power-interruption recovery.

## Fresh preflight and LINK isolation

Owner immediately confirmed normal orientation, all four changing cards, no
corruption and stable USB power. Authenticated GETs confirmed fresh six-second
telemetry, M8 446944 B / boot 2962927510, physical flash 4194304 B, exact enabled
OEM capability and no native OTA writer. Current point samples were
**19424 / 16672 / 1728 B** free heap / largest block / continuation reserve.
No pending receiver/body/staging, live secondary references, secondary busy,
allocation failure or canary failure. These are entry samples, not upload peaks;
no upload-phase memory high-water is claimed.

The one existing LINK process was suspended at **07:21:50.178 UTC**. After a
three-second drain for an already in-flight ready-client request, a new serial
Digest reader challenged at **07:21:53.198 UTC**. Immediate image rehash occurred
at **07:21:53.316 UTC**, directly before the one POST. LINK remained stopped
through the response and resumed in `finally` at **07:22:04.084 UTC**.
The same single process is running again. Before/after private in-memory/file
hash comparison confirms unchanged LINK configuration, credentials and existing
autostart entry. No sender retargeting, restart or duplicate sender was added.
Its preserved SHINO target is not a claim of telemetry compatibility with OEM.

## Reboot verification and remaining uncertainty

At **07:23:01 UTC**, bounded read-only home-LAN rediscovery matched the retained
owner-unit MAC and live GET `/v.json` returned HTTP 200:
`{"m":"SmallTV-Ultra","v":"Ultra-V9.0.44"}`. This verifies the expected OEM
application boot. No further firmware POST followed it. In response to the current
post-boot LCD check, owner confirms: **"OEM display normal and correctly
oriented"**, including no corruption. Physical display evidence is owner-reported;
the live HTTP identity check is separate machine-observed evidence.

The original failed upload's HTTP status/body remain unrecoverable. This
successful corrected attempt with LINK paused demonstrates current request
acceptance; it does **not** isolate shared-nonce rotation as the original cause.
P1 was neither rebuilt nor installed. Household credentials were not written.
R3 PARTIAL / R10 BLOCKED remain open. Further installation needs fresh explicit
owner authorization; earlier two-hop consent is superseded by this single-hop
stop. Historical failed attempt and offline investigation evidence are preserved.

[Sanitized numeric receipt](oem-single-hop-2026-10-02.json),
[original failed attempt](DEVICE_INSTALLATION_2026-10-02.md),
[corrected client investigation](OEM_UPLOAD_CLIENT_INVESTIGATION.md).
