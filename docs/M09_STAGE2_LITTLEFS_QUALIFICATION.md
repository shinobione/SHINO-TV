# Mission 9 Phase F - Stage-2 LittleFS qualification (OFFLINE ONLY)

5 October 2026. Existing branch `feature/shino-tv-m9-flash-layout-liberation`,
starting clean HEAD `4fde7ba1c948e065accb5ac5540bb848abacf12a`, existing
[Draft PR #42](https://github.com/shinobione/SHINO-TV/pull/42), open/unmerged.
The active roadmap records the owner decision before implementation.

**OFFLINE DESIGN / PACKAGE QUALIFICATION ONLY. Stage-2 physical write HOLD;
Stage-2 runtime NOT_RUN. STOP after Phase F.** No serial discovery/access,
device network request, chip qualification, flash read/write/erase, RTC access,
reset/reboot, upload or SmallTV contact occurred. PC build-source writes are
local preparation, not device filesystem writes. All five Phase F device
operation counters are **0**. No firmware source/policy/installed app change,
no local Stage-1 rebuild, no normal-profile activation or merge.

## Accepted baseline and evidence classes

[Phase E](M09_STAGE1_PHYSICAL_EVIDENCE.md) is owner-provided physical evidence:
all six Stage-1 physical gates PASS. Installed FS-less FIRST_BOOT_BRIDGE is
**399168 B**, SHA-256
`cd99139121fa47fedd6286a185fb16e8fb9e120280ecd75f1c6b41b905e31011`.
Payload `0x000000..0x06173F`, touched sectors `0x000000..0x061FFF`.
UI is PROGRAM_FLASH_ONLY; metrics are RAM_ONLY. The retained local Stage-1
file was rehashed unchanged in Phase F; it was neither rebuilt nor replaced.

Known header is **RST - GPIO0 - 3V3/VCC - RX - TX - GND**. Existing reversible
micro-hooks, no solder, no new PCB access/photos. RST/GPIO0/RX/TX/GND access and
same-unit ROM/full 4 MiB reads are established. EN/CH_PD is not exposed/assumed.
Phase E established RTC retention across the exposed RST pad and successful
powered zero/zero -> GPIO0 release -> RST -> `(3,7)` / `~ld`, no observed `cp:`.
Historical EBOOT_COLD_START_GATE remains HOLD. None of this authorizes a new
operation. Phase F source/model/PC package evidence is not physical Stage 2.

| Gate | Phase F result | Evidence limit |
| --- | --- | --- |
| PHASE F STAGE-2 OFFLINE QUALIFICATION | PASS | pinned source, exact retained PC image, synthetic tests; CI separately in PR |
| STAGE2_EXECUTOR_MODEL_GATE | PASS | source/model only, direct raw UART selected |
| STAGE2_RAW_WRITE_BOUNDS_GATE | PASS | exact source and deterministic range model, no physical write |
| STAGE2_IMAGE_FREEZE_GATE | PASS | exact retained local image only; not a universal rebuild hash |
| STAGE2_READBACK_MODEL_GATE | PASS | synthetic PRE/POST, not fresh device captures |
| STAGE2 PHYSICAL WRITE | HOLD | no authorization or operation |
| STAGE2 RUNTIME | NOT_RUN | installed app remains FS-less |

## Geometry and intended destruction

Verified against explicit `env:esp12e_m9_4m2m`, espressif8266 **4.2.1**, Core
**3.1.2** (`platformio/framework-arduinoespressif8266@3.30102.0`), and pinned
`eagle.flash.4m2m.ld`. The verifier rejects default/inherited 4m3m and altered
platform/Core inheritance. Default `esp12e` remains 4m3m; opt-in alone is 4m2m.

| Region | Inclusive range | End exclusive | Bytes | Stage-2 requirement |
| --- | --- | --- | ---: | --- |
| Lower app + future OTA arena | `0x000000..0x1FFFFF` | `0x200000` | 2097152 | POST equals fresh PRE |
| New SHINO LittleFS | `0x200000..0x3F9FFF` | `0x3FA000` | 2072576 / `0x1FA000` | POST equals frozen image |
| Reserved/system tail | `0x3FA000..0x3FFFFF` | `0x400000` | 24576 / `0x6000` | POST equals fresh PRE |

The LittleFS image is **506** erase sectors of 4096 B, **253** LittleFS blocks
of **8192 B**, pages **256 B**. Core LD `_FS_start=0x40400000` and
`_FS_end=0x405FA000` map to these physical offsets; `_FS_block=0x2000`,
`_FS_page=0x100`. Do not confuse physical erase sectors with LittleFS blocks.

Stage 2 intentionally destroys the historical OEM filesystem **suffix** in
`0x200000..0x3F9FFF`. No PRE/POST equality is required inside that region.
Old bytes `0x100000..0x1FFFFF` remain protected during Stage 2; future OTA reuse
is a separate operation. No physical preservation has been demonstrated in F.

## Executor comparison and pinned raw write semantics

Historical [FS provisioning research](VERIFIED_FS_PROVISIONING.md) and
`verify_fs_provisioning.py`/tests remain useful historical bounds checks; their
old default-environment instructions are not this package workflow. They
checked image shape, not independently parsed exact LittleFS file payloads.
No old per-run FS hash is the new retained package hash.

| Option | Exact pinned source behavior | Phase F selection |
| --- | --- | --- |
| Non-atomic U_FS / HTTP | Updater writes active FS immediately; final MD5 validation occurs after sector erase/write | Reject for this Stage-2 packet |
| ATOMIC_FS_UPDATE full-size U_FS | `FS_START - FS_BYTES = 0x006000`, overlapping installed application sectors through `0x061FFF` | Reject; no isolated full-size staging arena |
| Direct UART raw image | Known nonzero target, no HTTP/app dependency, ROM recovery and full independent PRE/POST before boot | Accepted offline model; physical HOLD |
| Another full-size atomic staging slot | None demonstrated in this 4m2m flash layout; external scratch/custom firmware would be new scope | HOLD / unavailable here |

Pinned Core [Updater.cpp](https://github.com/esp8266/Arduino/blob/210897ef83305496947c4e73c937bab52a33cb48/cores/esp8266/Updater.cpp),
[esptool source](https://github.com/espressif/esptool/tree/5ac7935ee036f64080a4b2f5cda6c9a6188ae93b),
[version-2 flasher stub](https://github.com/espressif/esp-flasher-stub/tree/23959b780454adf885916d42f2274ec648e96a94)
and [stub library](https://github.com/espressif/esp-stub-lib/tree/d61983fa4d1f66b9c088608c1f702ad877121279)
are checked against existing complete `m9_executor_sources.json` pins, plus
three geometry/builder pins in `m9_stage2_sources.json`. Installed package is
official **esptool 5.4.0**, esp-pylib **1.1.5**, pyserial **3.5**, stub **2**.
No esptool or serial module is imported/executed by the new tools: package
identity is read via distribution metadata and all pinned source files hashed.

`write-flash --flash-mode keep --flash-freq keep --flash-size keep --no-compress
0x200000 <FS_IMAGE>` selects one exact file. `_update_image_flash_params`
returns non-boot offsets unchanged; all-keep also bypasses header mutation.
`--no-compress` prevents the stub's default compressed write path. `flash_begin`
uses uncompressed length `0x1FA000` at `0x200000`. Stub erase aligns down/up to
4096 B: exact start **0x200000**, end exclusive **0x3FA000**, last byte
**0x3F9FFF**. Opportunistic aligned 64 KiB erases remain inside those bounds
(maximum model: 31 blocks plus 10 sectors).

127 wire packets of 16384 B are needed; the final one contains 8192 B of image
and wire padding. Pinned `MIN(actual_data_size, total_remaining)` clamps writes
to the original total: padding does not extend into the reserved tail.
Whole-write attempts are internally bounded to **2**, using original address,
image and length; packet attempts default **3**. The source model bounds these
writes/erases, including modeled duplicate deliveries, without proving payload
idempotence, atomicity, ACK correctness, interruption behavior or device success.

Initial flags `--before no-reset --after no-reset-stub --connect-attempts 1`
do not constrain an internal reconnect's default reset. GPIO0 must stay LOW
with continuous main power through PRE, write and POST; a reconnect must not
launch the application before independent POST verification. An uncertain or
interrupted result means STOP, preserve evidence, no manual retry, no normal
boot, no automatic rollback. Source/model PASS alone grants no physical authority.

## Reviewed assets, exact retained image and nondeterminism

`m9_stage2_sources.json` pins **23** public assets by relative name, canonical
LF byte count and SHA-256: 10 HTML pages, 2 CSS files and 11 JavaScript files.
Allowed directories are only `web`, `web/css`, `web/js`. No real `config.json`
is present in the current source. Preparation adds one canonical blank seed:
empty wifi_ssid/wifi_password/api_token and lcd_rotation 0.
Exact schema and value types are required; false is not accepted for integer 0.
Total **24 files / 181402 payload bytes** (181317 assets + 85 blank config).

Audited asset bytes contain no real credential/API-token literals, private
files, symlinks or generic firmware/FS upload handlers. `otaUploadHandler.js`
is absent; update.html is informational. Existing Wi-Fi/token/GIF/reboot/NTP/
rotation/log forms remain reviewed inactive packaged bytes. No route activation
or normal-profile security acceptance is implied. Vendored Pico CSS **83319 B**
and Alpine JS **45764 B** are explicit reviewed inventory entries, not an
unbounded asset exception. Unknown files/directories, altered pinned bytes,
secrets/default changes and any unreviewed file over 200000 B fail closed.

Source preparation creates a NEW PC tree, normalizes CRLF to LF, copies sorted
inventory and fixes file/directory mtime to **1704067200**. It never modifies
`firmware/data`, existing build trees or frozen images. The local builder is
`platformio/tool-mklittlefs@1.203.210628`, version **0.2.3-35-g943d2f7**,
Windows executable SHA-256
`66c71b31576f77b0c857dcc9645a0aa4f059aff0821c56c925ac45bf10531fe5`.
Build arguments were `-c <REVIEWED_LOCAL_TREE> -p 256 -b 8192 -s 2072576
<NEW_LOCAL_IMAGE>`. This accepted file was built once and retained read-only:

- Size: **2072576 B**.
- SHA-256: `d7ce9133b34fb5937d5640db81ff863a8f22a3717255c4b23057aea9ed2ef045`.
- MD5: `1c28417e91dc8359f35a5a403839050b` (compatibility digest; SHA-256 is the gate).
- Source-inventory manifest SHA-256: `71cd397dd1741a4b4289b00ab9da8fb7de0c97aaa8ca73d21eb8203429cdae5d`.
- Retained locally under ignored `research-local/m9-phase-f/`; freeze receipt
  binds file, digests, geometry, builder and source manifest. Binary not published.

Independent **littlefs-python==0.15.0** parsing mounted the memory snapshot
with `mount=False` followed by explicit mount, autoformat disabled, write/erase
callbacks denied. Exact block geometry, directories and all 24 file payloads
matched the reviewed inventory; **parser writes 0**. The parser neither mounts
a device filesystem nor extracts/changes PC files. A future rehash requires an
externally supplied expected SHA; no rebuild is interchangeable with this file.

Nondeterminism was **partly resolved: a cause was isolated, universal byte
reproducibility was not established**. Pinned
[mklittlefs main.cpp](https://github.com/earlephilhower/mklittlefs/blob/943d2f76736eef6630edd4933e42c3016194770b/main.cpp)
stores file/directory stat mtime and root `t`/`c` attributes from `time(NULL)`;
its `readdir` order is also unsorted. Two actual PC builds from the same prepared
tree had identical independently parsed file payloads but different root
attributes (`6419c46a00000000` vs `aa19c46a00000000`) and different binary hashes.
The comparison image SHA was
`da228c5ba5e857f1ea97d8673b97a04331c6342cc90ddc235dcadf1892dac20c`.
It is disposable evidence, not an accepted replacement. Source normalization,
fixed timestamps and sorted copying reduce variation but do not override the
builder's root wall clock or guarantee enumeration order. Use the exact frozen
file later, never substitute a fresh same-source rebuild or a CI binary.

## Fresh PRE/POST and two separate rollback authorities

Future PRE-STAGE2 must be a NEW private **4194304 B** capture of the actual
known-good Stage-1 state in ROM/stub immediately before provisioning, distinct
from factory MASTER and Stage-1 PRE/POST. Stage-1 runtime may have changed the
system tail since Phase E; older captures cannot establish Stage-2 preservation.
Future POST-STAGE2 is another distinct full **4194304 B** capture, still in
ROM/stub and **before any normal application boot**.

`m9_stage2_readback_verify.py` requires three distinct regular local non-link
files, rejects hardlink aliases, checks FS size and external SHA, then requires:

1. `POST[0x200000:0x3FA000] == exact frozen FS image`.
2. `POST[0:0x200000] == PRE[0:0x200000]` (**2097152 B**).
3. `POST[0x3FA000:0x400000] == PRE[0x3FA000:0x400000]` (**24576 B**).

No equality is required in the intentionally replaced FS region. The local
comparison emits no private PRE/POST paths, bytes or digests. It proves only
the supplied files' equality: capture freshness/custody and physical origin
require separately observed evidence. Package qualification is a separate gate.

Rollback authority **I** is PRE-STAGE2, restoring the exact immediately
preceding known-good Stage-1 full chip, including old FS. Authority **J** is
the private factory MASTER, restoring its earlier full-chip custody snapshot.
Neither backup/digest is committed or published. Both full-chip operations at
zero lie outside the Stage-2 FS range and each requires its OWN exact owner
file/hash/operation authorization and independent full readback. OEM
application-only return does not restore overwritten FS assets. No failure
automatically chooses or executes either rollback. RTC/boot after a rollback
requires a separate reviewed authorization for the restored image.

## Future packet - PRINT ONLY, A-J

`python tools/m9_stage2_executor.py --render-commands` only prints this packet.
It contains no executable serial/device subprocess. All physical templates
below are **NOT AUTHORIZED BY PHASE F**; placeholders must remain unexecuted.
Pin the exact Python executable/version/module root with C0 before any separately
approved executor operation. Local current Python is 3.12.10, executable SHA
`4d6f5f81a4bca11191c4c7c6b43632694d0a4ce74e068619d8fdc161d469859a`.
Require C0/C1 again immediately before D. Use distinct new private output names;
never overwrite retained PRE/POST. Stop on any failed gate or uncertain result.

### A0 - ROM entry

```text
# NOT AUTHORIZED BY PHASE F
MANUAL: continuous USB-C power; GPIO0 LOW; existing RST pulse; require ROM (1,7). EN not assumed.
```

### A1 - same-unit ROM/stub chip qualification

```text
# NOT AUTHORIZED BY PHASE F
& "<PYTHON_EXE>" -I -m esptool --chip esp8266 --port "<PORT>" --baud 115200 --stub-version 2 --before no-reset --after no-reset-stub --connect-attempts 1 chip-id
```

### A2 - 4 MiB physical flash qualification

```text
# NOT AUTHORIZED BY PHASE F
& "<PYTHON_EXE>" -I -m esptool --chip esp8266 --port "<PORT>" --baud 115200 --stub-version 2 --before no-reset --after no-reset-stub --connect-attempts 1 flash-id
```

### B - fresh distinct PRE-STAGE2 in ROM/stub

```text
# NOT AUTHORIZED BY PHASE F
& "<PYTHON_EXE>" -I -m esptool --chip esp8266 --port "<PORT>" --baud 115200 --stub-version 2 --before no-reset --after no-reset-stub --connect-attempts 1 read-flash 0x000000 0x400000 "<PRE_STAGE2_4MB>"
```

### C0 - pinned local source/interpreter gate

```text
# LOCAL FILES ONLY
& "<PYTHON_EXE>" tools/m9_stage2_executor.py --core-root "<PINNED_CORE_ROOT>" --platformio-builder "<PINNED_PIO_BUILDER>" --stub-audit-root "<PINNED_STUB_AUDIT_ROOT>" --mklittlefs-source "<PINNED_MKLITTLEFS_SOURCE>" --expected-python-sha256 "<EXPECTED_PYTHON_SHA256>" --expected-python-version "<EXPECTED_PYTHON_VERSION>" --expected-module-root "<ESPTOOL_MODULE_ROOT>"
```

### C1 - immediate exact FS rehash/inventory gate

```text
# LOCAL FILES ONLY
& "<PYTHON_EXE>" tools/m9_stage2_fs_candidate.py --image "<FS_IMAGE>" --expected-sha256 "<EXPECTED_FS_SHA256>"
```

### D - STAGE2 FS WRITE ONLY

```text
# NOT AUTHORIZED BY PHASE F
& "<PYTHON_EXE>" -I -m esptool --chip esp8266 --port "<PORT>" --baud 115200 --stub-version 2 --before no-reset --after no-reset-stub --connect-attempts 1 write-flash --flash-mode keep --flash-freq keep --flash-size keep --no-compress 0x200000 "<FS_IMAGE>"
```

### E - independent full POST-STAGE2 BEFORE normal boot

```text
# NOT AUTHORIZED BY PHASE F
& "<PYTHON_EXE>" -I -m esptool --chip esp8266 --port "<PORT>" --baud 115200 --stub-version 2 --before no-reset --after no-reset-stub --connect-attempts 1 read-flash 0x000000 0x400000 "<POST_STAGE2_4MB>"
```

### F - local FS/lower/tail exact preservation

```text
# LOCAL FILES ONLY
& "<PYTHON_EXE>" tools/m9_stage2_readback_verify.py "<FS_IMAGE>" "<PRE_STAGE2_4MB>" "<POST_STAGE2_4MB>" --expected-sha256 "<EXPECTED_FS_SHA256>"
```

### G1 - RTC neutralization; require exact 0/0 readbacks

```text
# NOT AUTHORIZED BY PHASE F
& "<PYTHON_EXE>" -I -m esptool --chip esp8266 --port "<PORT>" --baud 115200 --stub-version 2 --before no-reset --after no-reset-stub --connect-attempts 1 write-mem 0x60001200 0x00000000 0xFFFFFFFF
```

### G2 - RTC neutralization; require exact 0/0 readbacks

```text
# NOT AUTHORIZED BY PHASE F
& "<PYTHON_EXE>" -I -m esptool --chip esp8266 --port "<PORT>" --baud 115200 --stub-version 2 --before no-reset --after no-reset-stub --connect-attempts 1 write-mem 0x6000127C 0x00000000 0xFFFFFFFF
```

### G3 - RTC neutralization; require exact 0/0 readbacks

```text
# NOT AUTHORIZED BY PHASE F
& "<PYTHON_EXE>" -I -m esptool --chip esp8266 --port "<PORT>" --baud 115200 --stub-version 2 --before no-reset --after no-reset-stub --connect-attempts 1 read-mem 0x60001200
```

### G4 - RTC neutralization; require exact 0/0 readbacks

```text
# NOT AUTHORIZED BY PHASE F
& "<PYTHON_EXE>" -I -m esptool --chip esp8266 --port "<PORT>" --baud 115200 --stub-version 2 --before no-reset --after no-reset-stub --connect-attempts 1 read-mem 0x6000127C
```

### H - still-FS-less Stage-1 normal boot

```text
# NOT AUTHORIZED BY PHASE F
MANUAL: only after all gates PASS and separately approved boot: release GPIO0 while powered, existing RST pulse, continuous power; require (3,7), ~ld, no cp:, Stage-1 LCD/AP/telemetry. No mount/format or normal-profile activation.
```

### I0 - separate exact full-chip rollback preflight

```text
# LOCAL FILES ONLY
& "<PYTHON_EXE>" tools/m9_master_restore_preflight.py "<PRE_STAGE2_ROLLBACK>" --expected-sha256 "<PRIVATE_PRE_STAGE2_SHA256>"
```

### I1 - separately authorized FULL CHIP ROLLBACK, not Stage-2 bounds

```text
# NOT AUTHORIZED BY PHASE F
& "<PYTHON_EXE>" -I -m esptool --chip esp8266 --port "<PORT>" --baud 115200 --stub-version 2 --before no-reset --after no-reset-stub --connect-attempts 1 write-flash --flash-mode keep --flash-freq keep --flash-size keep --no-compress 0x000000 "<PRE_STAGE2_ROLLBACK>"
```

### I2 - rollback full readback before normal boot

```text
# NOT AUTHORIZED BY PHASE F
& "<PYTHON_EXE>" -I -m esptool --chip esp8266 --port "<PORT>" --baud 115200 --stub-version 2 --before no-reset --after no-reset-stub --connect-attempts 1 read-flash 0x000000 0x400000 "<ROLLBACK_READBACK>"
```

### I3 - local rollback exact comparison, private report only

```text
# LOCAL FILES ONLY
& "<PYTHON_EXE>" tools/m9_master_restore_preflight.py "<PRE_STAGE2_ROLLBACK>" --expected-sha256 "<PRIVATE_PRE_STAGE2_SHA256>" --readback "<ROLLBACK_READBACK>"
```

### J0 - separate exact full-chip rollback preflight

```text
# LOCAL FILES ONLY
& "<PYTHON_EXE>" tools/m9_master_restore_preflight.py "<PRIVATE_MASTER>" --expected-sha256 "<PRIVATE_MASTER_SHA256>"
```

### J1 - separately authorized FULL CHIP ROLLBACK, not Stage-2 bounds

```text
# NOT AUTHORIZED BY PHASE F
& "<PYTHON_EXE>" -I -m esptool --chip esp8266 --port "<PORT>" --baud 115200 --stub-version 2 --before no-reset --after no-reset-stub --connect-attempts 1 write-flash --flash-mode keep --flash-freq keep --flash-size keep --no-compress 0x000000 "<PRIVATE_MASTER>"
```

### J2 - rollback full readback before normal boot

```text
# NOT AUTHORIZED BY PHASE F
& "<PYTHON_EXE>" -I -m esptool --chip esp8266 --port "<PORT>" --baud 115200 --stub-version 2 --before no-reset --after no-reset-stub --connect-attempts 1 read-flash 0x000000 0x400000 "<ROLLBACK_READBACK>"
```

### J3 - local rollback exact comparison, private report only

```text
# LOCAL FILES ONLY
& "<PYTHON_EXE>" tools/m9_master_restore_preflight.py "<PRIVATE_MASTER>" --expected-sha256 "<PRIVATE_MASTER_SHA256>" --readback "<ROLLBACK_READBACK>"
```

## Still-FS-less boot and gates before any physical Stage 2

Even a future verified FS write does not activate a normal SHINO runtime.
Installed Stage-1 never mounts/uses the new FS. Preserve SHINO_BOOT_PROFILE=0,
its compile-time normal-profile hold and disabled migration/native OTA writers.
Normal-profile FS use, signed native OTA, Home-LAN and product UI remain
separately reviewed/qualified future work.

Before Stage-2 physical write: exact owner approval of the destructive range
and frozen file/hash; verified private custody/restorability of both rollback
authorities; same-unit ROM/stub/4 MiB qualification; source/interpreter pins;
fresh complete distinct PRE; immediate frozen package rehash/inventory gate;
continuous-power/GPIO0 procedure and interruption STOP; independent full POST
before boot; protected-byte and payload verification; separately approved
RTC zero/zero and powered existing-RST transition. No cold-power/EN substitute.
A model PASS or successful local receipt is never automatic approval.

## Tests, CI and privacy

37 deterministic new tests cover geometry/default rejection, platform pins,
length/hash, every protected boundary, FS payload equality, aliases/hardlinks,
image/source links, UNC/device paths, secret/private/oversized/missing/updater
assets, independent corrupt/wrong-geometry/payload parsing, bounded padded/
duplicate packet models, print-only command ranges, rollback separation,
forbidden imports/executors and retained Stage-1/profile gates. All PRE/POST
fixtures are synthetic and local. Existing M9 + bridge/FS-less/FS provisioning
regressions pass together: **137 tests, 0 failures/errors/skips** locally,
including the 37 new tests. Exact-head CI is recorded separately in PR #42.
Windows without symlink privilege exercises mocked link metadata; Linux CI
creates real links. The existing RTC CI-artifact test now checks the exact
seven JSON allowlist, retaining its private-input prohibition.

The M9 CI job fetches immutable public source pins, audits source/model,
builds an ephemeral FS from reviewed blank assets, independently parses it,
and deletes it. Its binary/hash is NOT the retained local candidate. Only
safe JSON source/package/numeric reports are artifacts; no FS binary, private
MASTER/PRE/POST, local paths to backups, secrets or physical receipt. Existing
application builds remain disposable CI evidence; the retained installed
Stage-1 candidate is not rebuilt or replaced. CI outcomes never close Stage-2
physical or runtime gates. Draft PR #42 remains open/unmerged. STOP after F.
