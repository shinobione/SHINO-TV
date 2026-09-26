# SHINO Wi-Fi Recovery Loader (ESP8266 Ultra prototype)

**STATUS: SOURCE-ONLY PROTOTYPE. NO FLASH, NO OWNER HARDWARE VALIDATION, NO AUTOMATIC DEPLOYMENT.**

This is a **small intermediate application**, built separately from `firmware/`, modelled on the documented ESP8266 SmallTV-Ultra two-stage OTA approach. It is NOT a persistent bootloader: its subsequent OTA replacement will overwrite it. It cannot recover a unit if the intermediate loader itself no longer boots, and cannot guarantee a return to the original filesystem/settings/flash layout.

## Explicit security and failure gates

- Defaults to **read-only**, with zero upload routes compiled. A locally generated policy header is mandatory even for a build; **no compiled-in public/default passwords** exist.
- Creates only a private WPA2 Wi-Fi AP `SHINO-Recovery-<chip-id>`. No use of owner's Wi-Fi credentials, no fallback open AP. AP password random per build, >= 12 chars.
- Authenticates GET and POST routes using ESP8266WebServer's **HTTP Digest** challenge, with a separate random >= 20-character HTTP password.
- An *experimental* build can compile authenticated browser upload forms `GET /install` and `GET /restore`, backed by `POST /install` for exactly one pinned SHINO candidate and `POST /restore` for exactly the official OEM V9.0.44 application image. Bytes/MD5 are compiled into a per-build private policy, not accepted as untrusted client-supplied checksums.
- Uses ESP8266 `Update.begin(expected,U_FLASH)`, `Update.setMD5(expected)`, exact upload byte count and `Update.end(false)`: the core verifies digest **before scheduling** its eboot copy command. An invalid/aborted upload must not switch to it.
- Checks actual flash capacity is 4 MiB on experimental writes. Does not accept filesystem uploads or arbitrary firmware.
- No OTA binaries, generated credentials or private files are ever published in GitHub Actions. Their generated paths are gitignored.

The upload form is served with a restrictive Content Security Policy; it is not exposed by the read-only build. The MD5 check here is a streaming ESP8266 Updater compatibility control, **not a substitute for pinned SHA-256 verification on the trusted PC**. This is a local WPA2/Digest constrained maintenance route, not a secure-boot or hardware root-of-trust system. Wi-Fi disconnects and power interruptions at various stages require physical testing, and cannot be shown to be safe by CI.

## Build offline (still no device action)

The required official OTA archive is linked and SHA-256 pinned in [recovery](../recovery/README.md). Obtain that ZIP from the **historical pinned official GitHub commit**, not a random firmware download.

From the project root, with Python and PlatformIO available:

```powershell
py tools/verify_factory_ota.py --manifest recovery/factory_ota_v9_0_44.json "C:\\LocalRecovery\\FW-Smalltv-Ultra-V9.0.44.zip"
py tools/make_loader_policy.py --official-zip "C:\\LocalRecovery\\FW-Smalltv-Ultra-V9.0.44.zip"
cd recovery_loader
pio run -e esp12e_recovery
```

These steps create local ignored `recovery_loader/include/local_policy.h` and `recovery_loader/private/credentials.txt`. Keep both **private**, never copy them into GitHub or chat. The generated loader is **READ-ONLY**; it cannot accept OTA. The commands above do **not** upload it.

An experimental upload-capable firmware build can be generated with `--candidate-bin` pointing to the actual selected, independently verified SHINO application and `--enable-writes`. This flag is for a future supervised lab deployment only; do **not** use it on the owner's unit or treat its compilation as hardware approval. An independent end-to-end exercise on a compatible expendable board must verify: (1) factory Ultra initial OTA acceptance, (2) protected AP/HTTP access, (3) candidate stage/install, (4) original v9.0.44 stage/restore, (5) recovery after interrupted/rejected uploads, and (6) flash layout, data and update compatibility. Any failure leaves physical installation **NO-GO**.

## Relevant code source

- [Independent community smalltv-mod two-stage ESP8266 Ultra installer](https://github.com/giovi321/smalltv-mod/blob/main/docs/src/content/docs/getting-started/flashing.md) and its `src/loader.cpp`. The SHINO source implements its own policy rather than copying the open unauthenticated AP.
- [Arduino ESP8266 Updater.cpp](https://github.com/esp8266/Arduino/blob/master/cores/esp8266/Updater.cpp) (the MD5 check precedes writing eboot copy command).
- Manufacturer's historical exact [V9.0.44 OTA package](https://github.com/GeekMagicClock/smalltv-ultra/blob/55d7877fcba8b1cb7a66a0830d35d5b374bc8540/Ultra-V9.0.44/FW-Smalltv-Ultra-V9.0.44.zip).

## What this does NOT solve

| Failure | Can this transient loader fix it? |
|---|---|
| Wrong image/size sent to working experimental loader | Rejects it before activation if password/checksum and size controls work as intended; runtime still untested. |
| SHINO app installed successfully but no longer starts | **No guarantee.** The trampoline is overwritten by the final OTA, so its AP is absent. |
| Transient loader fails to boot | **No.** It cannot receive a Wi-Fi restore request. |
| OEM app restored but expected original filesystem/settings invalid | Unknown. OEM OTA is not a full 4-MiB flash image; end-to-end test mandatory. |
| Device has no UART/physical recovery available | Wi-Fi-only method carries residual permanent failure risk. |

**Do not advertise a firmware package as brick-proof.** We are still pursuing a no-solder option, not bypassing physics.
