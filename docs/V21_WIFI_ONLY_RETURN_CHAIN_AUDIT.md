# SHINO // TV V2 → OEM → V2.1 — actual Wi-Fi-only route reconstruction

**Purpose:** correct an earlier mistaken premise. There is an *already owner-tested* Wi-Fi return chain through the original OEM application, not merely an unimplemented hypothetical direct SHINO OTA. This record is a source/history audit, NOT an instruction or authority to upload. USB-C is power-only for the owner. No serial/UART/pogo/PCB/solder/device purchase as a normal development requirement. PR #20 Draft, `permission_to_flash=false`.

## Actual prior owner event, 2026-09-27

The owner previously explicitly authorized an **individual** return from the then-installed SHINO V2 to the **exact pinned OEM Ultra-V9.0.44 application**. The existing Digest-authenticated `GET /api/v1/bridge/factory-return` of that **PREVIOUS V2** was observed to report `write_enabled:true` (not an assertion about today's installed Hotfix). After the authorized action, the owner reported that the physical SmallTV showed the manufacturer clock, rejoined domestic Wi-Fi, `GET /v.json` reported `{"m":"SmallTV-Ultra","v":"Ultra-V9.0.44"}`, and the manufacturer's `GET /update` interface was reachable. A separate subsequent transition via the OEM update interface back to the private SHINO V2 Hotfix resulted in the physical 240x240 four-card LCD working.

The **CURRENT installed** Hotfix is the owner-reported private `review-002` built from source commit `cf65c74775ac55b52b3993704e2f8b8e6cce198a`; user-reported private candidate **400,592 bytes**, SHA-256 `d7d37092573e65be13f54077e95534438fe790a27b2e65cbd0b8034f18f93717`. The four later owner-reported running `/status` responses consistently showed `running_application_bytes=400592` and free heap 32,184 (idle), 32,016 (Chrome), 31,960 (ordinary PC metrics), 32,128 (after load). This supports running-image size/operation, but is **not an independent rehash of flash**.

## Source-specific current Hotfix facts and the sole remaining GET-only confirmation

At exact `cf65c747...`, the `SHINO_BOOT_PROFILE=0` `setup()` calls only `FirstBootBridge::run()` and returns: legacy normal-mode `Webserver`, `RescueMode` and any old `/legacyupdate` route do not start. There is **NO live generic SHINO native updater** in that firmware. Nevertheless, the original bridge registers `GET /api/v1/bridge/factory-return` under Digest, and conditionally compiles the same route's **OEM-only POST** with `SHINO_ENABLE_FACTORY_RESTORE=1`. Its read-only status reports pinned 494,144-byte manufacturer application, manufacturer SHA-256 and literal boolean `write_enabled`. The `review-002` private build tool `tools/build_private_owner_packet.py` explicitly generates policy with `--enable-restore`, and the owner-shared offline review manifest reported `factory_app_return_compiled:true`. That is **local-build evidence, not yet a post-Hotfix device status observation**.

A single final **read-only check of the CURRENT device** (one authorized normal browser visit while connected to SHINO private AP) is therefore genuinely decisive:

`GET http://192.168.4.1/api/v1/bridge/factory-return`

Use the **existing** `SHINO-FirstBoot` HTTP Digest login. Never send a file, POST, PUT, flash command, curl upload or a credential in chat. Record **only** `write_enabled`, `application_bytes` and whether the `manufacturer_sha256` equals the pinned expected `a6421f5bfee7860d97bed26620c346b8008f503e513702d4bfdf6e01010a7718`. The expected response also says `full_flash_backup:false` and `filesystem_layout_verified:false`. If `write_enabled` is false, missing, malformed, or the hash/size differs, STOP; no working current V2→OEM path established. **A true result is evidence that the exact-OEM-only route is present, not permission to invoke it or a zero-risk guarantee.**

## Conditional future chain, NOT approved for use now

1. **Running review-002 → original manufacturer application** via its *existing, specifically bounded and authenticated* OEM-only return receiver, **only if** the above post-Hotfix GET confirms the endpoint and separately reviewed owner consent names exactly this operation and the pinned OEM image.
2. Wait for actual boot and independently confirm the known manufacturer UI and `/v.json` version; absence of those signals means STOP — do not blindly attempt the second upload.
3. **Manufacturer Ultra-V9.0.44 `/update` → owner-private newly compiled SHINO V2.1**, using the already owner-observed OEM multipart update form, *only after* reviewing current source identity, private matching credentials, image hash/size, pinned 4m3m linked geometry, FS preservation model, offline header and known/residual risks, and a separate explicit go for this SECOND firmware operation. The previous 400,592-byte Hotfix was successfully installed through this kind of transition; a 402,320-byte CI diagnostic prototype is **not** an owner-ready private image or proof that a different image will be accepted/boot. Do not stage the old 4m1m trampoline as a fallback: its modeled second hop overlaps manufacturer file sectors.

**Risk honesty:** Two OTA writes and two boots are not automatically safer than one; this route is the *observed functional Wi-Fi alternative under owner constraints*, but power loss, bad OEM acceptance, nonbooting application, changed credentials and original-data loss still need explicit acceptance. Neither the OEM ZIP nor read-only API provides a full original 4-MiB backup or independent Wi-Fi recovery from an unbootable application. No serial/hardware purchases are required or proposed for the planned route; actual brick recovery is a separate, user-requested contingency only.

## Engineering handoff

- Stop telling the owner that all Wi-Fi installation pathways are absent: the **previous** V2→OEM→V2 private route was observed working and the **current** private build manifest says OEM return is compiled. Also stop pretending generic SHINO-native OTA already exists in current V2.
- Close the current-build OEM-return existence question via the above single existing, authenticated **GET only**, not an upload/dummy file or undocumented endpoint scan.
- Prepare the **next owner-private candidate** offline, with `SHINO_ENABLE_FACTORY_RESTORE=1`, matched new AP/Digest credentials, real opt-in heap diagnostics, verified OEM reference and exact image hash; do not publish the generated private policy or package or treat CI disposable BIN as a release.
- Keep the currently working review-002 running unless/until owner explicitly authorizes each concrete future Wi-Fi firmware transition. No automatic double-hop, no unattended rollback and no PR merge.

**Boundaries:** Past on-device observations were user-reported in project conversation, not reproducible CI-device tests; static private review is distinct from device GET; current manufacturer OTA application is not a full-chip original backup; memory snapshot results alone never authorize flash.
