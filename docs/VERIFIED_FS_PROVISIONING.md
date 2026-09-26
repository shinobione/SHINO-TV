# SHINO // TV — Verified LittleFS provisioning, **read-only phase**

**Status:** offline implementation only; single owner device on official Ultra-V9.0.44 remains untouched. This PR DOES NOT enable any filesystem upload, write, erase, mount or formatting operation. PR #12's first-boot bridge remains the only permitted startup profile.

## Critical result from the actual ESP8266 updater source

The source of the Arduino ESP8266 `UpdaterClass::begin(size,U_FS)` (see [Updater.cpp](https://github.com/esp8266/Arduino/blob/1475ed7d49fef5c5167061ac76abb6eced9abda5/cores/esp8266/Updater.cpp)) has two branches:

- In the **default (non-ATOMIC_FS_UPDATE) mode**, staging begins at `FS_start - 0x40200000`; the first upload sectors are immediately erased and rewritten in the **active** LittleFS region. The MD5 check is in `UpdaterClass::end()`, **after data writes**. An invalid digest or interrupted upload **can already destroy original filesystem bytes**; rejecting at the end cannot undo this.
- With optional `ATOMIC_FS_UPDATE`, it must fit the *whole* filesystem image **before** `FS_start`, without overlapping the current app. That is not available for our complete 4m2m image at current geometry, so enabling a flag does not magically make this operation transactional.

Here are the actual reviewed offsets for the 4,194,304-byte device, following the official `eagle.flash.4m2m.ld` source:

| Boundary | Flash offset |
|---|---:|
| SHINO LittleFS start | `0x200000` = 2,097,152 |
| SHINO LittleFS end (exclusive) | `0x3FA000` = 4,169,728 |
| **Whole LittleFS image** | **2,072,576 bytes** |
| Hypothetical atomic whole-image staging start | `0x200000 - 0x1FA000 = 0x006000` = 24,576 |

The running bridge application is much larger than 24,576 bytes (PR #12 read-only build: 375,840 bytes). Consequently a **full-size atomic filesystem stage is geometrically impossible** under this map. There is no way to represent an interrupted full-size `U_FS` upload as no-write or safe rollback on this layout.

The *inferred* stock 4m3m files area spans `0x100000..0x3FA000`. SHINO's entire proposed LittleFS is a **2,072,576-byte suffix of that old storage**. This inference is strongly supported by the owner's exact read-only `/space.json.total=3,121,152` matching Arduino 4m3m to the byte, but proprietary stock internals and actual user file backup have NOT been independently established. The official GeekMagic V9.0.44 ZIP is **application-only** and cannot restore OEM filesystem contents.

## Implemented now: verified package, NO writer

1. **Source inventory gate:** only first-party `web/*.html`, `web/css/*.css`, `web/js/*.js`, and a strictly blank disposable `config.json` may be packaged. A real SSID, password, token, symlink, arbitrary private file, legacy generic OTA script or update route fails. The two developer config examples now live at `firmware/examples/`, **outside** the packaged LittleFS root; legacy `otaUploadHandler.js` was deleted from source and its Alpine registration removed.
2. **Independent full-image check:** `tools/verify_fs_provisioning.py` refuses any `littlefs.bin` that is not the exact `2,072,576`-byte raw 4m2m LittleFS image. It records its own SHA-256 and the streaming ESP8266 Updater-compatible MD5, plus source asset hashes and the overlap/no-atomic status. It never calls an ESP device or sends an upload.
3. **Per-build firmware pin:** the workflow builds the filesystem **first**, checks it, then passes the same ephemeral image to `tools/generate_shino_device_policy.py --fs-image ...`. The ignored private C++ header includes FS size, image SHA-256 and MD5 along with the separately verified exact OEM V9.0.44 pin; `SHINO_ENABLE_FS_MIGRATION` is **hardcoded to 0**. A missing or incorrect FS image fails firmware policy generation. No FS binary is committed or published as a GitHub artifact.
4. **Authenticated GET-only description in first-boot bridge:** `GET /api/v1/bridge/fs-plan` displays the image digest and size, offsets, expected OEM-data overlap and irreversible-update warning. It has **no POST**, and compiler static assertions reject any policy that sets `SHINO_ENABLE_FS_MIGRATION != 0`.
5. **Software regressions:** tests reject malformed images, changed 4m2m map, any secret in `config.json`, obsolete arbitrary upload script, unexpected assets/symlinks, missing OEM/FS pins, and any attempt to compile a filesystem writer in bridge mode. All GitHub checks operate offline only.

## Safe workflow now (PC / CI only)

If doing independent research with an extracted copy of the current source and PlatformIO, run **from the project root**:

```powershell
# Only build a local filesystem image. NEVER use pio upload or uploadfs.
cd firmware
pio run -e esp12e -t buildfs
cd ..
py tools/verify_fs_provisioning.py --image firmware/.pio/build/esp12e/littlefs.bin --source-root firmware/data --platformio firmware/platformio.ini --out research-local/fs-plan.json
```

The blank `firmware/data/config.json` source is created by CI only. On a local source checkout, create that exact blank configuration first (see `EXPECTED_BLANK_CONFIG` in the verifier); never copy your real wireless/API secrets into build data. If `research-local/` does not exist, create it; the report is new-file-only, no overwrite. This command does **not** touch the SmallTV.

No migration upload instructions, upload URLs, or arbitrary write handlers are supplied in this PR.

## Decisions needed before an actual device migration could ever be approved

- **Asset strategy first:** Consider serving the SHINO UI/assets from program flash or from the existing Windows companion, avoiding a new on-device LittleFS entirely. The desktop is already a required telemetry partner. This is a legitimate alternative to losing OEM GIF/photo data.
- **If a new on-device FS is indispensable**, determine whether the owner has obtained an independent restorable copy of their manufacturer assets (the OEM app ZIP does not suffice), then request **separate explicit acceptance** that `0x200000..0x3FA000` would be rewritten. Wi-Fi-only with no UART cannot promise recovery if the program fails to boot.
- Plan a genuinely isolated user-authorized destructive operation, exact package and staged host-side digest validation **before** starting `U_FS`, protected local AP/Digest authentication and on-screen confirmation, interruption warnings, and a read-back validation strategy. Host-side SHA-256 assures the *prepared file*, not the success of any later destructive flash transmission. Even with MD5 on the device, a bad stream can already erase sectors.
- Do NOT allow an automatic migration after the initial OTA or while first-boot bridge is merely observed.

## Result interpretation

**Validated local image != permission to write it.** The continued software gate is `OFFLINE_IMAGE_INTEGRITY_ONLY__FS_WRITER_NOT_AUTHORIZED`; first boot remains FS-unmounted and EEPROM-uninitialized by SHINO app source. The full user dashboard remains held. The only existing experimental POST in the bridge is the separate, exact-pinned original **application** V9.0.44 return; it cannot restore the original filesystem. No actual manufacturer/SHINO roundtrip or hardware recovery has been tested. All stacked PRs remain Draft.
