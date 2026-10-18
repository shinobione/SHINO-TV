# P0 + Updater512 + B5.4 LAN — public source review

Source-only, sanitized export for [issue #71](https://github.com/shinobione/SHINO-TV/issues/71),
following [PR #70](https://github.com/shinobione/SHINO-TV/pull/70).
This is a new review history based on public `main`, not the private firmware's
original build commit and not an installable release. No private BIN/ELF, release
manifest, receipt, owner identity, network target, weather/OTA key or private history
is included. See [PROVENANCE.md](PROVENANCE.md).

## Inspect the actual code

- `native/src/boot/M9NormalStageA.cpp`: complete single-server application,
  deferred dispatch, Digest, metrics, clock, bounded journal and OTA routes.
- `native/include/ShinoHttpOta.h`: fixed-key HMAC, memory floors, staged SHA/CRC,
  segments and Core commit path. Native Updater code/patch in `native/core/`.
- `native/src/boot/B54LanNative.cpp`, `native/include/B54Lan*.h` and
  `B54LanHttp.inc`: existing SHINO-WX/1 receiver, exact query-free STATUS URI,
  80-byte SAMPLE/STATUS/ACK, replay/time/identity/resource gates.
- `native/http/`: actual materialized ESP8266WebServer headers/parser.
- `native/linker/`: 4m2m linker. `weather_vm/`: existing cache-only publisher and
  protocol, with explicitly synthetic location binding. No VM installer,
  migration, collector, systemd unit or activation configuration is shipped.
- `host/`, `core/`, `seams/`: existing complete HOST laboratory materialization,
  real HTTP/Digest/Core/Updater512/BearSSL paths with radio/SNTP/LCD/heap/flash/RTC
  seams. This includes source adaptations for HOST portability, not a permissive
  replacement router.

## Reproduce the public tests

Requirements: Python 3.11+ standard library, GCC/G++ with C++20 on Linux, or MSVC
x64 on Windows. No pip packages, downloaded dependency, private Git object, device,
VM or firmware artifact is required; necessary public source headers are included.

```sh
python3 -B review/run_tests.py
```

The runner first verifies the closed source inventory, builds only a HOST executable
and native protocol test, then exercises source mutation refusal, production fixture
refusal, native/HOST code correspondence, Updater patch identity, real HTTP/Digest,
journal, LINK TTL, signed clock, SHINO-WX authentication/replay/expiration/framing,
AP/resource/concurrency refusals, publisher OFF/cadence/lost-ACK, OTA HMAC/SHA/CRC,
and Core staging/RTC on RAM seams. Python network access is bounded to numeric
127.0.0.1; the C++ server binds loopback. No serial or firmware build command exists
in this runner. `.build/` outputs remain ignored and CI uploads no artifacts.

`SOURCES.json` hashes the public source inventory only. It is not a private firmware
manifest, an installation authorization or proof of private binary equivalence.
Synthetic identity headers explicitly fail preprocessing on ESP8266 and outside
HOST_MOCK. Original private builders/guards stay local and unchanged; no production
path accepts these review fixtures.

HOST PASS does not qualify physical heap/CONT/WDT, weather LCD, the live VM-to-device
link, OTA or recovery. Current device status remains the owner-reported installed
P0+Updater512; this B5.4 combination is not installed. The existing VM is not contacted,
reconfigured, deployed or activated. Review only; no merge is performed.
