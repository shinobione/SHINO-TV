# Mission 9 Phase N â€” true normal 4m2m StageA, OFFLINE only

Authority: [latest owner Phase N comment](https://github.com/shinobione/SHINO-TV/pull/42#issuecomment-6043431763),
7 October 2026. Start exact clean `2bd225ad21e8e0839b7757c7092a227a1fb81de1`,
existing `feature/shino-tv-m9-flash-layout-liberation`, Draft/open/unmerged PR42.
The earlier readiness/design-only HOLD is preserved, not rewritten. This phase
implements the explicitly authorized first normal StageA; media/full scenes,
home-LAN, persistent configuration and native OTA remain later bounded stages.

**OFFLINE SOURCE/LINK/RESOURCE GATES PASS. Candidate freeze pending clean source
checkpoint. All238 offline regressions PASS,0 failures/errors/skips. NORMAL_PROFILE_LITTLEFS_MOUNT_GATE=NOT_RUN;
NORMAL_PROFILE_RUNTIME_GATE=NOT_RUN.** No host/compiler result is physical PASS.

## Exact build and ownership contract

`esp12e_m9_4m2m_normal_qualification` extends the existing4m2m layout, explicitly
uses `eagle.flash.4m2m.ld`, `SHINO_BOOT_PROFILE=1`,
`SHINO_M9_NORMAL_QUALIFICATION=1`, `-fstack-usage`. All other profile1 builds
remain compile-blocked; normal opt-in on another profile/unknown flag fails.
Target guard rejects upload/buildfs/uploadfs/erase/program and embedded/case
variants before the environment-local parser is materialized. `buildprog` is
permitted. FirstBootBridge.cpp is excluded; StageA never calls its run/loop.
Policy assertions forbid home-LAN, factory writer, native signed OTA and FS
migration flags, and require the existing generated private build identity.

The default remains `esp12e` /4m3m. Profile0/2 startup, bridge, observer, telemetry,
resource floors, FS manifest/stream helper, frozen binaries and physical tools
remain unchanged. Narrow shared changes are the explicit profile1 gate,
main's separate guarded StageA branches, the separate mounted ConfigManager API,
and extending the proven FS owner's translation-unit guard to StageA. The FS
adapter/validator body is byte-identical to its predecessor. Historical pins
stay immutable; `m9_phase_n_compat.py` checks exact current pins before removing
only reviewed additions to verify predecessor hashes. Reports explicitly label
this predecessor projection, rather than claiming raw current-file equality.
Current StageA has separate exact source pins and source/link gates.

```text
main.setup first instruction -> StageA.beforeSetup (whole setup observation)
  serial/version prelude -> StageA.begin(ConfigManager)
    DisplayManager.begin(0), normal ST7789 service
    beforeFs -> shared read-only FS owner.begin (exactly one attempt)
      actual4MiB/linker geometry -> install denied-prog/erase adapter
      LittleFSConfig(false) -> exactly one LittleFS.begin
      exact24 files/181402B; hashes/85B blank seed,256B stream/408B BSS workspace
    ConfigManager.loadMountedReadOnly(validated)
      open /config.json read-only ->85B exact seed,32B bounded chunks +EOF
      clear credentials/token/NTP in RAM; rotation0; no begin/migrate/save/storage
    afterFs -> RAM-only setApiToken(existing generated identity)
    WiFi.persistent(false) -> WiFiManager.startAccessPointMode()
      private WPA2 AP only; failure WIFI_OFF, no server/open fallback/STA
    dedicated Webserver routes -> four-card RAM dashboard when config ready
  watchdog enable -> afterSetup (aggregate setup minimum; fresh runtime watermark)
main.loop -> normal Webserver.handleClient -> bounded dirty/stale LCD update
  watchdog feed/yield -> observer.poll, only loop-end sampling, <=1Hz
```

On FS/seed/hash/geometry failure, no consumer starts and telemetry returns503;
private AP/authenticated scalar status remains available when AP succeeds.
The global read-only object stays installed after failure. No end/remount,
format/repair/retry, unrestricted replacement, credential reset or reboot.
The unchanged adapter rejects every non-read open, format/remove/rename/mkdir/
rmdir and physical prog/erase callback, including internal metadata repair.
There is no reachable SecureStorage begin/get/put/remove, EEPROM initialization/
commit, RescueMode boot counter, RTC write, Wi-Fi credential persistence/erase,
legacy API registration, token/config save or OTA writer. Linked symbol gates
prove those normal legacy methods are absent; SDK library internals are not
misrepresented as agent-performed or application-authorized flash operations.

## Dedicated HTTP and display workload

Every registered route requires the existing private Digest credentials;
Basic is rejected. GET `/status`, `/api/v1/m9/normal/status` and
`/api/v1/m9/normal/resources` return the same bounded cached scalar receipt.
GET/POST `/api/v1/bridge/metrics` reuse the actual qualified RAM telemetry
contract for LINK compatibility; the profile itself remains normal StageA.
All other methods/paths, including `/config.json`, encoded/traversal paths,
legacy mutation/config/reboot/GIF routes, media ingress and OTA, are closed.
Static FS reads are disabled entirely. No normal web assets or private path,
MAC, saved SSID, password or token value appear in status.

The stock Core would allocate POST bodies before authentication. StageA therefore
materializes a pinned environment-local Webserver parser, following the reviewed
bounded pre-body approach without HomeLan/media/recovery extensions. It limits
request line256B, header line512B, total headers2048B/32lines and the whole request
to2s; rejects duplicate authority/auth/framing headers, queries, malformed or
oversized lengths, transfer encoding, multipart and encoded forms. Private Digest
and the exact route/type/16..384B telemetry gate run before body reads/allocation.
The original Core Stream/Digest primitives remain pinned. The installed Core is
never modified. Compiler source records for both Webserver.cpp and StageA.cpp
prove the same environment-local header ABI; default/probe builds use stock Core.

Status uses one512B reusable formatting buffer, four prechecked chunks, exact
Content-Length, no-store/nosniff. It reads only cached FS/resource scalars; no
HTTP stack reset, sampling, heap getter, clock read or FS access. Worst-case
scalar/counter serialization and every insufficient capacity are host-tested.
Metrics GET uses a checked768B output buffer; no input-dependent output allocation.

The actual unchanged FslessMetrics validates bounded payloads, preserves the
previous good sample on rejection and uses the6s TTL (fresh through6000ms;
stale at6001ms, including clock wrap). Real four108px cards fit240x240, with no
full framebuffer: CPU/GPU%, used RAM GB with an honest optional denominator,
GPU Celsius only when available. Stale/unavailable values show primitive dashes.
Percentage palettes retain20/50/80 boundaries and2-point hysteresis. Temperature
has a neutral bar because no device-specific thermal normalization is qualified.
This is the StageA workload, not full IDLE/clock/weather/music UX acceptance.

## Resource design and offline evidence

Scalar observer <=96B state /128B total persistent budget. Whole normal setup
starts before serial/LCD/mount. Separate FS/config and runtime windows have fresh
watermarks. Setup's minimum aggregates pre-FS, FS/config and post-FS segments;
intermediate resets cannot erase an earlier setup low-water observation. Four
setup boundary resets only; no runtime/HTTP/timer/ISR reset. Runtime samples at
most once per second, no catch-up burst, unsigned clock wrap, structural heap/
stack validity, monotone minima/maxima, saturating counts, latched invalidity on
rejection. Zero stack is retained as a real failing observation.

Floors remain heap>=20480B, largest block>=16384B, fragmentation<=25%,
continuation>=2048B for setup, FS/config and runtime. `design_floors_observed`
also requires valid measurements and at least one runtime sample; it grants no
physical authority. Static RAM<=49152B retains at least32KiB before dynamic
allocations; `.noinit` must remain56B. Every major individual compiler frame
<=1024B. These are offline budgets, not a proven physical high-water call chain.

Public inert-fixture baseline/current builds pass for default4m3m, profile0/4m2m,
profile2 mount probe and profile2 resource probe. For all four, BIN bytes and
SHA-256 are identical with a fixed common public version. Public StageA passes
source/link/ABI/resource/image checks: BIN399264B, linked395115B, static RAM39736B,
noinit56B, rounded end0x062000<0x100000, FS at0x200000..0x3F9FFF and reserved tail
0x3FA000..0x3FFFFF. Public fixtures are not the private candidate identity.

Major StageA frames: main setup48B/loop0B, StageA begin96B/loop48B, FS begin272B,
ConfigManager mounted read128B, dashboard render176B/card96B, Digest helper32B,
pre-body96B, status32B + serializer608B, telemetry208B, metrics GET880B,
bounded Core parser224B. No frame is classified physical PASS.

Validation includes native flag matrix, executing target guard variants,
actual config short reads/byte mutations/EOF, extracted actual adapter mutation
callbacks, actual scalar observer windows/cadence/wrap/floors/rejections, maximum
status JSON/privacy, actual controller/dashboard/unchanged telemetry with fake
hardware (normal, failed FS, failed AP), historical pins and writer identity.
Real pinned parser/Digest host loopback:29 checks PASS, unauthorized and oversized
requests read zero body bytes. Radio/SDK and LCD remain mocks. Full regression
and candidate/exact-head CI results are recorded after completion below.

## Freeze and final checkpoint

Pending final clean source checkpoint, single private-identity application build
and ignored local freeze. No FS image is built or rewritten. The installed
411152B profile2 successor/evidence remains unchanged. The existing physical
writer still selects only `e1852e56d99801b694f37d235b08a201188cf36d5a25f3f6f59d059a129bc27e`;
normal candidate rejection will be verified locally before any transport exists.

Changed files are the focused firmware gate/main/API/FS guard plus ten new
StageA firmware files, current source/link/host proof tooling, narrow historical
scope/fixture updates, numeric-only CI evidence, this receipt and canonical
handoff/roadmap/current-status pointers. Exact final committed file list follows.

**DEVICE CONTACTS=0; SERIAL I/O=0; FLASH WRITES=0; RTC WRITES=0; REBOOTS=0;
DEVICE FILESYSTEM WRITES=0. STOP after offline qualification. DO NOT FLASH.
DO NOT REBIND THE PHYSICAL WRITER. DO NOT MERGE PR42.**

## Exact Phase N changed files

- `.github/workflows/m9-flash-layout.yml`
- `docs/AGENT_HANDOFF.md`
- `docs/M09_FLASH_LAYOUT_LIBERATION.md`
- `docs/M09_NORMAL_PROFILE_READINESS.md`
- `docs/M09_PHASE_N_STAGE_A.md`
- `docs/ROADMAP.md`
- `firmware/include/boot/M9NormalHttpPolicy.h`
- `firmware/include/boot/M9NormalResources.h`
- `firmware/include/boot/M9NormalStageA.h`
- `firmware/include/boot/M9NormalStatusJson.h`
- `firmware/include/boot/M9StageAConfig.h`
- `firmware/include/boot/ShinoBootProfile.h`
- `firmware/include/config/ConfigManager.h`
- `firmware/platformio.ini`
- `firmware/scripts/m9_normal_qualification_gate.py`
- `firmware/scripts/m9_normal_webserver.py`
- `firmware/scripts/m9_normal_webserver_build.py`
- `firmware/src/boot/M9LittleFsMountProbe.cpp`
- `firmware/src/boot/M9NormalDashboard.cpp`
- `firmware/src/boot/M9NormalStageA.cpp`
- `firmware/src/config/ConfigManager.cpp`
- `firmware/src/main.cpp`
- `tools/m9_mount_probe_resources.py`
- `tools/m9_mount_stack.py`
- `tools/m9_normal_readiness.py`
- `tools/m9_phase_n_compat.py`
- `tools/m9_phase_n_http_lab.cpp`
- `tools/m9_phase_n_http_runner.py`
- `tools/m9_phase_n_qualification.py`
- `tools/m9_phase_n_sources.json`
- `tools/test_m9_mount_probe.py`
- `tools/test_m9_phase_n.py`
- `tools/test_m9_phase_n_routes.py`
- `tools/test_m9_rtc_neutralization.py`
- `tools/test_m9_stage2.py`
