# SHINO // TV — existing V2 read-only heap snapshot gate

**Status:** tool and offline unit tests only. The owner's installed V2 Hotfix `review-002` and its `FirstBootBridge.cpp` already expose `GET /api/v1/bridge/status` after the existing `SHINO-FirstBoot` Digest login. That JSON currently has `available_heap_bytes = ESP.getFreeHeap()` and `running_application_bytes = ESP.getSketchSize()`. This is ONE instantaneous reading of live free heap, **not** a peak/minimum or a measurement of heap fragmentation, largest allocatable block, TCP queue or watchdog health. We have not connected to the user's device in CI or installed anything.

## Explicit manual read-only measurement

From the checked-out repository, with Windows connected to **the already installed SHINO private AP** (`192.168.4.1`), matching-build private `firmware/private/credentials.txt` present locally, and no passwords in shell history:

    py companion/read_fsless_heap.py

This default invocation is strictly offline and does **not** open a socket or read a credentials file. To trigger ONE status GET and print ONLY the sanitized integer heap/image readings:

    py companion/read_fsless_heap.py --measure --credentials-file firmware/private/credentials.txt --phase idle

For a later separate single reading at another human-observed stage, use `--phase browser_open`, `--phase pc_telemetry`, or `--phase after_load`. These labels are selected by the operator; they **do not automatically launch Chrome, Windows telemetry or any load**. Start/stop the existing companion only by its separately reviewed normal RAM-telemetry workflow. A reasonable low-risk observation sequence is to record an idle sample after AP startup, a sample with one normal browser dashboard open, a sample when existing normal Windows telemetry is already active, and an after-load sample. Avoid automated high-rate status polling: this legacy status endpoint uses Digest, and repeatedly initiating challenges can interact with the currently shared ESP8266WebServer nonce/session behavior. Do not create more simultaneous connection load than the currently working setup has already tolerated without separate hardware approval.

The probe hardcodes the **exact private AP IP** and **only** the legacy status GET path, with `ProxyHandler({})`, no redirects, exact `SHINO-FirstBoot` Digest realm, 4-second request deadline and max **4,096 JSON response bytes**. It requires the read-only bridge identity (`mode FIRST_BOOT_BRIDGE`, `pc_metrics_storage RAM_ONLY`), the shared legacy-and-new **explicit false** flash-installation, diagnostics-write, filesystem-migration, LittleFS-mount and EEPROM-commit status markers, and positive integral free-heap/firmware-size fields. The already-installed `review-002` predates the `native_ota_writer_compiled` response key; the probe accepts that key's absence ONLY when all shared no-write markers are present, and rejects it if the newer status explicitly reports anything other than false; rejects duplicate JSON keys, non-JSON, missing data and impossible typed values. It does not send a Cookie, metrics POST, OTA arm/upload, installer, body or credential in URL/argv. The matching private password is read only from the existing ignored credentials file, never printed. It does not create local reports, change firmware or perform background work. Test cases mock ALL requests, so CI cannot contact the private device.

**Interpreting readings:** compare real phase-labelled snapshots to observe a change; do not label the device safe merely because `free_heap_bytes` is positive or the compile-time RAM image is 49.2%. The current status cannot provide *minimum free heap under load*, heap fragmentation, largest free block or the future two-client parser/socket overhead. The static Xtensa cap (`2*sizeof(NativeOtaSingleIngressShadow) <= 6144`) is **parser-only compile-time storage**, not an allocatable free-heap guarantee. Capture any unexpected 401/403, browser login-prompt regression, stalled telemetry, unstable screen or reboot as a failed/held observation rather than suppressing it.

## Future instrumentation is separately gated

Only in a separately owner-approved candidate and physical-operation plan, type-check/validate supported ESP8266 Core 3.1.2 APIs for fragmentation/largest free block and record baseline, minimum during normal load, after-connection cleanup, and reset reason. Do not expose hardware secrets, client IPs, Wi-Fi passwords or heap addresses in telemetry. Introduce no second listener, upload route, filesystem/EEPROM write, automatic firmware update or reset. Before a candidate hardware install, separately review recovery and backup, owner-specific consent for that **individual** installation, and real Chrome/Windows session regression on the 240x240 V2 display. Nothing in this doc authorizes flash.

**Source locks:** `FirstBootBridge.cpp`, `FslessWebUI.cpp`, the running Windows sender and installed owner firmware are unchanged; PR #20 remains **Draft** and `permission_to_flash=false`.


## Owner-reported first physical observation — 2026-09-27 (READ ONLY)

**Provenance:** four integer outputs copied into the project conversation by the owner from an explicit PowerShell invocation of `companion/read_fsless_heap.py` while Windows was joined to the already installed private AP. These are **owner-reported, instantaneous on-device status readings**, not measurements performed by GitHub Actions or an independent attached probe. No raw JSON, passwords, cookies, private IP identity, device dump or credentials are stored in this repo. The installed V2 Hotfix `review-002` was **not changed or reflashed**. Each response independently reported the same running application size: **400,592 bytes**.

| Human-selected phase | Existing bridge free heap |
| --- | ---: |
| `browser_open` — normal Chrome dashboard visible | **32,016 bytes** |
| `idle` — dashboard tab closed, normal sender stopped, about 30 seconds later | **32,184 bytes** |
| `pc_telemetry` — Chrome dashboard and normal Windows RAM-only metrics active, about 3 minutes | **31,960 bytes** |
| `after_load` — dashboard tab closed, Windows sender stopped, about 30 seconds later | **32,128 bytes** |

Recorded deltas: the **lowest sampled** free heap was 31,960 bytes, which is **224 bytes below** the idle snapshot; after stopping normal load the reported heap increased **168 bytes** from that sampled low, and ended **56 bytes below** the prior idle reading. This is one controlled usage cycle; the measurements are not a high-water/low-water trace and do **not** establish the true minimum during an in-flight TCP/HTTP response, the ESP8266 free heap with two *new* parser objects instantiated, fragmentation, largest contiguous allocation, future nonblocking-server viability or absence of slow leaks. The compiled binary report of 399,152 bytes on PR #20 is **not** the installed binary size: the existing device status reported 400,592 bytes, consistently across all four reads; do not substitute one for the other.

Browser observation explicitly reported by owner: Chrome requested HTTP Digest username/password **once** after the dashboard was reopened; no repeated prompt during the normal telemetry observation was reported. This is a positive but limited real-Chrome session regression observation. No claim is made about browser internals or exhaustive cookie expiry tests. The diagnostic uses existing Digest GET and does not create a write/OTA authority.

**Result of this limited gate:** the original V2 has supplied a reproducible four-phase read-only *baseline and post-load recovery observation*. No large persistent decrease is visible in these four snapshots. Keep the **production server migration, concurrent-device memory budgeting, native OTA registration and firmware installation gates CLOSED** pending separate instrumented-device consent, real minimum-heap/fragmentation and Chrome/Windows/LCD coverage. `permission_to_flash=false`; PR remains Draft.



## Disconnected future minimum / fragmentation observation model — 2026-09-27

Prepared **source-only and compile-only** next instrumentation after the first owner-reported V2 heap cycle. `firmware/include/boot/NativeOtaHeapReview.h` is a bounded, dependency-light pure C++ accumulator of **at most 1,024 successfully validated samples**; each prospective reading carries only three integer fields: current free heap, largest free block and the core fragmentation metric. It tracks first/latest, **lowest free heap observed**, **lowest largest block observed** and **highest fragmentation observed**. It discards missing or inconsistent readings without altering the previous summary. It makes no dynamic allocation, has no network/authentication, does not persist observations, and cannot infer unobserved in-flight peaks. In particular the lowest recorded sample must not be called the device's actual minimum free heap over all scheduler ticks.

In the already DISCONNECTED `NativeOtaDevicePumpCompileProbe.cpp`, `NativeDeviceHeapSource::read` only type-checks the native **32-bit largest-block overload** `ESP.getHeapStats(&freeBytes,&largestBlock,&fragmentation)` with the pinned ESP8266 Arduino Core **3.1.2** Xtensa compiler. The header/source's small C++ type-size cap is separately checked there. Its explicit template instantiation has **no live caller**, and it is absent from `FirstBootBridge.cpp`: no second listener, status field, timer, HTTP endpoint, reboot, binary deployment or flash writer has been added. `tools/native_ota_heap_review_probe.cpp` plus `tools/test_native_ota_heap_review.py` exercise the **actual pure C++ accumulator** on a synthetic finite sensor, checking baseline/after-load regression, invalid samples, exhaustion and sample-cap handling; they never contact the owner's private AP. A successfully compiled API declaration is not evidence of heap behavior at runtime.

Before proposing any separately owner-approved instrumentation build: preserve original status GET/Digest/read-only session, screen's four cards and 2-second PC metrics; choose an independently audited low-frequency cooperative sampling point (not within critical display/TCP sections), time-bound it, expose only aggregate integers via the existing authenticated **status** route, never print network peers/passwords/heap pointers, and audit the actual overhead of JSON/cookie/HTTP responses. A physical test would need explicit approval for the exact build, recovery/rollback and a known-good backup before any installation. The proposed concurrent parser's static two-slot 6 KiB cap **excludes** lwIP buffers/driver/stack/heap fragmentation. Candidate gate remains closed until actual minimum-observed heap, largest block, fragmentation, Chrome nonce behavior, normal Windows telemetry, Wi-Fi stability, LCD redraw and recovery are independently recorded. No numerical pass/fail heap threshold is inferred from four user-supplied snapshots. **PR remains Draft, permission_to_flash=false.**



## Disconnected 1 Hz cooperative sampling cadence — 2026-09-27

Added a **pure, disconnected** `NativeOtaHeapSampleCadence` helper to constrain any future owner-approved runtime instrumentation. It allows at most **one heap observation per 1,000 ms**, uses unsigned elapsed-time arithmetic across `millis()` wrap, and intentionally schedules from the **actual** attempt time. If the main loop is delayed for 10 seconds, the next cooperative call produces **one** sample only; it does not emit ten catch-up samples and therefore cannot create an artificial burst of `ESP.getHeapStats()` calls immediately after a stalled display/network section.

The cadence helper has no timer interrupt, `Ticker`, `delay()`, `yield()`, task, network, device reference, allocation, persistence or status route. It is not included by `FirstBootBridge.cpp`. The pinned Xtensa compile-only probe checks the 1,000 ms constant and an **8-byte maximum type-size envelope** under the actual ESP8266 toolchain, but constructs no runtime object. Host virtual-clock tests cover initial sample, sub-second suppression, normal 1 Hz progression, a 10-second stall with no burst, and `uint32_t` clock wrap.

This cadence is a **maximum observation rate, not a promise that every second is sampled**. Missed cooperative opportunities remain missed. Accordingly, even an eventual owner-approved instrumented build may still fail to observe a shorter in-flight heap trough between samples; any reported value must remain named *lowest observed free heap*, not the true runtime minimum. The sampling helper does not change the current device or authorize an instrumented installation. **PR Draft; permission_to_flash=false.**



## Opt-in instrumented ESP8266 candidate — actual bridge hook (NOT INSTALLED)

A dedicated `firmware/include/boot/ShinoHeapDiagnosticCandidate.h` now combines the pinned Core 3.1.2 `ESP.getHeapStats(&freeBytes,&largestFreeBlockBytes,&fragmentationPercent)` source, the previously audited 1 Hz wrap-safe/no-catchup cadence and the fixed-size observed-heap accumulator. **This is a real, separately selectable compilation profile, not a live firmware installation.**

The real `FirstBootBridge.cpp` has only three `#if SHINO_ENABLE_HEAP_DIAGNOSTICS` guarded additions: one fixed-size observer (no dynamic allocation), projection into the **same** already authenticated `GET /api/v1/bridge/status`, and a cooperative `pollAfterExistingWork(millis())` call **after** `server.handleClient()`, potential normal four-card LCD painting and `FactoryRollback::tick()`, and before the existing watchdog feed/yield. The optional helper never reads the sensor from inside `sendStatus()`, never creates another listener, timer, route, background task or new authentication/cookie behavior. The original four dashboard values, existing `available_heap_bytes` and all original status fields remain intact. In a candidate compiled with the flag, this sample is from an earlier cooperative loop iteration, not from the request handler, so it cannot quantify the transient heap during the status response itself.

Default build `pio run -e esp12e` uses `SHINO_ENABLE_HEAP_DIAGNOSTICS=0` and MUST NOT contain the `OBSERVED_HEAP_V1` firmware marker. The explicitly opt-in build `pio run -e esp12e_heap_diagnostics` inherits the exact same pinned ESP8266 board/core/ArduinoJson/lib/linker and adds only `-DSHINO_ENABLE_HEAP_DIAGNOSTICS=1`. CI compiles **both** variants offline with disposable generated private build policy; it checks that the default image excludes instrumentation, the opt-in candidate image includes marker and original V2 bridge/telemetry markers, both stay below the individually reviewed image-size ceiling, and neither produces a filesystem image. No CI command uploads a binary.

Only on that opt-in candidate, the existing HTTP Digest-protected status JSON would gain a bounded `heap_observation` object, preserving backward compatibility of the original fields:

```json
"heap_observation": {
  "schema": "OBSERVED_HEAP_V1",
  "sampling_interval_ms": 1000,
  "sample_count": 3,
  "max_samples": 1024,
  "state": "SAMPLING",
  "first_free_heap_bytes": 32000,
  "latest_free_heap_bytes": 31900,
  "latest_largest_free_block_bytes": 25000,
  "latest_fragmentation_percent": 17,
  "lowest_observed_free_heap_bytes": 31850,
  "lowest_observed_largest_free_block_bytes": 24000,
  "highest_observed_fragmentation_percent": 18
}
```

**The numbers above are illustrative fixture values, NOT device measurements.** On a candidate before the first valid sample, `state="NO_SAMPLES"` and `sample_count=0`, and measurement fields are **omitted rather than represented as fictitious zeros**. After 1,024 *valid* samples the finite observer reports `state="SATURATED"`, freezes the prior result and performs no more sensor reads; it does not overwrite a previous minimum. The observer remains volatile in RAM and never writes to flash/FS/EEPROM. This is a bounded observation window, not indefinite monitoring, and `sampling_interval_ms=1000` is a maximum cadence rather than guaranteed periodic sampling. A 1-second cooperative sample interval cannot prove the true lowest heap during shorter HTTP/network spikes.

**Approval gates still CLOSED:** Optional firmware was only compiled offline. The owner-installed `review-002` stays unchanged. Before an explicit *per-device/per-binary* owner approval for any physical candidate installation, independently inspect binary identity/checksum, nonwriting policy, backup/recovery route, image geometry, status/nonce and normal Chrome + 2-second sender + 240x240 LCD compatibility. After owner authorization, any real memory values must be separately gathered and reported as actual observed device readings. No production single-owner port-80 replacement, generic OTA writer, merge or flash is authorized by this document.

