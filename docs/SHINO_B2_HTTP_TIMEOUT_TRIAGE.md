# SHINO // TV — B2 HTTP timeout triage (no firmware operation)

## Physical observation

Owner-reported: exact A2→B2 Wi-Fi upload was acknowledged by
\`BOOT_AND_TELEMETRY_CONFIRMED\` and distinct B2 SHA/build/boot ID, with LINK
restored. B2's fixed 30-cycle \`QUALIFY-B2.cmd\` subsequently returned
\`READONLY_QUALIFICATION_FAILED\`: cycle 5, \`NETWORK_TIMEOUT\`, on authenticated
\`GET /api/v1/update/status\`. One later, separately authorized read-only
authenticated status responded from B2 with the same boot ID, LittleFS mounted,
OTA enabled, heap 29552 B, block 27424 B, stack historical free 2048 B,
fragmentation 8%.

**Interpretation:** physical A2→B2 OTA confirmed; prolonged HTTP qualification
is NOT PASSED. A transient five-second HTTP timeout is not evidence of eboot
failure or device crash. The root cause is not established.

## Evidence from exact firmware/client source

- \`companion/shino_qualify.py\` performs 3 authenticated GETs per cycle,
  30 cycles, fixed 5s timeout per logical GET and 2s between cycles.
- \`companion/shino_link.py\` sends telemetry every 2s when connected;
  Digest authentication can add HTTP challenge/reply work.
- \`ota/firmware/Normal.cpp\` serves sequentially in \`loop()\` via
  \`server.handleClient()\`, alongside dashboard redraw and observer polling.
- \`tools/shino_http_ota_network.py\` checks 150 normal loopback requests
  but the host socket shim and simulated flash do not model real AP RF/lwIP
  timing or all memory/SDK effects.

These are contention **hypotheses** rather than a proven cause. Do not lower
stack/heap limits, hide errors, modify B2, or infer native resource headroom.

## Small bounded read-only observer

\`companion/shino_http_observe.py\` is a *new diagnostic*, not a rerun of
\`QUALIFY-B2.cmd\`, and does not modify historical qualification receipts.

By default it verifies the local BIN and manifest and exits \`PRINT_ONLY\` with
zero device requests. With explicit \`--authorize-read\` it makes 3 authenticated
GETs per cycle, at most 3 cycles / 9 logical GETs, stops on the first timeout
and never retries. It records sanitized operation/type and maximum latency,
never raw response bodies, credentials, tokens or private device IDs. It can be
used once during a separately planned observation; it is NOT an acceptance
gate and must not be used to promote a failed B2 qualification to PASS.

No firmware, serial, OTA, POST, reset, LittleFS write, or physical device action
was performed to prepare this tool.

## HOLD / next

Preserve original \`OTA-B2-receipt.json\`,
\`B2-readonly-receipt.json\`, PRE/POST captures and all \`.attempt\` markers.
Keep the known working B2 installed. Additional physical acceptance stays HOLD.
Investigate HTTP single-client fairness, Digest challenge frequency,
read/response latency and stack high-water *offline*. Any firmware fix requires
a new build and a distinct owner approval for OTA; not authorized here.

## Offline Phase 2 — simultaneous Digest/telemetry adversarial regression

The exact Core 3.1.2 \`ESP8266WebServer.h\` uses
\`HTTP_MAX_DATA_WAIT = 5000 ms\` and \`HTTP_MAX_CLOSE_WAIT = 2000 ms\`.
The B2 qualification client also uses a 5-second read bound. A competing
client that holds a server slot is a credible **hypothesis**, not a
demonstrated diagnosis. The core also has a 30-ms pending-client shortcut.

\`tools/shino_http_ota_network.py\` now launches eight synchronized pairs of
independent Digest-authenticated clients against the **actual Normal.cpp
HTTP/parser/handlers running in a loopback host process**: one status GET and
one bounded RAM telemetry POST, each with a six-second timeout. The old
sequential 150 requests, negative tests and valid host-mode OTA remain in
place. GitHub Actions asserts eight successful status/telemetry pairs and
records the largest GET/POST response latency as offline evidence.

Strict limitations: the ESP8266 Core HTTP source is pinned, but host socket
and memory shims do not model RF contention, lwIP, memory fragmentation, or
real Xtensa continuation stack. A host PASS is not physical B2 qualification.
No physical device contact, OTA, UART, reset, firmware modification,
credential publication or new owner action is requested.

## Phase 2 failure and deterministic Core proof

The first experimental 8-pair concurrent loopback test failed with repeated
Digest 401 responses (\`urllib.error.HTTPError: HTTP Error 401: digest auth
failed\`), despite the original 150 sequential requests passing.
This is a **negative finding**, not a successful concurrency regression.

Core 3.1.2 \`ESP8266WebServer-impl.h\` sets its single mutable \`_snonce\`
and \`_sopaque\` afresh on each \`requestAuthentication(DIGEST_AUTH,...)\`.
Its \`authenticateDigest(...)\` rejects any authorization whose nonce or
opaque differs from that latest pair. Independent clients can therefore
invalidate one another's Digest challenge/response windows.

A deterministic loopback test now: (1) obtains client A challenge, (2)
obtains client B challenge, (3) validates B with correct credentials,
(4) verifies that A's equally valid-but-stale challenge is rejected with
401. No retry, no socket requests to physical B2. The CI asserts the
**known limitation is reproduced**, not that concurrent authentication is
fixed. This proves a Core-level mechanism capable of causing the physical
symptom, but the physical cycle-5 \`NETWORK_TIMEOUT\` remains unclassified;
RF/lwIP and five-second timeout competition have not been ruled out.
Do not convert the original B2 \`HOLD\` to PASS or authorize B3 on this alone.

## Phase 3 — Windows coordination candidate (PC only, not yet physical PASS)

The proposed opt-in coordinator uses a per-RFC1918-target inter-process
OS byte lock at the user's local SHINO-TV application-data directory.
On Windows it uses nonblocking \`msvcrt.locking\`; on Unix host tests,
\`fcntl.flock\`. The lock spans the **entire** Digest challenge, authorized
request and response body, not merely the socket open. A second cooperating
client waits at most 1.5 seconds and then fails closed; it never bypasses
the lock or retries an HTTP request. A killed process releases its OS lock.
The tiny non-secret lock file stays on disk to avoid unlink/recreate races.

Normal SHINO LINK's actual \`make_engine_from_config\` uses the coordinated
sender. The earlier \`LinkEngine\` injected-sender lab API is unchanged.
The new PC-only \`shino_coordinated_qualify.py\` runs the existing qualifier
with the coordinated reader only upon separate explicit authorization and
an independent receipt path; the original failed B2 receipt and
\`QUALIFY-B2.cmd\` remain frozen. The short observer also shares this
coordination when explicitly authorized. **Uncoordinated legacy/custom
clients can still invalidate Digest challenges**, and coordination does
not prevent RF interference or prove a native B2 stability pass.

Cross-process CI tests must pass on Windows and Linux before proposing
any owner-side observation. No network, device contact or firmware update
is required or authorized to test this candidate offline.
