# SHINO // TV — Owner-unit full-flash backup gate

> **ARCHIVAL / BREAK-GLASS ONLY (owner instruction 2026-09-27):** The owner's normal project workflow is **Wi-Fi only**, because USB-C is power-only. Do not suggest PCB access, soldering, test pads, USB-UART, pogo pins, hardware purchases or readback as a routine SHINO update precondition. This historical serial recovery plan may be revisited **only after an actual brick/nonbooting event and a fresh explicit owner request**. See `docs/V21_OWNER_INSTALLATION_DECISION.md`. This section does not authorize any physical action.

**Status:** preparation only. No physical access, board identification, ROM entry, backup, or restore has occurred. **Do not perform these steps until the actual PCB's serial/power/pad wiring has been identified from photos and reviewed.** The target is the owner's current **SmallTV-Ultra / Ultra-V9.0.44**, not a generic ESP8266 devboard.

## 0. Hardware evidence needed (no disassembly instructions yet)

- Clear exterior images of the device (front, back, connector/label) and, once safely opened by the owner, sharp photographs of *both sides* of the PCB showing module, flash chip marking and labelled pads.
- Which USB-UART adapter is available? Confirm its actual UART IO voltage is 3.3 V (some adapters' 3.3 V pin does not imply 3.3 V TX output).
- Confirm whether original device USB power and UART power could be simultaneously connected; **never power the board from two supplies without an explicitly reviewed wiring scheme**.
- Identify physical GND, board TX/RX, GPIO0/BOOT, EN/RST, power rails with independent evidence before connecting anything. Do **not** presume the LCD pinout is the UART header pinout.
- Confirm detected flash capacity on owner hardware before specifying any read length.

## 1. Electronics constraints

ESP8266 ROM UART accepts **3.3 V logic**, not RS-232 nor 5 V TTL. UART connections are crossed (device TX → adapter RX; device RX → adapter TX) plus common GND. Its bootloader mode is selected by GPIO0 low **at reset**; GPIO2 is a boot strap pin and, according to Espressif, can output UART TX in download mode. Protect this existing LCD wiring and do not improvise a connection.

All the above is a *conditional future* action to be tailored once the owner supplies PCB photos. See Espressif's:
- https://docs.espressif.com/projects/esptool/en/latest/esp8266/esptool/serial-connection.html
- https://docs.espressif.com/projects/esptool/en/latest/esp8266/advanced-topics/boot-mode-selection.html

## 2. Before connecting to ROM

1. Confirm boot pad and ground mapping, solder/contact integrity and isolation from 5 V TX.
2. Record current web-reported firmware `Ultra-V9.0.44` and a rough current UI inventory (do not publicly share credentials).
3. Install latest compatible esptool on Windows only when the physical connection is ready: `py -m pip install "esptool>=5,<6"`. Verify CLI help. **Do not run erase or write commands.**
4. Set the observed COM port in commands below, for example `COM7` (placeholder, not assumed).
5. Confirm the interface is stable in ROM bootloader mode. Serial probing/backup can reset the unit and esptool normally loads a RAM-resident stub; this is not a promise of zero operational side effects, but the listed commands perform **no flash erase/write**.

## 3. Owner-operated read-only flash identification (only after step 0 review)

```powershell
py -m esptool --chip esp8266 --port COM7 --baud 115200 flash-id
```

Compare the reported manufacturer/device ID and flash size with the PCB markings. Our **working hypothesis** is 4 MiB (`0x400000` bytes), based on the compatible community board, not a measurement on this owner unit. **Stop** if the detected chip/size is unclear or differs.

## 4. Two independent full reads (no flash-writing commands)

The current Espressif esptool supports `read-flash 0 ALL output.bin`, where `ALL` requests size autodetection. The 115200 speed is intentional for initial wiring reliability. Work in a private, local, non-synchronised backup folder *outside the Git working tree*.

```powershell
py -m esptool --chip esp8266 --port COM7 --baud 115200 read-flash 0 ALL v9_0_44_read_A.bin
py -m esptool --chip esp8266 --port COM7 --baud 115200 read-flash 0 ALL v9_0_44_read_B.bin
```

If either read is truncated/errors, stop and fix the connection; never stitch arbitrary incomplete fragments together or rely on a vendor OTA update ZIP as a substitute. The source Times-Z historical 9.0.40 backup belongs to **its author's unit** and is not owner-unit recovery material.

## 5. Verify independently *before* preserving recovery claim

Run from the SHINO-TV repository root with Python:

```powershell
py tools/verify_flash_backup.py "FULL_PRIVATE_PATH_TO/v9_0_44_read_A.bin" "FULL_PRIVATE_PATH_TO/v9_0_44_read_B.bin" --expected-bytes 4194304
```

This verifier only **reads** local files. It requires correct size, identical SHA-256 and byte equality, and a plausible ESP8266 image header at offset 0; it refuses homogeneous or differing dumps. A matching pair is necessary, not by itself proof of future restoration; compare capacity and preserve independent evidence.

Store an offline duplicate in encrypted/private storage, with SHA-256 values and a record of the esptool version, actual chip/flash ID, exact read command, observed COM port, board revision, and any UART/voltage observations. **Never push flash dumps to GitHub**, attach them publicly or post screenshots that reveal home Wi-Fi credentials/API tokens. A full flash dump can contain secrets even if the firmware claims obfuscation.

## 6. Go/no-go

- [ ] PCB, 3.3 V UART, GPIO0/GND and safe power scheme visually identified.
- [ ] Flash ID and real size confirmed from owner's unit.
- [ ] Two complete independent reads finished without transport error.
- [ ] Backup verifier confirms exact size, matching hashes and byte identity.
- [ ] Offline encrypted/private copy retained; archive/hash manifest recorded.
- [ ] Separate proposed restoration procedure reviewed (including wiring, image offset, and chip flash-mode caveats).
- [ ] Upstream default AP credentials, rescue API and unauthenticated updater risks remediated and code reviewed.
- [ ] Owner gives **new explicit authorization** for a named build and action before *any* flash write.

**No automatic restore or flash command is included in this document.** A working backup and a compiled firmware are not sufficient to authorize hardware changes.

## Evidence sources

- [Espressif: basic commands, read-flash and flash-id](https://docs.espressif.com/projects/esptool/en/latest/esp8266/esptool/basic-commands.html)
- [Espressif: UART connections / 3.3 V logic](https://docs.espressif.com/projects/esptool/en/latest/esp8266/esptool/serial-connection.html)
- [Espressif: boot mode selection](https://docs.espressif.com/projects/esptool/en/latest/esp8266/advanced-topics/boot-mode-selection.html)
- [Times-Z: original backup readme](https://github.com/Times-Z/GeekMagic-Open-Firmware/blob/a0c2ddcef4e76fa6eb040f6f544124763a2d85f5/backup/readme.md) (requires board-specific verification)

## Historical official matching OTA image located (correction, 2026-09-26)

**Important correction:** the official GeekMagic repository's current `main` directory list does NOT show Ultra-V9.0.44, but **Git history retains the exact package** at historical commit `55d7877fcba8b1cb7a66a0830d35d5b374bc8540`:

- [Official V9.0.44 ZIP at pinned commit](https://github.com/GeekMagicClock/smalltv-ultra/blob/55d7877fcba8b1cb7a66a0830d35d5b374bc8540/Ultra-V9.0.44/FW-Smalltv-Ultra-V9.0.44.zip), Git blob `a829d48766cbd2f4f62656523cc9646ba67017d3`, 349,377 ZIP bytes as reported by Git tree.
- [Official V9.0.44 changelog at the same commit](https://github.com/GeekMagicClock/smalltv-ultra/blob/55d7877fcba8b1cb7a66a0830d35d5b374bc8540/Ultra-V9.0.44/update_history.txt).
- Version removed from present-day `main` listing, **not unavailable in historical source control**. Earlier documentation stating the exact package could not be found is superseded by this correction.

This is the **matching OTA application update** for the owner-reported firmware `Ultra-V9.0.44`, NOT a confirmed 4 MiB owner-specific full-flash backup. It can be investigated as a potential **Wi-Fi rollback package only while a compatible updater remains accessible and accepting that image**. It does not restore factory files, settings, flash partitions or boot/recovery access by itself and does not save a device whose loader fails to boot. Before any live use, inspect the archived ZIP/inner image, identify required unpacking/upload method, verify checksum and test rollback with a separately owned compatible test unit or other acceptable recovery assurance. **No uploads performed.**

An independent project [smalltv-mod](https://github.com/giovi321/smalltv-mod) documents a two-hop SmallTV-Ultra install: ~316 KiB minimal loader accepted by stock limited OTA slot, then a larger final firmware via the loader's own Wi-Fi update page. That documented path does not yet prove a reversible SHINO-TV installation on the owner's board and the public loader creates an unprotected Wi-Fi AP/update endpoint; SHINO integration needs explicit security and cross-layout assessment first.
