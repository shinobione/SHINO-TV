# SHINO // TV — comparative ESP8266 flash/layout audit
**Date:** 2026-09-26 · **Status:** source/official-release/owner-GET report analysis only · **Device NOT flashed.**

This compares the owner-observed stock `Ultra-V9.0.44`, the matching original GeekMagic application OTA, Times-Z's complete open firmware (our pinned base), giovi321's alternative `smalltv-mod` (full, lean and its bootstrap loader), and our current compiled SHINO candidate + protected loader. It does **not** conflate the ESP32-C2 or ESP32 Pro binaries with the owner's ESP8266 Ultra.

## Evidence sources, scope and vintage

- Owner **sanitized GET-only** report sampled `2026-09-26T21:00:35.221779Z`: `/v.json` model SmallTV-Ultra / version Ultra-V9.0.44; `/space.json` **3,121,152 total** / **1,056,268 free**, identified as photo/GIF filesystem; `/update` has a `POST` multipart form and file field `firmware`. No file upload, no accepted image, no exposed OTA slot capacity and no original filesystem type proven. Do not commit personal raw reports.
- Manufacturer's [original, historical V9.0.44 ZIP](https://github.com/GeekMagicClock/smalltv-ultra/blob/55d7877fcba8b1cb7a66a0830d35d5b374bc8540/Ultra-V9.0.44/FW-Smalltv-Ultra-V9.0.44.zip), pinned commit `55d7877...`, outer and inner SHA-256 in [our manifest](../recovery/factory_ota_v9_0_44.json): **494,144 B application BIN**, not 4-MiB stock backup.
- [Times-Z v1.5.0 release](https://github.com/Times-Z/GeekMagic-Open-Firmware/releases/tag/v1.5.0), published 2026-07-21: `firmware.bin` **445,696 B**, `littlefs-smartTV.bin` **2,072,576 B**. [Its source `platformio.ini`](https://github.com/Times-Z/GeekMagic-Open-Firmware/blob/a0c2ddcef4e76fa6eb040f6f544124763a2d85f5/platformio.ini) specifies `esp12e`, 4-MB DIO, `eagle.flash.4m2m.ld`, LittleFS.
- [smalltv-mod v2.16.0 release](https://github.com/giovi321/smalltv-mod/releases/tag/v2.16.0), published 2026-09-24: ESP8266 full **780,352 B**, lean **654,464 B**, loader **315,920 B** (actual uploaded GitHub asset byte counts). Source `[env:smalltv]` and `[env:smalltv_loader]` both use `eagle.flash.4m1m.ld`. Its documented Ultra install uses a short OTA loader, then an OTA of the full image; it explicitly records stock `ERROR[4]: Not Enough Space` with full firmware. [Flashing guide](https://github.com/giovi321/smalltv-mod/blob/main/docs/src/content/docs/getting-started/flashing.md), [PlatformIO source](https://github.com/giovi321/smalltv-mod/blob/main/platformio.ini).
- Our compiled PR #9 [read-only candidate](https://github.com/shinobione/SHINO-TV/actions/runs/36267887778): **453,296 B**; [experimental exact-OEM-return candidate & loader](https://github.com/shinobione/SHINO-TV/actions/runs/36267887773): **456,960 B** and **312,256 B**. Compiled `firmware/platformio.ini` uses `4m2m`; `recovery_loader/platformio.ini` uses `4m1m`. All are DIO, 4-MB, 40-MHz ESP8266 application images in our `esptool image-info` CI.
- ESP8266 linker maps compared at [Arduino core pinned commit `1475ed7...`](https://github.com/esp8266/Arduino/tree/1475ed7d49fef5c5167061ac76abb6eced9abda5/tools/sdk/ld). For the updater geometry model, see [`EspClass::getFreeSketchSpace()`](https://github.com/esp8266/Arduino/blob/1475ed7d49fef5c5167061ac76abb6eced9abda5/cores/esp8266/Esp.cpp) and [filesystem docs](https://arduino-esp8266.readthedocs.io/en/latest/filesystem.html). This is a *model*, not identification of the exact proprietary factory code.

## 27 September 2026 supersession note: actual FS-less 4m3m candidate

The older table below quotes PR #9 binaries using 4m2m and is retained **only for historical comparison**. The owner-approved FS-less V2 was later built with `eagle.flash.4m3m.ld`, which keeps the Arduino U_FLASH staging ceiling before the inferred original stock FS `0x100000`. New actual experimental V2 CI size: **398,848 B**, default read-only **395,472 B**; exact OEM app 494,144 B. Direct factory→V2 staged sectors `0x09E000…0x100000`; running 4m3m V2→OEM staged sectors `0x087000…0x100000`, no inferred stock FS overlap under the unproven 4m3m-like manufacturer model. Conversely 4m1m loader→V2 second hop overlaps **401,408 B** of inferred stock files. See [current decision packet](FIRST_INSTALL_DECISION_PACKET.md); do not use the historical 4m2m layout warnings below as current candidate metadata.

## 1. Exact storage fingerprint: `4m3m`

All three official Arduino layouts below are for **4,194,304 B total physical flash**. The physical file offsets follow by subtracting `0x40200000` from linker `_FS_start`. They share `_FS_end=0x405FA000`, i.e. flash offset `0x3FA000`; later reserved sectors hold EEPROM/RF/Wi-Fi.

| Candidate image/layout | Physical FS starts | FS ends (exclusive) | Raw FS bytes |
|---|---:|---:|---:|
| **`eagle.flash.4m3m.ld`** | `0x100000` | `0x3FA000` | **3,121,152** |
| `eagle.flash.4m2m.ld` (Times-Z and SHINO) | `0x200000` | `0x3FA000` | **2,072,576** |
| `eagle.flash.4m1m.ld` (smalltv-mod and loaders) | `0x300000` | `0x3FA000` | **1,024,000** |

The owner-observed `/space.json.total=3121152` matches the official `4m3m` **to the byte**. Thus the stock's filesystem geometry very strongly resembles `4m3m` or an equivalent custom map, more specific than a vague “around 3MB” inference. Still **not a full-stock-flash dump** or independent proof of stock program/OTA behavior: `/space.json` reports FS size, not free application OTA bytes. The remaining 1,073,152 bytes include program, OTA staging and reserved areas, **not one usable 1,073,152-byte OTA image slot**.

## 2. Image-size comparison and a conditional stock OTA model

| Raw application BIN | Bytes | Delta from nominal 512 KiB (positive = below) |
|---|---:|---:|
| GeekMagic official Ultra V9.0.44 | 494,144 | +30,144 |
| Times-Z v1.5.0 | 445,696 | +78,592 |
| SHINO default v9 preflight | 453,296 | +70,992 |
| SHINO experimental v9 preflight | 456,960 | +67,328 |
| SHINO mini-loader | 312,256 | +212,032 |
| smalltv-mod v2.16.0 mini-loader | 315,920 | +208,368 |
| smalltv-mod v2.16.0 lean | 654,464 | **-130,176** |
| smalltv-mod v2.16.0 full | 780,352 | **-256,064** |

The older manufacturer samples already inspected in [audit 01](FIRMWARE_AUDIT_01.md) reinforce this pattern: V9.0.40 **510,496 B**, V9.0.46 **501,040 B**, and V9.0.50 **505,200 B**, all under nominal 512 KiB. These come from different manufacturer OTA packages and illustrate that the vendor itself keeps these applications small. They do not disclose the updater's precise allocation logic.

**Important distinction:** The 512-KiB comparison is a useful *nominal* half of the inferred ~1-MiB pre-filesystem region. It is not a measured stock OTA setting. The ESP8266 Arduino updater derives free sketch staging from the **currently running sketch size** and linked `FS_start`, aligns to flash sectors and also has implementation-specific checks. If (1) the stock really uses `4m3m`/equivalent, (2) its active sketch really occupies approximately the 494,144-byte OEM BIN and (3) it uses a compatible Arduino-style update path, the simple rounded geometry predicts:

```
0x100000 (FS starts) - round_up_4096(494144 = 495616)
    = 552960 bytes for update staging (UNMEASURED model only).
round_up_4096(SHINO experimental 456960) = 458752 bytes.
552960 - 458752 = 94208 bytes geometric spacing (NOT a boot/safety proof).
```

The smalltv-mod full and lean builds are larger than this hypothetical space, coherently explaining its documented Ultra loader technique. **SHINO is smaller than the official current OEM BIN by 37,184 B**, and the Times-Z installation guide instructs a direct stock `/update` first hop with its `445,696`-byte binary. It follows that a **direct SHINO OTA should be investigated, not presumed successful**, before making the owner carry out two irreversible application updates. Manufacturer validation, alignment details, ESP image format, app-slot rules and SDK/library behavior remain unknown until more evidence.

Do NOT try uploading a dummy BIN merely to provoke `Not Enough Space`. This engages the proprietary updater's write/validation path on the owner's only device.

## 3. Changing FS map is more consequential than these BIN sizes

| Current stock-like FS | Candidate FS | Relationship |
|---|---|---|
| `0x100000 … 0x3FA000` | SHINO/Times-Z `0x200000 … 0x3FA000` | New 2-MiB FS is a **suffix of the stock user-data range**; changing/mounting/formatting can overwrite existing stock files. |
| `0x100000 … 0x3FA000` | smalltv-mod `0x300000 … 0x3FA000` | New 1-MiB FS is an even smaller **suffix**, and discards the stock layout too. |

The original manufacturer ZIP is **just the application**, not a filesystem snapshot. Returning only its BIN does not recreate overwritten stock assets, preferences or filesystem geometry. The Arduino ESP8266 docs explicitly warn that an incompatible LittleFS/SPIFFS mount may automatically format a partition.

**Concrete inherited SHINO bug found in source:** `firmware/src/main.cpp` currently calls `LittleFS.begin()` *before* checking boot loop and before starting our protected recovery. `ConfigManager::load()` and `save()` call it again; no `LittleFSConfig(false)` is set. The upstream's default `LittleFSConfig(bool autoFormat=true)` may therefore format SHINO's `4m2m` region (`0x200000` onward) on its **very first boot**. In addition, `SecureStorage::begin()` can initialize EEPROM-backed state on that boot. This is **not acceptable as an unqualified “safe first OTA.”**

The bundled Times-Z tutorial includes a separate LittleFS upload *after* its direct firmware OTA. In our hardened SHINO tree, arbitrary firmware/FS upload endpoints and the insecure `/legacyupdate` path were correctly removed. This leaves **no implemented, protected way to install/provision our new LittleFS** following a direct first OTA. We must solve it explicitly rather than silently format old data or deploy a candidate with a broken first-boot web UI. A future stage-0 diagnostics/rescue build can avoid *all* storage writes until a separately confirmed, intentional FS migration; it must supply an authenticated minimal first-boot UI in program flash and an exact-OEM return path while bootable. Merely setting `setAutoFormat(false)` is necessary but by itself is not a complete migration/rollback design.

## 4. What each project's approach actually solves

| Approach | First transition from stock | Subsequent provisioning/updates | Real limitation |
|---|---|---|---|
| Official V9.0.44 → vendor updates | OEM image via HTML multipart | Retains manufacturer update/storage behavior | Exact proprietary updater source/OTA acceptance and complete stock dump unavailable. |
| Times-Z open v1.5.0 | Direct OTA documented; 445,696 B app | Installs separate 2,072,576-B LittleFS image using open `/legacyupdate` | Requires changing/creating FS; its inherited default open AP/unauthenticated update has security concerns and does not provide full factory rollback. |
| smalltv-mod v2.16.0 | Official `315,920`-B loader OTA, then `780,352`-B app via loader AP | 4m1m layout, regular full/lean self-updates | Tiny stock OTA slot forces 2 hops for large app; transient unprotected loader replaced by second app. It cannot recover a unit if app/loader does not boot. |
| SHINO current source | 456,960-B experimental app could geometrically fit inferred first slot; alternatively 312,256-B protected loader | Source contains OEM-only authenticated app/Rescue return and 4m2m layout | Direct OTA acceptance unproven; autoformat/EEPROM first-boot hazard; no secure initial FS provisioning; OEM-only return cannot restore original FS or nonbooting hardware. |

The v2.16.0 smalltv-mod full and lean BINs refer **only to ESP8266**; its `-c2`, `-esp32`, `-esp32-pro` packages target *different chips/boards* and must never be selected for this unit.

## 5. Other practical ceiling: DRAM/heap, not only flash

On the ESP8266, RAM used by static allocations cuts into the heap used for Wi-Fi, JSON, HTTPS and scene rendering. Our actual experimental SHINO CI reports **44,080 / 81,920 B** static RAM (53.8%) and **452,803 / 1,044,464 B** linked flash (43.4%); the released raw app BIN has different file padding and totals **456,960 B**. The upstream smalltv-mod source documents **55,536 B** standard versus **46,804 B** lean static RAM **at v2.12.0** (not claimed as current v2.16 measurements); the lean image omits Home Assistant and usage features to reclaim **8,732 B**. Keep assets and online processing on Windows rather than adding unnecessary TLS/animated buffers on the TV.

## 6. Revised single-device research decisions (not owner-facing upload instructions)

1. **Do not make the two-hop loader mandatory solely due to the size of smalltv-mod.** SHINO and Times-Z are substantially smaller. The very high-confidence 4m3m storage fingerprint justifies first auditing the direct factory→SHINO path offline.
2. **Gate any proposed first-boot candidate on guaranteed no-autoformat and no-EEPROM-initialization behavior when the original filesystem is still present**. Default GUI/secure state may be unavailable until explicit provisioning. The current app does not yet pass this condition.
3. Design a protected small **first-boot bridge/recovery view compiled into program flash**, with read-only status and a separately controlled, exact-OEM original app reinstallation path. Preserve stock FS unless the owner explicitly agrees to irreversible migration after understanding the limited rollback.
4. Determine the original update-handler compatibility and true usable OTA slot **from actual manufacturer image/source evidence** or a previously documented compatible test on the exact stock version, not by probing uploads against the owner's device.
5. All subsequent source-built candidate checks must compare **both the application BIN and its FS image**, resource overhead, runtime RAM, and the original FS protection. Document whether stock assets can really be preserved. Never confuse an OEM application ZIP with a complete 4-MiB device backup.
6. Physical first flash has residual unrecoverable-brick risk without UART/hardware access; report it plainly. The owner alone may later authorize an exact named image/action. All PRs remain Draft.

## Reproducible calculation

`python tools/compare_flash_layouts.py --stock-report <locally-sanitized-stock-report.json>` performs **only offline arithmetic**, no network or physical-device action. Source snapshots and known sample sizes are pinned in code. The tool deliberately reports `stock_OTA_capacity_proven=false`, `OEM_FS_preserved_after_layout_switch_proven=false` and `permission_to_flash=false`. CI exercises this with synthetic reports; the owner report itself is not committed.

**Bottom line:** the observed FS byte count matches the vendor-style Arduino `4m3m` configuration exactly. The size of our application by itself does **not** force a loader. The biggest unmitigated risk is currently first-boot filesystem/EEPROM mutation and incomplete restoration, not raw BIN size.
