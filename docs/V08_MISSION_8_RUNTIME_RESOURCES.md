# Current continuation resource evidence

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

Private text/data/BSS 439207/2840/32704; BIN 446144. Continuation 4096; secondary 6200; fixed Authority/Ingress/Receiver 2104/1432/1120. Lifecycle B releases the crypto stack before body/JSON. Peak explicit receiver 9256 and prior image+crypto 10808 do not include allocator/SDK overhead. Native canaries/high-water, allocation counts, minima and timing are instrumented but unmeasured physically.

Clean committed validation at `432263feb139c7af2fecc0ecaa0c348b05304914`: both focused configurations pass;
both PR and push CI runs pass all **11 jobs**. A clean-head rebuild produces
byte-identical private ELF/BIN; public and private isolation analyses pass.
One-shot offline checks verify all 202 signed packets and 190 receiver records
across 30 coverless/32/48 groups. This does not substitute for target measurements.
CI: [PR run](https://github.com/shinobione/SHINO-TV/actions/runs/36779971808),
[push run](https://github.com/shinobione/SHINO-TV/actions/runs/36779968038).

---
Historical records preserved below; their gates and zero-contact statements describe those earlier runs.

# Current runtime/resource gate after Mission 8R

**BLOCKED: complete native stack maximum UNKNOWN.** Selected 4,096-byte-stack
guarded M8R graph: text 427,907, data 2,792, BSS 30,488, BIN 434,800; Authority
2,104, Ingress 1,424, Receiver 1,120. No extra heap scratch. Known EC chain
2,224 bytes replaces M7's 4,384-byte accounted chain; that is not a stack-fit
PASS. ROM `__umulsidi3`/copy/clear and complete receiver bounds remain UNKNOWN.
Unselected 6,144-byte macro sensitivity increases SYS entry reservation by
2,048 with no BSS/data change; a safe SYS region and target heap margin are
unproved. There are no instrumented target readings. See [M8R resources and
stack evidence](V08_MISSION_8R_STACK_REMEDIATION.md).

---
Historical Mission 8 record (preserved):

# Mission 8 runtime resources and static stack stop

30 September 2026, Europe/Paris. **BLOCKED before candidate installation.**
This report separates actual existing-V2.1 device observations from native
compiler/link evidence. There is no instrumented Mission 8 target measurement.

## Existing device observations

| Existing review-003 reading | Bytes/value | Scope |
|---|---:|---|
| Free heap at status GET | 31,168 | One physical device response, including current GET load |
| Lowest observed free heap | 29,152 | Retained finite accumulator, already SATURATED |
| Lowest observed largest free block | 28,320 | Same retained accumulator |
| Highest observed fragmentation | 11% | Same retained accumulator |
| First/latest recorded free heap | 36,176 / 32,928 | Same retained accumulator |
| Latest recorded block/fragmentation | 30,248 / 9% | Same retained accumulator |
| Samples / interval | 1,024 / 1,000 ms | Saturated, no longer recording new extrema |

These extrema were read now but collected earlier during this boot. They do not
describe Mission 8, the current GET's true transient peak, or a new continuous
soak. No reset was requested to clear the accumulator. No arbitrary safe heap
threshold is inferred from these numbers.

## Reproduced unchanged Mission 7 graph

Local PlatformIO **6.2.0**, espressif8266 **4.2.1**, Core **3.1.2**,
Xtensa GCC **10.3.0**, ArduinoJson **7.4.3**, GFX **1.6.4**, AnimatedGIF **2.2.0**.
The full build has the inherited zero-valued startup guard and public inert
policy. It is **not an install candidate**: OEM restore is disabled in that
public policy and authority remains unprovisioned/epoch zero. No private policy
was copied into an executable candidate.

| Bytes | Mission 6A legacy equivalent | Mission 7 media equivalent | Delta |
|---|---:|---:|---:|
| ELF text | 394,647 | 427,771 | +33,124 |
| ELF data | 1,672 | 2,792 | +1,120 |
| ELF BSS | 26,960 | 30,456 | +3,496 |
| BIN | 400,416 | 434,656 | +34,240 |

| Reproduced local artifact | SHA-256 |
|---|---|
| `experiments/v08_m7/.pio/build/media_compile/firmware.elf` | `5a63a5b4c8551a0c23965b2d9c5ed1b01a3af22931e9a00e6f0897be8fe45099` |
| `experiments/v08_m7/.pio/build/media_compile/firmware.bin` | `3a4ff5b8aa4b9ff7656c8cbed25048d86e52c3ac936b4b742f143b5eeed76b7c` |
| Legacy equivalent ELF | `a05c873b98b71272238dbbf9dd69acb3c50014b62df5c6e74388755033fece69` |
| Legacy equivalent BIN | `e1c11c2b011fd446cc520de3bddfae4341852096ee88efb78a4a444d6f4a4f0e` |

These exact local artifacts are identified; CI generates separate artifacts
and hashes. Local paths/toolchain metadata can change hashes between builds.
The preserved clean Mission 7 CI resource artifact instead reports text 427,775
and ELF hash `aec30a993f79e32fcb8f4460df394a91db23995a8b293463e8542472d6dbdaad`.
It is historical evidence, not this local binary.

Compared with the retained 405,712-byte V2.1 image, the guarded media BIN is
28,944 bytes larger. That is a size comparison only: startup, private/OEM policy
and diagnostic composition differ, so this is not an equivalent V2.1 feature delta.
The linked `4m3m` application ceiling is `0x100000` (1,048,576 bytes; PlatformIO
maximum program size 1,044,464). This inherited BIN is below the app ceiling.
Its sector-rounded 438,272 bytes are below the live reported 638,976 free-sketch
bytes. With the current app rounded to 409,600, the modeled staging gap is
200,704 bytes. None of that establishes candidate safety or live OEM acceptance:
**flash fit passes arithmetically; stack fit fails.**

Native fixed objects remain Authority 2,104, Ingress 1,384, Receiver 1,120 and
existing server 424 bytes. Maximum explicit allocations remain: body 552,
JSON arena 4,096, image 0/2,048/4,608 bytes. Before a replacement Begin accepts,
previous image + arena + body can total **9,256 bytes**, excluding allocator,
TCP/SDK, stack and graphics costs. Arena dies before new image staging; Commit
moves ownership without another full-image copy. These are inherited bounds,
not measured target margins.

## Actual linked call-chain evidence

`tools/v08_m8_stack_gate.py` disassembles the actual ELF, verifies prologue
stack decrements and direct calls, resolves `br_ec_p256_m15`'s offset-24
function pointer to `api_muladd`, and resolves that adapter's literal-backed
tail jump to `api_muladd$part$0`. These are nested calls on one continuation
stack, not a sum of unrelated compiler frames. `p256_mul` computes its initial
window by calling `p256_add`, which calls `mul_f256`, which calls `mul20`.

| Function on reachable nested path | Actual linked frame, bytes |
|---|---:|
| `Ingress::poll<WiFiClient>` | 736 |
| `Ingress::parse` | 784 |
| `br_ecdsa_i15_vrfy_raw` | 720 |
| `api_muladd$part$0` | 528 |
| `p256_mul` | 1,264 = 32 + 1,232 |
| `p256_add` | 624 |
| `mul_f256` | 192 |
| Xtensa `mul20` | 1,056 = 32 + 1,024 |
| Crypto-only subtotal | **4,384** |
| Receiver + crypto subtotal | **5,904** |
| Core continuation stack | **4,096** |

The crypto subtotal already exceeds available stack by **288 bytes**; receiver
plus crypto exceeds it by **1,808 bytes**, before owner, application loop,
continuation entry and other callees. The preserved Core header defines 4,096
and no project stack override is configured. The SDK multiplier's 1,056-byte
scratch frame was missing from the earlier C-only compiler-frame view. This
resolves a concrete concern that Mission 7 explicitly left HOLD.

This does not prove that the physical SmallTV has crashed; the path was never
sent to it. It proves the inherited native activation fails the static stack
fit check. Raising stack size, changing crypto, switching stacks or moving parser
storage is a separate implementation and memory-budget review, not an automatic
qualification workaround. No such change was made.

Reproduce both inherited links, then run `python tools/v08_m8_stack_gate.py`.
Expected evidence is BLOCKED with 4,384/5,904 versus 4,096, with all call/prologue
checks passing. [Local disassembly evidence](V08_MISSION_8_STACK_EVIDENCE.json)
includes hashes, addresses, call instructions and pointer/tail resolution.

## Required Mission 8 instrumentation and target measurements

| Requested measurement | Mission 8 status |
|---|---|
| Free heap / largest block / fragmentation | Existing V2.1 readings above; candidate NOT MEASURED |
| Stack/high-water | Static blocker proven; physical high-water NOT MEASURED |
| Allocation failures | NOT MEASURED on candidate |
| Receiver phase / body buffer / staging size | No candidate activated; inherited bounds only |
| Challenge count / transaction state | No physical media transaction |
| ECDSA / SHA duration | NOT MEASURED on ESP8266 |
| Request/poll / longest application service interval | NOT MEASURED; HTTP GET RTT is not loop timing |
| Watchdog/reset / boot reason | Existing endpoints do not expose these; UNKNOWN |
| Wi-Fi reconnect count | Not exposed; current AP connected, no counter evidence |
| Media accept/reject counters | No candidate active; no physical media requests |

The Phase 2 bounded counter/ring-buffer diagnostic adapter was not implemented
after identifying this earlier unsafe stack prerequisite. No fabricated zeros,
host timing, CI or saturated baseline readings substitute for these missing
candidate measurements.
