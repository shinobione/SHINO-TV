# SHINO // TV V0.8 Mission 1 — HTTP and crypto research gate

**29 September 2026. GO for offline carriage/profile research; HOLD for an unconnected native ingress/verifier prototype; BLOCKED for route activation, production credentials, sender and device operations.** Work began at clean reviewed V0.7 head `f578e11e19b4f7c7a4e78b8f6a0a7c2b4a09f702` on a separate `feature/shino-tv-v08-http-crypto-research` branch. Draft PR #29 remains on its V0.7 branch. No active firmware, frozen V0.5 host codec or historical characterization test, V0.7 wire-v2 reference, metrics path, browser session, OEM return, tray, installation package or device was modified.

## Evidence reviewed and decisions made

The complete V0.7 [review gate](V07_REVIEW_GATE.md), [host wire contract](V07_HOST_WIRE_SPEC.md), [native ingress/auth review](V07_NATIVE_INGRESS_AUTH_REVIEW.md) and [source-executed ingress report](V07_SOURCE_EXECUTED_INGRESS_REPORT.md) were read, alongside the V0.6 memory report and RFC 9421/9530/8941 primary specifications. The pinned ESP8266 Core 3.1.2 parser still reads an unbounded `String` request line before hooks and ordinary POST bodies before application handlers. V0.7's source-executed observations and synthetic single-owner handoff remain distinct from actual firmware. No new pinned-source execution or native patch is claimed here.

1. **HTTP carriage:** [V08_HTTP_CARRIAGE_CONTRACT.md](V08_HTTP_CARRIAGE_CONTRACT.md) proposes exact `POST /api/v2/bridge/media/{operation}/{tx}` for v2, resolving V0.7 Mission 1's generic target versus later operation-specific Gate 1 requirement. The 32 lowercase hex transaction carries an eight-byte epoch and eight-byte nonzero sequence; all 16 bytes, the operation, length and metadata transaction must agree with the unchanged 40-byte binary header. This is an amendment proposal, not a silent backward-compatibility promise or sender implementation.
2. **Authentication:** [V08_CRYPTO_PROFILE_REVIEW.md](V08_CRYPTO_PROFILE_REVIEW.md) fixes a candidate RFC 9421 ECDSA-P256-SHA256 signature base over the actual method, request target, authority, content type, content length and RFC 9530 Content-Digest. Its constrained RFC 8941 field grammar, media-only public-key role, 64-bit boot epoch and 128-bit single-use challenge lifecycle are explicit. Public test vectors prove real host signature verification; they do not establish production key custody, entropy, canonicalizer completeness or native timing.
3. **Resources:** [V08_NATIVE_RESOURCE_BUDGET.md](V08_NATIVE_RESOURCE_BUDGET.md) separates classification, Gate 1, bounded body, staging, Commit and cleanup lifetimes. The 1,706-byte conservative ingress envelope and 6,826/4,266/2,218-byte illustrative simultaneous floors exclude native crypto, stack, TCP, JSON, graphics and allocator costs. Historical V2.1 free-heap observations are not a new-build reserve. Phase-specific measurement and mixed-load acceptance remain required.

## Host evidence and limits

`tools/v08_crypto_lab.js` reads a bounded fixed header and performs Gate 1 **before** allocating or consuming a body. It uses Node's real P-256 verification over a canonical RFC 9421 base, then checks the signed digest against a bounded complete body and checks binary identity/shape/CRC. `tools/v08_crypto_vectors.json` contains a fixed **public** key, fixed signatures and seven request bodies; no private key. `tools/test_v08_crypto_lab.js` includes valid records, duplicate/malformed fields, tampered request components, wrong principal/role, replay, exact expiry, stale epoch, changed/partial/trailing body, and correctly signed declarations with conflicting binary operation/transaction/epoch. `tools/test_v08_vector_compat.py` independently checks the valid record bytes, canonical Begin metadata and signed digest against the unchanged V0.7 reference. The stream and challenge table are synthetic, and the host model holds the input bytes already; its zero `bodyReads` counter proves ordering within that model only. It does not prove native socket read-ahead, stack, heap or time.

| Local check | Actual result |
|---|---|
| New fixed public crypto vector suite | **8/8 passed** with Node 24 on Windows. |
| New V0.7 wire-v2 interoperability check | **2/2 passed** with bundled Python. |
| Existing V0.7 focused source-executed C++ lab | **4/4 passed** with the installed MSVC/pinned package. |
| Full `companion` discovery | **134 run: 130 passed, 4 skipped**. Frozen V0.5 characterizations and V0.7 host reference remain intact. |
| Node simulator/browser/native UI | **20/20 passed**. |
| Full `tools` discovery on Windows | **291 run: 182 passed, 11 failed, 1 error, 97 skipped**. Eleven old tests hard-require absent `g++`/preprocessor; the symlink test errors with `WinError 1314`. These are not relabeled passes. |
| New V0.8 native route, actual TCP owner, ESP heap/stack/CPU, key provisioning, SmallTV | **Not executed / not present**. |
| V0.8 code-commit CI | **4/4 jobs passed** at `5b51cabb918e4311b9970fce80321fad171a8761`: [push run 36617821767](https://github.com/shinobione/SHINO-TV/actions/runs/36617821767) and [Draft PR #30 run 36617900485](https://github.com/shinobione/SHINO-TV/actions/runs/36617900485) each passed the pinned C++ lab, Ubuntu suite, Windows smoke and V0.8 public crypto vectors. Exact-head CI for the final documentation commit is reported in Mission 1 delivery. |

## Gate and unresolved decisions

| Gate | Decision and required next evidence |
|---|---|
| Exact HTTP carriage, candidate signature base, fixed public vectors, bounded host challenge/state model, resource worksheet | **GO for offline review only.** The fixed vectors and test counts establish host behavior at their stated scope. |
| Unconnected, compile-only single-owner native preparse seam and verifier | **HOLD.** Needs separate instruction; ratify the v2 carriage amendment and narrow structured-field profile with an independent reviewer, prove real legacy request-line handoff and no body read-ahead, select/review native P-256/RFC parser, specify entropy/boot epoch/challenge issuance and key lifecycle, then measure phase heap/largest block, stack and worst blocking time. |
| Ordinary `server.on()` media handler or `addHook()` alone | **BLOCKED.** Pinned request-line/body allocation precedes the needed strict Gate 1. |
| Active media route, production authentication, device sender, credential provisioning, OTA, firmware installation, live SmallTV contact | **BLOCKED.** This research branch contains none of them. Separate technical gates and explicit owner instruction are required. |

Unresolved decisions are the configured production Host authority and exact optional-field policy; an independently reviewed full RFC 8941 parser versus proven restricted grammar; public-key enrollment/rotation/revocation and PC key custody; boot entropy, epoch collision/fail-closed policy and challenge issuance/rate limits; per-principal outstanding-slot count and expiry; one-owner TCP/legacy handoff and close/pipeline behavior; and native memory, stack, ECDSA CPU, watchdog and mixed-load limits. A static signature or signed digest cannot by itself establish replay safety or received-body integrity. **Stop after this gate.**
