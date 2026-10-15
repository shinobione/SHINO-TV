# B5 LAN diagnostic schema compatibility — HOST-only

## Cause supported by source (not a retained HTTP body)
The reviewed `companion/shino_b5_get_diagnostic.py` previously accepted only
exactly four LAN fields, matching B5's legacy response. The generated
`tools/shino_b5_lan_build.py` adds four fields:
`credential_state`, `connection`, `provision`, `firmware`.
The B5.1 handler retains a literal `firmware: "B5.1"` even in B5.2.
The old diagnostic test explicitly rejected that extended response.
The owner physically reported an authenticated HTTP 200 + INVALID_SCHEMA at
the LAN step, but the response body was NOT retained, so causal attribution
remains a high-confidence HYPOTHESIS rather than directly observed bytes.

## Fix
Allow **exactly** four (legacy) or eight (extended) fields. Validate types,
fixed protocol, IPv4 and online/IP consistency, producer-defined enums,
literal firmware label, safe SDK credential state, successful/idle provisioning,
and non-fault connection before reporting extended LAN status as acceptable.
Unknown fields, partial extensions, known failure states, corrupt JSON,
timeouts, Digest errors, changed identity and uncertain network reads stay
fail closed. Existing fully bounded two-wire-GET authentication, one
operation lock, hard timeout and no-repeat rules are unchanged.

This branch is deliberately separate from the B5.3 candidate source SHA
`54aed39fa7cff7b982be7dafd6ac430cbb8cef20`, whose private BIN
and local receipt remain untouched.

**Tests:** GitHub Actions simulates responses and may use loopback TCP for
HOST regressions. This commit performs NO physical GET/POST, OTA, restart,
Wi-Fi change, filesystem/RTC/flash write or secret access.

**Next authorization:** a separate and explicit owner GO is required to
perform any further real diagnostic GET. Do not retry the prior terminal
session under the previous authorization. Runtime stack (last observed
2144 B free), fresh LINK and whole-native OTA peaks remain HOLD.

## LAN_STATE_HOLD field-independent triage (HOST-only)

The second real B5.2 session had two authenticated HTTP 200 results but ended
on `LAN_STATE_HOLD`. Its LAN body was not retained. The new offline-only
code does **not** relax any acceptance gate: it keeps `LAN_STATE_HOLD`
as the terminal reason, but adds one of ten fixed non-secret `lan_hold_gate`
categories to the report. Unknown/missing JSON still stops as `INVALID_SCHEMA`.
These categories do not disclose the raw LAN response, credentials, tokens,
SSID or passwords. No automatic retry and no subsequent resource GET on HOLD.

No physical execution or device modification in this commit. A new separately
scoped owner GO will be necessary before any additional physical GET; this
work does not authorize one. Last owner observation: B5.2 stack free 2144 B,
LINK stale; B5.3 OTA remains HOLD.
