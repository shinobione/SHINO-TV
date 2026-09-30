# SHINO // TV - V0.8 Mission 6C review gate

30 September 2026, Europe/Paris. Start `7d40df9f69bead1aa3a8c7ebd88dbfa0121968e0`. Branch `feature/shino-tv-v08-legacy-http-hardening`.

**GO for review of the partial isolated R7 evidence. HOLD for production/security/native-runtime acceptance. BLOCKED for pre-body application authorization and compatible incremental multipart under the existing API, and for active media/device operations. Stop at review; no deeper ownership/policy integration, fabricated approval or merge.**

| Gate | Decision / evidence |
|---|---|
| Independent auth/framing repairs | GO for host review: exact Basic scheme, Digest target/nc checks, duplicate critical framing and complete terminal headers |
| Legacy input work | PARTIAL: 130-byte first line / 64-read slice; 2048 header bytes /32 fields /512 line bytes; 4096 body bytes; 8192 reader iterations; wrap-safe 2000-ms absolute deadline. Whole-poll application input <=6208 for this path; synchronous parser and native call durations unqualified |
| Authorization before protected body | BLOCKED BY ARCHITECTURE: actual pinned API lacks completed-header/pre-body application gate; 4096 unauthorized bytes still consumed before401 |
| Digest content integrity | HOLD: qop=auth altered first-use POST remains accepted; replay repair is not body binding. No custom Digest variant or cookie POST substitution |
| Conditional OEM upload compatibility | BLOCKED BY ARCHITECTURE: candidate rejects every multipart before body/callbacks; authorized legacy upload unavailable; no OEM writer linked |
| Actual ordinary application routes | GO for exercised host subset: dashboard/JS/metrics/status/FS/OTA/browser sessions/factory GET and ordinary conditional POST; four metrics, invalid-state preservation, exact6000/6001 and rollover retained |
| R1-R6/history | Preserved; R1/R2/R4 host fixes, R3/R6 partial, R5 strict >30 retained; no prior source/test/report/evidence edits; Draft PRs29-35 preserved |
| R8/R9 | HOLD native/runtime/accepted-media composition gaps; PC cleanup/source execution is not SDK/lwIP/heap/WDT/LCD proof |
| R10 | BLOCKED production authority/custody/entropy/persistent freshness/delivery |
| Exact-head CI | Required at delivery: no-skip six-variant artifact with candidate SHA, clean tree, input hashes, assertion outcomes and host measurements; run links/conclusions verified in separate Draft PR. Historical6B job is explicitly pinned6B evidence |
| Media / sender / private key / firmware / device / OTA / installation / merge | DENY-ALL / none performed |

Deliverables: [report](V08_MISSION_6C_R7_REMEDIATION_REPORT.md), [matrix](V08_MISSION_6C_FINDINGS_MATRIX.md), isolated transformer/TCP/source tests, and exact-head CI artifact in the separate Draft PR. This is a blocked architecture review outcome, not completed end-to-end legacy security remediation.
