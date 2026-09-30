# Mission 4 findings → Mission 6B host candidate traceability

Exact start: `799e69a17730c117e1c599912b0b57919d64cea2`. All earlier reports, tests and known-failure evidence are preserved. FIXED below means the isolated host contract only.

| ID | Mission 6B reproducible evidence | Status and boundary |
|---|---|---|
| R1 | Explicit enabled/revoked/media-role roster; terminal revocation, challenge invalidation, revision tickets; before issue/after issue/after proof/during body/before admission; rotation and unrelated isolation | **FIXED (host)**; no persistent revocation/enrollment authority or application media cleanup architecture |
| R2 | Literal `53 54 56 37` equality after digest; 10,222 unchanged-wire differential records, including 1,020 magic octet negatives and 15 high-bit permutations | **FIXED (host)**; wire-v2 unchanged, no signature forgery or native receiver claim |
| R3 | Fixed ≤16 roster, global ≤64/default4 outstanding cap, per-principal cap2, constant 132-bit issuance watermark; reissue after consume/sweep/lifecycle denied; increasing 64-bit epoch/reboot/A-B-A rejection; failure/exhaustion semantics | **PARTIAL**; live-model boundedness/freshness fixed, reconstructed-A replay explicitly characterized; trusted production issuer, entropy and persistent epoch authority remain blocked |
| R4 | Read-only challenge admission precedes real ECDSA; zero verifies for unknown/used/expired/wrong-principal/stale epoch; bad proof preserves slot; final exact challenge/key/revision recheck catches interleavings | **FIXED (host)**; single synchronous owner required; native atomicity/timing/rate policy unqualified |
| R5 | Mission 6A actual pinned no-data >30-ms contention repair retained | **FIXED in inherited isolated candidate**; no changes in Mission 6B |
| R6 | Mission 6A query/reservation/rationale repairs and capped/strict-path compatibility policy retained | **PARTIALLY ADDRESSED**; physical/OEM/long-target parity still HOLD |
| R7 | Historical Basic!/Digest wrong-URI/replay/body alteration and body-before-auth/blocking evidence unchanged | **OPEN**; no auth/parser/firmware changes |
| R8 | Prior PC alias/FIN/RST/stop/cleanup characterizations retained | **NATIVE/RUNTIME GAP**; SDK/lwIP/native close/resource behavior HOLD |
| R9 | Prior legacy host composition retained; corrected security model still isolated from native ingress and wire transfer state | **NATIVE/ACCEPTED-MEDIA COMPOSITION GAP**; DENY-ALL |
| R10 | Only public fixtures, fixed trusted lab roster, injected ordered nonces and epoch values | **BLOCKED for production**; custody, enrollment/revocation authority, entropy and challenge delivery are not real architecture |

The unchanged five Mission 5 known-failure Node tests still reproduce original R1–R4 defects. Corrected tests run against new files and demonstrate their host remediation independently. No CI/native-link result upgrades production authority.
