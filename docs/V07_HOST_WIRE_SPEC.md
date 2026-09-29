# SHINO // TV V0.7 Mission 1 — host media wire v2

**Status: host-only specification and deterministic reference. No native route, device sender, production authentication, OTA, firmware build or installation.** This is a new wire version (`v=2`, `STV7` envelope), not a binary-compatible revision of frozen V0.5 `media_wire_v1.py`. The reference is `companion/media_wire_v2_host.py`; its tests are `companion/test_media_wire_v2_host.py`. The eight V0.6 Mission 2 `test_gap_*` characterizations of V0.5 remain intact and continue to pass as historical defect evidence.

## Source and decision boundary

This design follows `V06_REVIEW_GATE.md`, `V06_MEDIA_AUTH_AND_TRANSFER_REVIEW.md`, `V06_MEMORY_AND_STRESS_REPORT.md`, `SECURITY_AUDIT_01.md`, the frozen V0.5 host codec and the V0.6 memory lab. The active native bridge uses a single `ESP8266WebServer` on port 80; its generic POST parser currently buffers body data before handler authorization. No existing native path safely accepts these records. Browser read cookies, the numeric metrics route and OEM return grant no media authority. The v2 host `Authority` object is only an injected assertion that a hypothetical external verifier has already authorized the **actual** request. It cannot verify a password, Digest proof, nonce, HTTP framing or request body.

## Payload variants and pixel interpretation

| Variant | Width × height | RGB565LE bytes | Indexed tiles | Image storage with revoke-first ownership transfer | Area versus 64×64 |
|---|---:|---:|---:|---:|---:|
| Primary experiment | 48×48 | **4,608** | **9 × 512** | 4,608 B | 56.25% |
| Smaller fallback | 32×32 | **2,048** | **4 × 512** | 2,048 B | 25% |
| Text-only fallback | 0×0 | **0** | **0** | 0 B | 0% |
| V0.5 reference comparison only | 64×64 | 8,192 | 16 × 512 | 8,192 B if the same new ownership policy were used | 100% |

The v2 receiver **rejects 64×64**. RGB565LE is row-major, left-to-right/top-to-bottom, two bytes per pixel. `word = ((R8 >> 3) << 11) | ((G8 >> 2) << 5) | (B8 >> 3)`; transmit low byte then high byte. Red `#ff0000` is `00 f8`, green `#00ff00` is `e0 07`. The PC must resize/crop and convert before transport. The device proposal neither decodes JPEG nor stores a framebuffer, URL, file or image cache. Physical ST7789 quality, scaling and draw timing remain unverified.

## Exact v2 metadata

Begin body is **1–512 bytes** of UTF-8 JSON, canonicalized with keys sorted by Unicode code-point order, no spaces after `:` or `,`, `ensure_ascii=false`, lowercase `true`/`false`/`null` tokens, and base-10 integers without leading zeros. In strings, `"` and `\` are backslash escaped; other allowed non-ASCII characters are emitted directly as UTF-8, not `\u` escapes. Text fields disallow C0/C1 controls and surrogate code points, so no control-character escape form is valid there. No Unicode normalization is performed. This is the exact serialization accepted by the host reference's `json.dumps(..., ensure_ascii=False, sort_keys=True, separators=(",", ":"), allow_nan=False)` followed by UTF-8 encoding. The receiver rejects noncanonical bytes, duplicate/unknown/missing fields, invalid UTF-8, incorrect types, and any mismatch between envelope transaction and metadata `tx`. All 16 fields are mandatory:

| Field | Exact value or constraint |
|---|---|
| `v` | integer `2` (boolean is not an integer) |
| `tx` | 32 lowercase hex characters encoding the 16-byte transaction ID |
| `state` | `PLAYING`, `PAUSED`, `STOPPED`, `NO_SESSION` or `UNAVAILABLE` |
| `source`, `title`, `artist`, `album` | strings, respectively ≤80/60/60/48 Unicode code points; no C0/C1 controls or surrogate code points |
| `position`, `duration` | `null` or integer 0..604800 seconds; position ≤ duration if both present |
| `track_key` | 64 lowercase hex characters; media identity only, never authorization |
| `width`, `height` | both `48`, both `32`, or both `0` |
| `pixel_format` | `RGB565LE` for images, `NONE` for text-only |
| `cover_len` | exactly 4608, 2048 or 0 according to dimensions |
| `tile_count` | exactly 9, 4 or 0 according to dimensions |
| `cover_sha256` | lowercase 64-hex SHA-256 of the exact raw image bytes, or JSON `null` when coverless |

The global 512-byte limit remains binding even when every individual text field is within its limit. A producer must shorten optional text before Begin; the receiver never silently truncates. For a coverless transaction, Commit is still required and clears previously accepted artwork. V0.5 canonical metadata is a different schema and is never accepted by v2.

## Exact binary record and prospective HTTP carriage

Each operation is one complete record: **40-byte fixed header followed immediately by exactly `payload_len` bytes**. All multi-byte header integers are unsigned **big-endian**; pixel data alone is little-endian. No padding, trailer, second record, chunked body or extra bytes are accepted. The host encoder returns header and body separately to make the pre-body boundary explicit.

| Offset | Size | Field | Rule |
|---:|---:|---|---|
| 0 | 4 | magic | ASCII `STV7` |
| 4 | 1 | version | `2` |
| 5 | 1 | operation | Begin `1`, Tile `2`, Commit `3`, Abort `4` |
| 6 | 2 | flags | zero; all other bits rejected |
| 8 | 8 | epoch | nonzero authorization/boot epoch, externally established |
| 16 | 16 | transaction | first 8 bytes equal epoch; last 8 bytes are nonzero, monotonic transaction sequence |
| 32 | 2 | tile index | 0 for Begin/Commit/Abort; 0..8 or 0..3 for the selected image |
| 34 | 2 | payload length | Begin 1..512; Tile exactly 512; Commit/Abort 0 |
| 36 | 4 | CRC32 | IEEE/zlib CRC32 over the payload; empty payload CRC is 0 |

The highest complete request body is **552 bytes** (40+512). A future native adapter would reserve `POST /api/v2/bridge/media` with `Content-Type: application/vnd.shino-tv.media-wire-v2`, one complete record per request, exact decimal `Content-Length` 40..552, and a connection close after the response. That route is **not registered**. Its adapter must reject duplicate/invalid `Content-Length`, all `Transfer-Encoding`, `Expect`, content encoding, multipart, extra bytes, partial FIN, oversized request line/headers and unsupported methods/types before body-dependent allocation; authenticate and authorize the actual method/path/operation/principal/epoch/transaction before reading a body. Exact native header workspace, timeout, idle budget and per-poll work limits require separate source-executed review. An application handler called after the current WebServer parser does **not** meet the ordering requirement.

The CRC detects transport corruption per record; final SHA-256 checks the complete raw image. Both are sender-provided checksums and **neither authenticates the sender or body**. An actual production scheme must cryptographically bind the request's actual method and target, operation, principal, epoch, transaction and body, enforce nonce freshness/replay control and a new unpredictable epoch after reboot. Existing Basic acceptance, shared Digest nonce, unbound Digest URI and `qop=auth` body gap remain blockers. Browser cookies cannot authorize media writes. The reference deliberately supplies none of those protections.

## Transaction and display state

One pending transaction maximum. Begin is accepted only after verified authority, valid complete metadata, exact envelope match, no pending transaction and `sequence > highest_sequence`. A competing or repeated Begin returns BUSY, preserving the pending object and original start time. Accepted Begin records its sequence as the fixed-width replay high-water value, revokes old artwork and returns the visible view to PC HEALTH **before** attempting the single staging allocation. This intentional boundary gives up image rollback. Allocation failure leaves the ID terminal and no artwork. Invalid or unauthorized Begin never crosses this boundary and cannot clear unrelated art or pending work.

Tile and Commit require the same verified principal, epoch and transaction as pending. Tile indices arrive in ascending order. An exact earlier tile is idempotent and does not advance progress or reset the deadline; a conflicting duplicate, skipped index, wrong CRC/length, unexpected cover tile, owned interruption, incomplete Commit or final SHA mismatch is terminal: free staging, keep old artwork revoked, return to PC HEALTH. A stale/unbound Commit cannot publish or cancel a newer transaction. Commit validates completeness and SHA-256 **in place** over the staging buffer, then moves that same buffer to display ownership; there is no full-image Commit copy. Once published, the renderer must treat it as immutable and never retain a second full image. Text-only Commit publishes metadata with no image. An unauthenticated or unrelated request is rejected without calling owned cleanup; a proven owned cancellation may terminally clean its transaction.

The accepted Begin deadline is **8.0 seconds absolute**: exactly 8.0 is accepted, greater than 8.0 expires; no retry or progress extends it. An independent timer/poll must call expiry cleanup even if no request arrives. The model uses monotonic seconds; a native wrap-safe tick implementation and fairness under slow HTTP reads are separate gates. Only a newly committed PLAYING track identity starts a **five-second** overlay; pause/resume/progress on the same identity preserve the original deadline, and `now >= overlay_until` returns to four-card PC HEALTH. `STOPPED`, `NO_SESSION` and `UNAVAILABLE` return immediately. Any terminal media failure returns to health. Media has no pointer to `FslessMetrics`: it cannot change any of the four displayed metric values, `received`, or `lastReceivedMs`. Native freshness remains unsigned elapsed **strictly >6000 ms**; at +6000 ms it is fresh, at +6001 ms stale. Native scheduling that delays metric acceptance or repaint is still untested.

Replay/terminal memory is **one 64-bit highest-sequence value per current epoch**, plus the one pending 16-byte ID/principal. It does not grow with transfers and never flushes on a count threshold. All accepted Begin IDs, whether pending, failed, expired or committed, have sequence ≤ high-water and cannot be reused in that epoch. Sequence exhaustion fails closed until an independently authorized fresh epoch. Reboot loses volatile media and high-water; **production authorization must invalidate the old epoch and issue a fresh unpredictable one before accepting a request**. The host constructor receives an epoch from tests and proves no cryptographic freshness.

## Quantitative memory comparison and limits

| Design at steady replacement | 48×48 | 32×32 | Text-only | 64×64 comparison |
|---|---:|---:|---:|---:|
| V0.5-style old + staging + Commit copy | 13,824 B | 6,144 B | 0 B | 24,576 B |
| Retain old + transfer staging ownership | 9,216 B | 4,096 B | 0 B | 16,384 B |
| **Chosen revoke-first + transfer ownership** | **4,608 B** | **2,048 B** | **0 B** | 8,192 B |
| Conceptual image + max metadata + one tile + header storage | **5,672 B** | **3,112 B** | **552 B** (Begin, no tile) | 9,256 B |

The chosen image-storage peak and committed capacity are respectively 4,608/4,608 B, 2,048/2,048 B and 0/0 B. The 48×48 image saves 3,584 B (43.75%) relative to 64×64; 32×32 saves 6,144 B (75%), and is 2,560 B smaller than 48×48. Receiver image-allocation volume is one image allocation per covered accepted Begin, with no Commit-sized copy. The conceptual row counts payload buffers only and is **not** an ESP8266 heap requirement: parsed JSON/canonicalization, authentication state, fixed header workspace, SHA context, TCP/lwIP/WebServer, allocator overhead, `String`, Wi-Fi, stack, graphics, scheduling and a declared engineering reserve are not measured. A native renderer would need one contiguous 4,608 B or 2,048 B allocation plus an explicitly budgeted transport/metadata path. The historical owner-observed 28,272 B free heap and 26,216 B largest block were from another build without media and cannot be subtracted into a safety claim. Text-only removes image storage but still needs bounded metadata/auth/transport memory.

For maximum-length metadata, v2 application record totals are 5,560 B for 48×48 (`552 Begin + 9×552 Tile + 40 Commit`), 2,800 B for 32×32 and 592 B for text-only. These are transferred bytes, not simultaneous storage or an HTTP-header budget. Visual legibility and quality for all three choices remain a PC/hardware comparison task; no subjective quality winner is claimed from host tests.

## Remaining gates

Mission 1 tests exercise only separated in-memory records and a model-level authority assertion. They do not test real request-line/header parsing, pre-body auth, native allocation, partial TCP timing, LCD color/layout, heap fragmentation, loop fairness, watchdog service or reboot challenge issuance. A future candidate needs source-executed bounded ingress and a reviewed production cryptographic scheme, exact native link/stack/phase heap measurements including largest block, allocation failure injection, mixed metric/media timing, and physical rendering evidence under a separate owner decision. No active firmware route, sender, OTA or installation follows from this specification.

## Local validation at this Mission 1 commit

Windows bundled Python and Node were used locally. `python -m unittest discover -s companion -p test_*.py` ran **134 tests: 130 passed, 4 skipped**. The new isolated v2 module contributed **18 passed**; unchanged V0.5 wire, Mission 2 security and Mission 3 memory modules passed **11/11, 29/29 and 20/20**, respectively. The eight `test_gap_*` tests remain present and pass as V0.5 defect characterizations. The four companion skips depend on unavailable local compiler/OpenSSL support; they were not executed. Node simulator/browser checks passed **20/20**. Focused native-source checks passed **5/5** dashboard and **4/4** heap-wiring tests. `git diff --check` passed and firmware showed no diff from the requested baseline.

Full `tools` discovery ran **269 tests: 160 passed, 11 failed, 1 error, 97 skipped**. The eleven failures require an absent local `g++`/preprocessor. The error is a Windows symlink privilege denial (`WinError 1314`). These are not counted as passes or as source-executed native evidence. No Linux CI, native media build, ESP8266 heap measurement, physical screen inspection or device action was performed.
