# Initial technical research

## Manufacturer's firmware

https://github.com/GeekMagicClock/smalltv-ultra

The manufacturer repository contains downloadable versioned ZIP update packages and manuals. The latest version observed during project initialization is **Ultra-V9.0.50**. The owner's device reports **Ultra-V9.0.44**; the repository does not list that exact version as a separate top-level package.

The V9.0.46 ZIP was inspected at the archive-directory level and contains a compressed firmware update binary and `md5sum.txt`. Its uncompressed firmware payload is about 501,040 bytes. **An OTA update payload is not necessarily a complete flash image**.

V9.0.50's update notes mention manual/automatic timezone and DST fixes. No urgency to update the stock firmware while the existing unit is operational.

## Open-source baselines

1. **Times-Z/GeekMagic-Open-Firmware**, default branch `develop`, GPL-3.0. Its README reports SmallTV-Ultra support and documents ST7789/SPI pins, display initialization, GPIO5 active-low backlight, and a UART readback workflow with 16 × 0x40000-byte chunks (4 MiB). Validate on this device before executing.
2. **giovi321/smalltv-mod**, default branch `main`. Its README explicitly identifies the Ultra's stock OTA/partition restriction and a two-stage loader installation path; this is a *risk to assess*, not an instruction to flash now. Contains ideas for dynamic content pushed over LAN.
3. **aydarik/geekmagic-tv-esp8266**, default branch `dev`, MIT. README reports testing on SmallTV-Ultra, serial first flash, HTTP routes for metrics, notifications and images.

Sources:
- https://github.com/Times-Z/GeekMagic-Open-Firmware
- https://github.com/Times-Z/GeekMagic-Open-Firmware/blob/develop/backup/readme.md
- https://github.com/giovi321/smalltv-mod
- https://github.com/aydarik/geekmagic-tv-esp8266

## Decision register

- **D-001** Research first, no flash operations until backup/recovery gate.
- **D-002** PC companion owns integrations and sensitive credentials; ESP8266 handles lightweight local drawing.
- **D-003** Do not vendor/copy upstream source until license obligations and actual hardware compatibility are reviewed.
- **D-004** Factory read-only API observations are version-specific; route names not yet probed on the owner's hardware must not be stated as verified.

## Open questions

- Board revision and flash chip marking? Can a complete readback be taken with a 3.3 V adapter?
- Can the factory V9.0.44 image be found from an official source or by readback?
- Which memory layout, web resources and recovery partition(s) actually exist on this unit?
- What scene rendering strategy fits available RAM and refresh goals without flash wear?
- What minimum device security is feasible on an ESP8266 within an isolated home LAN?
