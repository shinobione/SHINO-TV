# Mission 9 — SHINO Flash Layout Liberation

> **Current owner evidence, 7 October 2026:** the exact411152 B mount-stack
> successor is now owner-reported installed; dedicated profile2 physical/resource
> gates **PASS**. Both normal-profile gates **NOT_RUN**. See the
> [owner-supplied acceptance](M09_SUCCESSOR_PHYSICAL_ACCEPTANCE.md) and
> [offline normal-readiness design](M09_NORMAL_PROFILE_READINESS.md).
> The dated receipt below retains its original results as historical evidence;
> recording this update performed no device operations and grants no authority.

**Phase B continuation, 5 October:** [first physical migration design](M09_FIRST_PHYSICAL_MIGRATION.md)
selects application-only FS-less activation before separately gated future FS
provisioning. The Phase A architecture and historical evidence below remain
unchanged. Physical write HOLD; no device contacts/writes in Phase B.

**Date:** 2026-10-05  
**Status:** Phase A / OFFLINE ARCHITECTURE QUALIFICATION  
**Physical device writes:** **0 — NOT AUTHORIZED by this mission state**  
**Source baseline:** `codex/shino-tv-p1-home-lan@a9c5627375c867d399df991f161757efc390df50`

## Decision

The owner approved SHINO // TV moving toward the standard ESP8266 **4m2m**
layout as its target native flash architecture:

- about 1 MiB maximum application space;
- enough pre-filesystem space for a second sector-rounded application during
  Arduino ESP8266 `U_FLASH` OTA staging;
- **2,072,576 bytes** of SHINO LittleFS;
- **24,576 bytes** after `FS_end` retained for the standard ESP8266
  end-of-flash geometry.

Mission 9 deliberately begins with an **opt-in compile-only environment**.
The deployed/default `esp12e` environment remains on `eagle.flash.4m3m.ld`.
The new `esp12e_m9_4m2m` environment is not an upload authorization.

## New target map

Pinned Arduino ESP8266 Core 3.1.2
(`platformio/framework-arduinoespressif8266@3.30102.0`) provides
`eagle.flash.4m2m.ld` with these exact boundaries:

| Region | Physical offsets | Bytes |
| --- | ---: | ---: |
| Application + OTA staging arena | `0x000000..0x1FFFFF` | 2,097,152 |
| SHINO LittleFS | `0x200000..0x3F9FFF` | 2,072,576 |
| Post-FS reserved geometry | `0x3FA000..0x3FFFFF` | 24,576 |
| Total physical flash | `0x000000..0x3FFFFF` | 4,194,304 |

The linker advertises a maximum sketch of **1,044,464 bytes**
(`0xFEFF0`, about 1019 KiB). Sector-rounded, that is `0xFF000`.

The standard Core `Updater.cpp` stages a `U_FLASH` image immediately below
`FS_start`, after rounding the new image to 4096-byte sectors, and rejects the
update if that staging start overlaps the sector-rounded current sketch.

For a worst-case linkable application updating to another worst-case linkable
application:

```
current rounded     = 0x0FF000
new image rounded   = 0x0FF000
FS_start            = 0x200000

staging start       = 0x101000
gap after current   = 0x002000 = 8192 bytes
```

So the pinned standard 4m2m geometry preserves a **two-sector geometric gap**
even for max-linker-size → max-linker-size staging. This is an arithmetic/source
property, not a physical OTA qualification.

## Owner-unit evidence that changed the decision

The private owner-unit serial investigation established:

- ESP8266EX on a detected **4 MiB** flash;
- ROM UART download mode works;
- two independent full-chip reads of exactly **4,194,304 bytes** matched
  bit-for-bit;
- the private MASTER SHA-256 is retained by the owner and **must not be
  committed to Git** as a binary;
- the physical stock-style LittleFS begins at `0x100000` and extends to
  `0x3FA000`, matching the historical 4m3m fingerprint;
- the currently installed P1 application length is **464,544 bytes**
  (`0x716A0`), consistent with the retained installation record;
- an exact second copy of the sector-rounded current application is present in
  the pre-filesystem region, consistent with ESP8266 staging/copy behavior.
  This is **not** treated as proof of fixed A/B partitions.

The private dump may contain owner data, Wi-Fi/configuration state and personal
assets. **Never upload or commit the 4 MiB dump.**

## Migration consequence

The target 4m2m filesystem starts at `0x200000`, while the current owner-unit
filesystem starts at `0x100000`.

Therefore Mission 9 intentionally reclaims:

```
0x100000..0x1FFFFF
```

from the old GeekMagic filesystem for application/OTA use.

A future physical 4m3m → 4m2m migration is therefore a **layout migration**, not
a harmless linker toggle. After migration, restoring only the manufacturer's
application BIN is not a complete factory restore. The recovery authority is
the owner's independently verified **full 4 MiB UART MASTER**.

## Phase A implementation

This branch adds:

1. `[env:esp12e_m9_4m2m]`, extending the exact existing `esp12e` graph and
   changing only `board_build.ldscript` to `eagle.flash.4m2m.ld`.
2. `tools/m9_flash_layout.py`, an offline-only geometry auditor.
3. Unit tests that pin:
   - exact 4m2m FS/reserved boundaries;
   - the linker maximum;
   - P1 → max-linker staging geometry;
   - max-linker → max-linker staging geometry;
   - preservation of 4m3m as the default environment.

The tool explicitly reports `device_contacts=0` and `device_writes=0`.

Run locally:

```powershell
python tools/m9_flash_layout.py
python -m unittest discover -s tools -p 'test_m9_flash_layout.py' -v
pio run -d firmware -e esp12e_m9_4m2m
```

The final PlatformIO command is a **compile only** operation unless the user
separately supplies an upload command. Do not add `upload`, `erase`,
`uploadfs`, `esptool write-flash`, or a device port during Phase A.

## Gates before any physical migration

Mission 9 remains **HOLD FOR PHYSICAL WRITE** until all of the following are
recorded against one exact candidate SHA:

- [ ] 4m2m application compiles from the exact retained source graph.
- [ ] BIN size and linked flash/DRAM usage are recorded.
- [ ] `esptool image-info` / ESP8266 image structure passes offline.
- [ ] The candidate stays below the pinned 1,044,464-byte linker ceiling.
- [ ] Current → candidate and candidate → same-size/larger update staging are
      calculated with sector rounding and retain an explicit safety margin.
- [ ] Normal SHINO boot no longer depends on the old `0x100000` filesystem.
- [ ] A fresh SHINO LittleFS provisioning design exists for
      `0x200000..0x3F9FFF`; no implicit auto-format of owner data is permitted.
- [ ] Power-loss behavior for the first migration is reviewed.
- [ ] A byte-exact UART restore procedure for the private 4 MiB MASTER is
      written and reviewed without committing the dump.
- [ ] The owner separately approves one exact physical migration action and
      exact image/hash.

## Phase A decision

**Architecture: GO. Physical migration: HOLD.**

The purpose of Mission 9 is to stop treating GeekMagic's 4m3m geometry as a
permanent SHINO constraint while keeping the first implementation phase
completely offline and reversible at the source/review level.
