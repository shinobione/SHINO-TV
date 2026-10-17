# Mission 9 Phase R — owner status diagnostic

Implementation and CI are offline. Default/no arguments and `--audit` read no
private config or credentials and make no request. Codex never runs the live
option. After the owner reviews exact-head CI and separately chooses to perform
the read, the **one future PowerShell command**, from the repository root, is:

```powershell
py -3 companion\m9_stagea_status_probe.py --live
```

The helper uses the existing private LINK config and per-build credentials.
It needs no new credential entry, host argument or report file. It does not
switch Wi-Fi. Only an exact RFC1918 IPv4 is accepted. Missing/invalid config
fails closed; environment proxies and redirects are disabled. It requests only
GET `/api/v1/m9/normal/status`, with SHINO-StageA Digest, JSON/no-store headers
and a 3-second timeout per transport request. One initial challenge may produce
one authenticated retry (at most two GETs); no other retries or paths exist.
An unchallenged HTTP200 fails closed as `HTTP_401` rather than claiming an
authenticated reading.

Expected sanitized output:

| Outcome | Output | Exit |
| --- | --- | --- |
| Valid status | `STAGEA_STATUS_GET=HTTP_200`, fixed StageA identity, selected integer/boolean fields, `RESOURCE_FLOORS=PASS` or `HOLD`, runtime `HOLD/PARTIAL` | 0 |
| Recognized pre-body 404 | `STAGEA_STATUS_GET=HTTP_404 ERROR_CODE=STAGE_A_PREBODY` | 1 |
| Recognized closed-route/fallback 404 | `STAGEA_STATUS_GET=HTTP_404 ERROR_CODE=STAGE_A_ROUTE_CLOSED` | 1 |
| Other/oversized/misleading 404 | `STAGEA_STATUS_GET=HTTP_404 ERROR_CODE=404_UNATTRIBUTED` | 1 |
| Other failures | Fixed class: `HTTP_401`, `HTTP_403`, `HTTP_OTHER`, `REDIRECT_BLOCKED`, `UNEXPECTED_REALM`, `TIMEOUT`, `NETWORK_ERROR`, `CONFIG_INVALID`, `MALFORMED_RESPONSE`, `OVERSIZED_RESPONSE` or `CLIENT_ERROR` | 1 |

No raw body, header, challenge, Authorization, host, URL, private path or
exception text is printed or saved. The status body cap is4096 B; error body
cap256 B. Declared oversize is rejected before reading. An undeclared response
that reaches the cap is rejected conservatively without reading an extra byte.
Only a single-key JSON object with a recognized `error` string attributes404;
this is a response-code observation, not proof of its physical origin.

`RESOURCE_FLOORS` checks the unchanged20480 B heap /16384 B block /25%
fragmentation /2048 B setup, FS/config and runtime continuation floors, valid
measurements, positive samples and zero rejected samples. This snapshot cannot
prove the intermittent404 resolved or certify earlier workload. Mount PASS
remains prior owner evidence; **NORMAL_PROFILE_RUNTIME_GATE=HOLD/PARTIAL** until
valid post-workload physical evidence is reviewed. No gate changes are automatic.
HTTP200 means a structurally validated status, including when resource floors
are HOLD; inspect the reported mount/config/count/blocked-write fields separately.

No firmware, LINK telemetry, filesystem, RTC, serial, flash, OTA or reboot
operation is performed. [Offline receipt](../docs/M09_PHASE_R_STATUS_PROBE.md).
