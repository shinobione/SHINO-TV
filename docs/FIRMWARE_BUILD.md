# SHINO // TV — Firmware baseline build

## Scope

This phase imports an **exact, pinned copy** of Times-Z's SmallTV-Ultra-compatible ESP8266 source under `firmware/` (see `firmware/UPSTREAM.md` and the source manifest). It builds the firmware and LittleFS locally or in GitHub Actions, **without uploading either image**. The owner unit still runs factory Ultra-V9.0.44.

## Requirements

- Python and PlatformIO (`python -m pip install 'platformio>=6.1,<7'`).
- An ESP8266 PlatformIO toolchain, acquired by PlatformIO during the first build.
- No connection to the TV is required.

## Source build

From the repository root, for a disposable local test only:

```powershell
python -m pip install "platformio>=6.1,<7"
Copy-Item firmware/data/config-smartTV.example firmware/data/config.json
cd firmware
pio run -e esp12e
pio run -e esp12e -t buildfs
```

Use **blank/example-only** Wi-Fi information; do not commit `firmware/data/config.json`. The build outputs are `firmware/.pio/build/esp12e/firmware.bin` and `littlefs.bin`.

The upstream optional PC metrics mode is compiled by setting a `METRICS_URL` build flag pointing at `http://YOUR_PC_LAN_IPV4:8765/metrics`; its default empty value leaves the feature disabled. See `companion/README.md`. The factory firmware cannot use this new mode without replacement.

## Safety and provenance

- Import pinned at upstream `a0c2ddcef4e76fa6eb040f6f544124763a2d85f5`. 56 imported Git blobs were compared by their exact SHA; all matched upstream.
- The upstream code is licensed GPL-3.0-or-later and its license/notices are preserved.
- We excluded historical full factory dumps and bulky demo media, not core source files.
- A successful compiler and LittleFS build is **not** physical-device validation, an OTA size guarantee, or a recovery proof.
- **Do not flash** before a complete readback of the owner's own V9.0.44 unit, a verified hash, an off-device copy and a reviewed 3.3 V UART restoration procedure.
- Review fixed factory AP credentials and unauthenticated rescue-mode write endpoints before enabling physical deployment.

## CI

`.github/workflows/firmware-build.yml` runs an offline source build and filesystem build, creates a throwaway config without real secrets, and publishes only binary sizes to the step summary. It neither uploads binaries as release assets nor writes to any physical device.
