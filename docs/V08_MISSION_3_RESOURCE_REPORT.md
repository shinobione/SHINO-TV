# SHINO // TV V0.8 Mission 3 — resource evidence

**Evidence: equivalent native compile/link and compiler frame accounting; no ESP8266 runtime measurement.** Full source/library/flag construction is in the [bridge report](V08_MISSION_3_FULL_BRIDGE_REPORT.md). Unlike Mission 2's small unstarted sketch, these images retain the actual bridge, browser assets, metrics and display implementation. Neither image has been run or installed.

## Local Windows Xtensa GCC 10.3.0 results

| Measure, bytes | Full baseline | Full preparse experiment | Delta |
|---|---:|---:|---:|
| ELF `size` text | 393,435 | 394,263 | **+828** |
| ELF data | 1,672 | 1,672 | **0** |
| ELF BSS | 26,808 | 26,960 | **+152** |
| Generated BIN | 399,200 | 400,032 | **+832** |
| PlatformIO reported flash | 395,051 | 395,879 | **+828** |
| PlatformIO reported RAM | 40,344 | 40,520 | **+176** |
| Linked anonymous bridge WebServer object (`nm -S`) | 272 | 416 | **+144** |

PlatformIO's ESP RAM estimate includes sections beyond ELF data/BSS (including IRAM); do not equate either count with free heap. An additional read-only media literal and alignment account for growth outside the server object; no image buffer or production verifier is linked. The ELF text total includes read-only content, not simply executable instructions. BIN sizes are local build outputs only, not installation packages. Absolute link results may differ by build path/tool host; compare equivalent pairs in the same run. CI prints its own pair and exact source head.

Linux [CI run 36628802737](https://github.com/shinobione/SHINO-TV/actions/runs/36628802737) at code head `62d19b8b0dc5790362a6a1806b1379d18ef4ff55` also linked both full images: text **393423/394251**, data **1672/1672**, BSS **26808/26960**, BIN **399184/400016**. Its paired deltas are exactly **+828/0/+152/+832**, and bridge server objects are **272/416** bytes. The small absolute Windows/Linux differences are reported rather than normalized away. No target runtime measurement was made in CI.

Local ELF SHA-256: baseline `89b9ed6a0df20627c793d74882f8bcee0ab16d738f47a85bb1f1baf26f824100`; experiment `153a17eac398c1d2546b0f1420980648f1c3e8565803d207b2e7570960cb1b71`. These identify the local uninstalled outputs; no deployable hash approval is implied. `tools/v08_m3_resource_report.py` also asserts real bridge symbols, exactly one linked bridge server, and overlay-symbol presence only in the experiment.

## Compiler stack frames, not stack high-water

The actual native bridge translation unit was compiled with `-fstack-usage`. Selected per-function frame records:

| Function | Baseline bytes | Experiment bytes |
|---|---:|---:|
| FirstBootBridge loop | 16 | 16 |
| WebServer handleClient | 64 | 64 |
| Experimental first-line preparse | absent | **192** |
| Generic request parser | 208 | 208 |
| authenticate | 256 | 256 |
| authenticateDigest | 368 | 368 |
| browserSessionValid | 96 | 96 |
| acceptMetrics | 224 | 224 |
| paintNativeDashboard | 240 | 240 |

These compiler records are static frames for this optimization/link configuration, not maxima of an entire call chain. They omit deeper String/JSON/crypto/network/library calls, interrupts, SDK activity and actual stack layout/high-water. The preparse has a local 131-byte decode array; a naive source-size sum would undercount its compiler frame. Loop + handle + preparse named frames total 272 bytes **before** deeper calls, not a certified runtime bound. The parser frame and preparse frame are sequential, while generic parser's nested callees still contribute. Do not add every table row as if simultaneously live.

## Phase allocation and work accounting

| Phase | Evidence now | Unmeasured/excluded costs |
|---|---|---|
| P0 accept/first-line | One owner; fixed 131-byte member slot including terminator; 130-byte wire cap; 64 input reads per poll, at most three polls for a complete maximum line; absolute unsigned elapsed ≥2000 ms rejection | WiFiClient/lwIP receive buffers, accept/FIN costs, scheduler time, SDK stack. A 131st byte may be consumed to detect overlength, without storing it. |
| P0 classify | Once-decode into fixed stack array; bounded namespace scan. Worst search work is bounded by line length and 20-byte literal; no new generic String in this function | Instruction/cycle count, available/read blocking behavior, real per-poll duration, WDT margin. Host counts prove source work, not CPU timing. |
| Legacy handoff | Exact prefetched line copied once into generic String; original parser then owns headers/body | String/header/argument allocations are uncapped; declared legacy body may be attacker-sized before handler auth. No global heap/DoS bound is credited. |
| Actual legacy handler | Valid metrics body is 16–384 bytes in handler; real JSON/state code executed on host; four-card formatting uses fixed buffers. Browser sessions remain two String tokens | Original parser already buffered the body; payload String copy, ArduinoJson allocator, status responses, route registration allocations and browser-session String capacity/overhead are not a measured ESP heap peak. |
| Media deny path in native candidate | Reject at line boundary; **no header, payload, image or crypto allocation by this path**, no legacy callback | TCP may already buffer body bytes internally. Zero application body consumption is not zero TCP RAM. |
| Proposed P1 Gate 1 host profile | External stream reads ≤1024 header bytes; an additional canonical-header fixture buffer and reused verifier buffer coexist on the PC. No body read/allocation before proof | Node/SF/OpenSSL allocations are not native budget evidence. No ECDSA/SF/SHA context or key/challenge production structure is linked in the native image. |
| Proposed P2–P5 media receiver | Existing model: ≤552-byte body; 4608/2048/0-byte image staging, 9/4/0 tiles; no full-image Commit copy. Model tests remain intact | No native staging/ownership, JSON metadata, final image SHA, rendering or five-second media integration implementation. |

The prior [resource worksheet](V08_NATIVE_RESOURCE_BUDGET.md) remains an assumption sheet. Correct P0 accounting now needs the **131-byte slot**, alignment and actual object growth, rather than treating its 130 wire bytes as total storage. A conservative line + header + record overlap is **131 + 1024 + 552 = 1707 bytes**, before fields/crypto/stack/TCP; adding one image and an illustrative 512-byte metadata allowance yields **6827 / 4267 / 2219 bytes** for 48×48 / 32×32 / coverless. These are named workspace floors, not runtime requirements or reserves. 64×64 remains a rejected comparison (8192 image bytes/16 tiles). No historical device free-heap value is used to declare available reserve.

## Acceptance exclusions and remaining gate

No measurements of ESP free heap, largest contiguous block, fragmentation, runtime stack high-water, crypto CPU, per-poll CPU duration, watchdog feed interval, TCP read-ahead/FIN/RST, real concurrency fairness, browser latency, SPI/display timing, power loss or physical freshness/overlay jitter exist. Host compile times, host no-op graphics and Node test elapsed times are not substitutes. No host allocator result is labeled target RAM.

Before runtime qualification: approve an explicit engineering reserve; instrument all phase boundaries and allocation failures; measure largest block and stack overlap, worst blocking interval and application feed gap; test slow/competing legacy clients, interrupted/pipelined media and repeated replacements; measure four-metric freshness and five-second overlay timing under load. The current stock legacy body/header path can still starve the loop; hardening it is a separate behavior decision. **GO** for measured link/frame research; **HOLD** for resource qualification; **BLOCKED** for route activation or physical installation.
