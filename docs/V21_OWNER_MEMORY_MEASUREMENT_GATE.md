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

