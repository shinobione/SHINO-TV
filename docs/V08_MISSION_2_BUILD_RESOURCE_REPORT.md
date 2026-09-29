# SHINO // TV V0.8 Mission 2 — isolated build and resource evidence

The separate `experiments/v08_preparse` PlatformIO project pins `espressif8266@4.2.1` and `framework-arduinoespressif8266@3.30102.0` (ESP8266 Core 3.1.2). Its default `baseline_compile` environment includes the stock library. The opt-in `preparse_compile` environment fingerprints the six pinned source files, copies the WebServer library to an ignored local overlay, changes only the copied header/parser/implementation, and defines `SHINO_V08_PREPARSE_EXPERIMENT`. The installed package and production `firmware/` tree are not patched. Both sketches hold a WebServer object for comparable linking but never call `begin()`, set up Wi-Fi or register a route. A zero-valued volatile guard retains `handleClient()` in the link graph without calling it in the research sketch. The generated `.bin` files are measurement artifacts, not installable candidates.

## Actual local Windows builds

PlatformIO 6.1.18, pinned Core 3.1.2, `esp12e`, Xtensa GCC 10.3.0. Both compile and link **PASS**. `tools/v08_native_size_report.py` read the linked ELF with `xtensa-lx106-elf-size` and the generated BIN lengths:

| Isolated image | ELF text | ELF data | ELF BSS | BIN bytes | PlatformIO reported RAM |
|---|---:|---:|---:|---:|---:|
| Stock baseline | 289,991 | 1,552 | 25,944 | 295,632 | 28,384 / 81,920 |
| Deny-all preparse | 290,779 | 1,552 | 26,096 | 296,432 | 28,556 / 81,920 |
| Candidate minus baseline | **+788** | **0** | **+152** | **+800** | **+172** |

The ELF BSS and PlatformIO RAM formulas count different linked regions; both figures are reported without equating them. This is a small unconnected sketch, not the full SHINO application. The 152-byte BSS delta is consistent with the 131-byte fixed first-line member plus length, start tick, close flag and alignment. The 131-byte local percent-decoding array is automatic stack storage; linked BSS and BIN figures do not measure its peak stack consumption. No active HTTP listener exists in this image.

## Source-level allocation and work accounting

| Phase | Candidate allocation and work | Remaining unmeasured cost |
|---|---|---|
| Accept | Reuses the one stock `_server.accept()` and `_currentClient`; initializes fixed members. | TCP PCB, Wi-Fi buffers and connection memory. |
| First-line classification | One 131-byte member slot; at most 64 available socket bytes examined in a `handleClient()` call; 130-byte CRLF-inclusive limit; a local 131-byte decoding array on completion; fixed scans of at most 128 text bytes; no `String` or heap allocation in this new method. | Compiler stack frame/high-water, scheduler time, yield timing, actual TCP arrival behavior. |
| Legacy handoff | Constructs one bounded `String` from the prefetched line; existing parser resumes at the first unread header byte. Host tests exercise exact cursor preservation. | Allocator overhead/capacity and any stock header/body parser allocations. |
| Media candidate | Calls one close helper; reads no header or body byte in the source-executed shim. No Gate 1, Gate 2, media staging or crypto context. | Actual TCP buffering and FIN/pipeline race behavior. |
| Stock legacy body and handler | Remains the pinned parser/handler path. | Existing unbounded header line and declared POST-body work, browser Digest fallback, metrics JSON, OEM conditional upload behavior under mixed load. |

The first-line deadline uses unsigned 32-bit subtraction and expires at elapsed `>= 2,000 ms`, including tick wrap. It does not reset when progress arrives. The bounded reader returns after one 64-byte slice if no line completion, allowing the outer loop to continue. A disconnected partial client is rejected; a queued client is not accepted while the first remains owned. Host execution proves these decisions under fake clients, not a native watchdog or heap reserve. The fixed first-line cap can reject otherwise legitimate long legacy targets, so general legacy acceptance parity is not established.

## Evidence and exclusions

`tools/v08_source_executed_preparse.py` fingerprints pinned Core source, materializes the overlay, extracts the **actual transformed** `_v08ReadFirstLine()`, `_v08CloseOnce()`, `handleClient()`, `_parseRequest()` and `_collectHeader()` methods plus pinned Stream/String primitives, then compiles and runs them with a host fake client/server. **37/37 assertions PASS under MSVC x64**: dashboard and metrics URI handoff, exact first-line cursor, media/encoded-media denial before headers, malformed line/escape/size, partial read, FIN, wrap deadline, competing client, close-once helper and a keep-alive pipeline. The fake owner is not the ESP8266 TCP stack. This is stronger evidence than a parallel mock implementation but does not qualify an active route.

No physical ESP8266 heap, largest free block, stack high-water, CPU cycle budget, watchdog feed interval, display/SPI cadence, browser login, actual metrics update latency, OEM return, native P-256 verifier or challenge store was measured. No firmware installation, OTA, sender or device communication occurred. The full production application and OEM path were not rebuilt with this overlay. These are required acceptance measurements before any active ingress proposal.
