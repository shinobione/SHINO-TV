# V0.5 — PC/SmallTV media transport PRE-FLIGHT, host emulation ONLY

**Status:** research, explicit bounded format and Python host emulation. This draft is stacked on real owner-tested V0.4 PR #25. The actual SmallTV continues running private V2.1 review-003, the four CPU/GPU/RAM/GPU TEMP metrics remain active via separately configured Windows V0.1 `$HOME\SHINO-LINK`. **No firmware source path, actual device URL, network sender, server handler, new OTA binary or filesystem write is introduced in V0.5.**

## Assumptions / known observations vs not yet proven

Owner observed current real V2.1 monitor free heap during the first physical test: minimum free 28,272 B, minimum largest allocatable block 26,216 B, maximum reported fragmentation 12%, with collector stopping recording new extrema after 1024 samples. This is **not** a continuous soak or a new measured budget for any future firmware. Prior 192×192 JPEG preprocessed on PC in V0.2 was bounded at <=40 KiB and PC-only V0.4 showed an actual 7,866-byte JPEG. An ESP8266 heap capable of ~26 KiB contiguous allocation must not be assumed to safely hold the raw JPEG, decode workspace, HTTP request buffers, scene frame and four-value monitoring all at once. In particular, 240×240×2 = **115,200 B** raw RGB565; DO NOT send a full-screen RGB565 framebuffer.

## Candidate v1 preview format — encode on PC; emulate on host

- Input: V0.4 in-RAM PC-local bounded JPEG preview plus already sanitized V0.2 GSMTC metadata. PC downscales/crops to fixed **64×64**, explicitly byte-order **RGB565 little endian** (8,192 B). This is a **first safety target**, not a final acceptable physical cover size or actual native visual approval. The existing PC simulator's larger art still remains browser-only.
- Encode one **canonical bounded JSON metadata document <=512 UTF-8 bytes**, exact known fields and schema version 1. Track key is metadata identity only, **NOT authorization**. Each transfer has a fresh 128-bit random transaction ID. Title/artist/source/album are clipped/sanitized on PC. No credentials, album-art URLs, filesystem paths, cookies, image uploads to V2.1, arbitrary JSON or signed firmware content appear in this format. Coverless metadata has null digest, zero cover length and zero tile messages.
- Send an initial Begin containing JSON plus commitment `cover_sha256`. When art exists, transfer **16 × 512 B** RGB565 chunks in ascending index, each with transfer ID, index and CRC32, then a separate Commit after the receiving side verifies the full-cover SHA-256. CRC32 is merely corruption detection; it is not authentication. No partial scene is rendered. Exact duplicates can be idempotently acknowledged; conflicting duplicate, out-of-order, bad CRC, missing final tile, final SHA mismatch, wrong transfer ID, unknown version, field/size mismatch or expired transfer is rejected with staged data discarded.
- At most **one** pending transfer, deadline **8 seconds**, and an independently retained four-value metric state. A successful new PLAYING identity causes a five-second music overlay; a same-identity progress update must not restart it. A failure/time-out/no session returns to PC HEALTH without replacing values with fabricated zeros. Replay and denial tests on the emulator use an explicit **boolean stand-in for the authentication gate**, not real HTTP Digest. Old transaction IDs are rejected by a bounded in-memory cache in these host tests, **not** claimed as a complete production replay defense.

## Prospective authenticated transport — NOT IMPLEMENTED on device

The existing V2.1 supports authenticated bounded numeric POST `/api/v1/bridge/metrics` ONLY. The proposed music receiver must use **separate versioned, opt-in authenticated routes**, subject to independent design and owner authorization; NEVER overload the existing metrics endpoint. A possible conceptual protocol is `Begin → ordered tile transfers → Commit → volatile overlay`, but route names, client/server Digest integration, nonce freshness, anti-CSRF/replay binding, HTTP timeout and maximum request-read work remain blocked until real firmware review. The host module does not make any HTTP request or access the private credentials file. Do not paste secrets into repo or public CI.

## Heap budget / fail-closed thresholds to measure before any physical firmware build

| Item | Experimental maximum | Caveat |
|---|---:|---|
| Cover pixels | 64×64 RGB565 = 8,192 B | Compared with full screen 115,200 B |
| Network tile | 512 B each, 16 tiles | HTTP stack/framing adds memory; unknown until native review |
| Canonical metadata | 512 B UTF-8 | Additional JSON parser/document/copy allocations unknown |
| Staged cover | 8,192 B | Single contiguous allocation must be demonstrably safe |
| Overlay life | 5 s | Return to unchanged four-value health display |
| Transfer deadline | 8 s | Interrupted transfer drops staged image |
| Previously owner-observed minimum free / block | 28,272 / 26,216 B | **Historical first V2.1 physical sampling only, not V2.2/next-build headroom** |

The 8,192 B image plus 512 B tile and 512 B metadata **already accounts for 9,216 B of conceptual payload/storage**, before HTTP/TLS(if any), Digest, JSON parser, stacks, renderer, heap fragmentation, allocations and network connection lifetime. Do not treat 28,272 − 9,216 as a safe production remainder; those measurements were on different live firmware without this feature. Avoid storing duplicate 8,192 B buffers, allocating a 240px framebuffer or caching JPEG on the microcontroller. Candidate must be revised or use text-only cover fallback if the necessary per-phase contiguous block/free heap cannot be demonstrated under real concurrent telemetry. Native RGB565 color, scaling, CPU/UI legibility and exact screen impact need physical visual validation **after** separately consented installation; PC screenshots cannot prove them.

**Next isolated hardware-oriented design gates BEFORE any user flash request:**
1. Review exact frozen V2.1 source without modifying PR #20 or owner-private review-003 BIN, identify auth/HTTP body handling/display allocation and meter highest per-phase stack/heap needs in a native host test/build. Test malicious payload, partial HTTP read, TCP disconnect, transfer replay, stale media and return-to-health while metrics continue.
2. Explicitly design per-route auth and nonce/CSRF semantics. No bearer token or static password in URLs; no unprotected media/write endpoint; bound every request **before** allocations and JSON parse.
3. Re-run Windows host frame/tile tests and soak a separately versioned **PC emulator** with simultaneous metric-feed fixtures. Decide whether a native 64x64 image is visually adequate before accepting its permanent heap cost.
4. Any future actual firmware build, OTA and owner-side physical install require **new individual permission**, full source/image hash, reviewed OEM return path and documented residual Wi-Fi-only brick risk. USB-C remains power only; no UART/solder/pogo/hardware acquisition as an ordinary prerequisite.

## Run host tests (NO DEVICE)

```powershell
cd "$HOME\Documents\SHINO-TV"
git fetch origin refs/heads/feature/shino-tv-v05-media-protocol-host-gate:refs/remotes/origin/feature/shino-tv-v05-media-protocol-host-gate
git worktree add --detach "$HOME\SHINO-TV-WIRE-LAB" refs/remotes/origin/feature/shino-tv-v05-media-protocol-host-gate
cd "$HOME\SHINO-TV-WIRE-LAB"
py -3 -m pip install -r companion/requirements-media.txt
py -3 -m unittest discover -s companion -p test_media_wire_v1.py -v
```

The last command only processes synthetic, in-memory cover pixels/mock auth/state tests, and touches no Wi-Fi address, real credential, live tray or SmallTV. The owner is NOT asked to flash, uninstall V0.1 or close the current V0.4 preview to execute these tests.
