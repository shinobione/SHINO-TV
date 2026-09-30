# Mission 7 review gate

30 September 2026, Europe/Paris. Start `4d6180959b843c64e92b72425134c2dfc6688c88`, preserved PR#36. Branch `feature/shino-tv-v08-native-media-receiver`.

**GO for offline native-receiver research review. HOLD for physical/native runtime qualification. BLOCKED for production provisioning/credentials, active device media route, sender, OTA, installation and merge. Stop after this gate.** No independent reviewer identity, attestation or production approval is fabricated.

| Required gate | Decision and evidence |
|---|---|
| Gate1 before body | GO offline: real BearSSL proofs, challenge precheck/final consume, zero body/allocation for cheap/wrong-proof denial and post-proof revocation; header-only proof test |
| Gate2 / wire-v2 | GO exercised record compatibility: exact SHA/digest/literal STV7/identity/CRC/shape;10,207-case unchanged-reference differential; signed full0/32/48 flows and Abort |
| R1/R2/R4 survive translation | GO for tested synchronous native/PC contract; production authority/timing/runtime remain unqualified |
| Legacy/OEM domain | GO for preserved source and exercised host behavior: Mission6A parser/auth,224/227 inherited checks including authorized conditional inert multipart; no wholesale6C adoption |
| Resource deltas | GO for measured equivalent full Xtensa static links, object sizes and compiler frame evidence; substantial crypto-stack concern explicitly HOLD |
| R3 | PARTIAL: bounded live volatile authority; power-loss freshness not established |
| R10 | BLOCKED until real owner-approved provisioning/custody/security design |
| Final exact-head CI | Required at delivery: new no-skip Mission7 head/socket/static artifact, clean checkout/input hashes/allowed diff; all retained jobs, with6B/6C explicitly historical pinned-head evidence |
| Hardware/native runtime | HOLD: no device execution, native heap/stack/WDT/security/socket/LCD proof |
| Production credentials/provisioning/active route/sender/OTA/install/merge | BLOCKED / no such operation performed |

This candidate's public test-only setup pointer and inactive full link are research seams, not a production configuration path. Future late TCP bytes are outside the retained buffered-trailing check; crypto executes synchronously without a native wall-time bound. See [native report](V08_MISSION_7_NATIVE_MEDIA_REPORT.md), [resources](V08_MISSION_7_RESOURCE_REPORT.md) and [findings](V08_MISSION_7_FINDINGS_MATRIX.md). Stop at review.
