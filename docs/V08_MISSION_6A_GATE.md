# SHINO // TV — V0.8 Mission 6A review gate

Date: 30 September 2026, Europe/Paris. Exact start `80ad35766528a3bf02b697a6ddebf70f852a9f0a`; separate branch `feature/shino-tv-v08-ingress-remediation`.

**GO for review of the completed isolated DENY-ALL candidate. HOLD for unconditional legacy parity, total-request bounds and ESP8266 runtime qualification. BLOCKED for active media ingress and production/device operations. Stop after this review gate.** This is an engineering evidence gate, not a fabricated independent reviewer attestation or merge/deployment approval.

| Gate | Result | Evidence and limits |
|---|---|---|
| R5 first-line scheduling remediation | GO, fixed in isolated candidate | Actual pinned strict >30-ms no-data ready/full-queue policy restored; 64-read slices and absolute 2000-ms deadline retained; partial/idle/full-queue/rollover/keep-alive/pipeline/one-stop cleanup regressions pass |
| R6 compatibility remediation | PARTIAL / bounded policy GO | Query over-reservation and mediax/unrelated substring denial corrected; path-decode rationale fixed; entire declared media namespace/ambiguous aliases terminally denied. 130-byte cap and documented strict path syntax remain; no universal legacy/OEM parity claim |
| Source → PC loopback composition | GO for exercised host cases | Stock/previous/corrected actual generated owner/parser/route/auth/response with unchanged legacy handlers and inert conditional OEM; no synthetic dispatch substitution |
| Security findings preservation | GO for traceability, HOLD for security | All R1–R10 retained in new matrix; Mission 4/5 documents and tests unchanged; known-failure R1–R4/R7 assertions continue to reproduce defects |
| R1–R4 and R10 | OPEN / active media BLOCKED | Separate security remediation and custody/enrollment/issuer architecture required; crypto/profile/wire behavior unchanged |
| R7 total-request work bound | OPEN / HOLD | Corrected legacy header poll observed >2.1 s and 4214 reads in one body poll; first-line fairness does not bound headers/body/auth/handler work or WDT/application-return latency |
| R8 client lifetime/native close | PARTIAL / native HOLD | PC one-stop and final socket/context cleanup pass; SDK/lwIP/flush/abort/drain/failure behavior unqualified |
| R9 accepted native media composition | HOLD / absent | Legacy host composition retained; media Gate1/2→wire receiver/state is not integrated and remains DENY-ALL |
| Native isolated link/static memory | GO for static comparison only | Fresh equivalent stock/previous/corrected links; corrected +352 text/+0 data/+0 BSS vs previous, +1140 text/+152 BSS vs stock locally; no ESP runtime resource evidence |
| Historical firmware/auth/protocol preservation | GO | Zero changes to firmware/companion/simulator, previous overlay, crypto profiles/media-wire-v2/V0.5 defect characterizations or historical Mission 4/5 docs; Draft PRs #29–33 preserved |
| Final exact-head CI | REQUIRED and verified at delivery | Dedicated no-skip source/socket/native jobs plus all retained jobs; temporary evidence files, clean checkout and downloaded final-head artifact checked; final URLs/conclusions in separate Draft PR and delivery |
| Production, sender, device, OTA, installation, merge | BLOCKED / outside scope | No such action performed or authorized by this gate |

Deliverables: [remediation report](V08_MISSION_6A_REMEDIATION_REPORT.md), [updated findings matrix](V08_MISSION_6A_FINDINGS_MATRIX.md), [local snapshot](V08_MISSION_6A_LOCAL_EVIDENCE.json), corrected generator, source/socket regression labs/tests, equivalent native compile project and CI evidence. Green known-failure tests and native links do not certify secure behavior or device acceptance.
