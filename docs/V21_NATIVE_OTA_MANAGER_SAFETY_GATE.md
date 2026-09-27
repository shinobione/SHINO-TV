# SHINO // TV V2.1 — Native OTA Manager safety architecture

**Status: PHASE A / READ-ONLY PROTOTYPE. No firmware update writer. No device installation authorized.**

The only working physical owner device runs the separately frozen `review-002` image:
400,592 B; SHA-256 `d7d37092573e65be13f54077e95534438fe790a27b2e65cbd0b8034f18f93717`;
source commit `cf65c74775ac55b52b3993704e2f8b8e6cce198a`.
It correctly refreshes four physical LCD metrics and Chrome at once, unmirrored, without Digest login storms.
That firmware does NOT contain this source-only V2.1 work and cannot SHINO→SHINO update.

## What Phase A implements now (unconditionally non-writing)

- Browser shows **Firmware & updates — READ-ONLY PREFLIGHT**. It offers no file picker, upload or install button.
- Authenticated `GET /api/v1/bridge/ota/capabilities` (either existing short-lived, IP-bound read cookie, or explicit Digest authentication) reports runtime flash capacity, current application bytes, reported free sketch space, expected `0x100000` end and explicit `writer_compiled=false`, `upload_route_registered=false`, `signature_verification_implemented=false`, and `physical_installation_authorized=false`.
- `tools/native_ota_preflight.py` is an **OFFLINE ONLY** Python image and geometry research tool requiring an **independently reviewed** expected SHA-256, actual binary on disk, source PlatformIO configuration, and *manually supplied* previously read runtime values. Checks 4-MiB DIO/40-MHz ESP8266 image, exact `4m3m` linker, conservative FS-less markers, size limit at present 494,144 B, rounded staging boundaries, 4-KiB gap, and current reported free sketch space. A passing report still declares **no installation permission**. A SHA-256 supplied by the same untrusted upload does NOT authenticate a release.
- No LittleFS mount/format/write, EEPROM init/commit, generic firmware or FS POST, external JavaScript, public default password, CI install artifact or device access.

## Why we cannot just expose POST /update

The 4-MiB chip has a `4m3m` SHINO layout and application OTA staging end `0x100000`. Streaming `Update.write()` modifies staging flash **before** the final whole-file digest can be established. `Update.end(false)` is a late verification/commit boundary, not an atomic full-flash rollback. A broken or incompatible application can still remove Wi-Fi recovery. The separately installed OEM-return module is only an exact manufacturer **application** writer, not an owner full-flash backup; it does not rescue a nonbooting SHINO.

Our previous real owner round-trip SHINO→OEM→SHINO succeeded, but that does **not** establish indefinite OTA/power-failure safety.

## Phase B: independent implementation and review gates (NOT DONE)

1. **Threat model / trust:** define a deterministic, bounded firmware package manifest with fixed board ID, linked layout, exact byte count, source/version and image SHA-256; select an ESP8266-feasible **cryptographic signature** and a compiled verification key, with external test vectors, before calling it a signed SHINO release. Never equate caller-provided SHA-256 or Arduino Updater MD5 with release authentication. Reject unsigned/wrong-board/expired-format packages. No production signing private key in repo, CI log, browser code, or device filesystem. Owner-private build credentials stay off GitHub.
2. **Exact runtime geometry:** observe actual `ESP.getFlashChipRealSize()`, `getSketchSize()`, `getFreeSketchSpace()`; check accepted app header, version/board/layout, rounded image length and at least one extra 4-KiB margin before any `Update.begin()`. Allow application `U_FLASH` only, never `U_FS`; fail closed on uncertain geometry.
3. **Authentication / CSRF / isolation:** existing read cookie must NEVER authorize update POST. Only separately authenticated privileged action, private-AP origin and one-use RAM authorization with short timeout, strict methods/content type/length, no redirects, no credentials in URL; protect session and stale-nonce behavior when telemetry sender is active. No user-facing automatic update.
4. **Transfer state machine:** IDLE→AUTHORIZED→STREAMING→DIGEST_VERIFIED→STAGED→CONTROLLED_RESTART; all unexpected requests, chunk overrun, client disconnect, timeout, mismatched MD5/SHA-256, early EOF, duplicate POST and power-cut experiments must fail closed. Streaming with bounded RAM; compute SHA-256 incrementally, do not trust supplied checksum. Ensure incomplete writes cannot call `Update.end(true)`; investigate and verify Updater cancellation semantics and how staging/eboot behave on each failure.
5. **Testing:** unit/parser/fuzzer fixtures, full microcontroller compile (normal + owner experimental return modes), flash footprint and no-FS checks, simulated malformed/dropped/duplicated chunks, interrupted sessions, simultaneous browser polling and Windows POST. Independent code review of every write route, read-session privilege isolation, and no unexpected recovery endpoint. CI must publish neither flashable firmware nor credentials.
6. **Recovery and user instructions:** demonstrate complete owner-specific safe restore possibilities separately (no claim if none), document power-loss limits, maintain `review-001` and `review-002` immutable; owner must separately authorize the exact first OTA of a future signed writer version. A nonbooting application cannot guarantee Web-based rescue. Shipping needs real-device monitored confirmation and later one deliberately approved SHINO→SHINO test, without any scripted retry.

## Required release threshold

**NO GO while any Phase B item is incomplete.** Successful Phase A CI means only research code and read-only UI compiled; it does not permit a new owner flash, does not install an OTA manager and does not make the current device capable of generic updates. The next physical transition from the installed `review-002` still requires a separately authorized OEM app return and separately authorized OEM→new exact private owner image, with STOP between hops. No transition is requested by this document.
