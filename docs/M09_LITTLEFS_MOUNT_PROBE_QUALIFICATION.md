# Mission 9 Phase H — LittleFS mount probe qualification (OFFLINE ONLY)

6 October 2026. Started clean on `feature/shino-tv-m9-flash-layout-liberation`
at `40b2d4c3c758b87150876d4e1878a5682568a347`; existing
[PR #42](https://github.com/shinobione/SHINO-TV/pull/42) Draft/open/unmerged.
The [active roadmap](ROADMAP.md) records the owner decision before implementation.
No SmallTV contact, serial executor, physical read/write/reset, FS image rebuild
or normal-profile activation occurred. The retained Stage-1 and frozen Stage-2
files were rehashed locally and remain unchanged; no private readback was inspected.

**PHASE H LITTLEFS MOUNT PROBE OFFLINE QUALIFICATION: PASS** for source,
deterministic host tests, real ESP8266 application builds, linked geometry/writer
exclusions and bounded resource evidence. Exact-head CI is recorded in PR #42.

| Gate | Phase H result |
| --- | --- |
| Mount-probe source/profile/manifest/Core gate | **PASS — offline** |
| Mount-probe application build/link/image/resource gate | **PASS — offline** |
| MOUNT_PROBE_PHYSICAL_GATE | **HOLD / NOT_RUN** |
| NORMAL_PROFILE_LITTLEFS_MOUNT_GATE | **NOT_RUN physically** |
| NORMAL_PROFILE_RUNTIME_GATE | **NOT_RUN** |

The current owner-reported installed app remains **399168-byte FS-less
FIRST_BOOT_BRIDGE**, PROGRAM_FLASH_ONLY UI / RAM_ONLY metrics. Phase G's
[owner-performed Stage-2 physical gates](M09_STAGE2_PHYSICAL_EVIDENCE.md) remain
PASS: frozen **2072576-byte** LittleFS at `0x200000..0x3F9FFF`, exclusive end
`0x3FA000`, SHA-256
`d7ce9133b34fb5937d5640db81ff863a8f22a3717255c4b23057aea9ed2ef045`.
It has not yet been mounted/used by the current app. P1/M8/full-product
qualification is unchanged; R3 PARTIAL / R10 BLOCKED, 6-second telemetry TTL
and 8-second native-media deadline remain unchanged. No native OTA activation.

## Why the held normal path is unsuitable

`main.cpp`'s held normal branch disables autoformat and calls `LittleFS.begin()`,
then initializes SecureStorage and calls `ConfigManager::load()`. That load
calls `LittleFS.begin()` again, can migrate Wi-Fi/API credentials using
`secure.put()`, and can call `ConfigManager::save()`. Save independently mounts
again and opens `/config.json` with **"w"**. Thus simply removing the current
hold could mutate both LittleFS and EEPROM-backed SecureStorage.

Phase H bypasses ConfigManager entirely, including its global instance in
profile 2. It does not initialize SecureStorage, EEPROM, credential migration,
Wi-Fi STA or OTA/FS writers. A narrowly guarded display rotation fallback uses
zero in profile 2 so the display does not retain a ConfigManager dependency.
Normal code is not refactored or activated. Before eventual full normal-profile
activation, centralize mount ownership, remove independent ConfigManager mounts,
separate read-only loading from mutation/migration, and gate migration writes
explicitly. These remain future design work, not Phase H implementation.

## Compile-time profiles and environment

| Profile | Meaning | Build authority |
| ---: | --- | --- |
| 0 | Existing FIRST_BOOT_BRIDGE | Existing default; original setup/loop bodies unchanged |
| 1 | Future full normal profile | Compile-time error; still HOLD/non-deployable |
| 2 | Mission-9 read-only mount probe | Explicit opt-in only |
| Other | Unknown profile | Compile-time error |

New `env:esp12e_m9_4m2m_mount_probe` extends reviewed `env:esp12e_m9_4m2m`,
uses **eagle.flash.4m2m.ld / littlefs**, and defines **SHINO_BOOT_PROFILE=2 /
SHINO_M9_MOUNT_PROBE=1**. Platform **espressif8266@4.2.1**, Core package
**3.30102.0 / Arduino 3.1.2**, toolchain **10.3.0**; local and CI orchestrator
**PlatformIO 6.1.18**. Default remains `esp12e` / 4m3m / profile 0. Generated
private policy retains profile 0 by default, allowing a reviewed explicit
override only under the shared fail-closed profile guard.

The probe environment's pre-build gate rejects **upload, uploadfs, buildfs,
erase, program and upload-prefixed targets**, before target execution. It builds
only the application; no FS deployment artifact is produced or frozen FS
substituted. Existing historical CI still builds independent disposable FS
images in its separate Phase A/F checks, never as a probe deployment package.

## Mount and write exclusion contract

Startup first reuses protected first-boot AP/LCD infrastructure, then runs the
dedicated probe. It verifies actual linked physical **0x200000 / 2072576 B**,
**8192-byte blocks / 256-byte pages** and actual 4 MiB flash size before mounting.

Only profile 2 replaces the global LittleFS implementation with a bounded
read-only adapter. It rejects write-capable opens and overrides format, remove,
rename, mkdir and rmdir with failure. Its **prog/erase callbacks always return
LFS_ERR_IO** and increment `blocked_write_attempts`; they never call physical
flash programming/erase. This also blocks an unexpected internal metadata write.
The sync callback remains the pinned Core's no-op. Seven exact normalized Core
source hashes pin this adapter's dependency in `tools/m9_mount_probe_sources.json`.
The [pinned Core implementation](https://github.com/esp8266/Arduino/blob/210897ef83305496947c4e73c937bab52a33cb48/libraries/LittleFS/src/LittleFS.h)
is reviewed with the local source gate.

**LittleFS.setConfig(LittleFSConfig(false)) must succeed before the single
LittleFS.begin() call.** Failure stops probe startup visibly; the attempt guard
prevents retries. Mount failure remains failure: no format-on-failure, repair,
file/directory creation, credential normalization, intentional reboot or loop.
Failure is logged and displayed; existing AP/authenticated status/telemetry
remain available if AP initialization succeeded. A later telemetry redraw can
replace the LCD error overlay; the serial failure and status remain authoritative.

Generic LittleFS virtual methods are still linked by the original global Core
object; this is not a claim that every generic writer symbol vanished. The
probe's replacement dispatch and physical callbacks deny those operations.
**write_paths_compiled=false** describes the active application writer policy;
`blocked_write_attempts` separately records attempted denied mutations. The
linked-image gate excludes ConfigManager, SecureStorage, EEPROM begin/commit,
HomeLan and callable OTA/factory-upload writer symbols. SDK/system-tail
housekeeping is distinct from this no-LittleFS-write contract.

## Inventory and payload verification

`M9ProbeManifest.h` is deterministically generated from the already-reviewed
public **tools/m9_stage2_sources.json**. Its pins live in PROGMEM, not an
181 KB RAM copy. Exactly **24 files / 181402 payload bytes** are checked, including
`/config.json`, `/web/index.html`, `/web/header.html`, `/web/footer.html`,
`/web/css/style.css` and `/web/js/main.js`, and all remaining reviewed assets.

Bounded enumeration covers `/`, `/web`, `/web/css`, `/web/js`; it rejects unknown
entries, duplicate files/directories, unsupported entry kinds, excess entries
and missing expected files/directories. A fixed 24-bit file inventory mask and
three-directory mask keep memory bounded. Each expected path must exist, open
as **"r"**, be a regular file and have the exact expected length. The same
host-tested streaming algorithm rejects read failures, zero reads, overreported
reads, premature EOF, extra bytes and digest mismatch. Real target SHA-256 uses
pinned native BearSSL, with a **256-byte** read buffer and context bounded to
**128 bytes**. Yield/heap observations occur between chunks.

The **85-byte canonical blank config seed** is compared byte-for-byte while
streaming and SHA-256 checked. It has `wifi_ssid=""`, `wifi_password=""`,
`api_token=""`, `lcd_rotation=0`; alternate/mutated bytes fail. It is neither
written nor normalized. Expected byte-exact seed proves the required values
without an allocating JSON parser. **Per-file payload hashes do not verify the
full raw LittleFS image SHA-256**, which includes metadata/free-space layout.

## Observation surfaces and resource limits

Serial remains **115200 baud**, with concise non-secret PASS/FAIL output.
**GET /api/v1/m9/fs-probe/status** uses the existing private WPA2 AP and explicit
HTTP authentication/Digest challenge; browser cookies alone cannot authorize it.
Only bounded scalar status is returned: attempted, autoformat_disabled, mounted,
inventory_checked/exact, checked_file_count/payload_bytes, config_seed_exact,
write_paths_compiled, blocked_write_attempts, heap after mount/inventory, sampled
minimum heap and actual FS start/end/bytes. Unreached heap phases retain zero
as a not-sampled sentinel, not a physical zero-heap observation.

No arbitrary FS serving, `/config.json`, legacy web UI routes, STA, NTP,
SecureStorage or writer route is enabled. Existing program-flash UI and four
RAM telemetry cards remain reused. Shared bridge status has profile-2-specific
mode/mount/geometry fields so it does not falsely claim an FS-less probe.

Status is fixed/bounded (compile-time **<=52 B**), JSON buffer **768 B** and
read-only adapter allocation **<=512 B**. Existing server response handling
still creates a bounded String copy; this is not a zero-allocation HTTP claim.
Mount caches and one file/directory's Core objects use heap; there is no full
payload accumulation or persistent file report list.

GCC 10.3 stack reports: payload checker **576 B**, probe begin **272 B**, JSON
formatter **80 B**, authenticated status handler **800 B**. These are individual
static frames, not total call-chain/interrupt stack use or physical high-water.
Existing server, snprintf, display and filesystem callees add stack. The source
gate caps probe frames at 768 B and persistent static growth at Stage-1 +1024 B.
Physical heap/block/stack and all runtime gates remain NOT_RUN. Phase E's
**33072-byte** free-heap snapshot is historical, not guaranteed probe headroom.
Minimum-observed heap means cooperative samples, not an exhaustive transient
allocation minimum, including during HTTP response copies.

## Exact retained LOCAL application candidate

Built from clean source **5f3db19e29398ef6498b08b02de29cae48f9b59a**. Subsequent
qualification/packet documentation does not change firmware source. Candidate
and default baseline use the retained private foundation policy identity; no
credentials are printed, regenerated or published. No P1/M8 qualification is
implied. Candidate BIN/ELF and receipts remain under ignored research-local only.

| Item | Exact local value |
| --- | --- |
| Environment / profile | esp12e_m9_4m2m_mount_probe / 2 |
| BIN bytes / SHA-256 | **407440** / `ca92cc2f4a8a67f70bd305875bd37be90d0cdff74bf7b338339856407dceef8b` |
| Linked flash | **403283 / 1044464 B** |
| Static RAM / .noinit | **40652 / 81920 B**, plus **56 B** .noinit |
| Default baseline linked flash / RAM | **395015 B / 40340 B**, plus **56 B** .noinit |
| Probe delta vs paired baseline / historical Stage-1 | **+8268 linked flash B / +312 static RAM B** |
| Future app target / exact payload | **0x000000 / 0x000000..0x06378F** |
| Future destructive sector extent | **0x000000..0x063FFF / 409600 B**, end exclusive **0x064000** |
| Remaining lower arena after rounded extent | **0x064000..0x1FFFFF / 1687552 B** |
| Sector-rounded margin below 0x100000 | **638976 B** |
| Protected FS / reserved tail | **0x200000..0x3F9FFF / 2072576 B**; **0x3FA000..0x3FFFFF / 24576 B** |

BIN inspection passes ESP8266/4 MiB/DIO headers, boot checksums, embedded
Arduino application length/CRC, linker ceiling and erase-sector bounds. ELF
confirms exact FS symbols and absent active credential/OTA/FS migration writers.
The file fits entirely below the 0x100000 application region and the stricter
1044464-byte linker ceiling, without FS overlap. It was **not flashed**.
CI uses a new disposable policy/build and is not the retained LOCAL candidate;
CI BIN/hash differences do not authorize substitution. No binary is published.

## Future physical packet — design / PRINT ONLY

`tools/m9_mount_probe.py` emits **NOT AUTHORIZED BY PHASE H** templates with
`<PINNED_PYTHON>`, `<PORT>`, `<EXACT_PROBE_BIN>` placeholders; no runner, serial
import or device discovery. A future separately authorized operation requires:

1. Same-unit ROM/chip/4 MiB qualification, fresh independent full PRE-PROBE,
   retained rollback authority, exact frozen application/source/interpreter
   pins and fresh exact-operation owner consent, including executor retry policy.
2. Confirm fresh PRE's FS slice is the frozen Stage-2 image; preserve private
   PRE/MASTER custody without publishing dumps/digests/paths.
3. Application-only target zero; pinned esptool **5.4.0 / stub 2**, no compression
   or header rewrite, GPIO0 LOW through PRE/write/full POST. No erase-all, FS
   write, uncertain retry, automatic rollback or unreviewed cold-power transition.
4. Full POST before first boot: application payload equals exact candidate;
   POST **0x064000..0x1FFFFF** equals PRE; POST **0x200000..0x3F9FFF** equals PRE
   and frozen FS; POST **0x3FA000..0x3FFFFF** equals PRE. Rounded final-sector
   slack inside the app extent is not a protected range. The existing local
   application verifier enforces the stronger continuous **0x064000..0x3FFFFF**
   protected equality. Real outputs/digests stay private.
5. Physically verify RTC words 0/0 while continuously powered; then GPIO0 release
   and existing RST. No Stage-3/full-normal activation is implied.
6. Future normal flash boot, one attempted mount, autoformat disabled, mount/
   inventory/config PASS, zero denied write indicators, authenticated status,
   actual heap after mount/inventory and minimum samples; capture block/stack
   margins before a bounded **180-second** observation and telemetry stale/recovery.
   Stop on reset, unsafe heap/stack, corruption or unavailable recovery. Any
   failure remains failure with no format/repair or automatic retry/rollback.

No one of these future physical gates is claimed PASS in Phase H. A successful
future dedicated probe would still not qualify full normal-profile mutation,
Home-LAN, native OTA or the complete product.

## Local validation, CI and privacy

**152 local tests PASS, no failures/errors/skips**: 12 Phase H tests (including
actual MSVC-compiled stream/profile cases, fault/mutation fixtures, target-gate
execution and synthetic protected arena/FS/tail failures), plus 140 existing
Mission 9 / first-boot / policy / factory regressions. Windows sandbox initially
blocked two hard-link fixtures; the same unmodified regressions passed with
permitted access. No test was weakened. Python/YAML, source/manifest, seven Core
pins, linked geometry/exclusions, BIN CRC/ranges and resource checks PASS.
Ordinary default and opt-in probe application builds PASS; no local buildfs.

Existing exact-head workflows remain offline. Mission 9 CI runs the focused
tests, original Stage-1/Stage-2 regressions and baseline/4m2m/probe builds; its
safe artifact allowlist gains one bounded JSON report (eight reports total),
never BIN/ELF/policy/private backup. The original real-symlink FS-verifier suite
continues in Linux CI. Final exact commit/CI links are recorded in PR #42.

No private PRE/POST/MASTER binary/digest/path, credentials, Wi-Fi/Digest password,
MAC, screenshots, identifying serial transcript, policy header or binary
artifact is committed/uploaded. Only public candidate/FS digests and source,
numeric geometry/resource/test evidence are published.

```text
PHASE H DEVICE CONTACTS = 0
PHASE H SERIAL I/O = 0
PHASE H FLASH WRITES = 0
PHASE H RTC WRITES = 0
PHASE H REBOOTS = 0
PHASE H DEVICE FILESYSTEM WRITES = 0
```

**STOP after Phase H. DO NOT FLASH THE MOUNT PROBE. DO NOT ACTIVATE FULL
NORMAL PROFILE. DO NOT MERGE PR #42.** Historical Phase G/F evidence is preserved.
