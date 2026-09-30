# SHINO // TV — V0.8 Mission 6B review gate

Date: 30 September 2026, Europe/Paris. Exact start `799e69a17730c117e1c599912b0b57919d64cea2`. Branch `feature/shino-tv-v08-security-remediation`.

**GO for review of the isolated corrected host candidate. HOLD for R3 persistent freshness/issuer design and all native/runtime qualification. BLOCKED for production authentication, native media acceptance and device operations. Stop after this review gate.** No independent reviewer identity, approval or attestation is fabricated.

| Gate | Decision | Evidence / limitation |
|---|---|---|
| R1 lifecycle | FIXED / host GO | Revoked/disabled/no-role deny before body; challenges/tickets invalidated; rotation and unrelated isolation; no real authority architecture |
| R2 exact bytes | FIXED / host GO | Digest first, literal byte comparison; 10,222 cases agree with unchanged wire-v2 function-level admission |
| R3 bounded challenge/live epoch | PARTIAL / HOLD overall | Global cap/fixed roster/watermark/reissue/exhaustion/reboot/A-B-A tests pass; reconstructed authority replay remains an external freshness gap |
| R4 cheap denial/consume | FIXED / host GO | Zero ECDSA for unknown/used/expired, no consumption on bad proof; race recheck; single-owner native synchronization required |
| Host validation | GO | 26 corrected +21 historical Node tests, no skips; 18 unchanged wire and 2 original compatibility tests; differential includes all fixed-header octet alternatives |
| Exact-head CI | Required at delivery | Dedicated no-skip evidence job plus retained jobs; SHA/clean tree/input hashes/TAP/differential artifact verified against final pushed head, links recorded in Draft PR/delivery |
| R5 / R6 | Inherited FIXED / PARTIAL | Mission 6A behavior/evidence untouched |
| R7 | OPEN | Legacy authentication/framing/whole-request work weaknesses untouched |
| R8 / R9 | HOLD | Native memory/timing/socket/SDK/lwIP and accepted-media composition absent; host evidence is not ESP8266 security or resource proof |
| R10 | BLOCKED | Production custody, enrollment, revocation authority, entropy, persistent freshness and delivery architecture absent |
| Preservation | GO | Production firmware/auth/wire-v2/V0.5/old tests/reports and Draft PRs #29–34 preserved; separate Draft PR |
| Production key/sender/activation/device/OTA/installation/merge | BLOCKED / outside scope | None performed; media native ingress remains DENY-ALL |

Deliverables: [report](V08_MISSION_6B_SECURITY_REMEDIATION_REPORT.md), [all-ten matrix](V08_MISSION_6B_FINDINGS_MATRIX.md), isolated authority/core/profile, corrected Node tests, unchanged-wire differential and exact-head CI artifact. No native verifier, endpoint or transfer-state integration is introduced.
