# V2.1 — Owner hardware installation decision (NO FLASH AUTHORITY)

**Gate:** BLOCKED — do not attempt an instrumented-device installation from the working `review-002` SmallTV. This is a concrete transition handoff, not an image release, generic advice to use the OEM updater, or permission to merge. Keep PR #20 Draft and `permission_to_flash=false`.

## What is already demonstrated

- Existing physical V2 bridge works on the private AP with its four LCD/Chrome values and the owner's normal RAM-only Windows sender. Four owner-reported one-shot diagnostic readings: 32,184 bytes idle; 32,016 Chrome; 31,960 normal telemetry; 32,128 after load. Installed sketch size was consistently 400,592 bytes. These readings do **not** establish peak/minimum free heap, heap fragmentation, largest free block or two-client resource budgets.
- A separate opt-in `esp12e_heap_diagnostics` profile actually compiles with the pinned ESP8266 Core 3.1.2, in the same linked layout as the default `esp12e` profile; CI's disposable build was 402,320 bytes vs default 399,152. The opt-in observer is read-only, cooperatively samples at most 1 Hz with no catch-up bursts, caps its valid observations at 1,024, and projects `heap_observation` only onto the existing Digest-protected GET status. The original four cards and existing status fields remain.
- The Windows one-shot tool accepts the old status and strictly validates the optional new observed summary without printing passwords/raw JSON. Exact-head offline CI at `8a26f2b2b090d7d7eda6189284f78feacb8b7592` passed 4/4.

## Why the working device CANNOT just be updated over its current Wi-Fi page

1. Installed `review-002` has **no live native SHINO OTA arm/upload route or flash writer**. Its real `GET /api/v1/bridge/status` is diagnostics only; `POST /api/v1/bridge/metrics` is bounded RAM-only telemetry. Never try to POST a BIN to either. Firmware and host-only OTA prototypes in this PR do not retroactively add a writer to installed hardware.
2. The existing browser session/cookie and legacy `SHINO-FirstBoot` Digest are not authority to install firmware. The future separate strict SHA-256 `SHINO-OTA` gate is still disconnected.
3. CI deliberately creates **disposable new per-build Wi-Fi and HTTP secrets**; its compiled BIN is not an owner-matched production image. Do not silently install it, reuse the old credential file against it, or publish the private policy and keys in Actions artifacts.
4. The verified OEM V9.0.44 ZIP/BIN is an **application OTA image only**, NOT this owner's 4 MiB full-chip readback, settings/files restore or hardware boot recovery. The research recovery loader was compiled but has not been proven to survive an invalid firmware/boot failure on this specific board. A functioning V2 web UI cannot be assumed to exist after an installation failure.
5. USB-C/ordinary Wi-Fi access must not be assumed to provide ESP8266 ROM serial access. No owner-board UART pinout, safe 3.3 V interface, independently matching complete readbacks, or independently demonstrated restore path has been established in this gate. Do not propose a serial/upload command based on guessed COM or GPIO pads.

## Minimum next owner-operated evidence, BEFORE proposing an installation

**A. Noninvasive hardware inventory.** If the owner is comfortable opening the case, collect clear PCB-front/PCB-back photographs (board revision, printed labels, chip and potential test pads visible), with power disconnected. No soldering, wiring, GPIO probing, case opening while powered, or 5 V serial connection is authorized by this memo. Ask first if disassembly is acceptable; the device remains usable as-is.

**B. Review the actual physical readback path.** Independently identify ESP8266 3.3 V UART TX/RX/GND, GPIO0 boot strap and reset/power wiring *from the actual PCB*, including LCD-related constraints. If a reliable, minimally invasive path is unavailable, label the physical upgrade **BLOCKED** rather than treating OEM application ZIP as brick recovery.

**C. Only after separate owner approval for hardware access and read-only identification**, follow `docs/RECOVERY_PROTOCOL.md` for flash-ID verification and TWO independent complete 4 MiB flash reads. The existing `tools/verify_flash_backup.py` must verify their exact size, byte equality, matching SHA-256 and plausible initial app header. Store backups encrypted, outside Git/connected shares, never disclose raw images or credentials. Merely compiling an image, seeing a positive heap count or extracting OEM OTA does not substitute for this evidence. Existing full-flash backups, if the owner already has them, can be checked *offline* first; no need to reread flash solely to repeat a proven exact backup.

**D. Owner-specific offline build gate.** After the backup/recovery route has been independently reviewed, generate or deliberately select a *matching private build policy*, keeping the future Wi-Fi PSK/Digest password in a new private folder. The current generator refuses overwriting preexisting credentials. Compile the exact opt-in candidate locally without any upload target; verify the binary SHA-256, source commit, pinned board/core/4m3m linker, size and genuine opt-in `OBSERVED_HEAP_V1` marker, absence of FS image and disabled native OTA/factory-return writer. Check that the owner has secure access to the **new** private credentials and an exact known-good fallback. Do not put secrets/firmware bytes into this PR.

**E. Per-action consent.** Present one named device, exact local BIN SHA-256 and size, actual transport/recovery route, known failure modes and post-install read-only smoke-test plan (AP login, Chrome session prompts, four LCD values, normal Windows metrics, status samples and observed-summary bounds). Require the owner's new unambiguous authorization **for that specific installation**. A generic `ok/go`, CI green or this document is not a flash approval. No default automated retry, FS migration, OTA writer activation or PR merge.

## Go/no-go now

**NO-GO for physical installation.** Safe next action is documentation/PCB inspection or an offline inventory of any existing verified *full-chip* backups. The opt-in diagnostic source and the host/CI test work can remain in Draft for review. Do not claim a zero-brick-risk Wi-Fi upgrade; we currently lack both an installed firmware writer and a verified hardware recovery path.

**Provenance and limits:** the four current-device numbers are owner-reported PowerShell outputs. The binary sizes cited above are disposable CI builds, not owner-specific installation images. No hardware upload, flash write, full-chip readback or independent live rollback test occurred in this work.
