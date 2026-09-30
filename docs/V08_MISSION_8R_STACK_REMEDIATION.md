# Mission 8R: stack remediation and qualification gate

30 September 2026, Europe/Paris. Exact parent:
`5179eb04ea51c2a92c7f796f07ebb963e2167e00` (Mission 8 / Draft PR #38).
Branch: `feature/shino-tv-v08-stack-remediation`.

**Final engineering gate: BLOCKED before installation.** The known linked EC
chain is reduced from 4,384 to **2,224 bytes**, and parsing returns before ECDSA.
This is a verified improvement, **not a complete stack-fit PASS**. The actual
linked m31 multiplier calls ROM `__umulsidi3` at `0x4000dcf0`; its instruction
body and stack bound are absent from the retained ELF and pinned Core sources.
ROM `memcpy` and `memset` are also reachable. Full owner, JSON, allocator and
receiver bounds remain UNKNOWN. The user's explicit UNKNOWN rule prohibits
installation. No Mission 8R device contact or write occurred.

## Remediation evaluated in the requested order

**A1: separate lifetimes.** A new bounded `Proof` state stores the signature
digest and prechecked challenge slot. Header parsing finishes and returns from
the noinline poll. The existing single owner invokes noinline `verifyHeaders`
on a later service call. Neither parser nor poll remains live during ECDSA.
The verification phase has no client reference and cannot read body bytes.
Challenge precheck runs again before ECDSA; slot, serial, principal revision
and epoch must still match. Final consume uses a fresh clock after verification.
Admission and the absolute 2,000 ms deadline are rechecked before body allocation.
Splitting alone cannot repair the inherited **crypto-only 4,384-byte** excess.

**A2: bound large objects without new scratch allocations.** Signature digest
32 bytes plus slot 4 bytes move into the fixed Ingress owner; alignment makes
the native Ingress increase **40 bytes**, from 1,384 to 1,424. This state lives
for the receiver object's lifetime, is reset on begin, becomes unreachable on
terminal phase, and is overwritten before reuse. It cannot fail allocation.
It coexists with the existing bounded buffers; no additional heap scratch is
introduced. `metadata` and `receive` are noinline so the 552-byte Metadata
automatic is not merged into the poll frame. No unbounded container replaces
an automatic. The Begin parsed Metadata still lives on stack; that path's
complete nested bound remains UNKNOWN.

**A3: use an existing pinned implementation.** The precompiled Core archive
exports m15/i15, not m31/i31. The exact pinned Core package nevertheless ships
the public `br_ec_p256_m31` API and unmodified `src/ec/ec_p256_m31.c`. The new
project compiles that exact source with its pinned inner/config headers, checks
its SHA-256, and passes its EC table to the same SDK
`br_ecdsa_i15_vrfy_raw`. SHA-256, P-256 and raw 64-byte r||s are unchanged.
Point validation uses the same table. Public retained and synthetic vectors
pass. The object is named `ec_p256_m31.c.o` to use the Core's existing `*.c.o`
flash placement rule; an ordinary `.o` consumed IRAM and failed the link. No
SDK source, assembly, algorithm, partition or linker script was changed.

**A4: inspect and measure, do not select a larger constant.** `cont.h` guards
its 4,096 default with `#ifndef CONT_STACKSIZE`; project build flags can override
it consistently in Core compilation. The disabled `stack_sensitivity_compile`
comparison uses 6,144 solely to measure a +2,048-byte change, not as a selected
safe value. Both full graphs link. Actual `app_entry_redefinable` frame changes
**4,160 -> 6,208 bytes**; text/data/BSS/BIN sizes remain identical. The pinned
Core allocates `cont_t` on SYS's DRAM stack, not a heap allocation or BSS array.
Its own explanation describes reclaiming roughly 4 KiB and warns that SDK
features can use that region. A larger SYS reservation has no established
capacity proof here. Static heap figures therefore do **not** prove spare SYS
stack or a target heap margin. No target heap delta was measured or invented.
The existing Core secondary BearSSL stack instead allocates 6,200 DRAM heap
bytes and aborts on allocation failure; it was not selected. The chosen phase
split/m31 candidate retains **4,096**, with no Core or assembly patch.

## Actual linked evidence and remaining blocker

The address-keyed analyzer reads the actual ELF, `nm -S` function extents,
instruction prologues, direct calls, literal-backed indirect calls, and the
linked 28-byte EC table. It excludes trailing literal pools from function
instruction inventories. It resolves offset 24 to the actual m31 `api_muladd`
and verifies each edge below. It asserts that parse and poll no longer call
the raw verifier and that `verifyHeaders` does. Compiler `.su` files are only
supplementary resource evidence.

| Reachable EC path | Linked frame bytes |
|---|---:|
| SDK raw i15 verifier | 720 |
| m31 `api_muladd` | 272 |
| m31 `p256_mul` | 592 |
| m31 `p256_add` | 304 |
| m31 `mul_f256` | 336 |
| Accounted EC chain subtotal | **2,224** |
| `verifyHeaders` frame, preceding this chain | 128 |
| `handleClient` / FirstBoot loop / loop wrapper | 48 / 16 / 16 |
| App `loop` tail adapter / continuation wrapper | 0 / 0 |
| Accounted normal owner + EC prefix | **2,432** |

The last subtotal excludes ROM multiplier/copy/clear bodies and other branches;
**1,664 bytes is not a proven spare margin**. The m15 `mul20` assembly frame is
no longer on this selected EC chain. The replacement's multiplication helper
is now an important **ROM assembly UNKNOWN**, not an assumed zero-frame leaf.
Pinned `eagle.rom.addr.v6.ld` proves its name/address, not its implementation.
Obtaining a target ROM dump would require device contact while the gate fails,
which the mission prohibits. Adding private probes or global ROM replacements
would broaden this bounded remediation without proving the complete gate.

| Important path | Accounted evidence | Complete maximum |
|---|---|---|
| Continuation/loop/owner | Actual entry and owner frames; cont assembly switches SYS/continuation stack | UNKNOWN; callbacks and switched contexts require full bounds |
| Header/profile | poll 208, parse 736; no nested ECDSA | UNKNOWN; formatting, ROM/string calls and clock callback |
| Gate 1 | verification 128 + EC 2,224; actual EC table and multiplier calls | UNKNOWN; ROM `__umulsidi3`, memcpy/memset and admission/clock/allocation branches |
| SHA update | linked update 48 -> compression 384, known chain 432 | Full enclosing request path UNKNOWN |
| SHA final | output tail -> finalizer 128 -> compression 384, known chain 512 | UNKNOWN; reachable ROM copy/clear |
| Gate 2 | poll 208, wire and admission; actual body SHA calls | UNKNOWN; complete owner/ROM/client bounds |
| Begin | receive 640 -> metadata 400; JSON nesting explicitly capped at 2 | UNKNOWN; JSON recursion and virtual arena callbacks need context-sensitive bounds |
| Tile | same noinline receiver, bounded 512-byte copy and conflict cleanup | UNKNOWN; ROM and allocator/cleanup bounds |
| Commit | receiver, final image SHA and unique ownership move | UNKNOWN; ROM SHA/cleanup bounds |
| Abort/expiry/revocation | terminal releases staging and sink | UNKNOWN; allocator/cleanup bounds |

No unconstrained sum of all SDK branches, recursion, abort/reset paths or data
decoded as instructions is presented as a valid maximum. JSON and allocator
inventory is evidence of work remaining, not proof that those paths exceed
4,096. Increasing the stack cannot turn an unknown maximum into a proof.

## Resource accounting

| Bytes | Retained M7 local media | M8R selected 4 KiB | Delta |
|---|---:|---:|---:|
| ELF text | 427,771 | 427,907 | +136 |
| ELF data | 2,792 | 2,792 | 0 |
| ELF BSS | 30,456 | 30,488 | +32 |
| BIN | 434,656 | 434,800 | +144 |
| Authority | 2,104 | 2,104 | 0 |
| Ingress | 1,384 | 1,424 | +40 |
| Receiver | 1,120 | 1,120 | 0 |

The independently linked unchanged legacy comparison is text 394,647, data
1,672, BSS 26,960, BIN 400,416. New media deltas versus that comparison are
33,260 / 1,120 / 3,528 / 34,384. BSS delta need not equal an individual object's
size delta because linked padding/layout changes. Server remains 424 bytes in
media and 416 in legacy. Native `sizeof` comes from ELF symbols; the MSVC host
sizes differ with 64-bit pointers and are not used for target RAM budgets.

Explicit heap buffers are unchanged: body 40..552, JSON arena 4,096, one image
0/2,048/4,608 bytes. Maximum replacement overlap is old 48x48 sink image + new
Begin body + temporary arena = **9,256 bytes**, excluding allocator/TCP/SDK/
graphics and stacks. Arena dies before new staging. A checked body allocation
failure rejects and frees on terminal; checked arena allocation/overflow rejects
metadata; checked staging failure calls terminal cleanup. Tile/Commit/Abort
terminal paths release owned buffers; Commit transfers ownership without a
second image allocation. These are explicit bounds, not total target peak RAM.

Compared with retained review-003 V2.1 BIN 405,712, this guarded public BIN is
29,088 bytes larger. Policy/startup/instrumentation differ, so that comparison
does not establish an equivalent V2.1 feature cost or OEM upload acceptance.
Local selected ELF SHA-256:
`269783955c3e0b9b2de26fa47e1177f2a6fb319a9e691b1e3178df71ddbbd9a1`.
BIN SHA-256:
`dec8669d412e29c1c800e560f45cd63fd84496c5453a7147b912603c38b06abc`.
**434,800 bytes; startup disabled, epoch zero, inert public policy, not an
instrumented installation binary.** No BIN is committed or uploaded.

## Regression and physical gates

Focused tests passed before dispatching the full retained CI suite. On MSVC,
each default/OEM native composition passed **1,047 checks**, zero failures,
246/246 default and 248/248 OEM contexts, zero live descriptors. The retained legacy portions passed
224 / 227 checks. The wire differential passed 10,207 cases (one admit); profile
1.1 passed 37 cases (seven admits). Maximum socket work remained 64 bytes/poll.
The expanded tests stop at the new Proof boundary and independently revoke,
expire, rotate the same key, advance epoch or expire the ingress deadline;
all deny before ECDSA/body allocation/body reads/receiver mutation.

Inherited real public P-256 vectors, R1 revocation, R2 literal STV7, R4 cheap
challenge denial, Begin/Tile/Commit/Abort, >30 ms contention, 2,000 ms/wrap
deadline, dashboard/four metrics and authorized conditional OEM multipart pass.
The legacy parser is still exactly the Mission 6A handoff; Mission 6C multipart
denial is not substituted. Host timing is not ESP8266 ECDSA latency or LCD proof.

Local rollback files were rehashed at **19:11:50 UTC / 21:11:50 Europe/Paris**:
exact V2.1, OEM and original ZIP pins unchanged. Previous live M8 GETs and the
owner's LCD/four-card confirmation are preserved, **not refreshed device proof**.
Part D's immediate live revalidation is NOT RUN because Part B does not PASS.
Parts E/F are NOT RUN: no activated instrumented build, install, reboot,
baseline, physical invalid/valid auth, coverless, 32x32 or 48x48 escalation.
No recovery was attempted. No device success or incident resolution is inferred.

R3 remains **PARTIAL**; R10 remains **BLOCKED**. No production key/provisioning,
permanent sender, public deployment, merge or Mission 9 work was introduced.
Historical PRs #29–38 and their files are preserved. The separate Draft PR
contains a candidate improvement and a reproducible **blocked** static gate.
Green CI means regression and UNKNOWN stop evidence reproduce, not permission
to install. Qualification can resume within the existing authorization only
after complete static bounds and the exact instrumented installation gate PASS.

Reproduce with `pio run -d experiments/v08_m8r -e legacy_compile -e media_compile
-e stack_sensitivity_compile`, then `python tools/v08_m8r_runner.py` with the
pinned ArduinoJson source, and `python tools/v08_m8r_stack.py`. The sensitivity
analyzer adds `--environment stack_sensitivity_compile`. Source hashes, native
addresses, local resources and regression results are retained in
[stack evidence](V08_MISSION_8R_STACK_EVIDENCE.json). Historical M7/M8 CI jobs
remain pinned to their own exact heads; all retained jobs remain enabled.
