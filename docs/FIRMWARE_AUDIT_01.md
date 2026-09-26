# Firmware audit 01 — source-backed layout and recovery assessment

Status: **preliminary/documentary review**, 2026-09-26. The owner's reported firmware is **Ultra-V9.0.44**, and we do not have its full flash image. No device was contacted, reflashed, or physically inspected in this review.

## Verified from owner-provided read-only observations

| Route | Reply at the time sampled | Meaning |
|---|---|---|
| `GET /v.json` | `{"m":"SmallTV-Ultra","v":"Ultra-V9.0.44"}` | Model and firmware reported by running device |
| `GET /app.json` | `{"theme":5}` | Reported active theme ID |
| `GET /space.json` | `{"total":3121152,"free":269836}` | Filesystem figure at sample time, before the owner's cleanup |

The owner later observed **1063 KB free in the UI** after removing images/GIFs. This difference is expected from changes between the two measurements; do not report it as a disagreement between API and UI. One weather GIF remained in `/gif`: `80x80-planet-2.gif` (~31 KB).

## Manufacturer package inventory

Source: https://github.com/GeekMagicClock/smalltv-ultra

Top-level packages available in repo include V9.0.24, V9.0.26, V9.0.31, V9.0.40, V9.0.46, V9.0.50. **V9.0.44 is mentioned in change logs but not separately packaged at repository root.**

The V9.0.46 ZIP archive central directory reports:
- `FW-Smalltv-Ultra-V9.0.46.bin`: 501,040 bytes after decompression (360,077 compressed).
- `md5sum.txt`: 76 bytes (67 compressed).

This is an **update package**, not evidence of a complete 4 MiB flash backup. Do not conflate its `.bin` length with the physical flash size. Any actual binary header, embedded URL/string extraction, disassembly or firmware filesystem extraction remains **pending local acquisition and analysis**.

Manufacturer notes document that V9.0.46 fixes the unavailable web console in V9.0.45. V9.0.48 adds an OpenWeather time fallback; V9.0.50 adds timezone mode and DST correction. No reason to update a working V9.0.44 merely for this research.

## ESP8266 hardware / flash cross-check from community sources

- Times-Z/GeekMagic-Open-Firmware's `develop` README reports SmallTV-Ultra compatibility, ESP8266, ST7789 RGB565 240×240, SPI Mode 3, MOSI GPIO13, SCK GPIO14, D/C GPIO0, reset GPIO2, active-low backlight GPIO5; CS permanently grounded. These are **documented community observations**, not yet independently verified on the owner's board.
- The Times-Z `backup/backup.sh` reads 16 chunks × `0x40000` bytes = `0x400000` bytes (4 MiB), and includes a separate historical V9.0.40 factory backup from that developer's own unit. It is **not** a replacement for a full backup of the owner's V9.0.44.
- giovi321/smalltv-mod explicitly documents that the stock SmallTV-Ultra partition/OTA arrangement reserves a large image/GIF data region; the normal alternative image can produce `ERROR[4]: Not Enough Space` in its small stock update slot. It describes a two-stage temporary loader, but that is a **write operation**, and it does not satisfy our backup-first requirement. No reason to try it during research.
- The giovi321 `partitions/smalltv_4mb_ota.csv` describes **ESP32-C2**, *not* the ESP8266 SmallTV-Ultra. It MUST NOT be copied into our device's configuration.

References:
- https://github.com/Times-Z/GeekMagic-Open-Firmware/blob/develop/readme.md
- https://github.com/Times-Z/GeekMagic-Open-Firmware/blob/develop/backup/readme.md
- https://github.com/Times-Z/GeekMagic-Open-Firmware/blob/develop/backup/backup.sh
- https://github.com/giovi321/smalltv-mod/blob/main/docs/src/content/docs/getting-started/flashing.md
- https://github.com/giovi321/smalltv-mod/blob/main/partitions/smalltv_4mb_ota.csv
- https://github.com/GeekMagicClock/smalltv-ultra/blob/main/Ultra-V9.0.50/update_history.txt

## Assessment

1. A static/factory update package inspection alone cannot guarantee stock recovery, because settings, filesystem, boot/flash map and other regions may be absent.
2. A full **owner-unit** readback with device identity, size and SHA-256 digest must precede replacement. Preserve it privately/off Git.
3. Actual recovery requires verifying serial access/pad markings, 3.3 V TTL levels, stable power and a complete readback. Never connect 5 V TTL logic to ESP GPIO.
4. Focus feature development initially on a simulated display and PC companion, which can be tested without any risky firmware upload.
5. Before firmware selection, evaluate its license, memory footprint and ESP8266-specific OTA layout. No unreviewed manufacturer binary redistribution.

## Next audit actions

- [ ] Obtain manufacturer ZIP files as local research artifacts; verify published MD5 and record independent SHA-256 digests.
- [ ] Inspect ESP image headers and segments, printable strings, library signatures, web asset format and possible filesystem organization; record offsets with reproducible scripts.
- [ ] Compare V9.0.40/46/50 and, only if the owner authorizes a hardware readback, V9.0.44.
- [ ] Separate *read-only confirmed* routes from unverified/community routes and all endpoints with write side effects.
- [ ] Photograph board pad markings and ascertain a safe 3.3 V USB-UART connection and COM port.
- [ ] Run full owner-unit readback and independently validate the backup before even contemplating any flash write.

**Gate remains closed:** documentation-only phase. No upgrade/loader/erase/write-flash operation approved.

## Static analysis of released ZIP payloads (update after initial review)

The V9.0.40, V9.0.46 and V9.0.50 archives were decoded from the manufacturer GitHub repository, ZIP members DEFLATE-decompressed in memory, and the first ESP8266 headers and visible printable strings inspected **without contacting or modifying the owner's SmallTV**.

| Version | BIN bytes | ESP header | Segments declared | Mode | Entrypoint | ZIP CRC32 of BIN |
|---|---:|---|---:|---|---|---|
| 9.0.40 | 510,496 | 0xE9 | 2 | DIO | 0x4010f480 | 7af5814d |
| 9.0.46 | 501,040 | 0xE9 | 2 | DIO | 0x4010f480 | 29428c9b |
| 9.0.50 | 505,200 | 0xE9 | 2 | DIO | 0x4010f480 | 06da984d |

All three begin with a segment loaded at 0x4010f000 (3,424 bytes), followed by a segment at 0x3fff20b8 (40 bytes). Additional image data follows these headers; it is **not** necessarily free space or an error. Full ESP8266 image map / SDK-specific tail interpretation remains pending.

### Extracted representative strings

- Common themes/config references: `/theme_list.json`, `/album.json`, `/brt.json`, `/gif.json`, `/app.json`, `/dst.json`, `/config.json`, `/ntp.json`, `/space.json`, `/doUpload`, and `/image/boot.gif`.
- V9.0.40 includes `/timecolor2.json`, visible WeatherAPI and OpenWeather URLs.
- V9.0.46 includes `/rotation.json`, `/wifi.json`, `/image.html`, and an Open-Meteo API URL.
- V9.0.50 includes `/tz.json`, `/rotation.json`, `/wifi.json`, and an Open-Meteo API URL.
- ZIP `md5sum.txt` contains an expected MD5 for V9.0.46 and V9.0.50; no separate MD5 member was present in V9.0.40 archive.

**Caveat:** strings inside firmware are candidate route names or resources, *not* proof that they are remotely callable on the owner's V9.0.44, nor that GET is read-only for every route. Avoid blind endpoint scanning or parameter guessing.

Official source archives:
- https://github.com/GeekMagicClock/smalltv-ultra/tree/main/Ultra-V9.0.40
- https://github.com/GeekMagicClock/smalltv-ultra/tree/main/Ultra-V9.0.46
- https://github.com/GeekMagicClock/smalltv-ultra/tree/main/Ultra-V9.0.50

A reproducible offline Python inspector and tests are being added under `tools/`. Its ESP8266 header parser is deliberately conservative, and must not be used to assert measured flash capacity or a recoverable full backup.
