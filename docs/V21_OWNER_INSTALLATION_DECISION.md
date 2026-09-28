# SHINO // TV — Owner Wi-Fi-only V2 → V2.1 transition decision

**Owner constraints (binding):** USB-C is power only; **Wi-Fi exclusively** for normal project development and updates. Do not propose serial/UART/pogo pins, six-pad investigation, PCB photos, soldering, opening the device or buying hardware. Physical recovery is a separate break-glass topic only if the device actually bricks and the owner then requests it. `docs/RECOVERY_PROTOCOL.md` is archival, not the execution plan.

**CURRENT GATE:** The installed V2 Hotfix remains functional. PR #20 is Draft. `permission_to_flash=false`; no upload/flash/restart/merge follows from a generic "ok/go" or this document. See [V21_WIFI_ONLY_RETURN_CHAIN_AUDIT.md](V21_WIFI_ONLY_RETURN_CHAIN_AUDIT.md) for exact historical/source evidence and stop conditions.

## Actual observed Wi-Fi path, not a hypothetical one

On 2026-09-27, the owner already performed **previous SHINO V2 → exact official OEM Ultra-V9.0.44 application by the existing authenticated factory-return Wi-Fi route**, then verified the OEM clock, domestic Wi-Fi, `/v.json` response identifying Ultra-V9.0.44 and available stock `GET /update`. The owner subsequently returned **OEM `/update` → current SHINO V2 Hotfix review-002**, with the four 240x240 CPU/GPU/RAM/temperature cards working.

The **CURRENT review-002** private candidate was owner-reported as source `cf65c74775ac55b52b3993704e2f8b8e6cce198a`, 400,592-byte BIN SHA-256 `d7d37092573e65be13f54077e95534438fe790a27b2e65cbd0b8034f18f93717`. Its private builder explicitly generated `--enable-restore` and the local review manifest reported factory return compiled true. Both the earlier V2 and **the currently installed review-002** have now separately produced a live owner-observed `factory-return` GET with `write_enabled:true`. The current response is documented below; neither observation is authorization for an upload.

The running current V2 has four owner-reported read-only free heap samples: 32,184 idle, 32,016 with Chrome, 31,960 with normal Windows sender and 32,128 after load. All responses gave running application size 400,592. Those are snapshots, not peak, fragmentation or binary checksum proof.

## Current Hotfix live OEM-return GET confirmed (read-only, 2026-09-28 local)

The owner supplied the actual authenticated `GET /api/v1/bridge/factory-return` result **after review-002 installation**: `write_enabled:true`, `application_bytes:494144`, and `manufacturer_sha256:a6421f5bfee7860d97bed26620c346b8008f503e513702d4bfdf6e01010a7718` exactly match the pinned original OEM application. The same real response states `full_flash_backup:false` and `filesystem_layout_verified:false`. This resolves the previous *current-device presence* uncertainty; do not ask owner to repeat that GET. It does not prove success of a future write or grant flash permission. Full provenance, safeguards and limits: [V21_WIFI_ONLY_RETURN_CHAIN_AUDIT.md](V21_WIFI_ONLY_RETURN_CHAIN_AUDIT.md).

## Conditional two-operation Wi-Fi transition (not approved yet)

1. With fresh **specific owner consent**, the existing Digest-authenticated and hash/size-pinned OEM-only receiver could return current running SHINO to exact official OEM V9.0.44. No generic SHINO OTA updater or abandoned 4m1m trampoline is presumed.
2. Only after independently observing actual manufacturer boot and `/v.json` should an entirely separate owner decision consider its previously observed stock `/update` form for a **new owner-private V2.1** with matching credentials. Any failed boot/auth/version check = STOP; no blind second-stage upload.
3. The private packet builder now supports explicit `--heap-diagnostics` to select the real instrumented ESP8266 profile while preserving `--enable-restore`, the exact pinned OEM image and private credential/image checks. It does not upload. The local owner-specific image SHA, size, private output and full offline preflight must be separately reviewed before any actual action. Disposable CI images cannot be used as owner-matched releases.

**Known risks:** Two OTA writes and two boots, power interruption, unknown live stock acceptance of a new/larger image, potentially lost original assets, changing AP/Digest credentials and no independent Wi-Fi rescue if the device becomes nonbooting. The manufacturer's 494,144-byte application OTA ZIP is **not** an original full-chip backup. An earlier successful run is important empirical evidence, not a guarantee the next will work. Do not claim zero brick risk or automatically try factory return as a test.

## Allowed work now versus blocked actions

**Allowed without device change:** source review of exact current/next branch, passively reading the above existing GET with owner authentication, validating manufacturer ZIP/hash locally, building/checking owner-private candidate offline, CI with generated throwaway policy, reviewing staged checksum/layout/credential migration and read-only diagnostics. **Not allowed:** firmware POST/upload, flash, forced reboot, silently turning on generic SHINO OTA, trying undocumented vendor endpoints, device hardware access, publishing owner credentials or private BINs, PR merge or future write based on a vague approval. Every potential actual Wi-Fi installation is an explicit separate go/no-go for **that exact binary and operation**.

## Next software-only handoff — private V2.1 review kit

The existing local Windows private owner builder now supports a **fourth explicit argument** `--heap-diagnostics` in `start-private-owner-build.cmd`; no argument keeps the older ordinary V2 profile. It chooses only the pinned `esp12e_heap_diagnostics` PlatformIO profile and always generates `--enable-restore` in the one-use owner-private policy so the bounded OEM-only Wi-Fi return receiver remains compiled. The owner-local review kit uses fresh WPA2/Digest/API credentials and retains them privately with the matching exact application BIN; it **does not reuse the current running review-002 credentials** or publish either build's secrets. The current installed V2 and its saved private `review-002` kit must not be altered or overwritten.

After checking out a clean, exact reviewed branch commit, the owner may run this one **local build-only command** from the repository directory with their already downloaded and checksum-verified original OEM ZIP path and a new, non-existing private output folder outside Git. Replace every quoted placeholder with its exact local value and pin `FULL_REVIEWED_COMMIT_SHA` to the final reviewed 40-character PR head, not the mutable branch name:

```powershell
.\start-private-owner-build.cmd "FULL_PATH_TO_VERIFIED_OEM_V9.0.44_ZIP" "NEW_PRIVATE_FOLDER_OUTSIDE_GIT" "FULL_REVIEWED_COMMIT_SHA" --heap-diagnostics
```

Prerequisites are installed Python, PlatformIO, esptool and a full clean Git checkout. PlatformIO may download toolchain dependencies; the build makes **no connection to the SmallTV**. The local builder deliberately refuses a dirty source tree, a pre-existing private output directory, old generated policy/credentials, or either stale `.pio/build/esp12e*/firmware.bin`. Inspect these conflicts instead of blindly deleting the owner's previously retained private backup. A local PlatformIO compile-clean for the relevant profiles may be used only after deciding the generated build output is disposable, but never delete an earlier private review folder or credential pair.

Expected private, **not deployment-approved** output: `SHINO-TV-V21-HEAP-PRIVATE-NOT-A-FLASH-APPROVAL.bin`, `OEM-V9.0.44-APPLICATION-ONLY.bin`, `credentials.txt`, `shino_private_policy.h`, and `REVIEW-ONLY-MANIFEST.json`. The sanitized manifest must report `build_profile=esp12e_heap_diagnostics`, `read_only_heap_instrumentation_compiled=true`, `private_pair_checks.experimental_exact_oem_return_present=true`, exact source SHA and candidate file SHA/bytes, `owner_ready_to_flash=false` and `physical_device_contacted=false`. Review only the **sanitized manifest** when discussing results; do NOT paste `credentials.txt`, `shino_private_policy.h`, the proprietary OEM binary, or the owner image into chat/GitHub. A successful local kit is only evidence to consider two later separate Wi-Fi write approvals; it is never an installation action.
