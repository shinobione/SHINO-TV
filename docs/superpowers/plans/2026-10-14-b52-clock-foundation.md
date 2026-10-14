# B5.2 Clock Foundation Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add a bounded authenticated PC clock to native B5.1 IDLE without changing the installed image or telemetry contract.

**Architecture:** Reuse the B5.1 generated Normal/LAN graph and the pure PR40 scene renderer. Add fixed clock state, two Digest-protected clock routes using existing scratch, and a disabled-by-default PC provider. Use the retained B5.1 public ELF and one new inert B5.2 build for resources.

**Tech Stack:** ESP8266 Core 3.1.2, ArduinoJson 7.4.3, GFX 1.6.4, C++17 native policy, Python standard-library provider.

**Spec:** `docs/B52_CLOCK_FOUNDATION.md` and the owner's B5.2 mandate recorded in the active roadmap.

## Global Constraints

- Frozen base 244334edac07701dc25b5ffc494715152ae1bfa5; isolated local branch only; no push.
- No device contact, secret read, private build, firmware install, RTC/flash/Wi-Fi write or merge.
- 240x240; all four metrics in IDLE; metrics TTL 6000 ms; no invented clock/weather.
- Fixed 16-byte clock body; 2-second total deadline; lease 1..120 seconds; existing Digest/LAN gates.
- Keep 4m2m, LittleFS and memory floors; no old Mission 8 graph.

## Review Focus

- Malformed or future/expired clock input must not renew a previous good lease.
- Millis rollover and subsequent rollover must not revive an expired clock.
- Offset changes must expire the old civil-time lease before DST.
- Frequent clock reads/draws must not postpone expiration or hide stale metrics.
- New routes must stay behind Digest/LAN admission and reuse bounded scratch.

### Task 1: Clock policy and IDLE renderer

**Files:** `firmware/include/display/ClockFoundation.h`, `firmware/include/display/SceneEngine.h`, `tools/shino_b52_clock_lab.cpp`, `tools/shino_b52_clock_runner.py`.

**Interfaces:** Fixed `ClockFoundation::State::synchronize(utc, offset, lease, started, now)`, `snapshot(now)`, `view(now)`; `ArtworkPilot::ClockData` gains explicit paired-PC source/offset/age metadata.

- [x] Write and run failing C++ policy/render cases (unsynced, invalid, expiration, midnight/date/leap year, rollover, disconnect/reconnect, all metric cards and bars).
- [x] Implement bounded state/calendar and source/age rendering; run targeted HOST cases, measure allocation count and LCD bounds.

### Task 2: Native clock routes and PC source

**Files:** `experiments/b52_clock/native/B52Clock.h`, `B52Clock.cpp`, `B52ClockHttp.inc`; `companion/clock_sync.py`, `companion/test_clock_sync.py`; `tools/shino_b52_clock_build.py`, `tools/test_shino_b52_clock_build.py`, `tools/shino_b52_clock_network.py`.

**Interfaces:** Native `B52Clock::synchronize`, `snapshot`, `refreshMetrics`, `step`; producer `capture_pc_clock` and `publish_clock(..., authorize_clock_sync=False)`; generator modifies only a new public B5.2 output graph.

- [x] Write and run failing producer/schema/generated-graph tests.
- [x] Implement routes, generator and explicitly disabled provider; test actual parser/Digest dispatch on HOST loopback only, including malformed framing and interrupted bodies.
- [x] Verify no existing routes, telemetry TTL/parser limits or normal updater sources change.

### Task 3: Public link, resources and review

**Files:** `docs/B52_CLOCK_FOUNDATION.md`, `docs/b52-clock/*`, active `docs/ROADMAP.md` and `docs/AGENT_HANDOFF.md`; generated build/logs remain ignored.

- [x] Build only a fresh public inert B5.2 graph, using already installed pinned dependencies and no private inputs.
- [x] Compare retained public B5.1 ELF/BIN and new B5.2 sections, symbols, compiler frames and resolved OTA paths. Keep physical heap/block/fragmentation/stack unknown.
- [x] Save and inspect actual renderer captures at 240x240; record commands, results, source hashes and limits.
- [x] Review the final diff, frozen branch and preserved artifact hashes; leave local changes reviewable and do not push.

Owner already supplied the scope and delegated provider choice/implementation;
execution proceeds inline to the requested reviewable offline result. Local
design documentation implements that mandate; further installation and push
remain outside this authorization. No additional approval gate is inferred.
