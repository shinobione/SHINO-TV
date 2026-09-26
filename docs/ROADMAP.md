# SHINO // TV — Roadmap

This roadmap deliberately separates **analysis**, **PC-side simulation**, and **hardware writes**.

## Phase 0 — Baseline and safety (current)

- [x] Identify model and reported version via the owner's read-only HTTP endpoints.
- [x] Inventory the manufacturer repository and selected community firmware projects.
- [x] Capture current configuration and observed storage behavior.
- [ ] Catalog V9.0.44-specific routes/requests from a local browser export or firmware image, distinguishing observed behavior from assumptions.
- [ ] Confirm device board revision, flash size, serial pads, and power constraints by photographs/inspection.
- [ ] Document the precise 3.3 V UART adapter and test/readback procedure.
- [ ] Obtain a complete factory flash readback, digest and an offline backup (requires owner hardware access).
- [ ] Review restoration plan and record explicit owner approval before any firmware write.

**Gate 0:** No firmware upload or flash write until baseline, backup and recovery plan have been verified.

## Phase 1 — Static firmware and API research

- Build a manifest of official firmware packages, archive hashes, image headers, layouts, embedded web resources and printable strings.
- Analyze factory image(s) offline, including V9.0.44 only if legitimately acquired from a device readback or matching official package.
- Document each API endpoint with HTTP method, parameters, response, version, side effects and confidence level.
- Assess existing projects for board variant coverage, memory and OTA limitations, licensing and restore routes.
- Do not assume an official OTA package is a full flash backup.

**Exit:** Reproducible research notes and a documented architectural choice.

## Phase 2 — Simulator and Windows companion

- Define a minimal JSON scene protocol with capability negotiation.
- Implement desktop-only telemetry adapters: system metrics, player/track data, development-task status, release countdowns.
- Render representative 240×240 scenes to a local preview; no device flash writes.
- Prefer delta/in-memory updates and rate limits over continuous image uploads.
- Treat cloud credentials as PC-side secrets, never embed them into device firmware.

**Exit:** Working simulated widget pipeline and tests.

## Phase 3 — Firmware prototype

- Choose the approved upstream baseline or a clean implementation after licensing review.
- Build with PlatformIO in CI, assert binary size, memory/flash constraints and board configuration.
- Implement ST7789 initialization and a minimal recoverable HTTP status interface.
- Run any hardware deployment only after Gate 0 has passed and with owner approval.
- Establish rollback path and keep the factory backup private.

**Exit:** A basic screen + local control prototype, with tested recovery.

## Phase 4 — SHINO // TV product features

- Scene/widget engine: clock, device health, PC telemetry, music, coding-agent status and SHINOBIWAN release panel.
- Web configuration with local authentication appropriate to an ESP8266 and an explicitly limited threat model.
- Graceful behavior when Wi-Fi or the PC companion disconnects.
- Safe updates with version checks, partitions and documented recovery.

## Phase 5 — Validation and release

- Soak test for memory leaks, power recovery and disconnect/reconnect.
- Assess update reliability, flash wear, input bounds, and access control.
- Document install/restore, user settings and troubleshooting.
- Release only assets for the verified model and hardware revision.

## Principles

No public exposure of the device HTTP service; no scanning beyond the owner's target without permission. No unreviewed firmware writes. No proprietary manufacturer binaries or personal flash dumps committed to this repository.
