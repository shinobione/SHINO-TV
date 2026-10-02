# P1 failed status diagnostic — offline review, 2 October 2026

Owner review [#5949087791](https://github.com/shinobione/SHINO-TV/pull/41#issuecomment-5949087791)
authorizes this investigation and preparation only. **No proposed diagnostic has
been executed. P1 baseline and Freebox first-write gate remain HOLD.** No device
contact, LINK/autostart change, firmware build/upload/reboot or provisioning.

## Finding: the original timeout phase is unrecoverable

The retained private client actually uses `http.client.HTTPConnection`, rather
than an urllib opener. Its 3-second socket timeout covers `connect()`,
`request()`, `getresponse()` and body reading. It records an attempt before
connecting, but records the first HTTP status only after `getresponse()` returns
(which includes response headers). There are no successful-connect/send markers
or traceback. Its overall timer publishes the socket only after connection.

The preserved receipt contains `TimeoutError`, 3015 ms, no status/challenge and
no authenticated follow-up. It cannot distinguish a TCP connect timeout from a
send, status-line or response-header timeout. A body timeout cannot explain the
missing status marker in ordinary control flow. The elapsed time alone cannot
recover the phase or show that the ESP received or parsed any request bytes.
No retained packet trace supplies that missing evidence.

There is also a deterministic validation defect: the old client rejects
`heap_observation.state = NO_SAMPLES`, which the exact P1 source permits. This
would affect a successful status response, and **does not explain this timeout**.
The corrected client accepts the three actual states: NO_SAMPLES, SAMPLING,
SATURATED.

## Exact retained installation/build evidence

The approved BIN remains **464544 bytes**, SHA-256
`31e3f225744bd806df3302dbf3355770a313f8b71f65b33fd6e2f431449b0be5`.
Its private-kit BIN/ELF match the retained owner build byte for byte; ELF SHA-256
`c40dde6b1cb1b9ad93acfe3d551d7088a5a68cb0d50631fffd8cd4fcda3edf45`.
The retained P1 parser overlay matches the P1 transformation over the six pinned
Core 3.1.2 sources. HomeLan, scene adapter and qualification sources match the
retained owner inputs. Existing ELF symbols confirm the active FirstBoot,
HomeLan and artwork paths and absence of the offline startup guard. No rebuild
was used. The ELF lacks usable decoded source-line tables for these units; this
is retained-build/source evidence, not complete DWARF provenance or a new read
of the running application.

The source/linked paths explain the intended first request:

- FirstBoot starts HomeLan, registers routes and calls `server.begin()` after a
  successful network setup. Its loop polls HomeLan, then calls
  `server.handleClient()` when network-ready, before artwork rendering and
  qualification observations. Media busy defers HomeLan transitions; it does
  not itself suppress a ready HTTP service. Prior cooperative work could delay
  service, but no native timing observation proves such a delay here.
- A validated inherited OEM SDK Wi-Fi profile can start AP+STA and associate
  without a new household credential write. Source readiness is not conditional
  on successful STA association. Current saved-profile/state and opaque SDK
  radio activity remain unknown because no status JSON was obtained.
- The initial GET traverses the bounded request-line/header parser and HomeLan
  authority policy before Digest. The P1 path has a 2-second header budget,
  strict CRLF and header limits, and a yielding wait. The retained client's
  numeric Host and normal GET headers have no identified deterministic policy
  mismatch. Comparing the parser's 2-second budget with the client's 3-second
  timeout is not causal evidence without connection/parser-entry observations.
- A permitted unauthenticated status GET calls `requestAuthentication` and
  should produce a fresh SHINO-FirstBoot Digest 401 with an empty framed body.
  It does not run status JSON serialization or native ECDSA verification before
  that first challenge. Nonce/String allocation and send paths exist; no
  runtime counters prove their failure. Missing 401 is not evidence of bad
  credentials or rejected Digest authentication.
- Core 3.1.2 `EspClass::wdtEnable(uint32_t)` ignores its timeout argument and
  restarts the SDK software watchdog. The retained overload/ELF path confirms
  that the caller's `WDTO_2S` is not a configured 2-second reset timer. No reset
  reason was captured. Quiet LCD stability does not prove a telemetry-only
  root cause, watchdog reset, healthy HTTP service or successful baseline.

Private original client SHA-256:
`5c42ac85e0f020576f6182bab026d0087edc498e3b2721e9e75c9c997b88dc50`.
Original receipt SHA-256:
`3e6bc8ab71ab8ec41937dbe7ced2f8d027eb7a39e75ad0ef0ccb63addc6c2678`.
Both preserved unchanged. Private receipts, credentials, exact shadow and
inspection outputs remain local and ignored.

## Corrected, reviewed diagnostic — not executed

Public transport implementation: `tools/p1_status_transaction.py`.
Private default-deny wrapper: `research-local/p1_one_status_phase_review.py`.
Neither import nor the wrapper's default review mode makes a connection.
The wrapper requires a fresh owner authorization reference, exact reviewed HEAD
and its own SHA, plus the pinned transport SHA. A command-line flag is not
authorization; the operator must check the new explicit owner decision.
Consumed #5948806085 and offline-only #5949087791 are refused as live authority.

Transport SHA-256:
`4d4c90fe3eb841b786338334fab2b149854dbac4714954fa440fa8a5c0b65126`.
Private wrapper SHA-256:
`d797f53cb4e7dcf0d54b9466e8a47cce8bd4c9c0177d3ba764157d46ca40b7b6`.

The exclusive reservation/receipt prevents accidental rerun. Monotonic start
and completion events identify TCP_CONNECT, REQUEST_SEND, HTTP_STATUS_WAIT,
RESPONSE_HEADERS, RESPONSE_BODY, DIGEST_PREPARATION and JSON_VALIDATION.
The receipt records connect/send completion, received HTTP status even when
subsequent headers fail, framing, bounded byte counts, errno/winerror,
elapsed time and the exact failure phase. Arbitrary exception text, challenge,
Authorization, credentials, raw headers/body, SSID/MAC/IP fields are excluded.
Status JSON uses numeric/boolean/enum allowlists, preserving actual resource
observations without manufacturing missing measurements or zeros.

Offline verification: **10 public scripted-socket tests plus 2 private wrapper
integration tests PASS**. Coverage includes distinct timeout phases, reset code,
absolute deadline abort during connect, exact MD5 Digest computation/GET URI,
first unauthenticated GET, one challenge follow-up, no third request after 401,
invalid challenge/status/framing/JSON, oversized/truncated response, NO_SAMPLES,
sanitization, default-deny wrapper and receipt-reuse refusal. All sockets,
credentials and local checks are injected fakes; no loopback or device server.
No broad firmware build or CI run substitutes for missing native evidence.
Delivery uses `[skip ci]` to honor the owner's no-rebuild constraint: this
repository's push/PR workflows compile firmware. These latest changes have
local client-test evidence only, not a new exact-head CI PASS. Draft stays
unmerged; prior CI belongs to its recorded historical heads.

## Exact next proposed test — fresh authorization required

1. Check locally that LINK is absent and Windows is already on the expected
   protected SHINO AP with WPA2/CCMP, preferred AP-subnet address and local route.
   Stop on ambiguity. Do not change Wi-Fi or autostart, restart LINK or probe AP.
2. Using the reviewed wrapper/transport hashes and matching private P1 Digest
   credentials in memory, perform one logical transaction: initial
   `GET http://192.168.4.1/api/v1/bridge/status`; only if it returns a valid fresh
   401, one authenticated GET to the same endpoint. Numeric IPv4, no DNS, proxy,
   redirects, polling, automatic retry, separate TCP probe or other endpoint.
3. Use at most 3 seconds per blocking phase and a 6-second absolute deadline
   across the entire pair, with socket published for interruption before
   connect. Bound headers/body to 16 KiB. Stop immediately on reset, timeout,
   invalid response or second 401. Never repeat the POST or install anything.
4. Report phase receipts and, only if obtained, actual boot/reset, current heap,
   previously observed heap/block/continuation minima, Wi-Fi state and P1 failure
   counters. A completed PC send does not prove ESP parser entry. Preserve HOLD:
   this single read is not the three-minute functional/resource baseline.

Then STOP. No Freebox password request or write, recovery, reboot, additional
device operation, upload, merge or native OTA activation follows this test.
