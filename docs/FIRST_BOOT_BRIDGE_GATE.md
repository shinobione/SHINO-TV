# SHINO // TV — First-Boot Bridge / storage preservation gate

**Status: offline SOURCE + CI prototype; NEVER deployed to owner's SmallTV.**
**Goal:** a *single-device, no-solder* candidate whose FIRST SHINO application entry does **not initialize/mount/format the manufacturer's 3-MiB photo/GIF filesystem or initialize/write EEPROM from application code.** The factory V9.0.44 OTA entry and acceptance remain unmeasured. Compiling does not authorize flashing.

## Why

The owner's `/space.json.total=3,121,152` bytes matches the official Arduino ESP8266 4-MB `4m3m` FS region exactly (physical `0x100000…0x3FA000`). The Times-Z/SHINO `4m2m` build instead has its LittleFS at `0x200000…0x3FA000`, a suffix of the manufacturer data area. Arduino `LittleFSConfig` defaults to **autoFormat=true**: blindly calling `LittleFS.begin()` on that incompatible image can format stock data. The prior SHINO normal startup also initialized `SecureStorage` via EEPROM-backed persistence *before* boot-loop Rescue. An app-only official OEM restore ZIP cannot restore an erased manufacturer filesystem.

## What this source actually implements

- Generated `firmware/include/shino_private_policy.h` **always** sets `SHINO_BOOT_PROFILE 0` — a separate first-boot bridge. The old full dashboard startup is blocked at C++ compile time for any nonzero profile pending a deliberate filesystem migration review.
- `setup()` enters `FirstBootBridge::run()` *before* `LittleFS.begin`, `SecureStorage.begin`, `ConfigManager.load/save`, persistent boot counters, or normal API/scene startup. `loop()` handles only the bridge.
- The bridge uses program-flash HTML (not a LittleFS page), RAM-only diagnostics and a private WPA2 AP with a random per-build secret. All GET routes use a **separate per-build HTTP Digest password**, never a known default. Wi-Fi SDK persistence is disabled before selecting AP mode. The screen shows network name and address without exposing passwords.
- Authenticated `GET /`, `GET /api/v1/bridge/status`, `GET /api/v1/bridge/factory-return`. The status explicitly labels SHINO's linked flash/FS geometry and the stock `4m3m` interpretation as **unverified inference**, not owner-stock OTA capacity. It does not serve arbitrary stock files, expose settings, install an image, or show a filesystem migration command.
- Only in an **experimental** source build explicitly generated with `--enable-restore` is `POST /api/v1/bridge/factory-return` compiled, and it calls the existing exact-494144-byte pinned V9.0.44 image handler. Normal CI builds do **not** compile this POST. Enabling it is **not a physical install approval**. Such a restoration requires actual flash staging, can modify/overwrite original data, and cannot fix an unbooting CPU/app.
- A legacy `Webserver::beginFS(true)` is now rejected; the permitted helper configures `LittleFSConfig(false)` before any mount. On the *held* normal path, the same no-autoformat config is required before a mount. Neither path is reachable from the allowed bridge profile.
- No automatic filesystem provisioning, LittleFS format, EEPROM initialization, token persistence, boot-loop counter writes, original-image ZIP redistribution, or upload handler is executed by first-boot bridge mode. We do not claim that the **boot ROM / vendor SDK / Wi-Fi calibration** make zero hardware-level flash writes; CI validates our application source paths, not electrical read-only behavior.

## What the owner would see IF such a build was ever separately authorized

| UI | Purpose |
|---|---|
| 240×240 screen | SHINO first boot, private AP SSID and AP address (no secret) |
| `GET /` | Minimal protected, program-flash explanatory page |
| `GET /api/v1/bridge/status` | Runtime physical flash ID/size, active sketch size, **linked SHINO** free-sketch space, current read-only/mode labels |
| `GET /api/v1/bridge/factory-return` | Verified original manufacturer's BIN reference, scope and whether experimental writer was compiled |
| Other paths / generic firmware / LittleFS upload | Not provided |

**This is not the finished SHINO PC dashboard.** After this source is tested and the owner accepts the risk of losing existing manufacturer photo/GIF data, a second, separate FS provisioning specification must be reviewed. The bridge does **not** self-upgrade or migrate on boot. Running the protected Wi-Fi page is not a proxy for a successful stock→SHINO OTA or a bootable OEM rollback.

## Migration and return design — deliberately NOT IMPLEMENTED yet

1. Establish the current stock FS semantics and whether owner files can be exported with existing manufacturer UI. A full 4-MiB owner-specific stock backup is **still unavailable** over the chosen Wi-Fi-only/no-UART path.
2. Decide which assets/settings, if any, must survive. Before touching `0x200000…0x3FA000` obtain separate **explicit owner approval** acknowledging the irreversible/partial-recovery risk. No claim that official app-only OTA can restore them.
3. Design a separate authenticated, exact-hash-and-size-pinned LittleFS image provisioning step. Recheck staging/flash geometry, power interruption and `U_FS` behavior. Do not expose generic filesystem upload or format-on-mount.
4. After provisioning verification, permit the normal dashboard only in a new reviewed, explicitly gated firmware profile. Retain a protected OEM-app-only return route for a still-booting application.
5. Compare direct first hop against a protected two-hop loader using *exact candidate BIN sizes* and original V9.0.44 OTA evidence. Failure/no-boot remains unrecoverable via Wi-Fi alone if no independent working code starts.

## Offline checks

- `tools/test_first_boot_bridge_source.py`: fail on first-boot FS/EEPROM API calls, normal startup, missing WPA2/Digest gate, unauthenticated arbitrary uploader, format-on-failure helper or false flash approval.
- `tools/test_generate_shino_device_policy.py`: both read-only and experimental OEM-only policy modes force `SHINO_BOOT_PROFILE 0`, refusing credential reuse and corrupt OEM pins.
- `tools/wifi_flash_preflight.py` now requires the **compiled `FIRST_BOOT_BRIDGE` marker** in actual SHINO BIN as well as the manufacturer's exact image digest. A small normal-startup BIN alone is no longer accepted.
- Two ephemeral CI builds verify **read-only bridge** and **experimental OEM-return bridge** without publishing firmware, OEM ZIP, personal credentials or contacting the owner's LAN.
- All source-only checks and CI builds remain evidence of compilation and static regressions, **not** successful hardware rollback.

Related: [comparative 4m3m / 4m2m audit](COMPARATIVE_FLASH_LAYOUT_AUDIT.md), [single-device plan](ONE_DEVICE_WIFI_PATH.md), [pinned official OTA](../recovery/README.md).

**Physical installation remains NO-GO. Do not upload any of these images to the owner's SmallTV until the owner separately authorizes an exact build, understands the remaining stock-slot/FS/boot risks and a complete operational plan is documented.**


## Exact 4m2m asset packaging (subsequent offline-only PR)

The [verified LittleFS provisioning analysis](VERIFIED_FS_PROVISIONING.md) now builds and hashes the complete **2,072,576-byte** filesystem independently, pins its SHA-256 into the private bridge policy, rejects credentials and inherited arbitrary OTA scripts, and exposes an authenticated **GET-only** `/api/v1/bridge/fs-plan` impact report. The entire 2-MiB range overlaps the inferred manufacturer filesystem. Default ESP8266 `U_FS` writes directly into the active region before its checksum verdict; full-image atomic staging is not possible under the reviewed 4m2m geometry with a running application. Therefore **`SHINO_ENABLE_FS_MIGRATION 0` is required by compilation**, no FS POST or format exists, and physical provisioning is explicitly held for a separate owner decision. Neither a verified hash nor the OEM app ZIP creates a stock FS backup.
