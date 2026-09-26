# SHINO // TV — Native FS-less dashboard (single-device prototype)

**Status:** source-only / GitHub CI prototype, not uploaded to the owner's working factory Ultra-V9.0.44. Builds remain draft. No soldering, spare board, serial adapter or second device required for development.

## Objective and architecture

Our stock read-only report strongly fingerprints the manufacturer's original roughly 3-MiB file area: its `/space.json.total=3,121,152` matches ESP8266 Arduino `4m3m` exactly. A replacement 4m2m LittleFS `U_FS` would rewrite a 2,072,576-byte suffix of that region and is not atomic. The prior verified-LittleFS package therefore remains **separate optional offline research**, not a runtime prerequisite. The SHINO dashboard does not mount, initialize, write, provision or format LittleFS or EEPROM from the first-boot application path.

The active `SHINO_BOOT_PROFILE 0` bridge now implements a useful read-only-first experience:

| Component | Where it lives | Operation |
|---|---|---|
| 240 × 240 native CPU/GPU/RAM/temp gauges and stale-state screen | SHINO application program flash + volatile device RAM | GPU fallback and PC-stale indication; no GIF/FS assets |
| Browser administration page, styles and client-side JavaScript | Compile-time `PROGMEM` strings, `GET /` and `GET /ui.js` | Same-origin, HTTP Digest protected, restrictive CSP, no external image/script/font |
| Metrics sample `GET/POST /api/v1/bridge/metrics` | Six bounded numeric values + boolean in RAM | POST requires per-build HTTP Digest, strictly bounded JSON; no firmware/FS route |
| Existing `GET /api/v1/bridge/status`, `GET /api/v1/bridge/fs-plan` | Flash-resident read-only diagnostics | Declares no FS image built, current linked geometry, original FS risk |
| Optional exact official V9.0.44 application-only return | Compiled **only** in separately enabled experimental variant | Default read-only build has no restore POST; OEM ZIP still not full original flash |
| Companion `push_fsless_metrics.py` | Owner's Windows PC only | Explicit per-build credential file and current private AP IP; sends CPU/GPU/RAM data, **not binaries** |

The device runs an **isolated WPA2 AP**, `SHINO-FirstBoot-<chip ID>`, ordinarily at `192.168.4.1`. It does not yet join the home network: Windows must be connected to this AP to deliver live PC stats. If that Wi-Fi connection disconnects Windows from the Internet/home network, Ethernet or a separate network adapter may be useful. This is a known UX limitation, not hidden. Home-Wi-Fi credential pairing via RAM-only STA could be evaluated later, after authentication and leak/failure-mode review; this PR never records those credentials.

Metrics schema matches the existing companion collector: `ok`, `cpu_usage`, `gpu_usage`, `memory_used_gb`, `gpu_vram_mb`, `gpu_temp_c`, `gpu_power`, `gpu_available`. Device validates all required numeric fields, sensible ranges and finite values in a small JSON payload; rejects invalid updates without replacing the last accepted sample. A sample expires after **6 seconds** and the screen/browser show stale/unavailable rather than indefinitely displaying an old measurement. No scene, data, script, configuration or device credential is accepted through this endpoint.

## See the actual new interface on Windows now — no TV needed

From a ZIP of this GitHub branch, double-click **`start-fsless-preview.cmd`**. It installs the existing `psutil` companion dependency if needed, then opens **`http://127.0.0.1:8766/`** after its local server starts.

The localhost-only Python preview extracts the **exact HTML and JavaScript strings from the C++ `PROGMEM` implementation** and supplies your current Windows CPU/RAM and NVIDIA GPU stats through the same GET schema. It marks diagnostic pages as `PC_ONLY_PREVIEW`, refuses all POST requests, never reads private firmware keys and has **no connection to the SmallTV**. This exercises the browser UI, not the device’s physical 240 × 240 display or ESP8266 Wi-Fi stack.

Manual equivalent:

```powershell
py -m pip install -r companion/requirements.txt
py tools/preview_fsless_dashboard.py --port 8766 --open-browser
```

## PC-only commands — no device flash

The software cannot currently connect to an owner's physical TV: it is still running untouched OEM Ultra-V9.0.44 and does **not** provide SHINO routes. Do not run the telemetry sender against `http://192.168.1.70/update` or any factory upload endpoint.

The script supports a safe local sampler test without connecting to a device or reading credentials:

```powershell
py -m pip install -r companion/requirements.txt
py companion/push_fsless_metrics.py --dry-run
```

In a future **separately authorized** physical test, after a reviewed SHINO image is installed and Windows is connected to its private AP, the manual telemetry-only command will be:

```powershell
py companion/push_fsless_metrics.py --host 192.168.4.1 --credentials-file firmware/private/credentials.txt --once
```

This is **not an installation command**. It sends only one short JSON sample to the authenticated RAM telemetry path. Omitting `--once` sends updates approximately every 2 seconds until Ctrl+C. Do not pass passwords on the command line or share the generated private credential file. The ignored credentials file must match the *same exact image build* as the running bridge; GitHub CI intentionally deletes its ephemeral copies, so a future approved installation needs a separate user-private paired build process. The sender refuses public/DNS/loopback/nonliteral hosts, disables ambient HTTP proxies and redirects, and never uses any firmware/FS/erase route.

## Runtime/UI endpoints

- `GET /` — flash-embedded styled dashboard, Digest-protected.
- `GET /ui.js` — embedded JS, Digest-protected, same-origin polling.
- `GET /api/v1/bridge/metrics` — current bounded RAM sample, freshness state and TTL.
- `POST /api/v1/bridge/metrics` — authenticated JSON **RAM update only**, no persistence.
- `GET /api/v1/bridge/status` / `/api/v1/bridge/fs-plan` / `/api/v1/bridge/factory-return` — prior approved diagnostics.
- No `U_FS`, generic `/ota/fw`, generic `/ota/fs`, open `/legacyupdate`, automatic format or LittleFS asset loading in this boot profile.

## Build gate

Default CI now verifies the exact pinned manufacturer application ZIP and inner SHA-256, generates private random WPA2/HTTP secrets with **`SHINO_FS_IMAGE_PRESENT 0`** and **`SHINO_ENABLE_FS_MIGRATION 0`**, and compiles the actual FS-less bridge without building `littlefs.bin` or generating a seed `config.json`. Size is compared with the original 494,144-byte OEM application **only as a conservative software-budget check**, not a measured stock OTA acceptance guarantee.

A second ephemeral workflow compiles the experimental *application-only* OEM-return mode and candidate-locked mini-loader against the actual current bridge binary. Both modes remain tested offline; no binaries or secrets are uploaded as release artifacts and no owner LAN requests occur. Optional `--fs-image` policy pins and the old verified-FS checker are retained solely for isolated future research; they do not enable migration.

Source tests cover protected routes, raw PROGMEM assets, numeric validation, stale-state semantics, no filesystem writes, strict Windows target/credentials, and absence of a required FS build.

### Still unproven

- The proprietary V9.0.44 updater's real available slot and acceptance/boot of our custom application.
- Runtime screen/Wi-Fi/HTTP Digest behavior and the Windows-to-AP PC telemetry exchange on the physical device.
- Preservation of all original manufacturer data by the updater itself: avoiding our app's LittleFS/EEPROM operations greatly reduces one known hazard, but does **not** establish a full owner-specific flash backup or brick-proof path.
- Restoring an original application after a nonbooting app/bootloader, or reconstructing stock assets if they are erased.

**Owner TV untouched; first physical flash remains separately gated by informed, explicit authorization of exact file/action and residual risk.**
