# V2.1 — Wi-Fi-only owner transition decision (NO FLASH AUTHORITY)

**Owner's binding operating choice (2026-09-27): WI-FI ONLY.** The SmallTV USB-C port is used for **power only**. Do not propose USB-UART, pogo pins, six-pad investigation, soldering, disassembly, buying an adapter, hardware backup, serial recovery or repeating PCB-photo requests as part of the normal SHINO // TV development and upgrade plan. Discuss physical recovery **only if the unit is actually brick/nonbooting and the owner explicitly chooses to revisit it then**. Do not turn hardware recovery into a recurring preflight request. This replaces prior hardware/pogo-pin planning in this document; the older `docs/RECOVERY_PROTOCOL.md` is archival break-glass contingency, **not the current execution roadmap**.

**Current installation gate: CLOSED** — PR #20 remains Draft, `permission_to_flash=false`. A generic "ok", "go", CI green or this decision document is never approval for a flash write, firmware merge, restart or new software updater.

## Working device and what we have proved

- The installed FS-less V2 Hotfix `review-002` is functioning: isolated Wi-Fi AP, authenticated Chrome dashboard, 240x240 display with four normal CPU/GPU/RAM/temperature readings, and the existing PC sender.
- Four owner-reported, existing Digest `GET /api/v1/bridge/status` heap snapshots: 32,184 bytes at idle; 32,016 with Chrome; 31,960 with normal Windows telemetry; 32,128 after stopping load. Installed application size reported in each was 400,592 bytes. This is four snapshots, not a peak/free-block/fragmentation guarantee.
- A separately selectable `esp12e_heap_diagnostics` build compiles with pinned ESP8266 Core 3.1.2 and a cooperative fixed-size 1 Hz/1,024-valid-sample observed-memory accumulator. CI-generated default BIN: 399,152 bytes; opt-in diagnostic BIN: 402,320 bytes. Both were **compiled offline with disposable test-build credentials, not deployed**. The optional reader accepts the old response and validates the new schema without revealing credentials.

## Hard technical limit on the already installed V2

The installed `review-002` does **not** expose a native SHINO application upload/OTA writer. Existing `GET /api/v1/bridge/status` is read-only diagnostics; `POST /api/v1/bridge/metrics` accepts bounded RAM telemetry only. Neither is an upload endpoint. The browser cookie/Digest login is not firmware-installation authority. A future OTA design in this PR does **not** make an updater appear retroactively on the unit. Never POST a BIN to diagnostics/metrics, guess hidden paths, repurpose an OEM URL from a different running firmware or assume that an offline recovery loader exists on this actual unit.

The source has a separately compiled experimental `factory-return` POST behind `SHINO_ENABLE_FACTORY_RESTORE`, but it is disabled in the conservative owner build. Do **not** infer its presence on the installed device without documented read-only evidence, and do not treat OEM-return as a generic SHINO OTA route.

The verified manufacturer V9.0.44 ZIP/BIN is an **OEM application OTA image**, not a full backup, firmware from the current installed build, or a guaranteed rescue of a nonbooting device. CI generates fresh disposable WPA2/Digest credentials, so CI's binary is not an owner-matched deployable update. Do not publish private headers, firmware dumps, credentials or raw HTTP authentication data.

## Only the least-risk normal route is in scope

1. **Keep V2 Hotfix installed and usable.** Prioritize PC companion, browser/dashboard and source/host-only development while a verified Wi-Fi update pathway is absent.
2. **Read-only Wi-Fi evidence audit.** Using only already authenticated, documented existing endpoints and owner-reported device output, establish whether any **separately authorized, compatible, existing** boot/recovery/update mechanism actually runs on this specific V2. Never probe by writing or guessing an upload route. If none exists (the current source indicates none), record `NO SUPPORTED WIFI INSTALL PATH` and stop at code/CI. Hardware is **not** the requested workaround.
3. **Offline preparation is allowed.** Develop and validate bounded HTTPS/HTTP authentication design, owner-matched credential migration plan, exact binary/manifest identity, official OEM-reference checks, strict signing, nonwriting host parser and explicit recovery limitations. Build the opt-in diagnostics candidate locally only on a separately approved private policy, **without uploading**. Do not mistake a compiling candidate for an available transport.
4. **Only if a supported Wi-Fi transport is demonstrated** and an acceptably limited rollback/failure plan is documented, present the exact operation, current device/build identity, candidate hash/size, credential changes, compatibility evidence, no-retry behavior and residual brick risk. Obtain specific explicit permission for that ONE Wi-Fi installation. Do not attempt an installation when the existing updater is missing or cannot provide the necessary verification. Never claim zero risk.
5. **Break-glass only:** if the SmallTV is actually bricked, tell the owner honestly what Wi-Fi recovery is or is not still available. Mention hardware recovery choices only at that moment, on request. An archival UART readback document does not override the owner's current no-hardware preference.

## Current go/no-go

**GO:** passive existing V2 read-only checks and offline source/tests/dual compilation; maintain the current working four-card firmware. **NO-GO:** flashing the opt-in candidate now, enabling a write route by documentation, replacing port-80 server on the actual unit, merging PR #20, any USB/UART purchase or hardware access in the normal workflow. The unresolved product constraint is the absence of a proven **installed Wi-Fi firmware-upgrade transport**, not the absence of hardware photos.

**Provenance:** owner supplied four sanitized PowerShell readings; GitHub Actions built ephemeral images and performed offline tests. No remote device write, reboot, flash backup or deployment occurred.
