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
