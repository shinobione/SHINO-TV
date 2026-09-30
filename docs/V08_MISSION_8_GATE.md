# Current Mission 8 engineering gate

30 September 2026. Continuation starts at exact existing PR #39 head
`cb58173495f811787a0fbb2c44bc1df6621c9990` on
`feature/shino-tv-v08-stack-remediation`; Draft PR #39 is retained.

**Current status: pre-install static/regression/image checks PASS; physical qualification PENDING.**
The user's continuation replaces the earlier whole-ROM static UNKNOWN stop
with exact linked isolation and required physical high-water measurements.
This is not a physical stack, heap, LCD, install or recovery PASS.
R3 remains PARTIAL; R10 remains BLOCKED. No production key, permanent sender,
Mission 9 work or merge. The existing one-device physical authorization remains
in force. Immediate owner LCD recheck is pending. The retained OEM address is
`192.168.1.70` (prior `/v.json` and `/update` visits); its exact model/version must
be verified live after factory return and before the second write. No firmware
write or media request has occurred in this continuation.

Clean committed validation at `432263feb139c7af2fecc0ecaa0c348b05304914`: both focused configurations pass;
both PR and push CI runs pass all **11 jobs**. A clean-head rebuild produces
byte-identical private ELF/BIN; public and private isolation analyses pass.
One-shot offline checks verify all 202 signed packets and 190 receiver records
across 30 coverless/32/48 groups. This does not substitute for target measurements.
CI: [PR run](https://github.com/shinobione/SHINO-TV/actions/runs/36779971808),
[push run](https://github.com/shinobione/SHINO-TV/actions/runs/36779968038).

---
Historical records preserved below; their gates and zero-contact statements describe those earlier runs.

# Current Mission 8 / 8R engineering gate

**BLOCKED — complete native stack prerequisite remains UNKNOWN.** Mission 8R
implements a separate Proof phase and evaluates unmodified pinned m31 crypto.
The known EC chain falls to 2,224 bytes; the actual ROM multiplier body and
full owner/receiver bounds are still unproved. No installation is authorized
by this result. Local focused regressions pass; retained CI is configured to reproduce the
blocked static gate and cannot establish physical qualification. M8R device
contacts/writes are zero; Parts D-live, E and F are NOT RUN. R3 remains PARTIAL,
R10 BLOCKED. Historical PRs #29–38 remain preserved. The physical authorization
persists, conditional on complete static and rollback gates passing; no new
mission is required to resume once safe. See [M8R report](V08_MISSION_8R_STACK_REMEDIATION.md)
and [evidence](V08_MISSION_8R_STACK_EVIDENCE.json).

---
Historical Mission 8 record (preserved):

# Mission 8 review gate

30 September 2026, Europe/Paris. Exact parent
`84129daa7359c73e738272b1c01131b3292dc315`.
Branch `feature/shino-tv-v08-device-qualification`.

**Final engineering status: BLOCKED before installation.**
The actual linked ECDSA/SDK path reserves at least **4,384 bytes** against a
**4,096-byte** continuation stack. The nested receiver + crypto path is at least
**5,904 bytes**, excluding owner/loop/entry overhead. This is a concrete static
fit failure, not an arbitrary heap threshold or an observed physical crash.

| Gate | Result |
|---|---|
| Exact clean start / separate branch | PASS at Mission 7 head |
| Mission 7 report/resource/matrix/gate read | PASS; historical evidence unchanged |
| PRs #29–37 | PASS live verification: all preserved OPEN/Draft |
| Actual installed lineage | Consistent with retained V2.1 review-003: exact size, matching Digest credentials, heap schema and capabilities; no device SHA/version label exposed |
| Physical baseline LCD / four metrics | PASS limited baseline: direct owner observation plus two fresh changing device GET readings |
| Local rollback artifacts | PASS: exact V2.1 and OEM bytes/hashes verified; no modification |
| Current OEM factory-return capability | PASS read-only: exact pinned identity and `write_enabled:true`; no rollback write |
| Instrumented Mission 8 candidate | NOT BUILT; early linked-stack precondition failed |
| Inherited app flash fit | Arithmetic PASS, not final candidate fit or OEM acceptance |
| Inherited native stack fit | **BLOCKED** from actual linked prologues, call edges, SDK assembly and continuation size |
| Installation / normal reboot / recovery | NOT RUN; stopped before first write |
| Several-minute candidate baseline | NOT RUN |
| Authentication-only physical qualification | NOT RUN; no ESP8266 ECDSA latency/body-denial proof |
| Coverless / 32x32 / 48x48 repetitions | NOT RUN; zero physical transfers |
| Heap/fragmentation/allocation/cleanup/UI margin | HOLD for future safe candidate; existing saturated V2.1 observer is not candidate evidence |
| R3 freshness | PARTIAL; no persistent freshness primitive introduced |
| R10 production provisioning | BLOCKED; no production private key/provisioning/sender introduced |
| Merge / public deployment / Mission 9 | Not performed |

This mission made its first authorized physical **GET-only** device contact.
It did not qualify a native media receiver on hardware and is not a production
GO. Local full links and the static negative gate are reproducible. The new CI
job executes the Mission 8 review head and expects proof of the **BLOCKED**
static result; green CI means the stop evidence is reproducible, not safe to
flash. Mission 7's own lab is preserved at its exact historical head because its
runner enforces Mission 7's allowed diff. All other retained jobs remain.

See [device qualification](V08_MISSION_8_DEVICE_QUALIFICATION.md),
[runtime/resources](V08_MISSION_8_RUNTIME_RESOURCES.md),
[recovery log](V08_MISSION_8_RECOVERY_LOG.md),
[sanitized device evidence](V08_MISSION_8_PREFLIGHT_EVIDENCE.json), and
[linked-stack evidence](V08_MISSION_8_STACK_EVIDENCE.json).

No automatic reviewer approval or attestation is fabricated. Stop at this Draft
review gate. The blocker requires an explicitly reviewed stack/memory change
before resuming instrumented build and physical qualification. The current
SmallTV, rollback packages, frozen V2.1 source, production firmware, SHINO LINK
and earlier PRs/evidence remain preserved.
