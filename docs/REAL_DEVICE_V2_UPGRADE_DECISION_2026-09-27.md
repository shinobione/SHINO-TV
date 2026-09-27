# SHINO // TV — real owner's V2 corrective update decision packet (NO WRITES)

**27 September 2026 · Decision state: READ-ONLY RESEARCH. No new device OTA authorized by this document.** Exact installed private owner build: 398,864 B, SHA-256 `bd8c9b1ea86caace5fd088f889071b8091b083887383cdc0123e5d950b2b5738`. Real device currently boots native four cards, its WPA2 `SHINO-FirstBoot-*` AP and HTTP Digest work, runtime reports 4,194,304 B flash and 398,864 B sketch, and Windows RAM-only telemetry is accepted. Reported faults: full LCD horizontal mirror and Chrome repeated Digest prompts under simultaneous background GET polling + PC POST. [Source-only hotfix PR #19](https://github.com/shinobione/SHINO-TV/pull/19) addresses these faults but is NOT deployed and is NOT the same exact binary/credentials.

## 1. Hard limit of what is INSTALLED on the owner's chip

The deployed `FirstBootBridge.cpp` registers:
- Authenticated `GET /`, `GET /ui.js`, `GET /api/v1/bridge/status`, `GET /api/v1/bridge/fs-plan`, `GET /api/v1/bridge/factory-return`, and `GET /api/v1/bridge/metrics`;
- Authenticated `POST /api/v1/bridge/metrics`: bounded **volatile numeric PC telemetry only**, NOT firmware or arbitrary bytes;
- With exact owner policy `SHINO_ENABLE_FACTORY_RESTORE=1`, one authenticated multipart `POST /api/v1/bridge/factory-return`: **ONLY** pinned manufacturer's `FW-Smalltv-Ultra-V9.0.44.bin` application, exactly 494,144 B, matching generated OEM MD5; firmware is NOT a 4-MiB owner backup.

The `FactoryRollback.cpp` source explicitly requires field name `factory_v9_0_44`, filename ending `.bin`, observed flash size 4 MiB, `ESP.getFreeSketchSpace() >= 494144+4096`, valid ESP8266 header, exact byte count and compiled MD5 before successful `Update.end(false)`. It writes OTA staging flash **while receiving bytes**, before final MD5 is known. Invalid/partial upload can reject and may schedule reboot to reset Update state. It cannot recognize or approve PR #19's application MD5. No generic SHINO→SHINO OTA, no `/update` vendor route on current SHINO, no `/legacyupdate`, no U_FS, no safe universal rollback.

**Never** send a hotfix BIN to the OEM-return route; never try a dummy/incomplete POST, substitute filename/field or use the PC metrics endpoint as an updater. Old `http://192.168.1.70/update` was the manufacturer's page and is not the current SHINO AP route.

## 2. One last useful live read-only check — perform only from an owner device attached to SHINO AP

Close browser tabs polling the V2 dashboard to avoid the existing Digest nonce/login storm. With the private original owner credentials, manually open only:
1. `http://192.168.4.1/api/v1/bridge/status`. Expected: `mode=FIRST_BOOT_BRIDGE`, `physical_flash_bytes_observed_at_runtime=4194304`, `running_application_bytes=398864`, `factory_app_return_compiled=true`, and the linked free-sketch-space report ~647168 B observed at the earlier runtime check (can vary). No claim this is the stock OEM slot size.
2. `http://192.168.4.1/api/v1/bridge/factory-return` **GET ONLY**. Expected: `firmware="GeekMagic Ultra-V9.0.44"`, `application_bytes=494144`, `manufacturer_sha256=a6421f5bfee7860d97bed26620c346b8008f503e513702d4bfdf6e01010a7718`, `write_enabled=true`, `full_flash_backup=false`, `filesystem_layout_verified=false`.

This proves only that a running route advertises the intended pinned app and enough *reported* stage budget, NOT that staging, reboot, OEM files/settings or subsequent OEM Wi-Fi/web updater will actually work. Record screenshots/sanitized JSON with no credentials, network identifiers or request authorizations. No POST or firmware is sent.

## 3. Alternatives, with distinct risks (NOT an instruction to execute)

| Option | Implications |
|---|---|
| Keep current SHINO V2 and close browser tab | LCD metrics work but glyphs mirrored; lowest current intervention. One can keep using it until a better recovery path is arranged. |
| Acquire independent ESP8266 UART/full-flash backup and documented recovery method | Requires physical access/equipment and careful electrical verification, but can provide an owner-specific recovery route without depending on Wi-Fi/booting SHINO. Not asserted to be available under current owner's no-solder/no-UART constraints. Do not connect unreviewed voltage/pins. |
| **Two separate Wi-Fi OTA actions**: current SHINO → pinned OEM V9.0.44 app, then after independently establishing actual OEM boot/GET-only `/v.json` and `/update` access, OEM → separately generated/frozen PRIVATE PR #19 hotfix BIN | First leg **unproven physically**. OEM app-only restoration cannot restore missing original GIFs/files/settings and may not join the old network or offer an accessible updater. If OEM fails to boot, there is no guaranteed Wi-Fi recovery. Second leg is another independently risky OTA and must be separately consented. One must never assume completing the first leg guarantees the second. |

The user's earlier original stock `GET /space.json` reported photo/GIF storage 3,121,152 B; this fingerprints—but does not independently prove—4m3m old FS geometry. The user's earlier SHINO runtime `getFreeSketchSpace=647168` and corrected 4m3m model nominally accommodate the OEM app (round staging 495,616 B at `0x087000..0x100000` with 151,552-B nominal gap). Arithmetic is not validation of either proprietary or physical OTA success. Power loss and any alternate SDK writes remain unknown.

## 4. Mandatory future gates if two-leg option is separately chosen

- **Before ANY new device write:** preserve the original working owner kit `review-001`, original credentials and original BIN, plus factory ZIP and matching app; close high-frequency browser polling and prevent simultaneous requests during any future physical update. Verify exact OEM app SHA-256 `a6421f5bfee7860d97bed26620c346b8008f503e513702d4bfdf6e01010a7718`; check real first-boot runtime status and GET-only factory reference above. Independently freeze a **NEW PRIVATE HOTFIX** against a reviewed, complete PR #19 source SHA in a **different** output folder, with its **new matching credentials**, unique SHA-256, ESP8266 esptool checks and offline owner-install gate. Never reuse old credentials with new binary. Public CI artifacts are ephemeral and not private release BINs. PR #19 remains Draft, and CI green is not proof of runtime behavior.
- **Separate gate 1**: a clear informed owner authorization naming **exact OEM application SHA** and the single SHINO→OEM POST, with acknowledgement that OEM app-only is not a full flash backup, files may be lost, and no Wi-Fi rescue if OEM does not boot. The only supported writer is the exact one currently compiled into running SHINO. No automated test upload, no retries on unclear response.
- **STOP AFTER LEG 1**, regardless of browser response, until independently observing the actual OEM boots and its own `GET /v.json` says Ultra-V9.0.44, and `GET /update` is accessible on its current real IP. If it is not accessible, STOP: do not attempt leg 2, don't assume old IP/credentials are restored, and don't improvise another write.
- **Separate gate 2**: only after OEM is independently observed, freeze/check exact new owner-private candidate and new key file, inspect OEM's current update form and network/power, and obtain a fresh explicit authorization for OEM→exact new private hotfix SHA. The first installer cannot be reused as the new image. An OEM POST is a second risky write; no vendor recovery guarantee.
- Post-install: verify new running sketch size, 4-MiB flash, unmirrored LCD labels/cards, no repeated Chrome authentication prompts while Windows sender runs, RAM-only metrics/stale behavior, current private credentials, no FS/EEPROM writes. Preserve the original `review-001` kit separately for forensic provenance.

**CURRENT DISPOSITION: existing SHINO remains physically untouched by PR #19. Read-only live reference verification is the only next owner action requested.**
