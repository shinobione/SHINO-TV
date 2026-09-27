# SHINO // TV — V2 Hotfix physical field validation (owner-reported)

**Date:** 2026-09-27. **Scope:** owner-owned single physical GeekMagic SmallTV-Ultra. This record reflects operations the owner independently performed after explicit per-step authorizations. No tool or assistant made an OTA request on the owner's behalf.

## Immutable deployed image

- The installed *private owner kit* is `review-002`, built from exact **source commit `cf65c74775ac55b52b3993704e2f8b8e6cce198a`**.
- Application: `SHINO-TV-V2-PRIVATE-NOT-A-FLASH-APPROVAL.bin`, **400,592 bytes**, SHA-256 `d7d37092573e65be13f54077e95534438fe790a27b2e65cbd0b8034f18f93717`.
- Original manufacturer application preserved in kit: 494,144 bytes, SHA-256 `a6421f5bfee7860d97bed26620c346b8008f503e513702d4bfdf6e01010a7718` (application only, not full 4-MiB owner-flash backup).
- Owner reported an independent local SHA-256 check of both `review-001` and `review-002` SHINO images and the original OEM application: all three PASS. Private secrets remain local and never belong in the repository.
- **Important provenance:** this document is a later documentation-only change. It does not change, replace or re-identify the already installed image; any later source commit in this PR must not be represented as the build SHA of the owner-installed binary.

## Physical OTA sequence reported by owner

1. Earlier V2 (`review-001`) had working private WPA2 AP, Digest-protected browser and live PC RAM telemetry, but physical LCD fully mirrored left-right and Chrome showed repeated Digest login dialogs during periodic metrics refresh.
2. Owner explicitly authorized exact pinned OEM V9.0.44 application-only return. Owner ran read-only local checks PASS, then performed a single owner-local OEM return. Device subsequently displayed stock clock and rejoined owner's local Wi-Fi.
3. Owner independently inspected stock `GET /v.json`, reporting `{"m":"SmallTV-Ultra","v":"Ultra-V9.0.44"}`, and stock `GET /update` was accessible at the actually observed device LAN IP. **Do not construe this as an owner-specific whole-flash restore or a blanket endorsement of two-step OTA safety.**
4. Owner separately explicitly authorized the exact `review-002` firmware by SHA-256 and 400,592-byte size. Owner reported a fresh local exact SHA/size PASS and installed this private image through the stock OEM `/update` UI.
5. Following reboot, owner confirmed **all four physical LCD cards present and in the correct, unmirrored orientation**. Owner then confirmed **Chrome browser Digest login storm is gone**.

## Test disposition

| Check | Disposition |
|---|---|
| OEM app return boots + clock + home Wi-Fi | OWNER-OBSERVED PASS |
| OEM V9.0.44 identity + stock /update GET | OWNER-OBSERVED PASS |
| review-002 SHINO V2 Hotfix install boots | OWNER-OBSERVED PASS |
| Four native 240×240 cards remain, unmirrored | OWNER-OBSERVED PASS |
| Repeating browser authentication dialogs no longer occur | OWNER-OBSERVED PASS |
| New owner-kit credential pairing | Static/private kit checks PASS; live credential handling evidently sufficient for browser reported by owner |
| Concurrent browser + Windows telemetry on the deployed hotfix | OWNER-OBSERVED PASS: all four readings update on both physical LCD and Chrome simultaneously; no repeated login dialogs |
| Exact two-hour browser session expiry + reauthentication | NOT FIELD-TESTED |
| OEM full flash/filesystem backup | DOES NOT EXIST; OEM image was application-only |
| Nonbooting/recovery/future update path | NOT PROVEN |

## Current working baseline and boundary

Keep existing `review-001`, `review-002`, and matching `credentials.txt` files private, separate and immutable. Do not automatically flash again or declare any other build deployed. SHINO's installed FS-less firmware still has no arbitrary SHINO→SHINO OTA. The manufacturer's exact-image-only app-return feature is not a generic update facility. A future write requires a new independent review and authorization.

**Next software milestone**: the owner has now separately confirmed concurrent live Windows metric delivery and browser refresh on the installed hotfix. Optional user-controlled Windows companion autostart can follow, with private credentials stored locally and no firmware update. Two-hour browser session expiry and extended endurance are still not separately field-tested.
