# SHINO // TV — B2 continuation-stack forensics (offline only)

**Physical context (owner-reported 2026-10-10).** The one-shot A2→B2 Wi-Fi OTA
returned \`BOOT_AND_TELEMETRY_CONFIRMED\`, with exact B2 SHA/build/boot and
LittleFS/telemetry restored. The first 30-cycle qualification later stopped
at cycle 5 on a five-second HTTP GET timeout. A short independent 6/6 GET
observation with LINK stopped passed (max observed latency 108 ms).
After Windows Digest coordination, the new owner-authorized qualification
ended at cycle **1** with \`RESOURCE_FLOOR_FAILED\`:
\`stack=1968 B\` against the mandatory \`2048 B\` floor, while LINK reported
\`CONNECTED\`. These are three different observations. Do not blend them
or claim the timeout has been eliminated.

## Critical distinction: historical stack painting

The pinned ESP8266 Core 3.1.2 \`Esp.cpp\` implements
\`ESP.getFreeContStack()\` by \`cont_get_free_stack(g_pcont)\` and
\`ESP.resetFreeContStack()\` by \`cont_repaint_stack(g_pcont)\`.
In SHINO's \`M9NormalResources::Observer\`, the stack paint is reset during
setup/mount stages and **not reset in \`poll()\`**. The status's \`stack\`
field therefore reflects a *historical free-watermark since a setup reset*,
not a snapshot of instantaneous call depth. A first-cycle 1968-B reading
does not identify the request that consumed the 80 B past the floor. It is a
real failed resource gate, **not proof of overflow or corruption**.

**Do not reset/repaint the stack at runtime to make the gate pass.** Do not
weaken the 2048 B threshold, increase HTTP timeouts as a substitute, or
repeat either historical qualification.

## Existing audit coverage and gap

\`tools/shino_http_ota_stack.py\` crosschecks native Xtensa prologues against
compiler \`.su\` frames on selected **OTA upload/verification/commit** paths.
It explicitly does not bound ROM/SDK/allocator/lwIP/IRQ/response paths. The
previously reported largest known compiled path (1840 B) is **not a whole
native high-water bound**; do not subtract it blindly from 4096.

The high-water that failed was exposed by ordinary
\`GET /api/v1/update/status\`. Before that read, SHINO B2 can perform
Digest challenges/verifications, \`POST /api/v1/bridge/metrics\` handling and
dashboard rendering, which must be analyzed as separate runtime paths.
\`GET\` success neither proves those callees' stack maxima nor that they
occurred concurrently or caused the deficit. The Windows lock prevents
cooperating-client Digest challenge overlap but does not recover historical
stack paint or bound firmware-side ArduinoJson, display, SDK/lwIP or ROM calls.

## Added reproducible evidence

\`tools/shino_b2_stack_forensics.py <public-build>\` parses the compiled
normal handler \`.su\` from the same **inert public** 4m2m image used by CI,
retains strict pre-existing frame ceilings for identity/status/metrics,
records optional handler frames with explicit \`DYNAMIC_UNKNOWN\` /
\`INLINED_OR_AMBIGUOUS\` rather than treating them as zero, and re-runs the
existing Xtensa OTA path audit. It returns top compiled native handler
frames, a SHA of the tracked source, explicit unresolved boundaries and
\`complete_normal_native_upper_bound=false\`.

This makes the **evidence gap explicit** and supplies comparable compiled
data for a later B3 candidate. It is not evidence of a 80-byte reduction,
does not identify the deepest unknown native branch, and has no physical
acceptance authority. No firmware, device, OTA, UART, credentials or private
receipts are read or modified.

## STOP and next decision

- Installed physical B2, 4 MiB PRE/POST, original one-shot OTA receipt,
  both failed qualifications and every attempt marker stay untouched.
- CI executes the public compiled evidence reporter and unit tests; 2048 B
  physical floor is unchanged.
- Only after finding a concrete, justified native handler frame/call-path
  reduction should a **new private B3 build** be considered. B3 OTA requires
  exact-image consent and separate admission assessment. Until then,
  physical prolonged B2 stability stays **HOLD**, even if offline CI passes.
