# Mission 9 Phase Q — offline StageA GET control-plane investigation

Authority: [owner Phase Q instruction](https://github.com/shinobione/SHINO-TV/pull/42#issuecomment-6064567041),
8 October 2026, and the owner's subsequent clarification in the current chat.
Start exact clean `061b5a844c00776e71a5a7803a2559b7500a4ce7` on
`feature/shino-tv-m9-flash-layout-liberation`, existing Draft/open/unmerged PR42.

**OFFLINE WORKLOAD REGRESSION PASS. OWNER RESIDUAL 404 NOT REPRODUCED;
ROOT CAUSE UNRESOLVED. No production fix is justified by this evidence.**
NORMAL_PROFILE_LITTLEFS_MOUNT_GATE=PASS (owner-supplied physical evidence).
NORMAL_PROFILE_RUNTIME_GATE=HOLD/PARTIAL. No promotion from host/CI results.

## Owner physical evidence and its limits

The owner reports the exact frozen profile1 StageA399264 B candidate installed,
SHA-256 `78a8d2d50409974fc775dd3dc9f3dbec4ac8eda839f6d9b338cadf35aab2467c`.
Independent full4 MiB PRE/POST before first boot proved candidate exact at0,
exact FF padding and POST[0x062000:0x400000]==PRE byte-for-byte. RTC words were
already0/0; no neutralization write was required. First boot reported
`rst cause:2`, `boot mode:(3,7)`, `v000617a0`, `~ld`.

The initial authenticated StageA GET succeeded: mounted/inventory/config exact,
24 files/181402 B, blocked writes0; setup continuation minimum2256 B,
FS/config minimum2368 B, runtime minimum3296 B, lowest heap33688 B,
lowest block33148 B, maximum fragmentation2%, rejected samples0,
sample count364, design_floors_observed=true. After Phase P, stock LINK one-shot
showed four values; >=180 s run stayed CONNECTED with evolving values and no
observed reboot/display corruption. Stale after Ctrl+C and recovery one-shot
passed. Subsequent authenticated GETs to both status aliases returned404.
This is a residual control-plane failure, not evidence of crash/mount failure.

The owner clarified that both failures came from ad-hoc Python3.12 scripts run
in Windows PowerShell, not a committed GET helper. First: stock
HTTPDigestAuthHandler, GET `/api/v1/m9/normal/status`. Second:
TelemetryDigestAuthHandler(store,url), GET `/status`. Both used
HTTPPasswordMgrWithDefaultRealm, SHINO-StageA, ProxyHandler({}), NoRedirect(),
read_credentials(), and Accept:application/json / Cache-Control:no-store.
Host came from private LINK configuration. The exception stacks showed Digest
challenge processing then HTTP404. No raw HTTP transcript, response body or
complete response headers were retained. **Their origin cannot be attributed to
firmware, host client or intermediary from these exception stacks alone.**
The owner explicitly directed unresolved attribution if offline reproduction
cannot explain it, and forbade any device contact/reboot/reflash/freeze change.
No private configuration or credentials were read in this pass.

## Executed composition and exact results

The existing real pinned Core lab is extended, rather than replaced by a fake
HTTP server. `m9_normal_webserver.materialize()` verifies the three stock Core
hashes and produces the same unchanged StageA parser/ABI in a temporary tree.
The inherited lab retains pinned parser, Core Digest, route matcher/dispatch and
response functions, with its existing enumerated host portability seams:
std::string-based Arduino String, host TCP/RNG/SDK dependencies, omitted
unregistered static handlers, multipart VLA storage and variadic spelling.
No installed Core or firmware input is edited.

Two native variants run: the raw parser fixture, and actual unchanged
M9NormalStageA.cpp + M9NormalDashboard.cpp + FslessMetrics.cpp with real pinned
ArduinoJson7.4.3 and M9NormalStatusJson. Hardware/display, Wi-Fi mode, mounted
config and FS status are inert fixtures. The wrapper delegates to the actual
server and adds only host counters/traces. Those fixtures are not physical
LCD/radio/heap/FS evidence. No new firmware diagnostic scalar is added.

Each urllib variant starts one server lifetime, performs initial authenticated
GETs to both status aliases,100 POSTs with stock Digest and100 with Phase P
cached Digest, then fresh stock **and** cached GETs to `/status`,
`/api/v1/m9/normal/status` and `/api/v1/m9/normal/resources` after each block.
Both actual owner GET client constructions and exact non-secret headers are
used. Synthetic generated-format credentials pass through read_credentials();
the host/port always come from the fixture's127.0.0.1 ephemeral listener.
No owner LINK configuration, private address, live credentials or device route
exists in this driver. Proxy/redirect suppression is retained.

The actual StageA variant advances a host-only virtual2 s offset after each
POST through stdin; ticks apply on the service thread between loop iterations.
It advances6001 ms after each block, observes actual FslessMetrics stale=true,
accepts a recovery POST on the retained opener, then proves stale=false.
Fresh GETs rotate the shared Core challenge naturally. No retry/reboot is added
outside the existing Digest challenge exchange. All sockets close through real
client behavior; the old fixture's forced stop/client replacement/queue clearing
is removed. Response receipt stops at exact declared length, avoiding Windows
select timer overhead; parser/body deadlines are unchanged.

| Evidence | Exact result |
| --- | --- |
| Raw native parser/Digest assertions | 233 PASS |
| Raw urllib lifetime | 200 accepted POSTs,14 successful GETs;214 HTTP200 |
| Actual StageA lifetime | 202 accepted POSTs,15 successful GETs;217 HTTP200 |
| Actual POST handler calls | 203:202 accepted +1 invalid JSON422 |
| Actual GET handler calls | 15:initial2 +final12 +post-negative1 |
| Final fresh GETs | 12/12 HTTP200, both client classes/all three paths |
| Unknown `/missing`, `/api/reboot`, `/config.json` | 404, policy rejection,0 route handler calls |
| onNotFound fallback calls | 0 |
| Basic | 401 |
| Oversized POST | 413 before body/handler; raw fixture proves zero body reads |
| Invalid JSON | 422 after bounded body; no accepted RAM sample |
| Stale/recovery | true/false twice using actual RAM telemetry |

Traces distinguish pre-body policy, method/URI, current handler, argument/plain
state, post args, and realm-match/nonce-presence/opaque-presence booleans. No
Authorization/proof/nonce/opaque/password value is logged. Every successful
GET handler has the correct matched handler,0 query args and empty plain body.
POST's prior plain argument persists until GET's `_parseArguments` runs;
`_currentArgsHavePlain` can remain1 afterwards with an empty slot. This retained
state is observed in the unchanged Core, but does **not** cause a404 in either
tested owner client or affect M9NormalHttpPolicy, which never reads arguments.
It is not evidence justifying a speculative state-reset firmware patch.

The exact emitted StageA parser hashes remain:
ESP8266WebServer.h `5c92371c93c29d006e8956693dea3b13077c6382e6677de8c72c2d3679b04a79`;
Parsing-impl.h `cfa8b295909f062dbd06de3bae8f1cb44bf8aa92a0cca0986f15847318b3933e`.
The fixture-only impl portability marker remains unchanged. Status/resource JSON
production source and semantics are unchanged.

## Regression, artifacts and stop boundary

244 relevant Mission9/provisioning/factory-policy regressions PASS,0 failures/
unresolved errors/skips. Initial batch passed242; two synthetic hardlink safety
tests could not create workspace aliases under the sandbox. Scoped unsandboxed
rerun passed both, without device/private readback access. Phase P sender19 and
LINK28 tests PASS. Native tests use Windows/Python3.12/MSVC locally; existing
layout CI uses Linux/Python3.13/GCC with ASan+UBSan. These platform seams remain
limits on attributing the physical report; no MCU/lwIP/heap-pressure proof.

Commands: `python tools/m9_phase_n_http_runner.py`; unittest discovery for
`test_m9*.py`, `test_verify_fs_provisioning`, `test_verify_factory_ota`,
`test_generate_shino_device_policy`, and companion `test_push_fsless_metrics.py`
/`test_shino_link.py`. Core/source/retained-image audit:
`python tools/m9_phase_o_qualification.py --candidate <retained-local-StageA-BIN>
--expected-sha256 78a8d2d50409974fc775dd3dc9f3dbec4ac8eda839f6d9b338cadf35aab2467c`.
Its historical normal NOT_RUN labels are the dated Phase O source model,
not today's owner physical verdict. Current verdicts are stated above.

All113 tracked firmware LF pins are unchanged; direct firmware/companion diff
empty. No no-write/auth/realm/route/TTL/resource-floor change; profile0/2 inputs
unchanged. The active writer still selects the same399264 B /rounded0x062000
candidate,98 packets; all acquisition/transaction/policy pins PASS. Retained
StageA rehash/image gate PASS. Frozen2072576 B LittleFS rehash remains
`d7ce9133b34fb5937d5640db81ff863a8f22a3717255c4b23057aea9ed2ef045`.
**No firmware build, replacement BIN, refreeze, writer rebind, FS mutation or
host diagnostic-client patch.** Earlier frozen/probe receipts remain intact.
CI's existing public-fixture application builds do not rebuild the retained
private candidate or publish private artifacts.

Local numeric/traced evidence is ignored under `research-local/m9-phase-q/`.
Final commit and exact-head CI completion are recorded in PR42 after push;
the existing layout job now asserts the workload counts, final GET200 and
unresolved/HOLD result and runs the focused Phase P suites.

Exact changed files:

- `.github/workflows/m9-flash-layout.yml`
- `docs/AGENT_HANDOFF.md`
- `docs/ROADMAP.md`
- `docs/M09_PHASE_Q_GET_CONTROL_PLANE.md`
- `tools/m9_phase_n_http_lab.cpp`
- `tools/m9_phase_n_http_runner.py`

The next attribution requires existing sanitized owner evidence of the actual
exchange or a separately authorized bounded diagnostic. This pass supplies
neither device-contact authority nor a request to perform such an operation.
**DEVICE CONTACTS=0; SERIAL I/O=0; FLASH WRITES=0; RTC WRITES=0; REBOOTS=0;
DEVICE FILESYSTEM WRITES=0. STOP before any device operation. DO NOT FLASH,
REBOOT OR MERGE. PR42 remains Draft/open/unmerged.**
