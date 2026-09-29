# V0.6 — memory, allocation and stress report

**29 September 2026 — host-only result: 64×64 native media remains HOLD/BLOCKED. No production GO.**

This mission started from clean `feature/shino-tv-v06-native-audit` commit `4c15287df3aa8f61500264790690b83cfcb26883`. It read the complete Mission 1 source audit, Mission 2 security review, V0.5 host gate, `media_wire_v1.py` and both existing media test modules. The new laboratory has no socket, address, credentials, firmware route, filesystem or update capability. Frozen PR #20, installed review-003, V0.1 tray/autostart, numeric metrics firmware and the application-only OEM return are unchanged.

Authentication and HTTP ingress remain **BLOCKED**. The synthetic model begins after a hypothetical authorization decision and cannot close either blocker. All byte totals below distinguish receiver image payload from CPython objects and unmeasured native overhead.

## 1. V0.5 allocation-lifetime inventory

### PC sender

`jpeg_to_rgb565()` (`companion/media_wire_v1.py:51-79`) loads and converts a bounded JPEG on the PC. At different points it owns the Pillow image/decoder state, a 64×64 RGB `pixels` bytes value (**12,288 B**), an **8,192 B** result `bytearray`, and the returned **8,192 B** immutable RGB565 value. These lifetimes overlap during conversion. `prepare()` (`:132-179`) retains that raw cover, calculates SHA-256, builds canonical metadata, and slices it into sixteen independent 512-byte packet bodies. The retained raw cover plus packet payloads therefore represent **16,384 B of PC payload** after preparation, excluding tuples, packet objects, JSON, strings, Pillow and decoder memory. This is PC memory, not proposed ESP storage.

`canonical_metadata()` (`:81-115`) serializes a Python dictionary to a JSON `str`, encodes another `bytes` value, and returns it. `prepare()` may repeat this work while shortening extreme metadata. Track identity constructs another JSON string/bytes value and a SHA object (`:42-48`). These are temporary/cumulative allocations; they do not define receiver capacity.

### V0.5 emulated receiver

At Begin, `EmulatedReceiver.begin()` (`:207-225`) decodes the input bytes to a Unicode string, parses a new dictionary and strings with `json.loads`, serializes another canonical bytes value for equality, then allocates `bytearray(cover_len)`. The input bytes remain caller-owned during the call. The pending dictionary retains the parsed document, staging array, counters and time. Python object overhead is variable and not counted in the 8,192-byte payload.

Each normal tile has a 512-byte request/packet body outside staging. Copying into `pending["buffer"]` writes in place (`:227-254`). The duplicate comparison slice creates a temporary 512-byte `bytearray`. CRC32 creates no specified 512-byte Python copy, but library-internal behavior is not a native guarantee.

At Commit, `raw = bytes(pending["buffer"])` (`:256-272`) creates a new immutable **8,192 B** object before completeness/SHA validation. If a previous cover is committed, the live receiver payload can therefore be:

1. previous committed bytes: 8,192 B;
2. new pending bytearray: 8,192 B;
3. new Commit bytes copy: 8,192 B.

The steady replacement peak is **24,576 B of image payload alone**. SHA-256 state, metadata, dictionaries, the HTTP library and display work are additional. On success, pending/staging and the old committed tuple become unreachable after assignment; the new bytes remains. This is a peak-lifetime finding, distinct from final capacity (8,192 B) and cumulative allocation volume (16,384 B of receiver image allocations per covered transfer).

Ordinary `ProtocolError` calls `fail()` (`:195-205`), releasing pending and revoking prior art by dropping references. Mission 2 demonstrated that `MemoryError` from JSON parsing/staging or Commit copy escapes this path and can leave old/pending state retained (`test_media_auth_transfer.py:438-461`). The eight `test_gap_*` results remain defect characterizations, not repaired security tests.

## 2. Isolated strategy comparison

`companion/media_memory_lab.py` is a separate experimental ownership model. Its `LogicalAllocator` measures receiver image storage and can deterministically fail staging/Commit allocations. `MemoryLabReceiver` binds Commit to a transaction, rejects a competing Begin without resetting its deadline, and releases/revokes on owned failure. Its small JSON input check is not the full V0.5 canonical metadata validator. It intentionally supplies **no authentication or HTTP framing**.

The following are steady replacement peaks after one cover already exists:

| Candidate | 32×32 (2,048 B) | 48×48 (4,608 B) | 64×64 (8,192 B) | Integrity and failure trade-off |
|---|---:|---:|---:|---|
| A. V0.5 staging + Commit copy, retain old | 6,144 B | 13,824 B | **24,576 B** | Immutable published copy; old+stage+copy peak. Owned allocation/hash/interruption failure must release stage and revoke old. Current V0.5 does not catch `MemoryError`. |
| B. Single ownership transfer, retain old while staging | 4,096 B | 9,216 B | **16,384 B** | SHA can read staging in place; verified staging becomes committed ownership. Preserves old art during a healthy transfer, but requires a renderer/API that accepts the owned buffer and never aliases/mutates it. |
| C. Revoke old before staging + ownership transfer | **2,048 B** | **4,608 B** | **8,192 B** | Lowest image peak. No rollback image: once Begin is accepted, failure leaves PC HEALTH/text fallback. Requires an intentional redraw and avoids obsolete-art fallback. |
| D. Smaller images | As above | As above | As above | 32×32 reduces area/detail to 25% of 64×64; 48×48 to 56.25%. Pixel quality, scaling and ST7789 transfer behavior are unverified. Protocol v1 currently fixes 64×64; these sizes are laboratory candidates only. |
| E. Coverless/text-only | 0 B new image | 0 B | 0 B | Strongest memory fallback. A/B may retain an old cover until metadata-only Commit; C revokes it at Begin. Successful metadata-only publication must clear previous art. Font/text layout and metadata storage still need native bounds. |

For the first cover with no previous art, A peaks at 2×N and B/C at 1×N. “Peak” is simultaneous logical payload, “capacity” is the final live cover, and “cumulative” is all image bytes requested over time. In the 250-cycle 64×64 run, A allocated 4,096,000 B cumulatively (500 allocations) while peaking at 24,576 B; B/C allocated 2,048,000 B cumulatively (250 allocations) while peaking at 16,384/8,192 B. C lowers peak by deliberately giving up visual rollback.

Additional allocations remain expected for all candidates: bounded request/header/body storage, authentication/Digest parsing, metadata input, UTF-8/JSON tree and canonical serialization, transaction/replay state, SHA-256 context, one 512-byte tile view/buffer, `String` capacity, TCP/lwIP, Wi-Fi, response serialization, graphics calls and stack frames. The lab does not estimate them.

## 3. Active native source memory analysis

The active owner is `ESP8266WebServer server(80)` in `FirstBootBridge.cpp:68`; legacy `Webserver`/`Api`/`SceneManager` is inactive. Existing memory classes are:

| Class | Verified source behavior | Native cost still unknown |
|---|---|---|
| Fixed/static | `FslessMetrics::state` (`FslessMetrics.cpp:7`) is one snapshot. Bridge globals include server, SSID, two `BrowserSession` String tokens, draw caches, and optional fixed heap observer (`FirstBootBridge.cpp:68-90,275-283`). Display owns static `Arduino_HWSPI`/`Arduino_ST7789` (`DisplayManager.cpp:35-36`). | Object ABI size, core/server/lwIP internals, String capacities and library globals need a link map and runtime phase measurements. |
| Stack | Metrics validation builds `Snapshot next{}` (`FslessMetrics.cpp:29`). Dashboard copies a Snapshot and creates four `Card` values with 16-byte number arrays (`FirstBootBridge.cpp:347-367`). The active dashboard directly draws primitives and has no application framebuffer. | Worst stack/high-water during HTTP + Digest + JSON + SHA + tile draw is unmeasured. `DisplayManager`'s general text wrapper uses ten 128-byte output lines plus 128-byte line and word arrays (`DisplayManager.cpp:412-486`), though the active four-card painter does not call it. |
| Dynamic heap | Cookie parsing creates/substrings `String`; status/metrics routes create `JsonDocument` and response `String`; `acceptMetrics()` copies `server.arg("plain")`, then ArduinoJson 7.4.3 parses it (`FirstBootBridge.cpp:93-272`, `platformio.ini:40-41`). The pinned WebServer buffers ordinary POST data before the handler, as Mission 2 established. | Exact capacities, allocator fragmentation, transient body/header/argument copies, response overlap and allocation-failure paths are unmeasured. Application length checks occur too late for ingress safety. |
| Graphics | Four 108×108 cards are drawn directly; `paintCard()` yields after each (`FirstBootBridge.cpp:285-344`). No source-owned 115,200-byte full frame is present. General GIF playback can dynamically `new Gif()` (`DisplayManager.cpp:660-687`) but is inactive in this boot profile. | Arduino_GFX/SPI driver internal buffers, RGB565 tile write behavior, time per art row/tile and overlay text costs need a compile/link audit and measured build. Do not activate GIF/FS for media. |
| Heap observer | Opt-in `Candidate` is statically bounded to <=96 B and samples `ESP.getHeapStats` after existing work at most once per second, for 1,024 samples (`ShinoHeapDiagnosticCandidate.h:16-67`; `NativeOtaHeapReview.h:13-69`; cadence `:12-39`). | It misses sub-second allocation peaks and any phase completed before the post-loop sample. Default `esp12e` omits it. Status serialization itself occurs after the stored sample. |
| Scheduling | `handleClient()` runs before repaint, OEM tick, heap poll, explicit watchdog feed and yield (`FirstBootBridge.cpp:468-480`). | Slow/parser-blocked requests may delay metrics acceptance, stale repaint, cleanup and watchdog progress. Host state interleaving does not measure native fairness or interrupt latency. |

The historic owner report — minimum free heap **28,272 B**, minimum largest block **26,216 B**, maximum fragmentation **12%** — came from a finite V2.1 review-003 window without native media. It is evidence about that past observation only. Subtracting any row of the strategy table from 26,216 or 28,272 would ignore changed code/static data, request/parser overlap, stack, fragmentation, timing and unsampled peaks, so this report makes no such safety claim.

## 4. Deterministic stress results

`test_media_memory_lab.py` adds 20 tests organized around allocation peaks, cleanup, transaction stress, metrics isolation and host-probe labeling. It covers repeated transfers, rapid/competing Begin, exact/conflicting duplicates, order, expiry, stale Commit binding, staging/Commit/metadata-copy/capacity failure, previous-art revocation, corrupt SHA, interruption, malformed/long UTF-8 metadata, coverless transition, overlay return and four-metric freshness. A direct V0.5 test checks that pause, resume and progress updates for one track do not restart the five-second overlay. The long test performs **500 cycles for each of 3 strategies × 4 sizes = 6,000 transfers**, with synthetic metrics updated during each covered transfer (and before Commit for coverless transfers).

Results on the local bundled CPython 3.12.14:

| Check | Result |
|---|---|
| New Mission 3 tests | **20/20 passed**. |
| Full companion discovery | **116 run, 112 passed, 4 skipped**. The four pre-existing compiler/OpenSSL-dependent cases remain NOT EXECUTED. |
| Node scene/native-browser UI | **20/20 passed**. |
| Existing tools discovery | **269 run: 160 passed, 11 failed, 1 error, 97 skipped**, unchanged from Missions 1/2: missing C++ compiler/preprocessor causes the 11 failures; Windows symlink privilege `WinError 1314` causes the error. |
| Native firmware/media route, physical LCD, ESP heap | **NOT EXECUTED / absent.** |

The final full-suite counts above are recorded after execution in this mission. Environment failures remain separate from functional regressions; tests were not weakened.

## 5. Host measurements and limitations

Running `companion/media_memory_lab.py` for 250 V0.5 transfers produced this **CPython-only** observation: `tracemalloc` current 14,223 B, peak 32,821 B, elapsed 0.054707 s; `sys.getsizeof(bytearray(8192))` was 8,249 B and `sys.getsizeof(bytes(8192))` 8,225 B. Synthetic sender metadata/packets were constructed before tracing and excluded. The logical stress results matched the peak table and preserved the exact metric boundary: fresh at +6,000 ms, stale at +6,001 ms.

These figures vary by interpreter/run and measure traced Python allocations, not total process RSS, Pillow, native libraries or ESP8266 heap. Timing is neither a network nor LCD benchmark. The deterministic logical ledger is reproducible bookkeeping, not allocator fragmentation or contiguous-block evidence.

## 6. Allocation failure and metrics isolation

The experimental model handles staging allocation failure, Commit-copy or metadata-copy failure, logical capacity failure, digest mismatch, conflict, expiry and interruption by releasing pending image tokens, revoking obsolete committed art for the accepted transaction, returning to PC HEALTH and retaining a terminal transaction ID. A stale Commit for another transaction neither publishes nor cancels the current transfer. Competing Begin returns BUSY without a new allocation or deadline extension. This demonstrates a desired ownership contract, not a V0.5 fix or native implementation.

For clarity under long host stress, the model's `terminal_tx` set is deliberately unbounded (250/500 IDs in the reported runs). That avoids reproducing V0.5's replay-cache flush defect, but is not a native memory design. A future authentication session needs a bounded, measured replay representation and lifetime that cannot silently re-authorize evicted transaction IDs.

The independent `MetricsFixture` retains exactly four values and the unsigned `>6000 ms` stale boundary throughout every media failure. Metrics accept/recovery continues in the interleaved 6,000-transfer test. This establishes deterministic state separation only. It does not exercise `server.handleClient()`, scheduling latency, real `FslessMetrics.cpp`, LCD repaint or watchdog behavior.

## 7. Required measurable acceptance criteria for a future native candidate

A later unconnected native candidate should remain HOLD until it can provide all of the following without weakening Missions 1/2:

1. A link map/static-RAM and worst-stack inventory for the exact build, including WebServer, ArduinoJson, SHA, graphics and observer.
2. Phase-tagged free heap **and largest contiguous block** immediately before/after authorization, bounded header parse, body/tile allocation, JSON parse, staging allocation, every tile, SHA, publication, rendering and cleanup. One-second post-loop sampling is insufficient.
3. Demonstrated allocation-failure handling at every phase with zero leaked pending storage, obsolete-art revocation under the chosen policy, transaction replay state intact and four metrics unchanged.
4. Mixed-load latency: continuous metrics POST/GET, dashboard reads, partial/slow media traffic, transfer expiry and overlay rendering, with measured maximum `handleClient()` occupancy, metric acceptance delay, stale-frame delay and watchdog service interval.
5. Repeated replacement/coverless/track-change soak long enough to expose fragmentation trends; report minimum free heap and largest block by phase, not one aggregate minimum. Define an engineering reserve before testing rather than deriving it from the historical owner sample.
6. Exact RGB565 draw path and render time with no full-screen framebuffer, no filesystem and a forced return/redraw of all four cards after five seconds or failure.
7. Compiler/OpenSSL/Linux-symlink CI green at the exact commit, then a separate review before any owner-device observation. Passing host/native tests still would not authorize installation.

No universal numeric “safe heap” threshold is invented here. Acceptance needs an exact implementation, measured phase peaks, a documented reserve for Wi-Fi/core/stack variability, and failure injection that proves cleanup.

## 8. Decision and recommendation

- **GO:** retain this host-only lab and use ownership/revocation as design candidates.
- **HOLD:** 64×64 RGB565 as an experimental quality target. Strategy A is not defensible for native work: its 24,576-byte payload peak leaves all native overhead unaccounted for. Strategy B materially reduces copies but still needs two covers (16,384 B). Strategy C requires one cover (8,192 B) and has the clearest bounded ownership, at the cost of blank/text fallback during replacement failure.
- **INVESTIGATE NEXT:** compare 48×48 strategy C (4,608 B) against 32×32 (2,048 B) and coverless text on the 240×240 simulator, then carry only the smallest acceptable candidate into an unconnected native allocation prototype. Keep 64×64 available for comparison, not as the presumed default.
- **BLOCKED:** native route registration, production authentication, real request ingress, device contact/build installation, firmware/OEM/FS policy changes. Mission 2 pre-allocation framing and real authorization blockers remain critical and unchanged.

Mission 3 does not select a production image size. The memory evidence favors **revoke-old + ownership transfer with mandatory coverless fallback**, while visual evidence is still absent. Stop here before Mission 4.
