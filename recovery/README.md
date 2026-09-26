# SHINO // TV — Pinned factory return reference (Ultra-V9.0.44)

**Status: offline recovery asset validated. Hardware rollback NOT tested. First physical flash remains blocked.**

This folder does **not** contain any manufacturer's firmware bytes. Instead it records their precise, verifiable official source and the SHA-256 of both the original archived update and its application image. This avoids redistributing an OEM proprietary application binary inside GPL-derived firmware or GitHub artifacts.

## Source and exact identity

Original official archive:
[FW-Smalltv-Ultra-V9.0.44.zip at the preserved manufacturer's commit](https://github.com/GeekMagicClock/smalltv-ultra/blob/55d7877fcba8b1cb7a66a0830d35d5b374bc8540/Ultra-V9.0.44/FW-Smalltv-Ultra-V9.0.44.zip).

- Source Git commit: `55d7877fcba8b1cb7a66a0830d35d5b374bc8540`
- ZIP Git blob: `a829d48766cbd2f4f62656523cc9646ba67017d3`
- ZIP size: **349,377 bytes**
- ZIP SHA-256: `cfbef50754ec552f9791878931c5f3643734de15f3c81cebdecf7ce05b28230f`
- Inside ZIP: `FW-Smalltv-Ultra-V9.0.44.bin`, **494,144 bytes**
- Inner BIN SHA-256: `a6421f5bfee7860d97bed26620c346b8008f503e513702d4bfdf6e01010a7718`
- Plausible ESP8266 app header `0xE9`, **2 segments**.
- All values obtained by pinned manufacturer Git checkout and read-only inspection on an ephemeral GitHub Actions runner.

The hashes and file properties are checked strictly against `factory_ota_v9_0_44.json`. A wrong manufacturer revision, changed archive, corrupted ZIP, unexpected member or malformed header fails CI. Independent tests use **synthetic locally constructed** ZIP/BIN data only.

## Why the OEM image is not embedded in our test firmware

1. The manufacturer distributes it as an application OTA update, **not** as the 4-MiB owner-specific original flash. It cannot by itself restore all settings/files/flash layout.
2. Placing a ~494-KB duplicate in the SHINO application increases the flash budget and leaves no way to run the restore if the bootloader/loader/firmware fails to start.
3. The OEM ZIP must not be silently redistributed as if it were part of the GPL-licensed Times-Z-derived project; an original-source link plus locally verified user-provided copy is the appropriate approach.
4. A rollback from an *alternative* flash layout back to OEM still needs a running updater compatible with its 494-KB app image. An image's correct SHA is **not** an OTA compatibility test.

The recovery design is therefore a **dedicated minimal, authenticated recovery/update environment** plus a local copy of the manufacturer application image, rather than placing the whole binary inside the on-device SHINO app. A protected transient mini-loader and exact-OEM-only return handler in SHINO and its boot-loop Rescue mode are implemented as offline source prototypes in stacked PRs #7 and #9, but **no image has been deployed or validated on the owner's TV**. The app loader is overwritten by the final firmware, not a persistent independent recovery environment.

## Preparing the reference locally — NO device contact

Download the official ZIP from the historical link above to a folder outside SHINO-TV. From the SHINO-TV repository root, run, changing the local file paths:

```powershell
py tools/verify_factory_ota.py --manifest recovery/factory_ota_v9_0_44.json "C:\\LocalRecovery\\FW-Smalltv-Ultra-V9.0.44.zip"
py tools/prepare_factory_rollback.py "C:\\LocalRecovery\\FW-Smalltv-Ultra-V9.0.44.zip" --out "C:\\LocalRecovery\\FW-Smalltv-Ultra-V9.0.44-VERIFIED.bin"
```

The tool refuses a checksum mismatch and existing output, then extracts one byte-for-byte verified local BIN. It performs **no Wi-Fi, UART, OTA or flash operations**. Keep both files privately outside Git.

## Mandatory software gates

- The dedicated factory reference CI job checks the official archived ZIP **from the exact historical commit**, verifies original Git blob SHA, outer ZIP SHA-256, inner image SHA-256 and header. It publishes **metadata only**.
- Every offline ESP8266 build workflow depends on that reference job; if the official rollback reference is absent or changed, firmware compilation is blocked.
- Static/synthetic unit tests cover mismatch and unsafe archive rejection and safe local extraction.
- CI must **never** upload manufacturer binaries, add them to the firmware image, publish them as release assets or POST them to an actual device.
- CI success means the factory application image is identified and intact — **not** that Wi-Fi restoration works on the owner's PCB.

## Physical failure matrix (still unresolved)

| State of TV after experimental action | Is Wi-Fi OEM rollback available? | Required proof |
|---|---|---|
| SHINO runs and its authenticated OTA route works | Potentially, if original image accepted under installed flash layout | Full OTA-to-OEM test on a separate compatible unit |
| Dedicated SHINO recovery loader runs but SHINO app fails | Potentially, if loader AP/update remains active and original image is layout-compatible | Recovery-loader-to-OEM full test |
| Loader does not boot / flash image invalid / power lost at wrong moment | **No software-only guarantee** | Hardware recovery or proven hardware-independent fallback absent |
| Only OEM `/update` currently accessible in V9.0.44 | Accepts manufacturer upgrades and potentially the small third-party trampoline | Does not enable whole-chip flash readback; first experiment still has risk |

## Release decision

Do not mark a firmware build as *safe to flash* until the mini-loader security, stock slot, image layout/OTA size, independent restoration test, and the **owner's explicit go/no-go** have been reviewed. As the owner does not want soldering and USB-C shows no serial interface, a zero-brick-risk claim is not technically supportable today. Keep the current working V9.0.44 in place pending that decision.

Related: [RECOVERY_PROTOCOL.md](../docs/RECOVERY_PROTOCOL.md), [SECURITY_AUDIT_01.md](../docs/SECURITY_AUDIT_01.md), [smalltv-mod's Ultra two-stage OTA design](https://github.com/giovi321/smalltv-mod/blob/main/docs/src/content/docs/getting-started/flashing.md).
