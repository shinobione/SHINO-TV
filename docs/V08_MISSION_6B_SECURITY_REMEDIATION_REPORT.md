# SHINO // TV — V0.8 Mission 6B host security remediation

Date: 30 September 2026, Europe/Paris. Exact start: `799e69a17730c117e1c599912b0b57919d64cea2`; separate branch `feature/shino-tv-v08-security-remediation`.

**R1, R2 and R4 are FIXED in the isolated host candidate. R3 is PARTIAL: bounded live-authority invariants are corrected, while persistent epoch freshness and a production issuer remain unproved. R10 remains BLOCKED. Media native ingress remains DENY-ALL.** This is an engineering review gate, not an independent security attestation or native qualification.

## Provenance and isolation

The clean checkout matched the exact requested Mission 6A SHA before branch creation. Read the Mission 4 security review (all R1–R10 and reproducer appendices), Mission 5 findings/socket report, Mission 6A report/matrix/gate, profile 1.1 decision/adapter, original crypto host lab, seven public vectors and unchanged V0.7 wire-v2 specification/reference. Live read-only GitHub inspection confirmed Draft PRs #29–34 OPEN/Draft at their preserved heads:

| PR | Head |
|---|---|
| #29 | `f578e11e19b4f7c7a4e78b8f6a0a7c2b4a09f702` |
| #30 | `c5cac0ab87f0ade5bf1e2bd62934b61cedc1a4c5` |
| #31 | `273b386070802cc6aba0a16c8cd8b5a6dc7abf00` |
| #32 | `7cf56a6c0466a07f1d738f97c6ba3e049355ca98` |
| #33 | `80ad35766528a3bf02b697a6ddebf70f852a9f0a` |
| #34 | `799e69a17730c117e1c599912b0b57919d64cea2` |

The candidate lives exclusively in new `tools/v08_m6b_*.js` files. The original header/core/profile code is retained; candidate copies preserve its parsing/signature-base/CRC/shape behavior except for the explicit lifecycle API and byte-exact magic fix. The profile parser continues to use the existing pinned structured-headers 2.0.3 dependency. No signer or private key is generated; the distinct wrong-key test derives the public point −Q from the existing public point. No production firmware, companion, simulator, Basic/Digest auth, media-wire-v2, V0.5 tests, previous mission report, overlay, public vector or historical test is edited. CI gains one isolated job and retains all prior jobs. GitHub delivery and CI are the only external operations; no device contact, sender, enrollment, OTA, installation or merge occurs.

## R1 — explicit lifecycle and admission boundary

`v08_m6b_authority.js` copies and validates a fixed roster of 1–16 own principal entries at construction. Each principal requires explicit boolean `enabled`/`revoked`, roles including `media`, allowed operations and a validated public P-256 key. No mutable fixture-map removal serves as a revocation mechanism. Caller edits to that map or its operation arrays cannot change enrolled state. New identities require a separate authority construction, which is an explicit host initialization, not enrollment architecture.

`setState` changes enabled/media state or permanently revokes a principal. Every accepted state change increments its bounded 64-bit revision and invalidates all that principal's outstanding challenges. Re-enabling does not revive challenges or previously proven requests. Revocation is terminal within this authority. Revision exhaustion disables/revokes and fails closed; no revision wraps. `rotateKey` validates the replacement before changing state, increments revision and invalidates that principal's challenges/tickets even if the supplied public key is the same. Invalid key input preserves the old state. Other principals' challenges and admissions remain valid.

Gate 1 rejects an inactive principal/role/operation before ECDSA or any body read/allocation. After proof, it returns a frozen request bound to a private identity ticket and principal revision. Gate 2 rechecks admission before body allocation and after digest/header validation; `admit` rechecks once more and consumes the ticket. Application admission requires successful Gate 2. Revocation between Gate 1 and body receipt therefore reads zero body bytes; revocation during receipt or after Gate 2 prevents admission. Disable/enable, rotation and reboot similarly invalidate earlier proof. Once admitted, retroactive removal of existing application media is not implemented: there is no application transfer state integrated here. A future receiver must define cancellation/display policy separately and couple admission plus state mutation to the same synchronization owner.

Gate 2 receipt is attempted only once per ticket. The signed digest is copied privately after proof, so caller mutation of the exposed digest cannot change the authenticated declaration. The verified body also has an owned copy before application admission, preventing mutation of the returned Gate 2 buffer from changing admitted bytes. These copies are host-model choices, not a native memory budget. Privileged model methods and the test-injected roster are trusted lab APIs, not remotely callable endpoints.

## R2 — byte-exact fixed header

Gate 2 compares the first four bytes with `Buffer.from([0x53, 0x54, 0x56, 0x37])` using byte equality. No ASCII decoding is involved. Every non-identical four-byte value fails this equality. Body length/framing and SHA-256 digest verification still precede interpretation. A changed signed body fails its original digest even if the exposed request digest is mutated.

`test_v08_m6b_wire.py` sends 10,222 records through the corrected function-level Gate 2 probe and the unchanged V0.7 `HostReceiver.receive`: one original canonical Begin is admitted and 10,221 negatives reject in both. This includes each of the 255 alternative octets at all 40 fixed-header positions (10,200 cases), all 15 nonzero high-bit magic permutations, five truncated bodies and one trailing body. The first four positions provide 1,020 exact magic octet negatives. The byte-equality implementation supplies the general rejection rule; this suite does not enumerate all 2³² magic values.

The differential injects an already-proven request context and a matching digest for each changed record, as a malicious authenticated-body model. It does not forge a signature. Original public vectors separately run through real ECDSA and both gates. The differential uses a fixed signed target/Begin authority and compares record admissibility; it does not claim all transfer-state decisions are equivalent. Variant tile index, pending ownership, metadata canonicality, final image hash and transaction high-water remain separate unchanged wire-v2 responsibilities. No media-wire-v2 compatibility change is made.

## R3 — bounded RAM enforcement and remaining issuer obligations

Outstanding storage is one global Map, capped at 1–64 entries (default 4), with an additional per-principal cap (default 2). The roster is fixed; arbitrary IDs cannot allocate a row. Capacity failure rejects without eviction or watermark advancement. Expired entries remain until explicit sweep and may conservatively fill capacity; precheck never consumes/sweeps them. Exact expiry `now >= expiresAt` denies. All time inputs must be nondecreasing safe integer host ticks; rollback/invalid clocks fail closed. The clock is one continuing host authority domain, not native rollover-safe millis evidence.

The narrow host issuance contract requires each 22-character nonce's base64url-alphabet ordinal to be strictly greater than a global 132-bit watermark. This deliberately stronger, explicit host issuer rule allows every original public vector in separately initialized contexts without changing their signed bytes. It retains one fixed-width watermark, not a set/list of consumed nonces. Reissue, collision, lower/out-of-order values and cross-principal reuse reject even after consume, expiry, disable/re-enable or rotation. Exhausting the maximum ordinal fails closed until a valid new epoch. Syntax/expiry/capacity failures do not alter other slots or the watermark; a throwing injected issuer cannot install a challenge. There is no retry loop or claim that arbitrary random candidates satisfy this ordered issuer contract.

Reboot clears every challenge/ticket and requires a nonzero, strictly increasing 64-bit epoch relative to the current live authority. A→B→A and equal epochs reject; epoch exhaustion rejects without reset. The watermark resets only on a valid increasing epoch, when old signatures are independently denied by epoch binding. This is a documented host epoch policy; it does not alter the wire's epoch field or silently upgrade production profile compatibility. Revoked roster state persists in this host reboot operation.

**RAM limitation:** reconstructing a new volatile authority at epoch A after loss of the old instance can still admit a captured A signature if the same public challenge is reintroduced. The corrected test explicitly demonstrates this external-state gap. A live host fixture cannot prove cross-power-loss freshness, production entropy, issuance health, delivery, revocation persistence or custody. Persistent monotonic authority, or another independently reviewed boot freshness mechanism and trusted issuer, must prevent rollback/reconstruction and provide the required unpredictability. None is fabricated here. Consequently R3 is PARTIAL overall even though roster/global-cap/reissue/live-epoch regressions no longer reproduce against the candidate.

Storage cardinality is O(roster + capacity) plus fixed-width epoch/watermark/revisions/clock. Weak identity tickets are request-lifetime objects, not nonce replay history; this host model does not budget concurrent native request buffers or GC/native allocation. No ESP RAM, entropy strength, timing or sustained CPU claim follows from it.

## R4 — cheap rejection and final consume

Gate 1 parses the bounded profile header, then `precheck` checks active principal/operation, current epoch, challenge existence, principal/epoch/revision binding and strict expiry before real `crypto.verify`. The admission check reads challenge state without removing or sweeping entries. Public keys are validated once at enrollment/rotation, rather than imported from attacker-selected headers per request. Unknown, already used, wrong-principal, stale-epoch and expired challenges incur **zero ECDSA verifications** in instrumentation tests. Repeated bad signatures for a live challenge incur one verification each and leave that challenge intact; successful proof consumes once. No rate-limiting or live-challenge CPU budget is established.

After successful ECDSA, a fresh clock sample and full recheck must identify the exact same immutable challenge object and key. Synchronous recheck→delete→ticket publication contains no await, callback or external application call. Injected interleavings between preliminary check and final consumption cover expiry, revocation, rotation, reboot and a competing successful consumer. They reject the older candidate without body reads; only one proof can win. Crypto exceptions preserve the slot.

This is atomic under the single synchronous Node owner used by the host model. A future native implementation must serialize all issuance/sweep/consume, lifecycle changes, epoch reset and admission/application mutation under one owner or critical section. Cryptography may run outside that section only with a snapshot plus final identity/revision/expiry recheck; consuming before complete cryptographic proof is forbidden. Reentrant callbacks or unsynchronized threads cannot be inferred safe from Node tests. Native critical-section duration, entropy, ECDSA/WDT timing and resource limits remain unqualified.

## Validation and exact-head CI

Local Windows Node validation: **47/47 tests**, zero skips (26 corrected tests plus 21 retained tests, including five known-failure tests). Historical vulnerable tests still pass by reproducing the original defects; they are not security acceptance. Corrected tests separately deny the R1/R2/R3-live/R4 counterexamples. Wire differential: **10,222/10,222 agreement**, 1 admit/10,221 reject. Unchanged focused wire-v2 tests: **18/18**; original vector compatibility: **2/2**. Local development evidence is a dirty working-tree snapshot, never substituted for final-head CI. Initial implementation test failures were corrected before these final passes.

Reproduce with the retained SF dependency, Node and Python:

```text
node --test tools/test_v08_crypto_lab.js tools/test_v08_m3_profile.js tools/test_v08_m5_known_failures.js tools/test_v08_m6b_security.js
python tools/test_v08_m6b_wire.py
python tools/v08_m6b_evidence.py
python -m unittest discover -s companion -p test_media_wire_v2_host.py -v
python -m unittest discover -s tools -p test_v08_vector_compat.py -v
```

The dedicated no-skip CI job checks out the actual PR head SHA, runs all retained/corrected Node tests and the wire differential, verifies exact allowed diff/preserved historical inputs, asserts clean checkout and matching expected head, and uploads `v08-m6b-security-evidence-<head>`. The artifact contains SHA, input hashes, full TAP counts and differential results. All existing source/socket/link/companion/Windows jobs remain enabled. Final exact-head run URL/conclusions and downloaded artifact identity are recorded in the separate Draft PR body and delivery; a document cannot contain its own commit hash without changing that hash. No earlier green run is substituted.

R5 stays fixed and R6 partially addressed exactly as Mission 6A reported. R7 stays OPEN; legacy Basic/Digest/body-before-auth and whole-request work issues are untouched. R8/R9 remain native/runtime/accepted-media composition gaps. R10 is BLOCKED. Stop after the [review gate](V08_MISSION_6B_GATE.md).
