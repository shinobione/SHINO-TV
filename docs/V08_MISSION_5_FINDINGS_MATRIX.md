# Mission 4 findings → Mission 5 traceability

All ten findings remain preserved. Known-failure assertions pass when the existing vulnerable behavior is reproduced; they never mean remediation or media security acceptance.

| ID | Mission 4 severity/finding | Mission 5 deterministic evidence | Review status and remaining work |
|---|---|---|---|
| R1 | High: revoked principal still accepted | `test_v08_m5_known_failures.js`: revoked existing public fixture accepted by unchanged profile | OPEN; separate lifecycle/security remediation |
| R2 | Medium: high-bit binary magic aliases | Same test file: Gate2 accepts `d3d4d6b7` with function-level matching digest | OPEN; function-level authenticated-body model, not forged signature; separate crypto/wire remediation |
| R3 | Medium: issuer freshness/global bound missing | Same test file: consumed nonce reissued, A/B/A epoch replay, 100 principal rows under per-key cap2 | OPEN; issuer-controlled host counterexamples, no production issuer |
| R4 | Medium: expensive crypto precedes nonce denial | Same test file instruments real crypto.verify: unknown challenge incurs one verification | OPEN; separate admission/security remediation, no native CPU claim |
| R5 | Medium: ready-client policy removed | Socket lab exact partial owner 0/1001/2000; stock idle owner releases at31 versus overlay2000; real-clock and full host queue comparison | REPRODUCED, HOLD; corrected pinned grace30ms; no scheduling repair |
| R6 | Medium / Low rationale: broader legacy denial and false path-decode rationale | Socket lab 130/131 bytes, literal-percent/escape variants, encoded media/mediax/query reservation, nested escape raw404; stock literal-percent200 | REPRODUCED, HOLD; conservative policy unchanged; historical-browser/OEM input inventory still missing |
| R7 | High: legacy body/resource/weak auth remains | Actual socket→parser→auth→handler tests: 4096 body bytes before401, trickled headers >2.1s, Basic!, Digest wrong URI/replay/body alteration, duplicate headers and incomplete terminal header | REPRODUCED, OPEN; no legacy/auth fix; multipart upload/auth ordering uses inert operations |
| R8 | Medium: lifetime/close semantics gap | Real loopback FIN/half-close/close/RST, complete/partial/body cuts, pipelines, host shared aliases/final cleanup and CLIENT_IS_GIVEN | PARTIALLY CHARACTERIZED; native ClientContext/lwIP flush/abort/ACK latency, allocator/close failure remain HOLD |
| R9 | Medium: source labs lacked composition | Actual generated owner/parser/URI/FunctionRequestHandler/auth/response code with unchanged bridge/metrics/UI source; actual peer response/state assertions | LEGACY HOST COMPOSITION ACHIEVED; native media Gate1/2→wire receiver/application state remains absent/deny-all; ESP qualification HOLD |
| R10 | High design blocker: custody/enrollment/entropy/challenge delivery absent | No implementation created; fixture policy/deterministic RNG explicitly synthetic; repository restrictions checked | BLOCKED; separate owner-approved production architecture/remediation |

R1–R4 and R10 are separate security remediation work. No production authentication, media admission, private signing key, provisioner or sender is introduced. Mission 4 report and historical assertions remain byte-for-byte unchanged.
