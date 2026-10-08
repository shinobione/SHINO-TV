# Mission 9 Phase R — offline status diagnostic receipt

Owner scope: [PR42 comment6065184600](https://github.com/shinobione/SHINO-TV/pull/42#issuecomment-6065184600).
Start: clean `62a28324aac58e0628e9dd61f473ca91802e09b4`, existing
`feature/shino-tv-m9-flash-layout-liberation`; PR42 Draft/open/unmerged.

The PC helper uses the existing strict LINK config loader and credential reader
only inside the future explicit live operation. It sends one logical GET to
the exact normal status route using the existing urllib Digest machinery,
closed SHINO-StageA realm, one challenge retry, disabled proxies/redirects,
JSON/no-store headers and3 s per transport timeout. All output is fixed or
allowlisted typed values. Bodies are bounded4096/256 B without a cap+1 read;
ambiguous cap-sized undeclared bodies fail closed. Unknown response strings,
raw headers/bodies and exception details never enter output or a report file.

HTTP200 validates StageA identity, nonwriting flags, TTL and unchanged floors.
Resource PASS additionally requires valid positive observations, no rejected
samples and numerical floors. HTTP200 with resource HOLD remains a diagnostic
reading. Mount/config/count/blocked-write observations are reported separately,
without automatic promotion. Unchallenged200 is not accepted as authenticated.
Only single-key JSON404 codes attribute PREBODY or closed-route/fallback;
hostile/unknown/oversized404 stays404_UNATTRIBUTED and exit1.

Changed files (and no others):

- `companion/m9_stagea_status_probe.py`
- `companion/test_m9_stagea_status_probe.py`
- `companion/M9_STAGEA_STATUS_PROBE.md`
- `.github/workflows/ci.yml` (Windows offline test/audit step; Linux companion discovery already includes the module)
- `docs/M09_PHASE_R_STATUS_PROBE.md`
- `docs/AGENT_HANDOFF.md` and `docs/ROADMAP.md` (active owner scope/receipt links; earlier evidence retained)

Offline validation:13 focused test methods with real urllib Digest MD5 proof
verification over an in-memory handler, inert generated credentials and DNS /
connection guards asserted unused. Covers challenge200; both recognized404
codes and unattributed/hostile404; Basic/plain401, closed realm, repeated401
without a third request,403/other status, timeout, redirects, bounded declared
and undeclared oversize, malformed/hostile status, strict integer/boolean types,
floor boundaries/HOLD, output privacy, exact method/path/headers/counts, inert
private-loader integration, and default/audit/invalid-argument zero accesses.
Neither tests nor CI invoke the live CLI option. Compilation, default/audit
commands and diff checks pass. Sender19 + LINK28 companion regressions pass.
Broader companion discovery:180 PASS,4 existing C++/OpenSSL dependency skips
on this Windows host, no failures/errors in the completed run. An initial
sandbox run was interrupted after its loopback preview-server tests stalled;
the scoped host-only rerun passed, including that ephemeral127.0.0.1 fixture.
No SmallTV access was involved. The skipped integration cases have their
dependencies in Linux CI and are checked there on the exact pushed head.

The transport models real urllib challenge/error/redirect processing and
verifies the Digest response using public fixture values. It models bounded
body reads with BytesIO, not TCP framing, ESP8266/lwIP, heap, watchdog, actual
device timing or installed authentication. Phase Q's separate real pinned
parser/StageA lab and its fixtures/evidence are unchanged. These tests cannot
explain or reproduce the owner's intermittent physical404.

Freeze checks: all113 tracked firmware files, all tools/writer/runner sources,
LINK sender/engine, Phase Q workflow and receipt equal the start checkpoint.
Retained StageA399264 B SHA256
`78a8d2d50409974fc775dd3dc9f3dbec4ac8eda839f6d9b338cadf35aab2467c`
and LittleFS2072576 B SHA256
`d7ce9133b34fb5937d5640db81ff863a8f22a3717255c4b23057aea9ed2ef045`
rehash PASS. No candidate build/refreeze or writer rebind.

Final commit and exact-head CI are recorded in PR42 after push; public CI
receipts identify their exact SHA. No merge or physical authority follows CI.
NORMAL_PROFILE_LITTLEFS_MOUNT_GATE=PASS (prior owner evidence only).
NORMAL_PROFILE_RUNTIME_GATE=HOLD/PARTIAL. Root cause UNRESOLVED.
Device contacts=0; serial I/O=0; flash writes=0; RTC writes=0;
device filesystem writes=0; reboots=0. **STOP before device contact.**
