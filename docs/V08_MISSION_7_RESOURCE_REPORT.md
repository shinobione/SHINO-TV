# Mission 7 native resource evidence

30 September 2026, Europe/Paris. Start `4d6180959b843c64e92b72425134c2dfc6688c88`. **Full Xtensa compile/link and compiler frames only; no target runtime qualification.**

`experiments/v08_m7` copies only tracked firmware sources, never generated private configuration. Both environments link the full equivalent SHINO source graph with the same pinned esp12e/Core3.1.2/espressif8266@4.2.1, linker/flash/lwIP settings, ArduinoJson7.4.3/GFX1.6.4/AnimatedGIF2.2.0 and public inert policy. `setup`/`loop` retain the research startup guard at zero. `legacy_compile` uses Mission6A. `media_compile` uses its separate media owner/receiver, with the same existing bridge server and no extra server. Its trusted authority starts at epoch0 with no enrolled principal. No route can accept media by default; no image is installed or started.

Reproduce full links using `pio run -d experiments/v08_m7 -e legacy_compile -e media_compile`, then `python tools/v08_m7_resource.py`. ELF hashes, actual object symbols, sections and compiler frames are retained in evidence. The final local comparison is recorded below; final exact-head CI values are independently generated in the Draft PR artifact.

| Field (bytes) | Mission6A full graph | Mission7 full graph | Delta |
|---|---:|---:|---:|
| text | 394647 | 427771 | +33124 |
| data | 1672 | 2792 | +1120 |
| BSS | 26960 | 30456 | +3496 |
| BIN | 400416 | 434656 | +34240 |
| existing bridge server | 416 | 424 | +8 |

These are final local development measurements with the owner timer service and native profile1.1 normalization, at a dirty snapshot of the starting SHA. They are not borrowed from Mission6C or a minimal-server specimen.

Native object symbols: Authority2104 bytes, Ingress1384, Receiver1120. Ingress includes its1025-byte header slot, parsed proof/target/digest/signature/ticket state and body pointer; it allocates at most552 body bytes after Gate1. Authority contains16 fixed principal rows, four challenge slots and bounded ordinal/serial/revision state. Receiver includes pending/sink metadata and image pointers; it allocates exactly0/2048/4608 staging bytes after accepted Begin. SHA contexts use112 bytes (compiler/API representation, not stack high-water).

The temporary native JSON arena is exactly4096 heap bytes, created after Gate2 and released before new image staging. A prior sink image can remain alive while validating a new Begin: maximum explicit image+arena+body storage at that point is4608+4096+552=9256 bytes, excluding allocator overhead, fixed objects, WiFi/lwIP/SDK buffers and all stack. Once Begin is accepted the prior image is released before new staging. Commit moves the original image allocation; metadata copy is bounded513 bytes. PC's64-bit JSON arena cap is8192; PC object sizes are not ESP object sizes.

Compiler frames observed in the development build: owner96, first-line208, Gate1 parse784, Begin192, metadata400, media poll736; these are individual frame measurements, not independent additive memory budgets or whole-call high-water. Separate `-Os -fstack-usage` compilation of exact native BearSSL C yields raw verifier720, P-256 mulgen1344/mul1264/add608, and SHA round320 bytes, among other recorded frames. These crypto frame compilations are diagnostic objects, not executed binaries or proof of the precompiled SDK's exact build flags. Xtensa multiplier assembly and SDK call stacks lack full frame/high-water evidence. Nested crypto call chains can approach/exceed a small ESP8266 stack; **HOLD** for stack/runtime safety. No claim of safe aggregate stack follows from a successful link.

No free heap, largest block, fragmentation, allocation-failure resilience across SDK/native operations, native ECDSA latency, WDT service bound, socket flush/abort/ACK/drain timing or LCD timing has been measured. Host observed timing is load dependent and includes portable-C P-256; the64-byte/poll bound limits application socket reads, not cryptographic or WiFi duration. No physical evidence exists. Native memory/runtime qualification remains HOLD.
